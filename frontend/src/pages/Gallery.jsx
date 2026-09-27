import { useEffect, useState } from "react";
import { api } from "../api";

export default function Gallery() {
  const [projects, setProjects] = useState(null); // null = loading
  const [allTracks, setAllTracks] = useState([]);
  const [q, setQ] = useState("");
  const [track, setTrack] = useState("");
  const [sort, setSort] = useState("title-asc");
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState(null);

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

  const sorted = projects
    ? [...projects].sort((a, b) => sort === "title-asc" ? a.title.localeCompare(b.title) : b.title.localeCompare(a.title))
    : null;

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
        </div>
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

      <div className="toolbar">
        <input placeholder="Search projects..." value={q} onChange={(e) => setQ(e.target.value)} />
        {allTracks.length > 0 && (
          <select value={track} onChange={(e) => setTrack(e.target.value)}>
            <option value="">All tracks</option>
            {allTracks.map((t) => <option key={t} value={t}>{t.slice(0, 8)}</option>)}
          </select>
        )}
        <select value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="title-asc">Title A→Z</option>
          <option value="title-desc">Title Z→A</option>
        </select>
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
                <span className="cta">VIEW PROJECT →</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
