import { useEffect, useState } from "react";
import { api } from "../api";

export default function ParticipantDashboard() {
  const [project, setProject] = useState(null);
  const [form, setForm] = useState({ title: "", tagline: "", description: "", repo_url: "", demo_url: "" });
  const [error, setError] = useState(null);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api.myProject()
      .then((p) => { if (!cancelled) setProject(p); })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  function set(k, v) { setForm((f) => ({ ...f, [k]: v })); }

  async function create() {
    setError(null);
    try {
      const p = await api.createProject(form);
      setProject(p);
      setStatus("Draft created.");
    } catch (e) {
      setError(e.message + " (create a team first via POST /api/teams if you haven't)");
    }
  }

  async function submit() {
    setError(null);
    try {
      const p = await api.submitProject(project.id);
      setProject(p);
      setStatus("Submitted!");
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div style={{ maxWidth: 480 }}>
      <h2>Your Project</h2>
      {loading && <p style={{ color: "var(--muted)" }}>Loading…</p>}
      {!loading && !project && (
        <>
          <input placeholder="Title" value={form.title} onChange={(e) => set("title", e.target.value)} />
          <input placeholder="Tagline" value={form.tagline} onChange={(e) => set("tagline", e.target.value)} />
          <textarea placeholder="Description" rows={4} value={form.description} onChange={(e) => set("description", e.target.value)} />
          <input placeholder="Repo URL" value={form.repo_url} onChange={(e) => set("repo_url", e.target.value)} />
          <input placeholder="Demo URL" value={form.demo_url} onChange={(e) => set("demo_url", e.target.value)} />
          <button className="primary" onClick={create}>Save draft</button>
        </>
      )}
      {project && (
        <div className="card">
          <h3>{project.title}</h3>
          <p>Status: <span className={`badge ${project.status === "submitted" ? "ok" : "warn"}`}>{project.status}</span></p>
          {project.status === "draft" && <button className="primary" onClick={submit}>Submit</button>}
        </div>
      )}
      {status && <p style={{ color: "var(--green)" }}>{status}</p>}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
