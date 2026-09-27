import { useState } from "react";
import { api } from "../api";

export default function Login({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setError(null);
    try {
      const user = await api.login(email, password);
      const me = await api.me();
      onLogin(me);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div style={{ maxWidth: 360 }}>
      <h2>Log in</h2>
      <form onSubmit={submit}>
        <input placeholder="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input placeholder="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button className="primary" type="submit">Log in</button>
      </form>
      {error && <p className="error">{error}</p>}
      <p style={{ color: "var(--muted)", fontSize: "0.85em" }}>
        Seeded accounts: organizer@raptor.os / judgea@raptor.os / judgeb@raptor.os / participant@raptor.os
        (see README for passwords).
      </p>
    </div>
  );
}
