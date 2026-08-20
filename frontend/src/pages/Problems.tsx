import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Problem } from "../api";

export default function Problems() {
  const [status, setStatus] = useState("Ładowanie…");
  const [items, setItems] = useState<Problem[]>([]);

  useEffect(() => {
    api<{ total: number; items: Problem[] }>("/problems?limit=100")
      .then((data) => {
        setItems(data.items);
        setStatus(data.total ? "Zadań: " + data.total : "Brak zadań");
      })
      .catch((error: Error) => setStatus(error.message === "unauthorized" ? "Zaloguj się" : "Nie mogę połączyć z backendem (:8000)"));
  }, []);

  return (
    <>
      <h2>Zadania</h2>
      <p>{status}</p>
      <ul>
        {items.map((item) => (
          <li key={item.id}>
            <Link to={"/problems/" + item.id}>{item.title}</Link>
            {item.difficulty != null ? " · " + item.difficulty : ""}
          </li>
        ))}
      </ul>
    </>
  );
}
