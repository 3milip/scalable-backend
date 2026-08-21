#!/usr/bin/env bash
# iso.sh - izolowany program w Dockerze + lokalna kolejka slotow
# Docker Desktop + WSL 2 / Linux
#
# Ulepszenia:
#   1. --init (sprzatanie procesow zombie)
#   2. nodev na tmpfs
#   3. whitelist obrazow (ISOLATE_ALLOWED_IMAGES)
#   4. szersza lista zabronionych mountow
#   5. prefiks dozwolonych mountow (ISOLATE_SAFE_MOUNT_PREFIXES)
#   6. logowanie exit 124 / 137 / 139 / 100
#   7. chmod 700 na SLOT_DIR
#   8. auto-parallel = min(N_cpu, N_ram)
#   9. tmpfs /box z exec (binarka C++); /tmp zostaje noexec
#  10. --compile: g++ w tym samym kontenerze, poza limitem -t
# Poprawki po review:
#   - mem_to_bytes w czystym bashu (bez gawk)
#   - walidacja MAX_PARALLEL >= 1 (po auto / po fladze)
#   - --entrypoint "" (PROGRAM_ARGS = prawdziwa komenda)
# Sędzia:
#   - tmpfs /work (WORKDIR istnieje na --read-only)
#   - stdin (-i) — wejście testu trafia do programu
#   - timeout w kontenerze (liczy program, nie docker pull/start)
#   - OOMKilled z docker inspect (pewny MLE)
#   - logi isolate na fd 3 / ISOLATE_LOG, nigdy na stdout
# Hartowanie:
#   - domyslny obraz z Pythonem (ten sam co worker)
#   - whitelist zawsze wlaczona (domyslnie tylko ten obraz)
#   - auto-parallel z `docker info` (VM Dockera, nie WSL) + cap 8
#   - SLOT_DIR per UID
#   - bez --ulimit nproc (limit per-UID na caly host)
#   - [isolate-meta] time_ms / memory_bytes / oom (fd 3, nie stdout)
set -euo pipefail

# --- Domyslne limity ---
IMAGE="${ISOLATE_IMAGE:-python:3.12-slim-bookworm}"
MEMORY="${ISOLATE_MEMORY:-256m}"
CPUS="${ISOLATE_CPUS:-0.5}"
PIDS_LIMIT="${ISOLATE_PIDS:-64}"
TIMEOUT_SEC="${ISOLATE_TIMEOUT:-30}"
WORKDIR_IN_CT="/work"
USER_ID="${ISOLATE_UID:-65534}"
GROUP_ID="${ISOLATE_GID:-65534}"

# --- Kolejka / sloty ---
MAX_PARALLEL="${ISOLATE_MAX_PARALLEL:-0}" # 0 = auto z min(CPU, RAM)
QUEUE_WAIT_SEC="${ISOLATE_QUEUE_WAIT:-120}"
SLOT_DIR="${ISOLATE_SLOT_DIR:-/tmp/isolate-slots-${UID:-$(id -u)}}"

# --- Whitelist obrazow (zawsze wlaczona; pusta env = tylko obraz sedziego) ---
# Przyklad: ISOLATE_ALLOWED_IMAGES="python:3.12-slim-bookworm alpine:3.20"
ALLOWED_IMAGES="${ISOLATE_ALLOWED_IMAGES:-python:3.12-slim-bookworm}"

# --- Prefiksy dozwolonych mountow (pusta = bez ograniczenia prefiksem) ---
# Przyklad: ISOLATE_SAFE_MOUNT_PREFIXES="$HOME/projects/ksi:/tmp/jobs"
# Wiele prefiksow rozdzielaj dwukropkiem.
SAFE_MOUNT_PREFIXES="${ISOLATE_SAFE_MOUNT_PREFIXES:-}"

