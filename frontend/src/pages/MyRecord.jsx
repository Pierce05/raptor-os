import { useEffect, useState } from "react";
import { api } from "../api";
import { fmt, Panel, LoadingState, EmptyState, ErrorState, PageHead } from "../ui";

// Judge's own participation record. The server decides which record is "mine"; verification is server-mediated
// because the HMAC key lives only on the server.
export default function MyRecord() {
  const [rec, setRec] = useState(undefined);
  const [error, setError] = useState(null);
  const [check, setCheck] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.myRecord().then(setRec).catch((e) => {
      if (e.status === 404) setRec(null);
      else { setError(e.message); setRec(null); }
    });
  }, []);

  const verifyUrl = rec ? `${window.location.origin}/api/verify/${rec.id}` : "";

  async function runCheck() {
    setCheck(null);
    try { setCheck(await api.verifyRecord(rec.id)); } catch (e) { setCheck({ error: e.message }); }
  }
  async function copyLink() {
    try { await navigator.clipboard.writeText(verifyUrl); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* link is shown on screen */ }
  }

  return (
    <div>
      <PageHead eyebrow="JUDGE DECK" title="MY RECORD" />
      {rec === undefined && <LoadingState rows={2} />}
      {error && <ErrorState>{error}</ErrorState>}
      {rec === null && !error && <EmptyState>No participation record has been issued to you yet. An organizer issues records once you have submitted at least one review.</EmptyState>}

      {rec && (
        <div className="cols-2">
          <Panel title="PARTICIPATION RECORD · SIGNED" accent>
            <span className="eyebrow">{rec.event}</span>
            <h1 className="dossier-title">{rec.name}</h1>
            <div className="kv">
              <div>Reviews completed</div><div className="v">{rec.reviews_completed}</div>
              <div>Issued</div><div className="v">{fmt(rec.issued_at)}</div>
              <div>Audit anchor</div><div className="v">#{rec.audit_seq} · {rec.audit_hash.slice(0, 24)}…</div>
              <div>Record id</div><div className="v">{rec.id}</div>
              <div>Verify link</div><div className="v">{verifyUrl}</div>
            </div>
            <div className="row" style={{ marginTop: 16 }}>
              <button onClick={copyLink}>{copied ? "Copied ✓" : "Copy verify link"}</button>
              <button className="primary" onClick={runCheck}>Check signature</button>
            </div>
          </Panel>

          <div className="stack" style={{ alignContent: "start" }}>
            <Panel title="VERIFICATION">
              {!check && <p className="meta">Not checked yet. Verification is performed by the server.</p>}
              {check && !check.error && (
                <div>
                  <div className={`stamp ${check.signature_valid ? "" : "bad"}`}>{check.signature_valid ? "✓ SIGNATURE VALID" : "✗ SIGNATURE INVALID"}</div>
                  <p className="meta" style={{ marginTop: 14 }}>Checked by the server just now.</p>
                </div>
              )}
              {check?.error && <p className="error" role="alert">{check.error}</p>}
            </Panel>
            <Panel title="WHAT OTHERS SEE">
              <p className="meta" style={{ lineHeight: 1.7 }}>
                Anyone with the link sees only your name, the event, your review count, the issue time and the audit anchor: no scores and no project information.
                The signature can only be checked by asking this server, because only the server holds the signing key.
              </p>
            </Panel>
          </div>
        </div>
      )}
    </div>
  );
}
