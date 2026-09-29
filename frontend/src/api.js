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
    const err = new Error(
      (data && data.detail) || `HTTP ${res.status}`
    );
    err.status = res.status;
    throw err;
  }

  return data;
}

export const api = {
  // ─────────────────────────────────────────────
  // AUTH
  // ─────────────────────────────────────────────

  login: (email, password) =>
    req("POST", "/api/auth/login", { email, password }),

  logout: () =>
    req("POST", "/api/auth/logout"),

  me: () =>
    req("GET", "/api/auth/me"),


  // ─────────────────────────────────────────────
  // PUBLIC GALLERY
  // ─────────────────────────────────────────────

  gallery: (params = {}) => {
    const qs = new URLSearchParams(params).toString();

    return req(
      "GET",
      `/api/gallery${qs ? "?" + qs : ""}`
    );
  },

  project: (id) =>
    req("GET", `/api/gallery/${id}`),


  // ─────────────────────────────────────────────
  // COMMUNITY / T3
  // ─────────────────────────────────────────────

  communityStatus: () =>
    req("GET", "/api/community/status"),

  ballot: () =>
    req("GET", "/api/community/ballot"),

  castVote: (project_id) =>
    req("POST", "/api/community/votes", { project_id }),

  communityResults: () =>
    req("GET", "/api/community/results"),

  comments: (project_id) =>
    req("GET", `/api/community/projects/${project_id}/comments`),

  postComment: (project_id, body) =>
    req(
      "POST",
      `/api/community/projects/${project_id}/comments`,
      { body }
    ),


  // ─────────────────────────────────────────────
  // PARTICIPANT / PROJECTS
  // ─────────────────────────────────────────────

  createTeam: (name, event_id) =>
    req("POST", "/api/teams", { name, event_id }),

  myProject: () =>
    req("GET", "/api/projects/mine"),

  createProject: (body) =>
    req("POST", "/api/projects", body),

  editProject: (id, body) =>
    req("PATCH", `/api/projects/${id}`, body),

  submitProject: (id) =>
    req("POST", `/api/projects/${id}/submit`),


  // ─────────────────────────────────────────────
  // JUDGE
  // ─────────────────────────────────────────────

  judgeQueue: () =>
    req("GET", "/api/judge/queue"),

  judgeProject: (id) =>
    req("GET", `/api/judge/project/${id}`),

  saveDraft: (id, scores) =>
    req(
      "PUT",
      `/api/judge/scores/${id}/draft`,
      { scores }
    ),

  mySc: (id) =>
    req("GET", `/api/judge/scores/${id}`),

  submitScores: (id, scores) =>
    req(
      "POST",
      `/api/judge/scores/${id}/submit`,
      { scores }
    ),

      myRecord: () =>
      req("GET", "/api/judge/record"),

      verifyRecord: (record_id) =>
      req("GET", `/api/verify/${record_id}`),


  // ─────────────────────────────────────────────
  // ORGANIZER
  // ─────────────────────────────────────────────

  currentEvent: () =>
    req("GET", "/api/organizer/event"),

  runAssignment: (event_id) =>
    req(
      "POST",
      `/api/organizer/assignments/run?event_id=${event_id}`
    ),

  dashboard: (event_id) =>
    req(
      "GET",
      `/api/organizer/dashboard?event_id=${event_id}`
    ),

  runNormalization: (event_id) =>
    req(
      "POST",
      `/api/organizer/normalization/run?event_id=${event_id}`
    ),

  rankings: (event_id) =>
    req(
      "GET",
      `/api/organizer/rankings?event_id=${event_id}`
    ),

  rankingExplanation: (project_id, event_id) =>
    req(
      "GET",
      `/api/organizer/rankings/${project_id}/explain?event_id=${event_id}`
    ),

  audit: (event_id) =>
    req(
      "GET",
      `/api/organizer/audit?event_id=${event_id}`
    ),

  exportCsvUrl: (event_id) =>
    `/api/organizer/export.csv?event_id=${event_id}`,
};