usage() {
  cat <<'EOF'
Uzycie:
  ./iso.sh [opcje] -- <program> [args...]
  ./iso.sh -- python3 /work/main.py < input.txt
  ./iso.sh --compile 'g++ -O2 -std=c++17 -pipe -o /box/main /work/main.cpp' -- /box/main

Opcje:
  -i, --image IMAGE          Obraz Docker (domyslnie: python:3.12-slim-bookworm)
  -m, --memory SIZE          Limit RAM (domyslnie: 256m)
  -c, --cpus N               Limit CPU (domyslnie: 0.5)
  -t, --timeout SEC          Timeout programu w sekundach (domyslnie: 30; 0 = bez)
  -p, --pids N               Max procesow (domyslnie: 64)
  --mount HOST:CONT          Mount tylko-do-odczytu (mozna wielokrotnie)
  --compile CMD              Komenda kompilacji (jeden argument). Poza limitem -t.
                             Blad kompilacji = exit 100 (nie kod g++).
  --compile-timeout SEC      Limit kompilacji w sekundach (domyslnie: 30)
  --allow-net                Wlacz siec (domyslnie: wylaczona)
  --max-parallel N           Max rownoleglych jobow na hoscie (0 = auto)
  --queue-wait SEC           Ile czekac na wolny slot (domyslnie: 120)
  -h, --help                 Pomoc

Env:
  ISOLATE_IMAGE, ISOLATE_MEMORY, ISOLATE_CPUS, ISOLATE_PIDS,
  ISOLATE_TIMEOUT, ISOLATE_MAX_PARALLEL, ISOLATE_QUEUE_WAIT, ISOLATE_SLOT_DIR,
  ISOLATE_ALLOWED_IMAGES, ISOLATE_SAFE_MOUNT_PREFIXES, ISOLATE_UID, ISOLATE_GID,
  ISOLATE_LOG   plik na logi isolate (domyslnie: stderr / fd 3; nigdy stdout)

Przyklady whitelist / prefiksow:
  export ISOLATE_ALLOWED_IMAGES="python:3.12-slim-bookworm alpine:3.20"
  export ISOLATE_SAFE_MOUNT_PREFIXES="$HOME/projekty/skalowalny-backend:/tmp/jobs"
EOF
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Blad: brak komendy '$1'." >&2
    exit 127
  }
}

die() {
  echo "Blad: $*" >&2
  exit 2
}

# Logi isolate nigdy nie ida na stdout (stdout = wynik programu).
# Domyslnie fd 3 = stderr. Mozna: ISOLATE_LOG=plik  albo  3>isolate.log
setup_log() {
  if [[ -n "${ISOLATE_LOG:-}" ]]; then
    exec 3>>"$ISOLATE_LOG"
  elif ! { true >&3; } 2>/dev/null; then
    exec 3>&2
  fi
}

log() {
  echo "[isolate] $*" >&3
}

# --- Rozmiar pamieci -> bajty (czysty bash, bez gawk) ---
# Akceptuje: 128, 256m, 1g, 512k, 2t (opcjonalnie przyrostek b: 256mb)
mem_to_bytes() {
  local s n u
  s="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  if [[ ! "$s" =~ ^([0-9]+)([kmgt]?)b?$ ]]; then
    return 1
  fi
  n="${BASH_REMATCH[1]}"
  u="${BASH_REMATCH[2]}"
  case "$u" in
    k) n=$((n * 1024)) ;;
    m) n=$((n * 1024 * 1024)) ;;
    g) n=$((n * 1024 * 1024 * 1024)) ;;
    t) n=$((n * 1024 * 1024 * 1024 * 1024)) ;;
  esac
  printf '%s\n' "$n"
}

# Dostepna pamiec hosta w bajtach (Linux / WSL: MemAvailable)
host_mem_available_bytes() {
  if [[ -r /proc/meminfo ]]; then
    local kb
    kb="$(awk '/^MemAvailable:/ { print $2; exit }' /proc/meminfo 2>/dev/null || true)"
    if [[ -n "${kb:-}" && "$kb" =~ ^[0-9]+$ ]]; then
      printf '%s\n' "$((kb * 1024))"
      return 0
    fi
  fi
  # fallback: nie ograniczaj po RAM
  printf '%s\n' "999999999999"
}

# Walidacja liczby calkowitej >= min
require_int_ge() {
  local name="$1" val="$2" min="$3"
  if [[ ! "$val" =~ ^[0-9]+$ ]]; then
    die "$name musi byc nieujemna liczba calkowita (dostalem: $val)"
  fi
  if (( val < min )); then
    die "$name musi byc >= $min (dostalem: $val)"
  fi
}

