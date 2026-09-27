import { useEffect, useState } from "react";
import { api } from "../api";

export default function OrganizerConsole() {
  const [eventId, setEventId] = useState(null);
  const [eventName, setEventName] = useState(null);
  const [tab, setTab] = useState("mission-control");
  const [dashboard, setDashboard] = useState(null);
  const [rankings, setRankings] = useState(null);
  const [audit, setAudit] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.currentEvent()
      .then((ev) => { setEventId(ev.id); setEventName(ev.name); })
      .catch((e) => setError(e.message));
  }, []);

  async function loadDashboard() {
    setError(null);
    try { setDashboard(await api.dashboard(eventId)); } catch (e) { setError(e.message); }
  }
  async function runAssignment() {
    setError(null);
    try { await api.runAssignment(eventId); await loadDashboard(); } catch (e) { setError(e.message); }
  }
  async function runNormalization() {
    setError(null);
    try { await api.runNormalization(eventId); await loadRankings(); } catch (e) { setError(e.message); }
  }
  async function loadRankings() {
    setError(null);
    try { setRankings(await api.rankings(eventId)); } catch (e) { setError(e.message); }
  }
  async function loadAudit() {
    setError(null);
    try { setAudit(await api.audit(eventId)); } catch (e) { setError(e.message); }
  }

  return (
    <div>
      <h2>Mission Control</h2>
      <p style={{ color: "var(--muted)", fontSize: "0.8em" }}>
        {eventId ? `Event: ${eventName} (${eventId.slice(0, 8)}…)` : "Loading event…"}
      </p>

      <nav style={{ padding: 0, border: "none", marginBottom: 10 }}>
        {["mission-control", "rankings", "audit"].map((t) => (
          <button key={t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>{t}</button>
        ))}
      </nav>

      {tab === "mission-control" && (
        <div>
          <button onClick={loadDashboard} disabled={!eventId}>Refresh</button>{" "}
          <button onClick={runAssignment} disabled={!eventId}>Run assignment</button>{" "}
          <button onClick={runNormalization} disabled={!eventId}>Run normalization</button>{" "}
          <a href={eventId ? api.exportCsvUrl(eventId) : undefined}>
            <button disabled={!eventId}>Export CSV</button>
          </a>
          {dashboard && (
            <div className="grid" style={{ marginTop: 14 }}>
              <div className="card"><h3>{dashboard.projects_submitted}</h3><p>projects submitted</p></div>
              <div className="card"><h3>{dashboard.projects_with_min_reviews}</h3><p>projects with min reviews</p></div>
              <div className="card"><h3>{dashboard.reviews_completed} / {dashboard.reviews_assigned}</h3><p>reviews completed</p></div>
              <div className="card">
                <h3>Under-reviewed</h3>
                {dashboard.under_reviewed.length === 0 && <p>None</p>}
                {dashboard.under_reviewed.map((u) => (
                  <p key={u.project_id}>&#9888; {u.project_id.slice(0, 8)}… {u.reviews}/{u.target}</p>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "rankings" && (
        <div>
          <button onClick={loadRankings} disabled={!eventId}>Refresh</button>
          {rankings && (
            <table>
              <thead><tr><th>Rank</th><th>Project</th><th>Final</th><th>Raw rank</th><th>Displacement</th></tr></thead>
              <tbody>
                {rankings.rankings.map((r) => (
                  <tr key={r.project_id}>
                    <td>{r.final_rank !== null ? `#${r.final_rank}` : "—"}</td>
                    <td>{r.title}</td>
                    <td>
                      {r.insufficient_data || r.final_score === null
                        ? <span className="badge warn">insufficient data</span>
                        : r.final_score.toFixed(3)}
                    </td>
                    <td>{r.raw_rank !== null ? `#${r.raw_rank}` : "—"}</td>
                    <td style={{ color: (r.rank_displacement ?? 0) > 0 ? "var(--green)" : (r.rank_displacement ?? 0) < 0 ? "var(--red)" : "var(--muted)" }}>
                      {r.rank_displacement === null ? "—" : `${r.rank_displacement > 0 ? "+" : ""}${r.rank_displacement}`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === "audit" && (
        <div>
          <button onClick={loadAudit} disabled={!eventId}>Refresh</button>
          {audit && (
            <>
              <p>Chain valid: <span className={`badge ${audit.chain_valid ? "ok" : "err"}`}>{String(audit.chain_valid)}</span></p>
              <table>
                <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Entity</th></tr></thead>
                <tbody>
                  {audit.events.map((e) => (
                    <tr key={e.id}>
                      <td>{new Date(e.created_at).toLocaleTimeString()}</td>
                      <td>{e.actor_id?.slice(0, 8)}</td>
                      <td>{e.action}</td>
                      <td>{e.entity_type}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}

      {error && <p className="error">{error}</p>}
    </div>
  );
}
