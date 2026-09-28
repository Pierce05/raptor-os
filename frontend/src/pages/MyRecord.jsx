import { useEffect, useState } from "react";
import { api } from "../api";

// Judge's own participation record. The server decides which record is "mine"
// (no id is sent). "Check" asks the server to re-verify the signature: the HMAC key
// lives only on the server, so verification is server-mediated, not offline.
export default function MyRecord() {
  const [rec, setRec] = useState(undefined); // undefined = loading, null = none issued yet
  const [error, setError] = useState(null);
  const [check, setCheck] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.myRecord()
      .then(setRec)
      .catch((e) => {
        if (e.status === 404) setRec(null);
        else { setError(e.message); setRec(null); }
      });
  }, []);

  const verifyUrl = rec ? `${window.location.origin}/api/verify/${rec.id}` : "";

  async function runCheck() {
    setCheck(null);
    try { setCheck(await api.verifyRecord(rec.id)); }
    catch (e) { setCheck({ error: e.message }); }
  }

  async function copyLink() {
    try { await navigator.clipboard.writeText(verifyUrl); setCopied(true); setTimeout(() => setCopied(false), 1500); }
    catch { /* clipboard unavailable; link is shown on screen */ }
  }

  return (
    <div>
      <div className="head">
        <div>
          <span className="eyebrow">JUDGE DECK</span>
          <h2>MY RECORD</h2>
        </div>
      </div>

      {rec === undefined && <div className="skeleton"><div className="skel-row" /><div className="skel-row" /></div>}
      {error && <div className="state state-error">{error}</div>}
      {rec === null && !error && (
        <div className="state">No participation record has been issued to you yet. An organizer issues records once you have submitted at least one review.</div>
      )}

      {rec && (
        <div className="card">
          <h3>{rec.name}</h3>
          <p>{rec.event}</p>
          <div className="table-wrap" style={{ marginTop: 12 }}>
            <table>
              <tbody>
                <tr><td>Reviews completed</td><td className="mono">{rec.reviews_completed}</td></tr>
                <tr><td>Issued</td><td className="mono">{new Date(rec.issued_at).toLocaleString()}</td></tr>
                <tr><td>Audit anchor</td><td className="mono">#{rec.audit_seq} · {rec.audit_hash.slice(0, 16)}…</td></tr>
                <tr><td>Record id</td><td className="mono">{rec.id}</td></tr>
              </tbody>
            </table>
          </div>
          <p className="mono" style={{ wordBreak: "break-all" }}>{verifyUrl}</p>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button onClick={copyLink}>{copied ? "Copied ✓" : "Copy verify link"}</button>
            <button onClick={runCheck}>Check signature</button>
          </div>
          {check && !check.error && (
            <div className={check.signature_valid ? "confirm" : "state state-error"} style={{ marginTop: 12 }}>
              <b>{check.signature_valid ? "✓ SIGNATURE VALID" : "✗ SIGNATURE INVALID"}</b>
              Checked by the server just now.
            </div>
          )}
          {check?.error && <p className="error">{check.error}</p>}
          <p style={{ marginTop: 12 }}>
            Anyone with the link sees only your name, the event, your review count, the issue time and the
            audit anchor: no scores and no project information. The signature can only be checked by asking
            this server, because only the server holds the signing key.
          </p>
        </div>
      )}
    </div>
  );
}
