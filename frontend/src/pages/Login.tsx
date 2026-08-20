import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, setSession } from "../api";

export default function Login() {
  const navigate = useNavigate();
  const [status, setStatus] = useState("");

  async function send(path: string, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const username = (form.elements.namedItem("username") as HTMLInputElement).value;
    const password = (form.elements.namedItem("password") as HTMLInputElement).value;
    setStatus("Czekaj…");
    try {
      const data = await api<{ token: string; username: string }>(path, {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      setSession(data.token, data.username);
      navigate("/problems");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Błąd");
    }
  }

  return (
    <>
      <h2>Konto</h2>
      <p className="muted">Konto jest tylko na backendzie. Sędzia OIOIOI nie dostaje twojego loginu.</p>
      <p id="status">{status}</p>
      <form onSubmit={(event) => send("/auth/login", event)}>
        <h3>Logowanie</h3>
        <p>
          <label>
            Login <input name="username" required minLength={3} maxLength={32} />
          </label>
        </p>
        <p>
          <label>
            Hasło <input name="password" type="password" required minLength={6} />
          </label>
        </p>
        <p>
          <button type="submit">Zaloguj</button>
        </p>
      </form>
      <form onSubmit={(event) => send("/auth/register", event)}>
        <h3>Rejestracja</h3>
        <p>
          <label>
            Login <input name="username" required minLength={3} maxLength={32} />
          </label>
        </p>
        <p>
          <label>
            Hasło <input name="password" type="password" required minLength={6} />
          </label>
        </p>
        <p>
          <button type="submit">Załóż konto</button>
        </p>
      </form>
    </>
  );
}
