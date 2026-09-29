import { useEffect, useState } from "react";
import { api } from "../api";
import { fmt, short, MetricStrip, Radar, StatusBadge, LoadingState, EmptyState, ErrorState, Panel } from "../ui";

const VOTER_ROLES = ["participant", "judge"];

export default function Gallery({ user, auditState }) {
  const [projects, setProjects] = useState(null);
  const [total, setTotal] = useState(null);
  const [allTracks, setAllTracks] = useState([]);
  const [q, setQ] = useState("");
  const [track, setTrack] = useState("");
  const [sort, setSort] = useState("title-asc");
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState(null);

  const [community, setCommunity] = useState(null);
  const [ballot, setBallot] = useState(null);
  const [results, setResults] = useState(null);
  const [voteMsg, setVoteMsg] = useState(null);
  const canVote = !!user && VOTER_ROLES.includes(user.role);
  const [comments, setComments] = useState(null);
  const [commentText, setCommentText] = useState("");
  const [commentMsg, setCommentMsg] = useState(null);

  // No /tracks endpoint exists: the filter options are the track_ids that appear in the gallery.
  useEffect(() => {
    api.gallery({}).then((rows) => {
      setTotal(rows.length);
      setAllTracks([...new Set(rows.map((r) => r.track_id).filter(Boolean))]);
    }).catch(() => {});
  }, []);

  function load() {
    setError(null);
    const params = {};
    if (q) params.q = q;
    if (track) params.track_id = track;
    api.gallery(params).then(setProjects).catch((e) => { setError(e.message); setProjects([]); });
  }
  useEffect(load, [q, track]);

  function loadCommunity() {
    api.communityStatus().then((c) => {
      setCommunity(c);
      if (c.state === "OPEN" && user) {
        api.ballot().then((b) => setBallot({ ids: b.projects.map((p) => p.id), voted: b.voted_project_ids, limit: b.vote_limit })).catch(() => setBallot(null));
      } else setBallot(null);
      if (c.state === "CLOSED") {
        api.communityResults().then((r) => setResults(Object.fromEntries(r.results.map((x) => [x.project_id, x.votes])))).catch(() => setResults(null));
      } else setResults(null);
    }).catch(() => setCommunity(null));
  }
  useEffect(loadCommunity, [user?.id]);

  useEffect(() => {
    setComments(null); setCommentText(""); setCommentMsg(null);
    if (selected) api.comments(selected.id).then(setComments).catch(() => setComments([]));
  }, [selected?.id]);

  async function castVote(e, projectId) {
    e.stopPropagation();
    setVoteMsg(null);
    try {
      const r = await api.castVote(projectId);
      setBallot((b) => (b ? { ...b, voted: r.voted_project_ids } : b));
    } catch (err) { setVoteMsg(err.message); }
  }

  async function postComment() {
    setCommentMsg(null);
    const body = commentText.trim();
    if (body.length < 1 || body.length > 500) { setCommentMsg("Comments must be 1 to 500 characters."); return; }
    try {
      const c = await api.postComment(selected.id, body);
      setComments((cs) => [...(cs || []), c]);
      setCommentText("");
    } catch (err) { setCommentMsg(err.message); }
  }

  const ballotRank = ballot ? new Map(ballot.ids.map((id, i) => [id, i])) : null;
  const sorted = projects
    ? [...projects].sort((a, b) => {
        if (ballotRank) return (ballotRank.get(a.id) ?? 0) - (ballotRank.get(b.id) ?? 0);
        if (results && sort === "votes") return (results[b.id] ?? 0) - (results[a.id] ?? 0);
        return sort === "title-asc" ? a.title.localeCompare(b.title) : b.title.localeCompare(a.title);
      })
    : null;

  function voteControl(project) {
    if (!community || community.state !== "OPEN") return null;
    if (!user) return <span className="meta">Log in to vote</span>;
    if (!canVote || !ballot) return null;
    if (ballot.voted.includes(project.id)) return <StatusBadge tone="ok">✓ voted</StatusBadge>;
    const exhausted = ballot.voted.length >= ballot.limit;
    return <button className={exhausted ? "" : "primary"} disabled={exhausted} onClick={(e) => castVote(e, project.id)}>{exhausted ? "Vote limit reached" : "Vote"}</button>;
  }

  /* ---------- project dossier ---------- */
  if (selected) {
    return (
      <div>
        <button className="ghost" onClick={() => setSelected(null)}>← GALLERY</button>
        <div style={{ marginTop: 28 }}>
          <span className="eyebrow">PROJECT DOSSIER · {short(selected.id)}</span>
          <h1 className="dossier-title">{selected.title}</h1>
          <p style={{ color: "var(--muted)", fontSize: "1.05rem", maxWidth: "60ch" }}>{selected.tagline}</p>
          <div className="row" style={{ marginTop: 14 }}>
            <StatusBadge tone="ok">{selected.status || "submitted"}</StatusBadge>
            {selected.track_id && <StatusBadge>TRACK {short(selected.track_id)}</StatusBadge>}
            {results && <StatusBadge tone="ok">{results[selected.id] ?? 0} votes</StatusBadge>}
          </div>
        </div>

        <div className="cols-2" style={{ marginTop: 32 }}>
          <div className="stack">
            <Panel title="DESCRIPTION" accent>
              <p style={{ whiteSpace: "pre-wrap" }}>{selected.description || "No description provided."}</p>
            </Panel>

            <Panel title="COMMENTS" right={comments ? `${comments.length}` : ""}>
              {comments === null && <LoadingState rows={1} />}
              {comments && comments.length === 0 && <EmptyState>No comments yet.</EmptyState>}
              {comments && comments.map((c) => (
                <div key={c.id} style={{ borderBottom: "1px solid var(--border)", padding: "10px 0" }}>
                  <p style={{ margin: 0 }}>{c.body}</p>
                  <div className="meta" style={{ marginTop: 4 }}>{c.author} · {fmt(c.created_at)}</div>
                </div>
              ))}
              {user ? (
                <div style={{ marginTop: 14 }}>
                  <textarea rows={3} maxLength={500} placeholder="Add a comment (1 to 500 characters)" aria-label="Comment" value={commentText} onChange={(e) => setCommentText(e.target.value)} />
                  <div className="row"><button onClick={postComment}>Post comment</button><span className="meta">{commentText.length}/500</span></div>
                  {commentMsg && <p className="error" role="alert">{commentMsg}</p>}
                </div>
              ) : <p className="meta" style={{ marginTop: 12 }}>Log in to comment.</p>}
            </Panel>
          </div>

          <div className="stack" style={{ alignContent: "start" }}>
            <Panel title="LINKS">
              <div className="stack" style={{ gap: 10 }}>
                {selected.demo_url ? <button onClick={() => window.open(selected.demo_url, "_blank")}>Live demo ↗</button> : <span className="meta">No demo link.</span>}
                {selected.repo_url ? <button onClick={() => window.open(selected.repo_url, "_blank")}>Repository ↗</button> : <span className="meta">No repository link.</span>}
              </div>
            </Panel>
            {community && community.state !== "NOT_CONFIGURED" && (
              <Panel title="COMMUNITY VOTE">
                <div className="row">
                  <StatusBadge tone={community.state === "OPEN" ? "ok" : community.state === "CLOSED" ? "err" : "warn"}>{community.state.replace("_", " ")}</StatusBadge>
                  {voteControl(selected)}
                </div>
                {voteMsg && <p className="error" role="alert">{voteMsg}</p>}
              </Panel>
            )}
          </div>
        </div>
      </div>
    );
  }

  /* ---------- gallery ---------- */
  const votesTotal = results ? Object.values(results).reduce((a, b) => a + b, 0) : null;
  const strip = [
    { value: total ?? "—", label: "SUBMISSIONS" },
    { value: allTracks.length, label: "TRACKS" },
    { value: community && community.state !== "NOT_CONFIGURED" ? community.state.replace("_", " ") : "—", label: "COMMUNITY VOTING", tone: community?.state === "OPEN" ? "ok" : "" },
  ];
  if (votesTotal !== null) strip.push({ value: votesTotal, label: "TOTAL VOTES" });
  else if (ballot) strip.push({ value: `${ballot.voted.length}/${ballot.limit}`, label: "YOUR VOTES USED" });
  if (auditState) strip.push({ value: auditState === "valid" ? "VALID" : "BROKEN", label: "AUDIT CHAIN", tone: auditState === "valid" ? "ok" : "err" });

  return (
    <div>
      <section className="hero">
        <div className="hero-grid">
          <div>
            <span className="eyebrow rise" style={{ animationDelay: "80ms" }}>PUBLIC GALLERY</span>
            <h1 className="rise" style={{ animationDelay: "180ms" }}>Judging you<br />can <span className="cut" style={{ color: "var(--crimson)" }}>explain.</span></h1>
            <p className="lede rise" style={{ animationDelay: "320ms" }}>A hackathon operating system built like it expects to be audited — every role has a door, every score has an owner, every judgment leaves evidence.</p>
          </div>
          <Radar dots={total || 0} />
        </div>
        <MetricStrip items={strip} />
      </section>

      <div className="ghead">
        <h2>Public Gallery</h2>
        <span className="meta">{projects ? `${projects.length} submissions` : "loading…"}</span>
      </div>

      {community && community.state !== "NOT_CONFIGURED" && (
        <div className={`banner ${community.state === "NOT_OPEN" ? "warn" : community.state === "CLOSED" ? "err" : ""}`}>
          {community.state === "OPEN" && (<><StatusBadge tone="ok">VOTING OPEN</StatusBadge><span>closes {fmt(community.close_at)}.{" "}
            {ballot ? `Projects are in your own randomized order. ${ballot.voted.length} of ${ballot.limit} votes used.` : user ? "" : "Log in to vote."}</span></>)}
          {community.state === "NOT_OPEN" && (<><StatusBadge tone="warn">VOTING NOT OPEN</StatusBadge><span>opens {fmt(community.open_at)}.</span></>)}
          {community.state === "CLOSED" && (<><StatusBadge tone="err">VOTING CLOSED</StatusBadge><span>final vote totals are shown on each project.</span></>)}
          {voteMsg && <span className="error" style={{ margin: 0 }}>{voteMsg}</span>}
        </div>
      )}

      <div className="searchbar">
        <div className="field">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#948c80" strokeWidth="2" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></svg>
          <input placeholder="Search projects" aria-label="Search projects" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        {allTracks.length > 0 && (
          <select aria-label="Track" value={track} onChange={(e) => setTrack(e.target.value)}>
            <option value="">All tracks</option>
            {allTracks.map((t) => <option key={t} value={t}>{t.slice(0, 8)}</option>)}
          </select>
        )}
        {!ballot && (
          <select aria-label="Sort" value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="title-asc">Title A→Z</option>
            <option value="title-desc">Title Z→A</option>
            {results && <option value="votes">Most votes</option>}
          </select>
        )}
      </div>

      {projects === null && <LoadingState />}
      {error && <ErrorState onRetry={load}>RAPTOR could not reach the gallery service.</ErrorState>}
      {sorted && sorted.length === 0 && !error && <EmptyState>No submitted projects yet. Check back once teams start submitting.</EmptyState>}

      {sorted && sorted.length > 0 && (
        <div className="list">
          {sorted.map((p, i) => (
            <div className="item" key={p.id} role="button" tabIndex={0} style={{ animationDelay: `${Math.min(i, 8) * 55}ms` }}
              onClick={() => setSelected(p)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelected(p); } }}>
              <span className="chip">{String(i + 1).padStart(2, "0")}</span>
              <div className="col-main">
                <h3>{p.title}</h3>
                <p>{p.tagline}</p>
                <div className="tags">
                  <span>{short(p.id)}</span>
                  {p.track_id && <span>TRACK {short(p.track_id, 6)}</span>}
                  <span style={{ color: "var(--cyan)" }}>● {p.status}</span>
                  {p.demo_url && <span>DEMO</span>}
                  {p.repo_url && <span>REPO</span>}
                </div>
              </div>
              <div className="side">
                {results && <StatusBadge tone="ok">{results[p.id] ?? 0} votes</StatusBadge>}
                {voteControl(p)}
                <span className="arrow">→</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
