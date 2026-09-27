import { useEffect, useState } from "react";
import { api } from "../api";

const FIELDS = ["title", "tagline", "description", "repo_url", "demo_url"];

export default function ParticipantDashboard() {
  const [project, setProject] = useState(null);
  const [form, setForm] = useState({ title: "", tagline: "", description: "", repo_url: "", demo_url: "" });
  const [editing, setEditing] = useState(false);
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
  const filled = FIELDS.filter((k) => form[k]?.trim()).length;
  const pct = Math.round((filled / FIELDS.length) * 100);

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

  function startEdit() {
    setForm({
      title: project.title || "", tagline: project.tagline || "", description: project.description || "",
      repo_url: project.repo_url || "", demo_url: project.demo_url || "",
    });
    setEditing(true);
  }

  async function saveEdit() {
    setError(null);
    try {
      const p = await api.editProject(project.id, form);
      setProject(p);
      setEditing(false);
      setStatus("Draft updated.");
    } catch (e) {
      setError(e.message);
    }
  }

  async function submit() {
    setError(null);
    try {
      const p = await api.submitProject(project.id);
      setProject(p);
      setStatus("submitted-now");
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div style={{ maxWidth: 480 }}>
      <div className="head">
        <div>
          <span className="eyebrow">MY PROJECT</span>
          <h2>{project ? project.title : "New submission"}</h2>
        </div>
        {project && <span className={`badge ${project.status === "submitted" ? "ok" : "warn"}`}>{project.status}</span>}
      </div>

      {loading && <div className="skeleton"><div className="skel-row" /></div>}

      {!loading && !project && (
        <>
          <div className="bar-label"><span>SUBMISSION</span><span>{pct}%</span></div>
          <div className="bar" style={{ marginBottom: 16 }}><div style={{ width: pct + "%" }} /></div>
          <input placeholder="Title" value={form.title} onChange={(e) => set("title", e.target.value)} />
          <input placeholder="Tagline" value={form.tagline} onChange={(e) => set("tagline", e.target.value)} />
          <textarea placeholder="Description" rows={4} value={form.description} onChange={(e) => set("description", e.target.value)} />
          <input placeholder="Repo URL" value={form.repo_url} onChange={(e) => set("repo_url", e.target.value)} />
          <input placeholder="Demo URL" value={form.demo_url} onChange={(e) => set("demo_url", e.target.value)} />
          <button className="primary" onClick={create}>Save draft</button>
        </>
      )}

      {project && project.status === "draft" && !editing && (
        <div className="card">
          <p>{project.tagline}</p>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={startEdit}>Edit</button>
            <button className="primary" onClick={submit}>Submit project</button>
          </div>
        </div>
      )}

      {project && project.status === "draft" && editing && (
        <>
          <input placeholder="Title" value={form.title} onChange={(e) => set("title", e.target.value)} />
          <input placeholder="Tagline" value={form.tagline} onChange={(e) => set("tagline", e.target.value)} />
          <textarea placeholder="Description" rows={4} value={form.description} onChange={(e) => set("description", e.target.value)} />
          <input placeholder="Repo URL" value={form.repo_url} onChange={(e) => set("repo_url", e.target.value)} />
          <input placeholder="Demo URL" value={form.demo_url} onChange={(e) => set("demo_url", e.target.value)} />
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={() => setEditing(false)}>Cancel</button>
            <button className="primary" onClick={saveEdit}>Save changes</button>
          </div>
        </>
      )}

      {project && project.status === "submitted" && status === "submitted-now" && (
        <div className="confirm"><b>✓ SUBMISSION LOCKED</b>Your project was submitted. It can no longer be edited, and judges can now be assigned to it.</div>
      )}
      {project && project.status === "submitted" && status !== "submitted-now" && (
        <div className="note">Locked — this project is submitted and can't be edited further.</div>
      )}

      {status && status !== "submitted-now" && <p style={{ color: "var(--green)" }}>{status}</p>}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
