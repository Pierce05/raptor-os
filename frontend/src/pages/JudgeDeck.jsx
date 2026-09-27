import { useEffect, useState, useCallback } from "react";
import { api } from "../api";

export default function JudgeDeck() {
  const [queue, setQueue] = useState(null); // null = loading
  const [activeId, setActiveId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [values, setValues] = useState({});
  const [error, setError] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [savedAt, setSavedAt] = useState(null);
  const [justSubmitted, setJustSubmitted] = useState(false);

  const loadQueue = useCallback(() => {
    setLoadError(null);
    api.judgeQueue().then(setQueue).catch((e) => { setLoadError(e.message); setQueue([]); });
  }, []);
  useEffect(() => { loadQueue(); }, [loadQueue]);

  async function open(projectId) {
    setError(null);
    setJustSubmitted(false);
    setActiveId(projectId);
    setDetail(null);
    const d = await api.judgeProject(projectId);
    setDetail(d);
    const existing = await api.mySc(projectId);
    const v = {};
    for (const s of existing.drafts) v[s.criterion_id] = s.value ?? "";
    for (const s of existing.submitted) v[s.criterion_id] = s.value;
    setValues(v);
  }

  function setScore(criterionId, val) { setValues((v) => ({ ...v, [criterionId]: val })); }

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
    const scores = detail.criteria.map((c) => ({ criterion_id: c.id, value: Number(values[c.id]) }));
    try {
      await api.submitScores(activeId, scores);
      setJustSubmitted(true);
      loadQueue();
    } catch (e) {
      setError(e.message);
    }
  }

  if (!activeId) {
    const complete = (queue || []).filter((q) => q.scored).length;
    const total = (queue || []).length;
    return (
      <div>
        <div className="head">
          <div>
            <span className="eyebrow">JUDGE DECK</span>
            <h2>{total} ASSIGNED</h2>
          </div>
          <span className="meta">{complete} COMPLETE · {total - complete} REMAINING</span>
        </div>

        {queue === null && <div className="skeleton"><div className="skel-row" /><div className="skel-row" /></div>}

        {loadError && (
          <div className="state state-error">RAPTOR could not reach the judging service.
            <div><button onClick={loadQueue}>Retry</button></div>
          </div>
        )}

        {queue && queue.length === 0 && !loadError && (
          <div className="state">Your judging queue is empty. Ask an organizer to run assignment.</div>
        )}

        {queue && queue.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Project</th><th>Status</th><th></th></tr></thead>
              <tbody>
                {queue.map((q) => (
                  <tr key={q.project_id}>
                    <td>{q.title}</td>
                    <td><span className={`badge ${q.scored ? "ok" : "warn"}`}>{q.scored ? "✓ scored" : "● pending"}</span></td>
                    <td><button onClick={() => open(q.project_id)}>{q.scored ? "Review" : "Score →"}</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {error && <p className="error">{error}</p>}
      </div>
    );
  }

  const locked = queue?.find((q) => q.project_id === activeId)?.scored;

  return (
    <div>
      <button onClick={() => { setActiveId(null); setDetail(null); }}>&larr; back to queue</button>
      {!detail && <div className="skeleton" style={{ marginTop: 16 }}><div className="skel-row" /><div className="skel-row" /></div>}
      {detail && (
        <div className="split" style={{ marginTop: 16 }}>
          <div>
            <h2>{detail.title}</h2>
            {detail._blind_note && <div className="note">{detail._blind_note}</div>}
            <p>{detail.tagline}</p>
            <p>{detail.description}</p>
            <div style={{ display: "flex", gap: 10 }}>
              {detail.demo_url && <button onClick={() => window.open(detail.demo_url, "_blank")}>Demo</button>}
              {detail.repo_url && <button onClick={() => window.open(detail.repo_url, "_blank")}>Repository</button>}
            </div>
          </div>
          <div>
            <h3>Rubric</h3>
            {detail.criteria.map((c) => {
              const val = values[c.id] === "" || values[c.id] == null ? 0 : Number(values[c.id]);
              const pct = c.max_score ? Math.min(100, (val / c.max_score) * 100) : 0;
              return (
                <div key={c.id} className={`rubric-row ${locked ? "locked" : ""}`}>
                  <div className="top">
                    <label className="mono">{c.name.toUpperCase()}</label>
                    <span className="w">w {c.weight}</span>
                  </div>
                  <div className="bar" style={{ marginBottom: 8 }}><div style={{ width: pct + "%" }} /></div>
                  <input
                    type="number" min={0} max={c.max_score} step={1}
                    value={values[c.id] ?? ""}
                    onChange={(e) => setScore(c.id, e.target.value)}
                    onBlur={saveDraft}
                    disabled={locked}
                  />
                  <span className="mono" style={{ color: "var(--muted)", fontSize: "0.68rem", marginLeft: 8 }}>/ {c.max_score}</span>
                </div>
              );
            })}

            {!locked && (
              <>
                <button onClick={saveDraft}>Save draft</button>{" "}
                <button className="primary" onClick={submit}>Submit final scores</button>
                {savedAt && <p className="mono" style={{ color: "var(--muted)", fontSize: "0.78em" }}>Draft saved {savedAt}</p>}
              </>
            )}
            {locked && !justSubmitted && <div className="note">Locked — scores are immutable once submitted.</div>}
            {justSubmitted && <div className="confirm"><b>✓ SCORE SUBMITTED</b>Immutable record. This score can no longer be edited.</div>}
            {error && <p className="error">{error}</p>}
          </div>
        </div>
      )}
    </div>
  );
}
