import { useEffect, useState } from "react";
import { api } from "./api";
import Gallery from "./pages/Gallery";
import Login from "./pages/Login";
import ParticipantDashboard from "./pages/ParticipantDashboard";
import JudgeDeck from "./pages/JudgeDeck";
import OrganizerConsole from "./pages/OrganizerConsole";

function StatusIndicator({ apiOk, checked, auditState }) {
  const [open, setOpen] = useState(false);

  // Prefer the audit chain's own verdict once we have one (organizer
  // has loaded the audit tab this session) -- the strongest honest
  // signal this shell can show. Otherwise fall back to "did the last
  // request succeed." Nothing here is invented.
  let dotClass = "idle", label = "connecting…";
  if (auditState === "valid") { dotClass = "ok"; label = "audit chain valid"; }
  else if (auditState === "broken") { dotClass = "err"; label = "audit chain broken"; }
  else if (checked) { dotClass = apiOk ? "ok" : "err"; label = apiOk ? "api reachable" : "api unreachable"; }

  return (
    <div style={{ position: "relative" }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{ display: "flex", alignItems: "center", gap: 7, fontSize: "0.66rem", padding: "6px 11px" }}
      >
        <span
          style={{
            width: 6, height: 6, borderRadius: "50%", flexShrink: 0,
            background: dotClass === "ok" ? "var(--cyan)" : dotClass === "err" ? "var(--crimson)" : "var(--muted)",
            boxShadow: dotClass === "ok" ? "0 0 0 3px rgba(63,168,143,.22)" : dotClass === "err" ? "0 0 0 3px rgba(184,32,47,.22)" : "none",
          }}
        />
        {label}
      </button>
      {open && (
        <div
          className="mono"
          style={{
            position: "absolute", top: "calc(100% + 8px)", right: 0, zIndex: 10,
            background: "var(--panel-2)", border: "1px solid var(--border)", minWidth: 220,
            fontSize: "0.68rem", color: "var(--muted)", padding: "12px 14px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
            <span>api</span><b style={{ color: "var(--text)" }}>{checked ? (apiOk ? "connected" : "unreachable") : "checking…"}</b>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
            <span>audit chain</span><b style={{ color: "var(--text)" }}>{auditState === "valid" ? "valid" : auditState === "broken" ? "broken" : "not loaded"}</b>
          </div>
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
  const [auditState, setAuditState] = useState(null); // "valid" | "broken" | null, set by OrganizerConsole from a real response

  useEffect(() => {
    api.me()
      .then((u) => { setUser(u); setApiOk(true); })
      .catch((e) => { setUser(null); setApiOk(e.status !== undefined); })
      .finally(() => setChecked(true));
  }, []);

  async function logout() {
    await api.logout();
    setUser(null);
    setAuditState(null);
    setView("gallery");
  }

  if (!checked) {
    return (
      <div style={{ padding: 40 }}>
        <div className="skeleton"><div className="skel-row" /><div className="skel-row" /><div className="skel-row" /></div>
      </div>
    );
  }

  return (
    <div>
      <nav>
        <b>RAPTOR-OS</b>
        <StatusIndicator apiOk={apiOk} checked={checked} auditState={auditState} />
        <button className={view === "gallery" ? "active" : ""} onClick={() => setView("gallery")}>Gallery</button>
        {user?.role === "participant" && (
          <button className={view === "dashboard" ? "active" : ""} onClick={() => setView("dashboard")}>My Project</button>
        )}
        {user?.role === "judge" && (
          <button className={view === "judge" ? "active" : ""} onClick={() => setView("judge")}>Judge Deck</button>
        )}
        {(user?.role === "organizer" || user?.role === "admin") && (
          <button className={view === "organizer" ? "active" : ""} onClick={() => setView("organizer")}>Mission Control</button>
        )}
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12 }}>
          {user ? (
            <>
              <span className="badge ok mono">{user.display_name} · {user.role}</span>
              <button onClick={logout}>Log out</button>
            </>
          ) : (
            <button className={view === "login" ? "active" : ""} onClick={() => setView("login")}>Log in</button>
          )}
        </div>
      </nav>

      <main key={view}>
        {view === "gallery" && <Gallery />}
        {view === "login" && <Login onLogin={(u) => { setUser(u); setView("gallery"); }} />}
        {view === "dashboard" && user?.role === "participant" && <ParticipantDashboard />}
        {view === "judge" && user?.role === "judge" && <JudgeDeck />}
        {view === "organizer" && (user?.role === "organizer" || user?.role === "admin") && (
          <OrganizerConsole onAuditLoaded={(valid) => setAuditState(valid ? "valid" : "broken")} />
        )}
      </main>

      <footer>RAPTOR-OS · role isolation enforced server-side · scores immutable once submitted</footer>
    </div>
  );
}
