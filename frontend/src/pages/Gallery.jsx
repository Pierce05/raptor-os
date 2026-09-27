import { useEffect, useState } from "react";
import { api } from "../api";

export default function Gallery() {
  const [projects, setProjects] = useState([]);
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    api.gallery(q ? { q } : {}).then(setProjects).catch(() => setProjects([]));
  }, [q]);

  if (selected) {
    return (
      <div>
        <button onClick={() => setSelected(null)}>&larr; back to gallery</button>
        <h2>{selected.title}</h2>
        <p>{selected.tagline}</p>
        <p>{selected.description}</p>
        {selected.demo_url && <p><a href={selected.demo_url} target="_blank" rel="noreferrer">Demo</a></p>}
        {selected.repo_url && <p><a href={selected.repo_url} target="_blank" rel="noreferrer">Repository</a></p>}
      </div>
    );
  }

  return (
    <div>
      <h2>Public Gallery</h2>
      <input placeholder="Search projects..." value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="grid">
        {projects.map((p) => (
          <div className="card" key={p.id} onClick={() => setSelected(p)} style={{ cursor: "pointer" }}>
            <h3>{p.title}</h3>
            <p>{p.tagline}</p>
          </div>
        ))}
        {projects.length === 0 && <p>No submitted projects yet.</p>}
      </div>
    </div>
  );
}
