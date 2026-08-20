const TOKEN_KEY = "judge_token";
const USER_KEY = "judge_user";
const API = "http://127.0.0.1:8000";

function authHeaders(extra) {
  const headers = extra ? { ...extra } : {};
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) headers.Authorization = "Bearer " + token;
  return headers;
}

function requireLogin() {
  if (!localStorage.getItem(TOKEN_KEY)) {
    const next = encodeURIComponent(location.pathname + location.search);
    location.href = "login.html?next=" + next;
    return false;
  }
  return true;
}

function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  location.href = "login.html";
}

(function navAuth() {
  const nav = document.querySelector("header nav");
  if (!nav) return;
  const link = document.createElement("a");
  const user = localStorage.getItem(USER_KEY);
  if (user) {
    link.href = "login.html";
    link.textContent = user + " · wyloguj";
    link.addEventListener("click", function (event) {
      event.preventDefault();
      logout();
    });
  } else {
    link.href = "login.html";
    link.textContent = "Zaloguj";
  }
  nav.appendChild(link);
})();
