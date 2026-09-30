import { useEffect, useState } from "react";
import { api } from "../api";
import { short, Panel, Progress, StatusBadge, LoadingState, PageHead } from "../ui";

const FIELDS = [
  ["title", "TITLE"],
  ["tagline", "TAGLINE"],
  ["description", "DESCRIPTION"],
  ["repo_url", "REPO URL"],
  ["demo_url", "DEMO URL"],
];

export default function ParticipantDashboard() {
  const [me, setMe] = useState(null);
  const [project, setProject] = useState(null);

  const [form, setForm] = useState({
    title: "",
    tagline: "",
    description: "",
    repo_url: "",
    demo_url: "",
  });

  const [teamName, setTeamName] = useState("");
  const [joinToken, setJoinToken] = useState("");
  const [inviteToken, setInviteToken] = useState(null);

  const [editing, setEditing] = useState(false);
  const [error, setError] = useState(null);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [teamBusy, setTeamBusy] = useState(false);

  async function refresh() {
    const [user, currentProject] = await Promise.all([
      api.me(),
      api.myProject(),
    ]);

    setMe(user);
    setProject(currentProject);
  }

  useEffect(() => {
    let cancelled = false;

    Promise.all([api.me(), api.myProject()])
      .then(([user, currentProject]) => {
        if (cancelled) return;
        setMe(user);
        setProject(currentProject);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  function set(k, v) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  const filled = FIELDS.filter(([k]) => form[k]?.trim()).length;
  const pct = Math.round((filled / FIELDS.length) * 100);

  async function createTeam() {
    if (!teamName.trim()) {
      setError("Enter a team name first.");
      return;
    }

    if (!me?.event_id) {
      setError("No active event is available.");
      return;
    }

    setError(null);
    setTeamBusy(true);

    try {
      await api.createTeam(teamName.trim(), me.event_id);
      setTeamName("");
      await refresh();
      setStatus("Team created.");
    } catch (e) {
      setError(e.message);
    } finally {
      setTeamBusy(false);
    }
  }

  async function joinTeam() {
    if (!joinToken.trim()) {
      setError("Enter an invite token.");
      return;
    }

    setError(null);
    setTeamBusy(true);

    try {
      await api.joinTeam(joinToken.trim());
      setJoinToken("");
      await refresh();
      setStatus("Joined team.");
    } catch (e) {
      setError(e.message);
    } finally {
      setTeamBusy(false);
    }
  }

  async function generateInvite() {
    if (!me?.team_id) return;

    setError(null);
    setInviteToken(null);
    setTeamBusy(true);

    try {
      const result = await api.inviteTeam(me.team_id);
      setInviteToken(result.token);
      setStatus("Invite generated.");
    } catch (e) {
      setError(e.message);
    } finally {
      setTeamBusy(false);
    }
  }

  async function create() {
    setError(null);

    if (!me?.team_id) {
      setError("Create or join a team before creating a submission.");
      return;
    }

    try {
      setProject(await api.createProject(form));
      setStatus("Draft created.");
    } catch (e) {
      setError(e.message);
    }
  }

  function startEdit() {
    setForm({
      title: project.title || "",
      tagline: project.tagline || "",
      description: project.description || "",
      repo_url: project.repo_url || "",
      demo_url: project.demo_url || "",
    });
    setEditing(true);
  }

  async function saveEdit() {
    setError(null);

    try {
      setProject(await api.editProject(project.id, form));
      setEditing(false);
      setStatus("Draft updated.");
    } catch (e) {
      setError(e.message);
    }
  }

  async function submit() {
    setError(null);

    try {
      setProject(await api.submitProject(project.id));
      setStatus("submitted-now");
    } catch (e) {
      setError(e.message);
    }
  }

  const submitted = project?.status === "submitted";

  const steps = [
    ["Project draft created", !!project],
    ["Repository linked", !!project?.repo_url],
    ["Demo linked", !!project?.demo_url],
    ["Submitted & locked", submitted],
  ];

  const stepPct = (steps.filter((s) => s[1]).length / steps.length) * 100;

  const formFields = (
    <>
      {FIELDS.map(([k, label]) => (
        <div key={k}>
          <label className="field-label" htmlFor={`f-${k}`}>
            {label}
          </label>

          {k === "description" ? (
            <textarea
              id={`f-${k}`}
              rows={4}
              value={form[k]}
              onChange={(e) => set(k, e.target.value)}
            />
          ) : (
            <input
              id={`f-${k}`}
              value={form[k]}
              onChange={(e) => set(k, e.target.value)}
            />
          )}
        </div>
      ))}
    </>
  );

  return (
    <div>
      <PageHead
        eyebrow="MY PROJECT"
        title={project ? project.title : "New submission"}
        right={
          project && (
            <StatusBadge tone={submitted ? "ok" : "warn"}>
              {project.status}
            </StatusBadge>
          )
        }
      />

      {loading && <LoadingState rows={2} />}

      {!loading && (
        <>
          {/* TEAM */}
          <Panel
            title="TEAM"
            right={me?.team_name ? me.team_name : "NOT FORMED"}
            accent={!me?.team_id}
          >
            {me?.team_id ? (
              <div>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <div>
                    <div className="field-label">TEAM NAME</div>
                    <div style={{ fontSize: 20, marginTop: 4 }}>
                      {me.team_name}
                    </div>
                  </div>

                  <button
                    className="primary"
                    onClick={generateInvite}
                    disabled={teamBusy}
                  >
                    {teamBusy ? "Working..." : "Generate invite"}
                  </button>
                </div>

                {inviteToken && (
                  <div
                    className="confirm"
                    style={{ marginTop: 16 }}
                  >
                    <b>INVITE TOKEN</b>
                    <div
                      style={{
                        marginTop: 8,
                        fontFamily: "var(--mono)",
                        fontSize: 18,
                        wordBreak: "break-all",
                      }}
                    >
                      {inviteToken}
                    </div>
                    <div className="meta" style={{ marginTop: 8 }}>
                      Share this token with your teammate. It expires in 3
                      days.
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="cols-2">
                <div>
                  <label className="field-label" htmlFor="team-name">
                    CREATE TEAM
                  </label>

                  <input
                    id="team-name"
                    placeholder="Team name"
                    value={teamName}
                    onChange={(e) => setTeamName(e.target.value)}
                  />

                  <button
                    className="primary"
                    style={{ marginTop: 12 }}
                    onClick={createTeam}
                    disabled={teamBusy}
                  >
                    {teamBusy ? "Creating..." : "Create team"}
                  </button>
                </div>

                <div>
                  <label className="field-label" htmlFor="join-token">
                    JOIN WITH INVITE
                  </label>

                  <input
                    id="join-token"
                    placeholder="Paste invite token"
                    value={joinToken}
                    onChange={(e) => setJoinToken(e.target.value)}
                  />

                  <button
                    style={{ marginTop: 12 }}
                    onClick={joinTeam}
                    disabled={teamBusy}
                  >
                    {teamBusy ? "Joining..." : "Join team"}
                  </button>
                </div>
              </div>
            )}
          </Panel>

          <div style={{ height: 18 }} />

          <div className="cols-2">
            <div className="stack">
              {!project && (
                <Panel
                  title="NEW SUBMISSION"
                  right={`${pct}% complete`}
                  accent
                >
                  {!me?.team_id && (
                    <div className="note" style={{ marginBottom: 16 }}>
                      Create or join a team above to unlock project submission.
                    </div>
                  )}

                  <Progress pct={pct} />

                  <div style={{ marginTop: 16 }}>{formFields}</div>

                  <button
                    className="primary"
                    onClick={create}
                    disabled={!me?.team_id}
                  >
                    Save draft
                  </button>
                </Panel>
              )}

              {project && !editing && (
                <Panel
                  title="YOUR SUBMISSION"
                  right={short(project.id)}
                  accent
                >
                  <p style={{ color: "var(--muted)" }}>
                    {project.tagline}
                  </p>

                  <p style={{ whiteSpace: "pre-wrap" }}>
                    {project.description}
                  </p>

                  <div className="row" style={{ marginTop: 10 }}>
                    {project.repo_url && (
                      <a
                        className="btn"
                        href={project.repo_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Repository ↗
                      </a>
                    )}

                    {project.demo_url && (
                      <a
                        className="btn"
                        href={project.demo_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Demo ↗
                      </a>
                    )}
                  </div>

                  {project.status === "draft" && (
                    <div className="row" style={{ marginTop: 18 }}>
                      <button onClick={startEdit}>Edit</button>
                      <button className="primary" onClick={submit}>
                        Submit project
                      </button>
                    </div>
                  )}
                </Panel>
              )}

              {project &&
                project.status === "draft" &&
                editing && (
                  <Panel title="EDIT DRAFT" accent>
                    {formFields}

                    <div className="row">
                      <button onClick={() => setEditing(false)}>
                        Cancel
                      </button>

                      <button className="primary" onClick={saveEdit}>
                        Save changes
                      </button>
                    </div>
                  </Panel>
                )}

              {submitted && status === "submitted-now" && (
                <div className="confirm">
                  <b>✓ SUBMISSION LOCKED</b>
                  Your project was submitted. It can no longer be edited, and
                  judges can now be assigned to it.
                </div>
              )}

              {submitted && status !== "submitted-now" && (
                <div className="note">
                  Locked — this project is submitted and can't be edited
                  further.
                </div>
              )}

              {status && status !== "submitted-now" && (
                <p style={{ color: "var(--green)" }}>{status}</p>
              )}

              {error && (
                <p className="error" role="alert">
                  {error}
                </p>
              )}
            </div>

            <div className="stack" style={{ alignContent: "start" }}>
              <Panel
                title="SUBMISSION STATUS"
                right={`${Math.round(stepPct)}%`}
              >
                <Progress pct={stepPct} crimson />

                <ul className="checklist" style={{ marginTop: 16 }}>
                  {steps.map(([label, on]) => (
                    <li key={label} className={on ? "on" : ""}>
                      <span className="box">{on ? "✓" : ""}</span>
                      {label}
                    </li>
                  ))}
                </ul>
              </Panel>

              <Panel title="JUDGING">
                <p className="meta" style={{ lineHeight: 1.7 }}>
                  {submitted
                    ? "Your project is in the judging pool. Scores and rankings stay private to organizers; nothing about individual reviews is shown to teams."
                    : "Judges can only be assigned to submitted projects. Submit to enter the judging pool."}
                </p>
              </Panel>
            </div>
          </div>
        </>
      )}
    </div>
  );
}