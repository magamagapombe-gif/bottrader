const API = process.env.NEXT_PUBLIC_API_URL || "https://supereye-api.onrender.com";
const ADMIN_SECRET = process.env.NEXT_PUBLIC_ADMIN_SECRET || "";

export async function validateToken(token: string) {
  const r = await fetch(`${API}/validate-token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
  return r.json();
}

export async function getMe(token: string) {
  const r = await fetch(`${API}/dashboard/me`, {
    headers: { "x-token": token },
  });
  if (!r.ok) return null;
  return r.json();
}

export async function getAllUsers() {
  const r = await fetch(`${API}/dashboard/users`, {
    headers: { "x-admin-secret": ADMIN_SECRET },
  });
  if (!r.ok) return [];
  return r.json();
}

export async function issueToken(username: string, role: string, expiresDays: number | null) {
  const r = await fetch(`${API}/admin/issue-token`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-admin-secret": ADMIN_SECRET,
    },
    body: JSON.stringify({ username, role, expires_days: expiresDays }),
  });
  return r.json();
}

export async function revokeToken(tokenId: string) {
  const r = await fetch(`${API}/admin/revoke-token`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-admin-secret": ADMIN_SECRET,
    },
    body: JSON.stringify({ token_id: tokenId }),
  });
  return r.json();
}

export async function sendCommand(userId: string, command: "stop" | "start") {
  const r = await fetch(`${API}/command/send`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-admin-secret": ADMIN_SECRET,
    },
    body: JSON.stringify({ user_id: userId, command }),
  });
  return r.json();
}

export function saveToken(token: string) {
  localStorage.setItem("se_token", token);
}
export function loadToken(): string {
  return typeof window !== "undefined" ? localStorage.getItem("se_token") || "" : "";
}
export function clearToken() {
  localStorage.removeItem("se_token");
}
