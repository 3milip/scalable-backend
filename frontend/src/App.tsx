import type { ReactNode } from "react";
import { Link, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { clearSession, getToken, getUser } from "./api";
import Login from "./pages/Login";
import Problem from "./pages/Problem";
import Problems from "./pages/Problems";
import Stats from "./pages/Stats";
import Submission from "./pages/Submission";
import Submissions from "./pages/Submissions";

function Guard({ children }: { children: ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  const navigate = useNavigate();
  const user = getUser();
  return (
    <>
      <header>
        <h1>Judge</h1>
        <nav>
          <Link to="/problems">Zadania</Link>
          <Link to="/submissions">Zgłoszenia</Link>
          <Link to="/stats">Statystyki</Link>
          {user ? (
            <a
              href="/login"
              onClick={(event) => {
                event.preventDefault();
                clearSession();
                navigate("/login");
              }}
            >
              {user} · wyloguj
            </a>
          ) : (
            <Link to="/login">Zaloguj</Link>
          )}
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Navigate to="/problems" replace />} />
          <Route
            path="/problems"
            element={
              <Guard>
                <Problems />
              </Guard>
            }
          />
          <Route
            path="/problems/:id"
            element={
              <Guard>
                <Problem />
              </Guard>
            }
          />
          <Route
            path="/submissions"
            element={
              <Guard>
                <Submissions />
              </Guard>
            }
          />
          <Route
            path="/submissions/:id"
            element={
              <Guard>
                <Submission />
              </Guard>
            }
          />
          <Route
            path="/stats"
            element={
              <Guard>
                <Stats />
              </Guard>
            }
          />
        </Routes>
      </main>
    </>
  );
}
