// ── WorkingEveryday Auth ────────────────────────────────────────────────────

// call this on every protected page to redirect if not logged in
async function requireAuth() {
  const res = await api.me();
  if (res.error) {
    location.href = "/login";
    return null;
  }
  return res;
}

// get stored username for display (fallback)
function getUsername() {
  return sessionStorage.getItem("wed_username") || "User";
}

// ── signup ─────────────────────────────────────────────────────────────────
async function signup() {
  const inputs = document.querySelectorAll(".input");
  const username = inputs[0].value.trim();
  const password = inputs[1].value.trim();
  const confirm  = inputs[2].value.trim();

  if (!username || !password) return showError("Please fill in all fields.");
  if (password !== confirm)   return showError("Passwords don't match.");

  const res = await api.signup(username, password);
  if (res.error) return showError(res.error);

  sessionStorage.setItem("wed_username", res.user.username);
  location.href = "/main";
}

// ── login ──────────────────────────────────────────────────────────────────
async function login() {
  const inputs = document.querySelectorAll(".input");
  const username = inputs[0].value.trim();
  const password = inputs[1].value.trim();

  if (!username || !password) return showError("Please fill in all fields.");

  const res = await api.login(username, password);
  if (res.error) return showError(res.error);

  sessionStorage.setItem("wed_username", res.user.username);
  location.href = "/main";
}

// ── logout ─────────────────────────────────────────────────────────────────
async function logout() {
  await api.logout();
  sessionStorage.clear();
  location.href = "/";
}

// ── error display ──────────────────────────────────────────────────────────
function showError(msg) {
  let el = document.getElementById("wed-error");
  if (!el) {
    el = document.createElement("p");
    el.id = "wed-error";
    el.style.cssText = "color:#ff6b6b;font-size:13px;margin:8px 0 0;";
    document.querySelector(".box").appendChild(el);
  }
  el.textContent = msg;
}
