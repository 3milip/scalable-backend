const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const TOKEN_KEY = "judge_token";
const USER_KEY = "judge_user";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): string | null {
  return localStorage.getItem(USER_KEY);
}

export function setSession(token: string, username: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, username);
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const token = getToken();
  if (token) headers.set("Authorization", "Bearer " + token);
  const response = await fetch(API + path, { ...init, headers });
  if (response.status === 401) {
    clearSession();
    throw new Error("unauthorized");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = (data as { detail?: string }).detail;
    throw new Error(detail || "Błąd " + response.status);
  }
  return data as T;
}

export type Problem = {
  id: number;
  title: string;
  difficulty: number | null;
  tags: string[];
  source: string;
  statement?: string;
  time_limit_ms?: number;
  memory_limit_mb?: number;
  solution?: string;
};

export type Submission = {
  id: number;
  problem_id: number;
  problem_title?: string;
  language: string;
  status: string;
  verdict: string | null;
  time_ms: number | null;
  memory_kb: number | null;
  message: string | null;
  code: string;
  score: number | null;
  max_score: number;
  tests?: Array<{
    test_id: number;
    position: number;
    group: string;
    hidden: boolean;
    verdict: string;
    score: number;
    max_score: number;
    time_ms: number | null;
    memory_kb: number | null;
    message: string | null;
    input: string | null;
    output: string | null;
  }>;
};
