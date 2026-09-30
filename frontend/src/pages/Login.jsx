import { useState } from "react";
import { api } from "../api";

export default function Login({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.login(email, password);
      const me = await api.me();
      onLogin(me);
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  }

  return (
    <div style={{ maxWidth: 360 }}>
      <span className="eyebrow">SESSION</span>
      <h2>Log in</h2>
      <form onSubmit={submit}>
        <input placeholder="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input placeholder="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button className="primary" type="submit" disabled={busy}>{busy ? "Signing in…" : "Log in"}</button>
      </form>
      {error && <p className="error">{error}</p>}
      <p className="mono" style={{ color: "var(--muted)", fontSize: "0.78em", marginTop: 12 }}>
        Seeded accounts: organizer@raptor.os / judgea@raptor.os / judgeb@raptor.os / participant@raptor.os
        (see README for passwords).
      </p>
    </div>
  );
}