MOUNTS=()
ALLOW_NET=0
PROGRAM_ARGS=()
COMPILE_CMD=""
COMPILE_TIMEOUT_SEC=30

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    -i|--image) IMAGE="${2:?}"; shift 2 ;;
    -m|--memory) MEMORY="${2:?}"; shift 2 ;;
    -c|--cpus) CPUS="${2:?}"; shift 2 ;;
    -t|--timeout) TIMEOUT_SEC="${2:?}"; shift 2 ;;
    -p|--pids) PIDS_LIMIT="${2:?}"; shift 2 ;;
    --max-parallel) MAX_PARALLEL="${2:?}"; shift 2 ;;
    --queue-wait) QUEUE_WAIT_SEC="${2:?}"; shift 2 ;;
    --mount) MOUNTS+=("${2:?}"); shift 2 ;;
    --compile) COMPILE_CMD="${2:?}"; shift 2 ;;
    --compile-timeout) COMPILE_TIMEOUT_SEC="${2:?}"; shift 2 ;;
    --allow-net) ALLOW_NET=1; shift ;;
    --) shift; PROGRAM_ARGS=("$@"); break ;;
    -*)
      echo "Nieznana opcja: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      PROGRAM_ARGS=("$@")
      break
      ;;
  esac
done

if [[ ${#PROGRAM_ARGS[@]} -eq 0 ]]; then
  echo "Blad: podaj program (po --)." >&2
  usage >&2
  exit 2
fi

require_cmd docker
require_cmd flock
require_cmd awk
require_cmd realpath

setup_log

if ! docker info >/dev/null 2>&1; then
  echo "Blad: Docker nie dziala." >&2
  exit 1
fi

# Wstepna walidacja liczb (MAX_PARALLEL: 0 = auto)
require_int_ge "ISOLATE_MAX_PARALLEL/--max-parallel" "$MAX_PARALLEL" 0
require_int_ge "ISOLATE_QUEUE_WAIT/--queue-wait" "$QUEUE_WAIT_SEC" 0
require_int_ge "ISOLATE_PIDS/-p" "$PIDS_LIMIT" 1
require_int_ge "ISOLATE_TIMEOUT/-t" "$TIMEOUT_SEC" 0
require_int_ge "ISOLATE_COMPILE_TIMEOUT/--compile-timeout" "$COMPILE_TIMEOUT_SEC" 1

if ! mem_to_bytes "$MEMORY" >/dev/null; then
  die "niepoprawny limit pamieci MEMORY/-m: $MEMORY (przyklady: 128m, 256m, 1g)"
fi

# Prosta walidacja CPUS (liczba dodatnia, tez ulamek)
# awk: exit 0 gdy NIEPOPRAWNE (c<=0) -> warunek if true -> die
#      exit 1 gdy OK (c>0) -> warunek if false (przy poprawnym regex)
if [[ ! "$CPUS" =~ ^[0-9]+([.][0-9]+)?$ ]] || awk -v c="$CPUS" 'BEGIN{ exit (c > 0) }'; then
  die "niepoprawny limit CPU CPUS/-c: $CPUS (przyklady: 0.5, 1, 2)"
fi

# --- 3. Whitelist obrazow (zawsze) ---
allowed=0
# shellcheck disable=SC2086
for img in $ALLOWED_IMAGES; do
  if [[ "$IMAGE" == "$img" ]]; then
    allowed=1
    break
  fi
done
if [[ $allowed -eq 0 ]]; then
  echo "Blad: obraz '$IMAGE' nie jest na liscie ISOLATE_ALLOWED_IMAGES." >&2
  echo "       Dozwolone: $ALLOWED_IMAGES" >&2
  exit 2
fi

# --- 8. Auto liczba slotow: min(N_cpu, N_ram) z VM Dockera ---
auto_parallel() {
  local cores avail job_bytes n_cpu n_ram n
  local docker_cpus docker_mem
  docker_cpus="$(docker info --format '{{.NCPU}}' 2>/dev/null || true)"
  docker_mem="$(docker info --format '{{.MemTotal}}' 2>/dev/null || true)"

  if [[ "$docker_cpus" =~ ^[1-9][0-9]*$ ]]; then
    cores="$docker_cpus"
  else
    cores="$(nproc)"
  fi

  n_cpu="$(awk -v c="$cores" -v j="$CPUS" 'BEGIN{
    if (j <= 0) j = 0.5;
    n = int(c / j);
    if (n < 1) n = 1;
    print n;
  }')"

  job_bytes="$(mem_to_bytes "$MEMORY")"

  # Zostaw ~30% RAM Dockera na system / inne procesy
  if [[ "$docker_mem" =~ ^[1-9][0-9]*$ ]]; then
    avail=$(( docker_mem * 70 / 100 ))
  else
    avail="$(host_mem_available_bytes)"
    avail=$(( avail * 70 / 100 ))
  fi

  if (( job_bytes <= 0 )); then
    n_ram=1
  else
    n_ram=$(( avail / job_bytes ))
    if (( n_ram < 1 )); then
      n_ram=1
    fi
  fi

  n="$n_cpu"
  if (( n_ram < n )); then
    n="$n_ram"
  fi
  if (( n < 1 )); then
    n=1
  fi
  if (( n > 8 )); then
    n=8
  fi

  log "auto_parallel: n_cpu=$n_cpu n_ram=$n_ram => max_parallel=$n (mem/job=$MEMORY)"
  printf '%s\n' "$n"
}

if [[ "$MAX_PARALLEL" -eq 0 ]]; then
  MAX_PARALLEL="$(auto_parallel)"
fi

# Po auto / recznej fladze: zawsze >= 1
require_int_ge "max_parallel" "$MAX_PARALLEL" 1

# --- Zajecie slotu (lokalna kolejka) ---
acquire_slot() {
  local i slot
  local deadline=$((SECONDS + QUEUE_WAIT_SEC))
  mkdir -p "$SLOT_DIR"
  # 7. multi-user: katalog slotow tylko dla wlasciciela
  chmod 700 "$SLOT_DIR" 2>/dev/null || true

  while (( SECONDS < deadline )); do
    for ((i = 0; i < MAX_PARALLEL; i++)); do
      slot="$SLOT_DIR/slot-$i.lock"
      exec 9>"$slot"
      if flock -n 9; then
        log "slot=$i max_parallel=$MAX_PARALLEL cpus=$CPUS memory=$MEMORY image=$IMAGE"
        return 0
      fi
      exec 9>&-
    done
    sleep 0.25
  done
  echo "Blad: brak wolnego slotu (max=$MAX_PARALLEL) przez ${QUEUE_WAIT_SEC}s." >&2
  return 75
}

slot_wait_ms=0
slot_t0="$(date +%s%N 2>/dev/null || true)"
acquire_slot || exit $?
# FD 9 trzyma lock do konca procesu - po exit slot sie zwalnia
if [[ "$slot_t0" =~ ^[0-9]+$ ]]; then
  slot_t1="$(date +%s%N 2>/dev/null || true)"
  if [[ "$slot_t1" =~ ^[0-9]+$ ]]; then
    slot_wait_ms=$(( (slot_t1 - slot_t0) / 1000000 ))
  fi
fi

# --- Walidacja mountow (tylko RO) + 4. + 5. ---
MOUNT_FLAGS=()
WORK_TMPFS=(--tmpfs /work:rw,noexec,nosuid,nodev,size=64m)
for m in "${MOUNTS[@]+"${MOUNTS[@]}"}"; do
  if [[ ! "$m" =~ ^[^:]+:[^:]+(:ro)?$ ]]; then
    die "mount HOST:CONT lub HOST:CONT:ro - dostalem: $m"
  fi

  host_path_raw="${m%%:*}"
  rest="${m#*:}"
  cont_path="${rest%%:*}"

  if [[ "$host_path_raw" != /* ]]; then
    die "sciezka hosta musi byc absolutna: $host_path_raw"
  fi

  if ! host_path="$(realpath -- "$host_path_raw" 2>/dev/null)"; then
    die "nie mozna rozwiazac sciezki (lub nie istnieje): $host_path_raw"
  fi

  # 5. Prefiks dozwolonych mountow (gdy ustawiony)
  if [[ -n "$SAFE_MOUNT_PREFIXES" ]]; then
    safe=0
    IFS=':' read -ra prefixes <<< "$SAFE_MOUNT_PREFIXES"
    for prefix in "${prefixes[@]}"; do
      [[ -z "$prefix" ]] && continue
      if prefix_resolved="$(realpath -- "$prefix" 2>/dev/null)"; then
        prefix="$prefix_resolved"
      fi
      if [[ "$host_path" == "$prefix" || "$host_path" == "$prefix"/* ]]; then
        safe=1
        break
      fi
    done
    if [[ $safe -eq 0 ]]; then
      die "mount poza ISOLATE_SAFE_MOUNT_PREFIXES ($SAFE_MOUNT_PREFIXES): $host_path"
    fi
  fi

  # 4. Szersza lista zabronionych sciezek hosta
  case "$host_path" in
    /|/boot|/boot/*|/dev|/dev/*|/etc|/etc/*|/proc|/proc/*|/sys|/sys/*|\
    /usr|/usr/*|/bin|/bin/*|/sbin|/sbin/*|/lib|/lib/*|/lib64|/lib64/*|\
    /root|/root/*|\
    /var/lib/docker|/var/lib/docker/*|\
    /var/run/docker.sock|/var/run/docker.sock/*|\
    /run/docker.sock|/run/docker.sock/*|\
    /var/run/docker.sock.raw|/run/docker.sock.raw|\
    "$HOME"/.ssh|"$HOME"/.ssh/*|\
    "$HOME"/.gnupg|"$HOME"/.gnupg/*|\
    "$HOME"/.aws|"$HOME"/.aws/*|\
    "$HOME"/.docker|"$HOME"/.docker/*|\
    "$HOME"/.kube|"$HOME"/.kube/*|\
    "$HOME"/.config/gcloud|"$HOME"/.config/gcloud/*|\
    "$HOME"/.azure|"$HOME"/.azure/*)
      die "zabroniony mount: $host_path"
      ;;
  esac

  # Cel w kontenerze
  if [[ "$cont_path" != /* ]]; then
    die "sciezka w kontenerze musi byc absolutna: $cont_path"
  fi
  if [[ "$cont_path" == *..* ]]; then
    die "sciezka w kontenerze nie moze zawierac '..': $cont_path"
  fi
  case "$cont_path" in
    /|/etc|/etc/*|/proc|/proc/*|/sys|/sys/*|/dev|/dev/*|/usr|/usr/*|/bin|/bin/*|/sbin|/sbin/*)
      die "zabroniony cel mountu: $cont_path"
      ;;
  esac

  MOUNT_FLAGS+=(--mount "type=bind,src=${host_path},dst=${cont_path},readonly")
  # Kontener leci jako 65534 — 700 na hoście = Permission denied.
  if [[ -d "$host_path" ]]; then
    chmod a+rX "$host_path" 2>/dev/null || true
    find "$host_path" -maxdepth 3 -type d -exec chmod a+rX {} + 2>/dev/null || true
    find "$host_path" -maxdepth 3 -type f -exec chmod a+r {} + 2>/dev/null || true
  elif [[ -f "$host_path" ]]; then
    chmod a+r "$host_path" 2>/dev/null || true
  fi
  # Bind na /work zastępuje tmpfs (inaczej: duplicate mount point).
  if [[ "$cont_path" == /work || "$cont_path" == /work/* ]]; then
    WORK_TMPFS=()
  fi
done

NETWORK_FLAGS=(--network none)
if [[ "$ALLOW_NET" -eq 1 ]]; then
  NETWORK_FLAGS=(--network bridge)
  log "UWAGA: siec wlaczona (--allow-net)."
fi

# Obraz musi byc lokalny zanim ruszy zegar. Pull NIE idzie na stdout.
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  log "pobieram obraz $IMAGE"
  docker pull "$IMAGE" >&3 2>&3
fi

# Wrapper w kontenerze: opcjonalna kompilacja, potem stoper tylko na program.
# ISOLATE_INNER_TIMEOUT — limit programu. ISOLATE_COMPILE — poza tym limitem.
# Blad kompilacji: exit 100 (oddzielone od exit 1 programu).
ISOLATE_WRAPPER='
set +e
if [ -n "${ISOLATE_COMPILE:-}" ]; then
  timeout --kill-after=1s "${ISOLATE_COMPILE_TIMEOUT:-30s}" bash -c "$ISOLATE_COMPILE"
  crc=$?
  if [ "$crc" -ne 0 ]; then
    echo "[isolate-meta] rc=100 time_ms=0 memory_bytes=0 compile=failed" >&2
    exit 100
  fi
fi
start_ns=$(date +%s%N 2>/dev/null || true)
if [ -n "${ISOLATE_INNER_TIMEOUT:-}" ]; then
  timeout --kill-after=1s "$ISOLATE_INNER_TIMEOUT" "$@"
  rc=$?
else
  "$@"
  rc=$?
fi
end_ns=$(date +%s%N 2>/dev/null || true)
time_ms=
if [ -n "$start_ns" ] && [ -n "$end_ns" ]; then
  case "$start_ns$end_ns" in
    *[!0-9]*) ;;
    *) time_ms=$(( (end_ns - start_ns) / 1000000 )) ;;
  esac
fi
peak=
if [ -r /sys/fs/cgroup/memory.peak ]; then
  peak=$(cat /sys/fs/cgroup/memory.peak)
elif [ -r /sys/fs/cgroup/memory.max_usage_in_bytes ]; then
  peak=$(cat /sys/fs/cgroup/memory.max_usage_in_bytes)
elif [ -r /sys/fs/cgroup/memory/memory.max_usage_in_bytes ]; then
  peak=$(cat /sys/fs/cgroup/memory/memory.max_usage_in_bytes)
fi
# Na stderr, nie stdout — docker cp z tmpfs po stopie nie dziala.
echo "[isolate-meta] rc=$rc time_ms=$time_ms memory_bytes=$peak" >&2
exit "$rc"
'

INNER_CMD=(bash -c "$ISOLATE_WRAPPER" -- "${PROGRAM_ARGS[@]}")
ENV_FLAGS=()
TIMEOUT_PREFIX=()
host_limit=0
if [[ "$TIMEOUT_SEC" != "0" ]]; then
  ENV_FLAGS+=(-e "ISOLATE_INNER_TIMEOUT=${TIMEOUT_SEC}s")
  host_limit=$((TIMEOUT_SEC + 10))
fi
if [[ -n "$COMPILE_CMD" ]]; then
  ENV_FLAGS+=(-e "ISOLATE_COMPILE=${COMPILE_CMD}")
  ENV_FLAGS+=(-e "ISOLATE_COMPILE_TIMEOUT=${COMPILE_TIMEOUT_SEC}s")
  if [[ "$host_limit" -eq 0 ]]; then
    host_limit=$((COMPILE_TIMEOUT_SEC + 10))
  else
    host_limit=$((host_limit + COMPILE_TIMEOUT_SEC))
  fi
fi
if [[ "$host_limit" -gt 0 ]]; then
  if command -v timeout >/dev/null 2>&1; then
    TIMEOUT_PREFIX=(timeout --kill-after=5s "${host_limit}s")
  else
    log "UWAGA: brak hostowego 'timeout' - zostaje tylko limit w kontenerze."
  fi
fi

NAME="isolate-$(date +%s)-$$-${RANDOM}"

cleanup() {
  docker rm -f "$NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

# Bez --rm: po wyjsciu inspect OOMKilled, potem trap kasuje kontener.
set +e
"${TIMEOUT_PREFIX[@]}" docker run \
  --name "$NAME" \
  --pull never \
  -i \
  --init \
  --entrypoint "" \
  --read-only \
  "${WORK_TMPFS[@]+"${WORK_TMPFS[@]}"}" \
  --tmpfs /box:rw,exec,nosuid,nodev,size=64m \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=64m \
  --tmpfs /var/tmp:rw,noexec,nosuid,nodev,size=16m \
  --tmpfs /run:rw,noexec,nosuid,nodev,size=8m \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --user "${USER_ID}:${GROUP_ID}" \
  --pids-limit "${PIDS_LIMIT}" \
  --memory "${MEMORY}" \
  --memory-swap "${MEMORY}" \
  --cpus "${CPUS}" \
  --ulimit nofile=256:256 \
  --ulimit core=0 \
  --workdir "${WORKDIR_IN_CT}" \
  --label "isolate=1" \
  "${ENV_FLAGS[@]+"${ENV_FLAGS[@]}"}" \
  "${NETWORK_FLAGS[@]}" \
  "${MOUNT_FLAGS[@]+"${MOUNT_FLAGS[@]}"}" \
  --attach stdin \
  --attach stdout \
  --attach stderr \
  "${IMAGE}" \
  "${INNER_CMD[@]}"
rc=$?

oom="false"
if docker inspect -f '{{.State.OOMKilled}}' "$NAME" >/dev/null 2>&1; then
  oom="$(docker inspect -f '{{.State.OOMKilled}}' "$NAME" 2>/dev/null || echo false)"
fi

# Wrapper juz wypisal time_ms/memory na stderr. Tu tylko oom + kolejka.
echo "[isolate-meta] oom=${oom} slot_wait_ms=${slot_wait_ms}" >&3
set -e

# --- Interpretacja kodow wyjscia ---
if [[ "$oom" == "true" ]]; then
  log "OOMKilled=true - przekroczony limit RAM (${MEMORY})"
  exit 137
fi

if [[ $rc -eq 100 ]]; then
  log "compile failed (exit 100)"
  exit 100
fi

if [[ $rc -eq 124 ]]; then
  log "timeout (${TIMEOUT_SEC}s) - program przekroczyl limit czasu"
  exit 124
fi

if [[ $rc -eq 137 ]]; then
  log "exit 137 (SIGKILL) - nie OOM (zewnetrzny kill / awaryjny timeout)"
  exit 137
fi

if [[ $rc -eq 139 ]]; then
  log "exit 139 (SIGSEGV) - segfault w programie"
  exit 139
fi

exit "$rc"
