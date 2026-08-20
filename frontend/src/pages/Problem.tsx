import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type Problem as ProblemInfo } from "../api";

const STUB = `#include <iostream>
using namespace std;

int main() {
    return 0;
}
`;

export default function Problem() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [problem, setProblem] = useState<ProblemInfo | null>(null);
  const [status, setStatus] = useState("Ładowanie…");
  const [showSolution, setShowSolution] = useState(false);
  const [code, setCode] = useState(STUB);
  const [submitStatus, setSubmitStatus] = useState("");

  useEffect(() => {
    if (!id) return;
    api<ProblemInfo>("/problems/" + id)
      .then((data) => {
        setProblem(data);
        setStatus("");
      })
      .catch((error: Error) => setStatus(error.message));
  }, [id]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitStatus("Wysyłam…");
    try {
      const created = await api<{ id: number; status: string }>("/submissions", {
        method: "POST",
        body: JSON.stringify({ problem_id: Number(id), language: "cpp", code }),
      });
      navigate("/submissions/" + created.id);
    } catch (error) {
      setSubmitStatus(error instanceof Error ? error.message : "Błąd");
    }
  }

  if (!problem) return <p>{status}</p>;

  return (
    <>
      <p>
        <Link to="/problems">← lista</Link>
      </p>
      <h2>{problem.title}</h2>
      <p>
        trudność {problem.difficulty ?? "–"} · {problem.time_limit_ms} ms · {problem.memory_limit_mb} MB
      </p>
      <p style={{ whiteSpace: "pre-wrap" }}>{problem.statement}</p>
      <p>
        <button type="button" onClick={() => setShowSolution((v) => !v)}>
          {showSolution ? "Ukryj rozwiązanie" : "Pokaż rozwiązanie"}
        </button>
      </p>
      {showSolution ? <pre>{problem.solution}</pre> : null}
      <h3>Wyślij kod (C++)</h3>
      <form onSubmit={onSubmit}>
        <p>
          <textarea rows={14} cols={70} value={code} onChange={(event) => setCode(event.target.value)} required />
        </p>
        <p>
          <button type="submit">Wyślij</button>
        </p>
      </form>
      <p>{submitStatus}</p>
    </>
  );
}
