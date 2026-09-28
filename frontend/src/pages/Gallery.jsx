import { useEffect, useState } from "react";
import { api } from "../api";

const VOTER_ROLES = ["participant", "judge"];
const fmt = (iso) => (iso ? new Date(iso).toLocaleString() : "");

export default function Gallery({ user }) {
  const [projects, setProjects] = useState(null); // null = loading
  const [allTracks, setAllTracks] = useState([]);
  const [q, setQ] = useState("");
  const [track, setTrack] = useState("");
  const [sort, setSort] = useState("title-asc");
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState(null);

  // T3-lite. community.state is decided by the server (UTC), never the browser clock.
  const [community, setCommunity] = useState(null);
  const [ballot, setBallot] = useState(null);   // { ids, voted, limit } while OPEN and signed in
  const [results, setResults] = useState(null); // { projectId: votes } only after CLOSED
  const [voteMsg, setVoteMsg] = useState(null);
  const canVote = !!user && VOTER_ROLES.includes(user.role);
  const [comments, setComments] = useState(null);
  const [commentText, setCommentText] = useState("");
  const [commentMsg, setCommentMsg] = useState(null);

  // No /tracks endpoint exists -- the only honest source for the filter's
  // option list is whatever track_ids actually appear in the gallery.
  useEffect(() => {
    api.gallery({}).then((rows) => {
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
        api.ballot().then((b) => setBallot({
          ids: b.projects.map((p) => p.id),
          voted: b.voted_project_ids,
          limit: b.vote_limit,
        })).catch(() => setBallot(null));
      } else setBallot(null);
      if (c.state === "CLOSED") {
        api.communityResults().then((r) =>
          setResults(Object.fromEntries(r.results.map((x) => [x.project_id, x.votes])))
        ).catch(() => setResults(null));
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
    if (body.length < 1 || body.length > 500) {
      setCommentMsg("Comments must be 1 to 500 characters.");
      return;
    }
    try {
      const c = await api.postComment(selected.id, body);
      setComments((cs) => [...(cs || []), c]);
      setCommentText("");
    } catch (err) { setCommentMsg(err.message); }
  }

  // While OPEN and signed in, the server's per-voter order wins over any client sort.
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
    if (ballot.voted.includes(project.id)) return <span className="badge ok">voted</span>;
    const exhausted = ballot.voted.length >= ballot.limit;
    return (
      <button disabled={exhausted} onClick={(e) => castVote(e, project.id)}>
        {exhausted ? "Vote limit reached" : "Vote"}
      </button>
    );
  }

  if (selected) {
    return (
      <div>
        <button onClick={() => setSelected(null)}>&larr; back to gallery</button>
        <div className="head" style={{ marginTop: 16 }}>
          <div>
            <span className="eyebrow">PROJECT · {selected.id.slice(0, 8)}</span>
            <h2>{selected.title}</h2>
            <p style={{ color: "var(--muted)" }}>{selected.tagline}</p>
          </div>
          <span className="badge ok">submitted</span>
        </div>
        <p>{selected.description || "No description provided."}</p>
        <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
          {selected.demo_url && <button onClick={() => window.open(selected.demo_url, "_blank")}>View demo</button>}
          {selected.repo_url && <button onClick={() => window.open(selected.repo_url, "_blank")}>Repository</button>}
          {voteControl(selected)}
          {results && <span className="badge ok">{results[selected.id] ?? 0} votes</span>}
        </div>
        {voteMsg && <p className="error">{voteMsg}</p>}

        <h3 style={{ marginTop: 28 }}>Comments</h3>
        {comments === null && <div className="state">Loading comments…</div>}
        {comments && comments.length === 0 && <div className="state">No comments yet.</div>}
        {comments && comments.map((c) => (
          <div className="card" key={c.id} style={{ marginBottom: 8 }}>
            <p style={{ color: "var(--text)", margin: 0 }}>{c.body}</p>
            <div className="rowmeta"><span>{c.author}</span><span>{fmt(c.created_at)}</span></div>
          </div>
        ))}
        {user ? (
          <div style={{ marginTop: 12 }}>
            <textarea rows={3} maxLength={500} placeholder="Add a comment (1 to 500 characters)"
              value={commentText} onChange={(e) => setCommentText(e.target.value)} />
            <button onClick={postComment}>Post comment</button>
            {commentMsg && <p className="error">{commentMsg}</p>}
          </div>
        ) : (
          <p className="meta" style={{ marginTop: 12 }}>Log in to comment.</p>
        )}
      </div>
    );
  }

  return (
    <div>
      <div className="head">
        <div>
          <span className="eyebrow">PUBLIC GALLERY</span>
          <h2>{projects ? `${projects.length} SUBMISSIONS` : "Loading…"}</h2>
        </div>
      </div>

      {community && community.state !== "NOT_CONFIGURED" && (
        <div className="state" style={{ marginBottom: 14 }}>
          {community.state === "OPEN" && (
            <>
              <span className="badge ok">VOTING OPEN</span>{" "}closes {fmt(community.close_at)}.{" "}
              {ballot
                ? `Projects are in your own randomized order. ${ballot.voted.length} of ${ballot.limit} votes used.`
                : user ? "" : "Log in to vote."}
            </>
          )}
          {community.state === "NOT_OPEN" && (
            <><span className="badge warn">VOTING NOT OPEN</span>{" "}opens {fmt(community.open_at)}.</>
          )}
          {community.state === "CLOSED" && (
            <><span className="badge err">VOTING CLOSED</span>{" "}final vote totals are shown on each project.</>
          )}
          {voteMsg && <div className="error" style={{ marginTop: 6 }}>{voteMsg}</div>}
        </div>
      )}

      <div className="toolbar">
        <input placeholder="Search projects..." value={q} onChange={(e) => setQ(e.target.value)} />
        {allTracks.length > 0 && (
          <select value={track} onChange={(e) => setTrack(e.target.value)}>
            <option value="">All tracks</option>
            {allTracks.map((t) => <option key={t} value={t}>{t.slice(0, 8)}</option>)}
          </select>
        )}
        {!ballot && (
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="title-asc">Title A→Z</option>
            <option value="title-desc">Title Z→A</option>
            {results && <option value="votes">Most votes</option>}
          </select>
        )}
      </div>

      {projects === null && <div className="skeleton"><div className="skel-row" /><div className="skel-row" /><div className="skel-row" /></div>}

      {error && (
        <div className="state state-error">
          RAPTOR could not reach the gallery service.
          <div><button onClick={load}>Retry</button></div>
        </div>
      )}

      {sorted && sorted.length === 0 && !error && (
        <div className="state">No submitted projects yet. Check back once teams start submitting.</div>
      )}

      {sorted && sorted.length > 0 && (
        <div className="grid">
          {sorted.map((p) => (
            <div className="card clickable" key={p.id} onClick={() => setSelected(p)}>
              <h3>{p.title}</h3>
              <p>{p.tagline}</p>
              <div className="rowmeta">
                <span>{p.id.slice(0, 8)}</span>
                {results ? <span className="badge ok">{results[p.id] ?? 0} votes</span> : <span className="cta">VIEW PROJECT →</span>}
              </div>
              {voteControl(p) && <div style={{ marginTop: 10 }}>{voteControl(p)}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
