import { useEffect, useState } from "react";
import { api } from "./api";
import Gallery from "./pages/Gallery";
import Login from "./pages/Login";
import ParticipantDashboard from "./pages/ParticipantDashboard";
import JudgeDeck from "./pages/JudgeDeck";
import MyRecord from "./pages/MyRecord";
import OrganizerConsole from "./pages/OrganizerConsole";
import { Logo, LoadingState } from "./ui";

function StatusIndicator({ apiOk, checked, auditState }) {
  const [open, setOpen] = useState(false);
  // Audit chain verdict wins once an organizer has loaded it; otherwise "did the last request succeed".
  let dot = "", label = "connecting…";
  if (auditState === "valid") { dot = "ok"; label = "audit chain valid"; }
  else if (auditState === "broken") { dot = "err"; label = "audit chain broken"; }
  else if (checked) { dot = apiOk ? "ok" : "err"; label = apiOk ? "api reachable" : "api unreachable"; }
  return (
    <div style={{ position: "relative" }}>
      <button className="status-pill" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <i className={`dot ${dot}`} />{label}
      </button>
      {open && (
        <div className="popover">
          <div><span>api</span><b>{checked ? (apiOk ? "connected" : "unreachable") : "checking…"}</b></div>
          <div><span>audit chain</span><b>{auditState === "valid" ? "valid" : auditState === "broken" ? "broken" : "not loaded"}</b></div>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [checked, setChecked] = useState(false);
  const [apiOk, setApiOk] = useState(true);
  const [view, setView] = useState("gallery");
  const [auditState, setAuditState] = useState(null);

  useEffect(() => {
    api.me()
      .then((u) => { setUser(u); setApiOk(true); })
      .catch((e) => { setUser(null); setApiOk(e.status !== undefined); })
      .finally(() => setChecked(true));
  }, []);

  async function logout() {
    try { await api.logout(); } catch { /* session may already be gone */ }
    setUser(null); setAuditState(null); setView("gallery");
  }

  if (!checked) return <main><LoadingState rows={3} /></main>;

  const role = user?.role;
  const isOrg = role === "organizer" || role === "admin";
  const Link = ({ id, children }) => (
    <button className={view === id ? "active" : ""} onClick={() => setView(id)} aria-current={view === id ? "page" : undefined}>{children}</button>
  );

  return (
    <div>
      <header className="topnav">
        <div className="nav-in">
          <button className="brand" onClick={() => setView("gallery")} aria-label="RAPTOR-OS home">
            <Logo /><span className="word">RAPTOR<b>·</b>OS</span>
          </button>
          <nav className="navlinks" aria-label="Primary">
            <Link id="gallery">Gallery</Link>
            {role === "participant" && <Link id="dashboard">My Project</Link>}
            {role === "judge" && <><Link id="judge">Judge Deck</Link><Link id="record">My Record</Link></>}
            {isOrg && <Link id="organizer">Mission Control</Link>}
          </nav>
          <div className="nav-right">
            <StatusIndicator apiOk={apiOk} checked={checked} auditState={auditState} />
            {user ? (
              <>
                <span className="who">{user.display_name} · {user.role}</span>
                <button onClick={logout}>Log out</button>
              </>
            ) : (
              <button className={view === "login" ? "primary" : ""} onClick={() => setView("login")}>Log in</button>
            )}
          </div>
        </div>
      </header>

      <main key={view}>
        {view === "gallery" && <Gallery user={user} auditState={auditState} onLogin={() => setView("login")} />}
        {view === "login" && <Login onLogin={(u) => { setUser(u); setView("gallery"); }} />}
        {view === "dashboard" && role === "participant" && <ParticipantDashboard />}
        {view === "judge" && role === "judge" && <JudgeDeck />}
        {view === "record" && role === "judge" && <MyRecord />}
        {view === "organizer" && isOrg && <OrganizerConsole onAuditLoaded={(valid) => setAuditState(valid ? "valid" : "broken")} />}
      </main>

      <footer>
        <span>RAPTOR-OS · role isolation enforced server-side · scores immutable once submitted</span>
        <span className="rev">AUDIT · SIGNED · APPEND-ONLY</span>
      </footer>
    </div>
  );
}
