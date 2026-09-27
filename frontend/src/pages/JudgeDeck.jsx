import { useEffect, useState, useCallback } from "react";
import { api } from "../api";

export default function JudgeDeck() {
  const [queue, setQueue] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [values, setValues] = useState({});
  const [error, setError] = useState(null);
  const [savedAt, setSavedAt] = useState(null);

  const loadQueue = useCallback(() => {
    api.judgeQueue().then(setQueue).catch((e) => setError(e.message));
  }, []);

  useEffect(() => { loadQueue(); }, [loadQueue]);

  async function open(projectId) {
    setError(null);
    setActiveId(projectId);
    const d = await api.judgeProject(projectId);
    setDetail(d);
    const existing = await api.mySc(projectId);
    const v = {};
    for (const s of existing.drafts) v[s.criterion_id] = s.value ?? "";
    for (const s of existing.submitted) v[s.criterion_id] = s.value;
    setValues(v);
  }

  function setScore(criterionId, val) {
    setValues((v) => ({ ...v, [criterionId]: val }));
  }

  async function saveDraft() {
    const scores = detail.criteria.map((c) => ({
      criterion_id: c.id,
      value: values[c.id] === "" || values[c.id] == null ? null : Number(values[c.id]),
    }));
    await api.saveDraft(activeId, scores);
    setSavedAt(new Date().toLocaleTimeString());
  }

  async function submit() {
    setError(null);
    const scores = detail.criteria.map((c) => ({
      criterion_id: c.id,
      value: Number(values[c.id]),
    }));
    try {
      await api.submitScores(activeId, scores);
      setActiveId(null);
      setDetail(null);
      loadQueue();
    } catch (e) {
      setError(e.message);
    }
  }

  if (!activeId) {
    return (
      <div>
        <h2>Judge Command Deck</h2>
        <table>
          <thead><tr><th>Project</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {queue.map((q) => (
              <tr key={q.project_id}>
                <td>{q.title}</td>
                <td><span className={`badge ${q.scored ? "ok" : "warn"}`}>{q.scored ? "scored" : "pending"}</span></td>
                <td><button onClick={() => open(q.project_id)}>Score</button></td>
              </tr>
            ))}
            {queue.length === 0 && <tr><td colSpan={3}>No assignments yet.</td></tr>}
          </tbody>
        </table>
        {error && <p className="error">{error}</p>}
      </div>
    );
  }

  return (
    <div>
      <button onClick={() => { setActiveId(null); setDetail(null); }}>&larr; back to queue</button>
      {detail && (
        <div className="split">
          <div>
            <h2>{detail.title}</h2>
            {detail._blind_note && <p style={{ color: "var(--amber)", fontSize: "0.85em" }}>{detail._blind_note}</p>}
            <p>{detail.tagline}</p>
            <p>{detail.description}</p>
            {detail.demo_url && <p><a href={detail.demo_url} target="_blank" rel="noreferrer">Demo</a></p>}
            {detail.repo_url && <p><a href={detail.repo_url} target="_blank" rel="noreferrer">Repository</a></p>}
          </div>
          <div>
            <h3>Rubric</h3>
            {detail.criteria.map((c) => (
              <div key={c.id} style={{ marginBottom: 10 }}>
                <label>{c.name} (weight {c.weight})</label>
                <input
                  type="number" min={0} max={c.max_score} step={1}
                  value={values[c.id] ?? ""}
                  onChange={(e) => setScore(c.id, e.target.value)}
                  onBlur={saveDraft}
                />
              </div>
            ))}
            <button onClick={saveDraft}>Save draft</button>{" "}
            <button className="primary" onClick={submit}>Submit final scores</button>
            {savedAt && <p style={{ color: "var(--muted)", fontSize: "0.8em" }}>Draft saved {savedAt}</p>}
            {error && <p className="error">{error}</p>}
          </div>
        </div>
      )}
    </div>
  );
}
