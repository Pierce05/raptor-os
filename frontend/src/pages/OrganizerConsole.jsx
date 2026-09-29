import { useEffect, useState, useCallback } from "react";
import { api } from "../api";
import { fmt, short, MetricStrip, Panel, Progress, StatusBadge, AuditIndicator, LoadingState, EmptyState, ErrorState, PageHead } from "../ui";

const time = (iso) => (iso ? new Date(iso).toLocaleTimeString() : "");

function Delta({ v }) {
  if (v === null || v === undefined || v === 0) return <span className="delta flat">—</span>;
  return v > 0 ? <span className="delta up">↑ {v}</span> : <span className="delta down">↓ {Math.abs(v)}</span>;
}

export default function OrganizerConsole({ onAuditLoaded }) {
  const [eventId, setEventId] = useState(null);
  const [eventName, setEventName] = useState(null);
  const [eventError, setEventError] = useState(null);
  const [tab, setTab] = useState("mission-control");
  const [dashboard, setDashboard] = useState(null);
  const [rankings, setRankings] = useState(null);
  const [audit, setAudit] = useState(null);
  const [community, setCommunity] = useState(undefined); // undefined loading, null unavailable
  const [explanation, setExplanation] = useState(null);
  const [explanationLoading, setExplanationLoading] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [lastSync, setLastSync] = useState(null);

  useEffect(() => {
    api.currentEvent().then((ev) => { setEventId(ev.id); setEventName(ev.name); }).catch((e) => setEventError(e.message));
  }, []);

  const loadDashboard = useCallback(async () => {
    if (!eventId) return;
    setError(null); setBusy(true);
    try { setDashboard(await api.dashboard(eventId)); setLastSync(new Date().toLocaleTimeString()); } catch (e) { setError(e.message); }
    setBusy(false);
  }, [eventId]);

  const loadAudit = useCallback(async () => {
    if (!eventId) return;
    try {
      const a = await api.audit(eventId);
      setAudit(a);
      onAuditLoaded?.(a.chain_valid);
    } catch (e) { setError(e.message); }
  }, [eventId]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadCommunity = useCallback(() => {
    api.communitySummary().then(setCommunity).catch(() => setCommunity(null));
  }, []);

  const loadRankings = useCallback(async () => {
    if (!eventId) return;
    setError(null);
    try { setRankings(await api.rankings(eventId)); } catch (e) { setError(e.message); }
  }, [eventId]);

  // Mission Control is a live view: everything loads on arrival and re-polls.
  useEffect(() => {
    if (!eventId) return;
    loadDashboard(); loadAudit(); loadCommunity();
    const t = setInterval(() => { loadDashboard(); loadAudit(); loadCommunity(); }, 20000);
    return () => clearInterval(t);
  }, [eventId, loadDashboard, loadAudit, loadCommunity]);

  async function runAssignment() {
    setError(null); setBusy(true);
    try { await api.runAssignment(eventId); await loadDashboard(); await loadAudit(); } catch (e) { setError(e.message); }
    setBusy(false);
  }
  async function runNormalization() {
    setError(null); setBusy(true);
    try { await api.runNormalization(eventId); await loadRankings(); await loadAudit(); } catch (e) { setError(e.message); }
    setBusy(false);
  }
  async function loadExplanation(projectId) {
    setError(null); setExplanationLoading(true);
    try { setExplanation(await api.rankingExplanation(projectId, eventId)); }
    catch (e) { setError(e.message); }
    finally { setExplanationLoading(false); }
  }

  function selectTab(t) {
    setTab(t);
    if (t === "audit" && eventId) loadAudit();
    if (t === "rankings" && !rankings && eventId) loadRankings();
  }

  useEffect(() => {
    if (!explanation) return;
    const onKey = (e) => { if (e.key === "Escape") setExplanation(null); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [explanation]);

  const coverage = dashboard && dashboard.reviews_assigned ? Math.round((dashboard.reviews_completed / dashboard.reviews_assigned) * 100) : null;
  const judgeLoad = dashboard ? Object.entries(dashboard.judge_load || {}) : [];
  const maxLoad = Math.max(1, ...judgeLoad.map(([, n]) => n));
  const brokenCount = audit ? (audit.chain_valid ? 0 : 1) : null;
  const health = !audit ? null : audit.chain_valid && (!dashboard || dashboard.under_reviewed.length === 0) ? "NOMINAL" : audit.chain_valid ? "ATTENTION" : "CHAIN BROKEN";

  return (
    <div>
      <PageHead eyebrow="MISSION CONTROL" title={eventName || "Loading event…"}
        right={
          <div className="row">
            {health && <StatusBadge tone={health === "NOMINAL" ? "ok" : health === "ATTENTION" ? "warn" : "err"}><i className={`dot ${health === "NOMINAL" ? "ok" : health === "ATTENTION" ? "warn" : "err"}`} />EVENT {health}</StatusBadge>}
            {eventId && <span className="meta">{short(eventId)}… {lastSync && `· synced ${lastSync}`}</span>}
          </div>
        } />

      {eventError && <ErrorState>{eventError}</ErrorState>}

      <div className="toolbar" role="tablist">
        {[["mission-control", "Mission control"], ["rankings", "Rankings"], ["audit", "Audit chain"]].map(([t, l]) => (
          <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "active" : ""} onClick={() => selectTab(t)}>{l}</button>
        ))}
      </div>

      {tab === "mission-control" && (
        <div className="stack">
          <div className="row">
            <button onClick={loadDashboard} disabled={!eventId || busy}>Refresh</button>
            <button onClick={runAssignment} disabled={!eventId || busy}>Run assignment</button>
            <button onClick={runNormalization} disabled={!eventId || busy}>Run normalization</button>
            <button
              onClick={async () => {
                setError(null);
                setBusy(true);
                try {
                  const result = await api.issueJudgeRecords();
                  setSuccess(
                    `✓ Judge records issued: ${result.issued?.length || 0} · skipped: ${result.skipped?.length || 0}`
                  );
                } catch (e) {
                  setError(e.message);
                } finally {
                  setBusy(false);
                }
              }}
              disabled={busy}
            >
              Issue Judge Records
            </button>
            <a className="btn" href={eventId ? api.exportCsvUrl(eventId) : undefined} aria-disabled={!eventId}>Export CSV ↓</a>
          </div>

          {!dashboard && !error && <LoadingState rows={2} />}

          {dashboard && (
            <>
              <MetricStrip items={[
                { value: dashboard.projects_submitted, label: "SUBMISSIONS" },
                { value: judgeLoad.length, label: "JUDGES ACTIVE" },
                { value: dashboard.reviews_assigned, label: "REVIEWS ASSIGNED" },
                { value: dashboard.reviews_completed, label: "REVIEWS COMPLETED" },
                { value: dashboard.under_reviewed.length, label: "UNDER-REVIEWED", tone: dashboard.under_reviewed.length ? "err" : "ok" },
                ...(brokenCount !== null ? [{ value: brokenCount, label: "AUDIT BREAKS", tone: brokenCount ? "err" : "ok" }] : []),
              ]} />

              <div className="cols-2">
                <Panel title="JUDGING PROGRESS" right={coverage !== null ? `${coverage}%` : ""} accent>
                  {coverage !== null
                    ? <Progress thick crimson pct={coverage} label={`${dashboard.reviews_completed} of ${dashboard.reviews_assigned} REVIEWS SUBMITTED`} />
                    : <EmptyState>No reviews assigned yet. Run assignment to build the queues.</EmptyState>}
                  <p className="meta" style={{ marginTop: 14 }}>{dashboard.projects_with_min_reviews} of {dashboard.projects_submitted} projects have reached the minimum review count.</p>

                  {dashboard.under_reviewed.length > 0 && (
                    <div style={{ marginTop: 16 }}>
                      <div className="label" style={{ marginBottom: 6 }}>UNDER-REVIEWED</div>
                      {dashboard.under_reviewed.map((u) => (
                        <div key={u.project_id} className="feed-row" style={{ gridTemplateColumns: "1fr auto" }}>
                          <span>⚠ {short(u.project_id)}…</span><b>{u.reviews}/{u.target}</b>
                        </div>
                      ))}
                    </div>
                  )}
                </Panel>

                <Panel title="AUDIT CHAIN">
                  {!audit ? <LoadingState rows={1} /> : (
                    <>
                      <div className={`big ${audit.chain_valid ? "ok" : "err"}`}>{audit.chain_valid ? "VALID" : "BROKEN"}</div>
                      <p className="meta">{audit.events.length} events{audit.events.length > 0 && ` · head #${audit.events[audit.events.length - 1].seq}`}</p>
                      {!audit.chain_valid && <p className="error">First invalid event: {audit.broken_at ? short(audit.broken_at) + "…" : "unknown"}</p>}
                    </>
                  )}
                </Panel>
              </div>

              <div className="cols-2">
                <Panel title="RECENT ACTIVITY" right="from audit chain">
                  {!audit && <LoadingState rows={2} />}
                  {audit && audit.events.length === 0 && <EmptyState>No audit events yet.</EmptyState>}
                  {audit && audit.events.length > 0 && (
                    <div className="feed">
                      {[...audit.events].slice(-8).reverse().map((e) => (
                        <div className="feed-row" key={e.id}>
                          <span>{time(e.created_at)}</span><b>{e.action}</b><span>#{e.seq}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </Panel>

                <div className="stack">
                  <Panel title="COMMUNITY">
                    {community === undefined && <LoadingState rows={1} />}
                    {community === null && <p className="meta">Community summary unavailable.</p>}
                    {community && (
                      <>
                        <StatusBadge tone={community.state === "OPEN" ? "ok" : community.state === "CLOSED" ? "err" : "warn"}>{String(community.state).replace("_", " ")}</StatusBadge>
                        <div className="big" style={{ marginTop: 12 }}>{community.total_votes}</div>
                        <p className="meta">{community.unique_voters} voters · {community.comment_count} comments</p>
                        {community.close_at && <p className="meta">closes {fmt(community.close_at)}</p>}
                        {community.top_projects?.length > 0 && community.top_projects.map((t) => (
                          <div className="feed-row" key={t.project_id} style={{ gridTemplateColumns: "1fr auto" }}><span>{t.title}</span><b>{t.votes}</b></div>
                        ))}
                      </>
                    )}
                  </Panel>

                  <Panel title="JUDGE LOAD" right={`${judgeLoad.length} judges`}>
                    {judgeLoad.length === 0 && <p className="meta">No assignments yet.</p>}
                    {judgeLoad.map(([id, n]) => (
                      <div key={id} style={{ marginBottom: 8 }}>
                        <Progress pct={(n / maxLoad) * 100} label={`${short(id)}…`} right={n} />
                      </div>
                    ))}
                  </Panel>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {tab === "rankings" && (
        <div>
          <div className="row" style={{ marginBottom: 14 }}>
            <button onClick={loadRankings} disabled={!eventId}>Refresh</button>
            <button onClick={runNormalization} disabled={!eventId || busy}>Run normalization</button>
            {rankings && <span className="meta">run {short(rankings.run_id)}…</span>}
          </div>
          {!rankings && <EmptyState>Run normalization first, then refresh.</EmptyState>}
          {rankings && (
            <Panel accent>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Rank</th><th>Project</th><th>Final</th><th>Raw rank</th><th>Δ</th><th></th></tr></thead>
                  <tbody>
                    {rankings.rankings.map((r) => {
                      const scores = rankings.rankings.map((x) => x.final_score).filter((x) => typeof x === "number");
                      const max = Math.max(...scores, 0.0001), min = Math.min(...scores, 0);
                      const pct = typeof r.final_score === "number" ? ((r.final_score - min) / ((max - min) || 1)) * 100 : 0;
                      return (
                        <tr key={r.project_id} className={r.final_rank === 1 ? "top1" : ""}>
                          <td className="mono">{r.final_rank !== null ? String(r.final_rank).padStart(2, "0") : "—"}</td>
                          <td>{r.title}</td>
                          <td className="mono">
                            {r.insufficient_data || r.final_score === null
                              ? <StatusBadge tone="warn">insufficient data</StatusBadge>
                              : <>{r.final_score.toFixed(3)}<span className="minibar"><i style={{ width: Math.max(4, pct) + "%" }} /></span></>}
                          </td>
                          <td className="mono">{r.raw_rank !== null ? `#${r.raw_rank}` : "—"}</td>
                          <td><Delta v={r.rank_displacement} /></td>
                          <td>
                            {r.insufficient_data ? <span className="meta">—</span> : <button onClick={() => loadExplanation(r.project_id)} disabled={explanationLoading}>Explain →</button>}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}
        </div>
      )}

      {tab === "audit" && (
        <div>
          <div className="row" style={{ marginBottom: 14 }}>
            <button onClick={loadAudit} disabled={!eventId}>Refresh</button>
            <AuditIndicator state={audit ? (audit.chain_valid ? "valid" : "broken") : null} />
            {audit && <span className="meta">{audit.events.length} events</span>}
          </div>
          {!audit && <EmptyState>Loading the audit trail…</EmptyState>}
          {audit && !audit.chain_valid && (
            <div className="confirm bad"><b>⚠ AUDIT CHAIN BROKEN</b>First invalid event: {audit.broken_at ? String(audit.broken_at).slice(0, 8) + "…" : "unknown"}</div>
          )}
          {audit && audit.events.length === 0 && <EmptyState>No audit events recorded yet.</EmptyState>}
          {audit && audit.events.length > 0 && (
            <div className="chain-v">
              {audit.events.map((e, i) => {
                const broken = audit.broken_at && audit.events.slice(0, i + 1).some((ev) => ev.id === audit.broken_at);
                return (
                  <div key={e.id}>
                    <div className={`chain-node ${broken ? "broken" : ""}`} style={{ animationDelay: `${Math.min(i, 20) * 40}ms` }}>
                      <b>#{e.seq} · {e.action}</b>
                      {short(e.id)}… · {time(e.created_at)} · actor {e.actor_id ? short(e.actor_id) : "—"} · {e.entity_type}
                    </div>
                    {i < audit.events.length - 1 && <div className={`chain-connector ${broken ? "broken" : ""}`} />}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {error && <p className="error" role="alert">{error}</p>}
      {explanation && <ExplainDrawer x={explanation} onClose={() => setExplanation(null)} />}
    </div>
  );
}

function ExplainDrawer({ x, onClose }) {
  const r = x.result || {};
  // Group the provenance rows by judge -- purely a regrouping of what the API returned.
  const byJudge = new Map();
  for (const e of x.explanations) {
    if (!byJudge.has(e.judge_id)) byJudge.set(e.judge_id, []);
    byJudge.get(e.judge_id).push(e);
  }
  const maxAbsZ = Math.max(0.0001, ...x.explanations.map((e) => Math.abs(e.z_score)));
  return (
    <div className="overlay" onClick={onClose}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-label="Ranking explanation" onClick={(e) => e.stopPropagation()}>
        <div className="head">
          <div>
            <span className="eyebrow">RANKING EXPLANATION</span>
            <h2 style={{ margin: 0 }}>Why this project ranked here</h2>
            <p className="meta" style={{ marginTop: 6 }}>project {short(x.project_id)}… · run {short(x.run_id)}…</p>
          </div>
          <button onClick={onClose} autoFocus>Close ✕</button>
        </div>

        <div className="hero-score">
          <div><div className="big">{typeof r.final_score === "number" ? r.final_score.toFixed(3) : "—"}</div><span className="label">FINAL SCORE</span></div>
          <div><div className="big">{r.final_rank ?? "—"}</div><span className="label">FINAL RANK</span></div>
          <div><div className="big">{r.raw_rank ?? "—"}</div><span className="label">RAW RANK</span></div>
          <div><div className="big"><Delta v={r.rank_displacement} /></div><span className="label">MOVEMENT</span></div>
        </div>

        <div className="banner">
          <span>{x.algorithm}</span><span>· shrinkage k={x.parameters?.shrinkage_k}</span><span>· min samples={x.parameters?.min_samples}</span>
          <span>· {byJudge.size} judges · {x.explanations.length} score inputs</span>
        </div>

        {x.explanations.length === 0 && <EmptyState>No per-score explanations recorded for this project.</EmptyState>}

        <div className="label" style={{ margin: "18px 0 8px" }}>SCORE PROVENANCE · BY JUDGE</div>
        {[...byJudge.entries()].map(([judge, rows]) => (
          <div className="judge-group" key={judge}>
            <div className="jh"><b>JUDGE {short(judge)}…</b><span>{rows.length} criteria</span></div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Criterion</th><th>Raw</th><th>Judge μ</th><th>Judge σ</th><th>Global μ</th><th>Global σ</th><th>Scale</th><th>Z</th><th>Mode</th></tr></thead>
                <tbody>
                  {rows.map((e, i) => (
                    <tr key={`${e.criterion_id}-${i}`}>
                      <td className="mono">{short(e.criterion_id)}…</td>
                      <td className="mono">{e.raw_score.toFixed(2)}</td>
                      <td className="mono">{e.judge_mean.toFixed(3)}</td>
                      <td className="mono">{e.judge_stdev.toFixed(3)}</td>
                      <td className="mono">{e.global_mean.toFixed(3)}</td>
                      <td className="mono">{e.global_stdev.toFixed(3)}</td>
                      <td className="mono">{e.scale.toFixed(3)}</td>
                      <td className="mono" style={{ color: e.z_score < 0 ? "var(--red)" : "var(--cyan)" }}>{e.z_score.toFixed(3)}
                        <span className="minibar"><i style={{ width: (Math.abs(e.z_score) / maxAbsZ) * 100 + "%", background: e.z_score < 0 ? "var(--red)" : "var(--cyan)" }} /></span></td>
                      <td><StatusBadge>{e.normalization}</StatusBadge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </aside>
    </div>
  );
}
