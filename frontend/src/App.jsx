import { useEffect, useState } from "react";
import { api } from "./api";
import Gallery from "./pages/Gallery";
import Login from "./pages/Login";
import ParticipantDashboard from "./pages/ParticipantDashboard";
import JudgeDeck from "./pages/JudgeDeck";
import OrganizerConsole from "./pages/OrganizerConsole";

export default function App() {
  const [user, setUser] = useState(null);
  const [checked, setChecked] = useState(false);
  const [view, setView] = useState("gallery");

  useEffect(() => {
    api.me().then(setUser).catch(() => setUser(null)).finally(() => setChecked(true));
  }, []);

  async function logout() {
    await api.logout();
    setUser(null);
    setView("gallery");
  }

  if (!checked) return null;

  return (
    <div>
      <nav>
        <b>RAPTOR-OS</b>
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
        <div style={{ marginLeft: "auto" }}>
          {user ? (
            <>
              <span style={{ marginRight: 10, color: "var(--muted)" }}>{user.display_name} ({user.role})</span>
              <button onClick={logout}>Log out</button>
            </>
          ) : (
            <button className={view === "login" ? "active" : ""} onClick={() => setView("login")}>Log in</button>
          )}
        </div>
      </nav>
      <main>
        {view === "gallery" && <Gallery />}
        {view === "login" && <Login onLogin={(u) => { setUser(u); setView("gallery"); }} />}
        {view === "dashboard" && user?.role === "participant" && <ParticipantDashboard />}
        {view === "judge" && user?.role === "judge" && <JudgeDeck />}
        {view === "organizer" && (user?.role === "organizer" || user?.role === "admin") && <OrganizerConsole />}
      </main>
    </div>
  );
}
