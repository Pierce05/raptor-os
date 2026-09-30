import { useEffect, useState, useCallback } from "react";
import { api } from "../api";
import { short, Panel, Progress, StatusBadge, LoadingState, EmptyState, ErrorState, PageHead } from "../ui";

export default function JudgeDeck() {
  const [queue, setQueue] = useState(null);
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
    setError(null); setJustSubmitted(false); setSavedAt(null);
    setActiveId(projectId); setDetail(null);
    try {
      const d = await api.judgeProject(projectId);
      setDetail(d);
      const existing = await api.mySc(projectId);
      const v = {};
      for (const s of existing.drafts) v[s.criterion_id] = s.value ?? "";
      for (const s of existing.submitted) v[s.criterion_id] = s.value;
      setValues(v);
    } catch (e) { setError(e.message); }
  }

  function setScore(id, val) { setValues((v) => ({ ...v, [id]: val })); }

  async function saveDraft() {
    try {
      const scores = detail.criteria.map((c) => ({
        criterion_id: c.id,
        value: values[c.id] === "" || values[c.id] == null ? null : Number(values[c.id]),
      }));
      await api.saveDraft(activeId, scores);
      setSavedAt(new Date().toLocaleTimeString());
    } catch (e) { setError(e.message); }
  }

  async function submit() {
    setError(null);
    const scores = detail.criteria.map((c) => ({ criterion_id: c.id, value: Number(values[c.id]) }));
    try {
      await api.submitScores(activeId, scores);
      setJustSubmitted(true);
      loadQueue();
    } catch (e) { setError(e.message); }
  }

  const complete = (queue || []).filter((q) => q.scored).length;
  const total = (queue || []).length;

  /* ---------- queue ---------- */
  if (!activeId) {
    return (
      <div>
        <PageHead eyebrow="JUDGE DECK" title={`${total} ASSIGNED`} right={<span className="meta">{complete} COMPLETE · {total - complete} REMAINING</span>} />

        {queue && total > 0 && (
          <Panel accent style={{ marginBottom: 20 }}>
            <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-end" }}>
              <div>
                <div className="big">{complete} <span style={{ color: "var(--muted)" }}>/ {total}</span></div>
                <span className="label">PROJECTS REVIEWED</span>
              </div>
              <StatusBadge tone={complete === total ? "ok" : "warn"}>{complete === total ? "ALL SUBMITTED" : `${total - complete} PENDING`}</StatusBadge>
            </div>
            <div style={{ marginTop: 14 }}><Progress thick pct={total ? (complete / total) * 100 : 0} /></div>
          </Panel>
        )}

        {queue === null && <LoadingState />}
        {loadError && <ErrorState onRetry={loadQueue}>RAPTOR could not reach the judging service.</ErrorState>}
        {queue && total === 0 && !loadError && <EmptyState>Your judging queue is empty. Ask an organizer to run assignment.</EmptyState>}

        {queue && queue.map((q, i) => (
          <div key={q.project_id} className={`queue-item ${q.scored ? "done" : "pending"}`}>
            <span className="chip">{String(i + 1).padStart(2, "0")}</span>
            <div className="col-main"><h3>{q.title}</h3><span className="meta">{short(q.project_id)}</span></div>
            <StatusBadge tone={q.scored ? "ok" : "warn"}>{q.scored ? "✓ scored" : "● pending"}</StatusBadge>
            <button className={q.scored ? "" : "primary"} onClick={() => open(q.project_id)}>{q.scored ? "Review" : "Score →"}</button>
          </div>
        ))}
        {error && <p className="error" role="alert">{error}</p>}
      </div>
    );
  }

  /* ---------- scoring console ---------- */
  const idx = queue ? queue.findIndex((q) => q.project_id === activeId) : -1;
  const locked = queue?.find((q) => q.project_id === activeId)?.scored;
  const criteria = detail?.criteria || [];
  const totalWeight = criteria.reduce((a, c) => a + Number(c.weight || 0), 0);
  const filled = criteria.filter((c) => values[c.id] !== "" && values[c.id] != null).length;
  const weighted = totalWeight
    ? criteria.reduce((a, c) => a + (c.max_score ? (Number(values[c.id] || 0) / c.max_score) * Number(c.weight || 0) : 0), 0) / totalWeight
    : 0;

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 20 }}>
        <button className="ghost" onClick={() => { setActiveId(null); setDetail(null); }}>← QUEUE</button>
        <span className="meta">ASSIGNMENT {idx >= 0 ? String(idx + 1).padStart(2, "0") : "—"} / {String(total).padStart(2, "0")} · {complete} REVIEWED</span>
      </div>

      {!detail && !error && <LoadingState rows={2} />}
      {!detail && error && <ErrorState>{error}</ErrorState>}

      {detail && (
        <div className="split">
          <div className="stack" style={{ alignContent: "start" }}>
            <div>
              <span className="eyebrow">PROJECT UNDER REVIEW</span>
              <h1 className="dossier-title">{detail.title}</h1>
              {detail._blind_note && <div className="note">{detail._blind_note}</div>}
              <p style={{ color: "var(--muted)" }}>{detail.tagline}</p>
            </div>
            <Panel title="DESCRIPTION" accent>
              <p style={{ whiteSpace: "pre-wrap" }}>{detail.description}</p>
              <div className="row" style={{ marginTop: 12 }}>
                {detail.demo_url && <button onClick={() => window.open(detail.demo_url, "_blank")}>Demo ↗</button>}
                {detail.repo_url && <button onClick={() => window.open(detail.repo_url, "_blank")}>Repository ↗</button>}
              </div>
            </Panel>
          </div>

          <div style={{ alignSelf: "start", position: "sticky", top: 84 }}>
            <Panel title="RUBRIC" right={`${filled}/${criteria.length} scored`} accent>
              {criteria.map((c) => {
                const val = values[c.id] === "" || values[c.id] == null ? 0 : Number(values[c.id]);
                return (
                  <div key={c.id} className={`rubric-row ${locked ? "locked" : ""}`}>
                    <div className="top">
                      <label className="mono" htmlFor={`s-${c.id}`}>{c.name.toUpperCase()}</label>
                      <span className="w">weight {c.weight}</span>
                    </div>
                    <div className="ctl">
                      <input type="range" aria-label={`${c.name} slider`} min={0} max={c.max_score} step={1} value={val} disabled={locked}
                        onChange={(e) => setScore(c.id, e.target.value)} onMouseUp={saveDraft} onTouchEnd={saveDraft} onKeyUp={saveDraft} />
                      <input id={`s-${c.id}`} type="number" min={0} max={c.max_score} step={1} value={values[c.id] ?? ""} disabled={locked}
                        onChange={(e) => setScore(c.id, e.target.value)} onBlur={saveDraft} />
                      <span className="meta">/ {c.max_score}</span>
                    </div>
                  </div>
                );
              })}
              <Progress pct={weighted * 100} label="WEIGHTED TOTAL (LIVE PREVIEW)" right={`${Math.round(weighted * 100)}%`} />

              {!locked && (
                <div className="row" style={{ marginTop: 16 }}>
                  <button onClick={saveDraft}>Save draft</button>
                  <button className="primary" onClick={submit}>Submit final scores</button>
                </div>
              )}
              {savedAt && !locked && <p className="meta" style={{ marginTop: 10 }}>Draft saved {savedAt}</p>}
              {locked && !justSubmitted && <div className="note">Locked — scores are immutable once submitted.</div>}
              {justSubmitted && <div className="confirm"><b>✓ SCORE SUBMITTED</b>Immutable record. This score can no longer be edited.</div>}
              {error && <p className="error" role="alert">{error}</p>}
            </Panel>
          </div>
        </div>
      )}
    </div>
  );
}
