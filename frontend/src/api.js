const BASE = "";

async function req(method, path, body) {
  const res = await fetch(BASE + path, {
    method,
    credentials: "include",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try {
    data = await res.json();
  } catch (e) {
    /* no body */
  }
  if (!res.ok) {
    const err = new Error((data && data.detail) || `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return data;
}

export const api = {
  login: (email, password) => req("POST", "/api/auth/login", { email, password }),
  logout: () => req("POST", "/api/auth/logout"),
  me: () => req("GET", "/api/auth/me"),

  gallery: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return req("GET", `/api/gallery${qs ? "?" + qs : ""}`);
  },
  project: (id) => req("GET", `/api/gallery/${id}`),

  createTeam: (name, event_id) => req("POST", "/api/teams", { name, event_id }),
  myProject: () => req("GET", "/api/projects/mine"),
  createProject: (body) => req("POST", "/api/projects", body),
  editProject: (id, body) => req("PATCH", `/api/projects/${id}`, body),
  submitProject: (id) => req("POST", `/api/projects/${id}/submit`),

  judgeQueue: () => req("GET", "/api/judge/queue"),
  judgeProject: (id) => req("GET", `/api/judge/project/${id}`),
  saveDraft: (id, scores) => req("PUT", `/api/judge/scores/${id}/draft`, { scores }),
  mySc: (id) => req("GET", `/api/judge/scores/${id}`),
  submitScores: (id, scores) => req("POST", `/api/judge/scores/${id}/submit`, { scores }),

  currentEvent: () => req("GET", "/api/organizer/event"),
  runAssignment: (event_id) => req("POST", `/api/organizer/assignments/run?event_id=${event_id}`),
  dashboard: (event_id) => req("GET", `/api/organizer/dashboard?event_id=${event_id}`),
  runNormalization: (event_id) => req("POST", `/api/organizer/normalization/run?event_id=${event_id}`),
  rankings: (event_id) => req("GET", `/api/organizer/rankings?event_id=${event_id}`),
  audit: (event_id) => req("GET", `/api/organizer/audit?event_id=${event_id}`),
  exportCsvUrl: (event_id) => `/api/organizer/export.csv?event_id=${event_id}`,
};
