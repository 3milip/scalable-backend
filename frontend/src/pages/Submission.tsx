import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, Submission } from "../api";

export default function SubmissionPage() {
  const { id } = useParams();
  const [sub, setSub] = useState<Submission | null>(null);
  const [status, setStatus] = useState("Ładowanie…");

  useEffect(() => {
    if (!id) return;
    let stop = false;
    async function load() {
      try {
        const data = await api<Submission>("/submissions/" + id);
        if (stop) return;
        setSub(data);
        setStatus("Zadanie #" + data.problem_id + " · " + data.language);
      } catch (error) {
        if (!stop) setStatus(error instanceof Error ? error.message : "Błąd");
      }
    }
    load();
    const timer = setInterval(load, 2000);
    return () => {
      stop = true;
      clearInterval(timer);
    };
  }, [id]);

  if (!sub) return <p>{status}</p>;
  const tests = sub.tests || [];

  return (
    <>
      <p>
        <Link to="/submissions">← zgłoszenia</Link>
      </p>
      <p>{status}</p>
      <h2>Zgłoszenie #{sub.id}</h2>
      <div className="cards">
        <div className="card">
          <span className="label">status</span>
          <span className="value">{sub.status}</span>
        </div>
        <div className="card">
          <span className="label">werdykt</span>
          <span className="value">{sub.verdict ?? "–"}</span>
        </div>
        <div className="card">
          <span className="label">punkty</span>
          <span className="value">
            {sub.score ?? "–"} / {sub.max_score}
          </span>
        </div>
      </div>
      <p>{sub.message}</p>
      <h3>Testy</h3>
      {tests.length === 0 ? (
        <p className="muted">Brak tabeli testów (OIOIOI często oddaje tylko wynik całości).</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Grupa</th>
              <th>Werdykt</th>
              <th>Pkt</th>
            </tr>
          </thead>
          <tbody>
            {tests.map((test) => (
              <tr key={test.test_id}>
                <td>
                  {test.position + 1}
                  {test.hidden ? " (ukryty)" : ""}
                </td>
                <td>{test.group}</td>
                <td>{test.verdict}</td>
                <td>
                  {test.score} / {test.max_score}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <h3>Kod</h3>
      <pre>{sub.code}</pre>
    </>
  );
}
