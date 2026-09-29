import { useEffect, useState } from "react";
import { api } from "../api";

export default function OrganizerConsole({ onAuditLoaded }) {
  const [eventId, setEventId] = useState(null);
  const [eventName, setEventName] = useState(null);
  const [eventError, setEventError] = useState(null);
  const [tab, setTab] = useState("mission-control");
  const [dashboard, setDashboard] = useState(null);
  const [rankings, setRankings] = useState(null);
  const [audit, setAudit] = useState(null);
  const [explanation, setExplanation] = useState(null);
  const [explanationLoading, setExplanationLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.currentEvent()
      .then((ev) => { setEventId(ev.id); setEventName(ev.name); })
      .catch((e) => setEventError(e.message));
  }, []);

  async function loadDashboard() {
    setError(null); setBusy(true);
    try { setDashboard(await api.dashboard(eventId)); } catch (e) { setError(e.message); }
    setBusy(false);
  }
async function runAssignment() {
  setError(null);
  setSuccess(null);
  setBusy(true);

  try {
    await api.runAssignment(eventId);
    await loadDashboard();
    setSuccess("✓ Assignment complete — review assignments updated.");
  } catch (err) {
    setError(err.message || "Failed to run assignment.");
  } finally {
    setBusy(false);
  }
}
async function runNormalization() {
  setError(null);
  setSuccess(null);
  setBusy(true);

  try {
    await api.runNormalization(eventId);
    await loadRankings();
    setSuccess("✓ Normalization complete — rankings updated.");
  } catch (err) {
    setError(err.message || "Failed to run normalization.");
  } finally {
    setBusy(false);
  }
}
  async function loadRankings() {
    setError(null);
    try { setRankings(await api.rankings(eventId)); } catch (e) { setError(e.message); }
  }

  async function loadExplanation(projectId) {
  setError(null);
  setExplanationLoading(true);

  try {
    const data = await api.rankingExplanation(projectId, eventId);
    console.log("EXPLANATION DATA:", data);
    setExplanation(data);
  } catch (e) {
    setError(e.message);
  } finally {
    setExplanationLoading(false);
  }
}
  async function loadAudit() {
    setError(null);
    try {
      const a = await api.audit(eventId);
      setAudit(a);
      onAuditLoaded?.(a.chain_valid);
    } catch (e) { setError(e.message); }
  }

  function selectTab(t) {
    setTab(t);
    if (t === "audit" && !audit && eventId) loadAudit();
    if (t === "rankings" && !rankings && eventId) loadRankings();
  }

  const coverage = dashboard && dashboard.reviews_assigned
    ? Math.round((dashboard.reviews_completed / dashboard.reviews_assigned) * 100)
    : null;

  return (
    <div>
      <div className="head">
        <div>
          <span className="eyebrow">MISSION CONTROL</span>
          <h2>{eventName || "Loading event…"}</h2>
        </div>
        {eventId && <span className="meta">{eventId.slice(0, 8)}…</span>}
      </div>

      {eventError && <div className="state state-error">{eventError}</div>}

      <div className="toolbar" style={{ marginTop: 4 }}>
        {["mission-control", "rankings", "audit"].map((t) => (
          <button key={t} className={tab === t ? "active" : ""} onClick={() => selectTab(t)}>{t}</button>
        ))}
      </div>

      {tab === "mission-control" && (
        <div>
          <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
            <button onClick={loadDashboard} disabled={!eventId || busy}>Refresh</button>
            <button onClick={runAssignment} disabled={!eventId || busy}>Run assignment</button>
            <button onClick={runNormalization} disabled={!eventId || busy}>Run normalization</button>
            <a href={eventId ? api.exportCsvUrl(eventId) : undefined}>
              <button disabled={!eventId}>Export CSV</button>
            </a>
          </div>
          {success && (
            <div className="state" style={{ marginBottom: 14 }}>
              {success}
            </div>
          )}

          {!dashboard && <div className="state">Hit Refresh to load live metrics.</div>}

          {dashboard && (
            <>
              <div className="grid" style={{ marginBottom: 16 }}>
                <div className="card"><h3>{dashboard.projects_submitted}</h3><p>SUBMISSIONS</p></div>
                <div className="card"><h3>{Object.keys(dashboard.judge_load || {}).length}</h3><p>JUDGES ACTIVE</p></div>
                <div className="card"><h3>{dashboard.reviews_assigned}</h3><p>REVIEWS ASSIGNED</p></div>
                <div className="card"><h3>{dashboard.under_reviewed.length}</h3><p>UNDER-REVIEWED</p></div>
              </div>

              {coverage !== null && (
                <div className="card" style={{ maxWidth: 340, marginBottom: 16 }}>
                  <div className="bar-label"><span>REVIEW COVERAGE</span><span>{coverage}%</span></div>
                  <div className="bar"><div style={{ width: coverage + "%" }} /></div>
                </div>
              )}

              {dashboard.under_reviewed.length > 0 && (
                <div className="card" style={{ maxWidth: 340 }}>
                  <h3>Under-reviewed</h3>
                  {dashboard.under_reviewed.map((u) => (
                    <p key={u.project_id} className="mono" style={{ fontSize: "0.78rem" }}>
                      &#9888; {u.project_id.slice(0, 8)}… {u.reviews}/{u.target}
                    </p>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}

        {tab === "rankings" && (
          <div style={{ display: "flex", flexDirection: "column" }}>
          <button onClick={loadRankings} disabled={!eventId}>Refresh</button>
          {!rankings && <div className="state" style={{ marginTop: 12 }}>Run normalization first, then refresh.</div>}
          {rankings && (
            <div className="table-wrap" style={{ marginTop: 12, order: 2 }}>
              <table>
                <thead>
                    <tr>
                      <th>Rank</th>
                      <th>Project</th>
                      <th>Final</th>
                      <th>Raw</th>
                      <th>Δ</th>
                      <th>Explain</th>
                    </tr>
                  </thead>
                <tbody>
                  {rankings.rankings.map((r) => (
                    <tr key={r.project_id}>
                      <td className="mono">{r.final_rank !== null ? String(r.final_rank).padStart(2, "0") : "—"}</td>
                      <td>{r.title}</td>
                      <td className="mono">
                        {r.insufficient_data || r.final_score === null
                          ? <span className="badge warn">insufficient data</span>
                          : r.final_score.toFixed(3)}
                      </td>
                      <td className="mono">{r.raw_rank !== null ? `#${r.raw_rank}` : "—"}</td>
                      <td className="mono" style={{ color: (r.rank_displacement ?? 0) > 0 ? "var(--green)" : (r.rank_displacement ?? 0) < 0 ? "var(--red)" : "var(--muted)" }}>
                        {r.rank_displacement === null ? "—" : r.rank_displacement > 0 ? `↑ ${r.rank_displacement}` : r.rank_displacement < 0 ? `↓ ${Math.abs(r.rank_displacement)}` : "—"}
                      </td>
                      <td>
                        {r.insufficient_data ? (
                          <span className="mono" style={{ color: "var(--muted)" }}>—</span>
                        ) : (
                          <button
                            onClick={() => loadExplanation(r.project_id)}
                            disabled={explanationLoading}
                          >
                            Explain
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

{explanation && (
  <div
    style={{
      position: "fixed",
      inset: 0,
      zIndex: 1000,
      background: "rgba(0, 0, 0, 0.78)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: 24,
      overflowY: "auto",
    }}
  >
    <div
      className="card"
      style={{
        width: "min(1100px, 100%)",
        maxHeight: "90vh",
        overflowY: "auto",
      }}
    >
      <div className="head" style={{ marginBottom: 12 }}>
        <div>
          <span className="eyebrow">RANKING EXPLANATION</span>
          <h2>Why this project ranked here</h2>
          <p className="mono">
            Project {explanation.project_id.slice(0, 8)}…
          </p>
        </div>

        <button onClick={() => setExplanation(null)}>
          Close
        </button>
      </div>

      <div className="grid" style={{ marginBottom: 16 }}>
        <div className="card">
          <h3>{explanation.result.final_score?.toFixed(3) ?? "—"}</h3>
          <p>FINAL SCORE</p>
        </div>

        <div className="card">
          <h3>{explanation.result.final_rank ?? "—"}</h3>
          <p>FINAL RANK</p>
        </div>

        <div className="card">
          <h3>{explanation.result.raw_rank ?? "—"}</h3>
          <p>RAW RANK</p>
        </div>

        <div className="card">
          <h3>
            {explanation.result.rank_displacement > 0
              ? `↑ ${explanation.result.rank_displacement}`
              : explanation.result.rank_displacement < 0
                ? `↓ ${Math.abs(explanation.result.rank_displacement)}`
                : "—"}
          </h3>
          <p>RANK DISPLACEMENT</p>
        </div>
      </div>

      <div className="state" style={{ marginBottom: 16 }}>
        <span className="mono">
          {explanation.algorithm}
          {" · "}
          shrinkage k={explanation.parameters.shrinkage_k}
          {" · "}
          minimum samples={explanation.parameters.min_samples}
        </span>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Judge</th>
              <th>Criterion</th>
              <th>Raw</th>
              <th>Judge μ</th>
              <th>Judge σ</th>
              <th>Global μ</th>
              <th>Global σ</th>
              <th>Scale</th>
              <th>Z</th>
              <th>Mode</th>
            </tr>
          </thead>

          <tbody>
            {explanation.explanations.map((x, i) => (
              <tr key={`${x.judge_id}-${x.criterion_id}-${i}`}>
                <td className="mono">{x.judge_id.slice(0, 8)}…</td>
                <td className="mono">{x.criterion_id.slice(0, 8)}…</td>
                <td className="mono">{x.raw_score.toFixed(2)}</td>
                <td className="mono">{x.judge_mean.toFixed(3)}</td>
                <td className="mono">{x.judge_stdev.toFixed(3)}</td>
                <td className="mono">{x.global_mean.toFixed(3)}</td>
                <td className="mono">{x.global_stdev.toFixed(3)}</td>
                <td className="mono">{x.scale.toFixed(3)}</td>
                <td className="mono">{x.z_score.toFixed(3)}</td>
                <td>
                  <span className="badge">{x.normalization}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  </div>
  
)}
        </div>
      )}


      {tab === "audit" && (
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
            <button onClick={loadAudit} disabled={!eventId}>Refresh</button>
            {audit && <span className={`badge ${audit.chain_valid ? "ok" : "err"}`}>chain {audit.chain_valid ? "valid" : "broken"}</span>}
          </div>

          {!audit && <div className="state">Hit Refresh to load the audit trail.</div>}

          {audit && !audit.chain_valid && (
            <div className="state state-error" style={{ marginBottom: 14 }}>
              ⚠ AUDIT CHAIN BROKEN — first invalid event: {audit.broken_at ? String(audit.broken_at).slice(0, 8) + "…" : "unknown"}
            </div>
          )}

          {audit && audit.events.length === 0 && <div className="state">No audit events recorded yet.</div>}

          {audit && audit.events.length > 0 && (
            <div className="chain-v">
              {audit.events.map((e, i) => {
                const broken = audit.broken_at && audit.events.slice(0, i + 1).some((ev) => ev.id === audit.broken_at);
                return (
                  <div key={e.id}>
                    <div className={`chain-node ${broken ? "broken" : ""}`} style={{ animationDelay: `${i * 40}ms` }}>
                      <b>#{e.seq} · {e.action}</b>
                      {e.id.slice(0, 8)}… · {new Date(e.created_at).toLocaleTimeString()} · actor {e.actor_id ? e.actor_id.slice(0, 8) : "—"} · {e.entity_type}
                    </div>
                    {i < audit.events.length - 1 && <div className={`chain-connector ${broken ? "broken" : ""}`} />}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {error && <p className="error">{error}</p>}
    </div>
  );
}
