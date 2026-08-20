import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Submission } from "../api";

export default function Submissions() {
  const [status, setStatus] = useState("Ładowanie…");
  const [items, setItems] = useState<Submission[]>([]);

  useEffect(() => {
    let stop = false;
    async function load() {
      try {
        const data = await api<{ total: number; items: Submission[] }>("/submissions?limit=50");
        if (stop) return;
        setItems(data.items);
        setStatus(data.total ? "Wszystkich: " + data.total : "Nie ma jeszcze żadnego zgłoszenia");
      } catch (error) {
        if (!stop) setStatus(error instanceof Error && error.message === "unauthorized" ? "Zaloguj się" : "Nie mogę połączyć z backendem");
      }
    }
    load();
    const timer = setInterval(load, 2000);
    return () => {
      stop = true;
      clearInterval(timer);
    };
  }, []);

  return (
    <>
      <h2>Zgłoszenia</h2>
      <p>{status}</p>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Zadanie</th>
            <th>Status</th>
            <th>Werdykt</th>
            <th>Punkty</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <Link to={"/submissions/" + item.id}>{item.id}</Link>
              </td>
              <td>{item.problem_title}</td>
              <td>{item.status}</td>
              <td>{item.verdict ?? "–"}</td>
              <td>
                {item.score ?? "–"} / {item.max_score}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
