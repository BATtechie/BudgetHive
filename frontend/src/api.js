const API_BASE = "";

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request(path, { method = "GET", body, token } = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token),
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!res.ok) {
    const detail = data?.detail ?? data ?? res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

export const api = {
  health: () => request("/health"),
  signup: (body) => request("/auth/signup", { method: "POST", body }),
  login: (body) => request("/auth/login", { method: "POST", body }),
  me: (token) => request("/users/me", { token }),
  updateProfile: (body, token) => request("/users/me", { method: "PATCH", body, token }),
  financialEvaluate: (body, token) =>
    request("/api/v1/financial/evaluate", { method: "POST", body, token }),
  needQuestions: (body) => request("/api/v1/need/questions", { method: "POST", body }),
  needEvaluate: (body) => request("/api/v1/need/evaluate", { method: "POST", body }),
  dealHunterEvaluate: (body) =>
    request("/api/v1/deal-hunter/evaluate", { method: "POST", body }),
  alternativesEvaluate: (body) =>
    request("/api/v1/alternatives/evaluate", { method: "POST", body }),
};
