import { useEffect, useState } from "react";
import { api } from "../api";

type Stats = {
  queued: number;
  running: number;
  failed: number;
  finished_last_minute: number;
  workers: number;
};

export default function Stats() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [status, setStatus] = useState("Ładowanie…");

  useEffect(() => {
    api<Stats>("/stats")
      .then((data) => {
        setStats(data);
        setStatus("");
      })
      .catch((error: Error) => setStatus(error.message));
  }, []);

  if (!stats) return <p>{status}</p>;
  return (
    <>
      <h2>Kolejka backendu</h2>
      <div className="cards">
        <div className="card">
          <span className="label">queued</span>
          <span className="value">{stats.queued}</span>
        </div>
        <div className="card">
          <span className="label">running</span>
          <span className="value">{stats.running}</span>
        </div>
        <div className="card">
          <span className="label">failed</span>
          <span className="value">{stats.failed}</span>
        </div>
        <div className="card">
          <span className="label">done / min</span>
          <span className="value">{stats.finished_last_minute}</span>
        </div>
      </div>
    </>
  );
}
