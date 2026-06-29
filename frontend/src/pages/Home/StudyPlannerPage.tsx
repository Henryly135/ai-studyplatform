import { useEffect, useMemo, useState } from "react";
import { Navigate, useOutletContext } from "react-router-dom";
import {
  LuArchive,
  LuCalendar,
  LuClock,
  LuPlus,
  LuRefreshCw,
  LuSave,
  LuSparkles,
  LuTrash2,
} from "react-icons/lu";

import {
  createStudyPlan,
  listStudyPlans,
  regenerateStudyPlan,
  updateStudyPlan,
} from "../../services/studyPlanner";
import type {
  StudyPlanContent,
  StudyPlanCreatePayload,
  StudyPlanRecord,
  StudyPlannerMaterialInput,
} from "../../types/studyPlanner";
import type { HomeOutletContext } from "./HomeSectionPage";
import "./StudyPlannerPage.css";

type MaterialDraft = StudyPlannerMaterialInput & {
  id: string;
};

function createDraftId() {
  return Math.random().toString(36).slice(2, 10);
}

function emptyMaterialDraft(): MaterialDraft {
  return {
    id: createDraftId(),
    title: "",
    materialType: "",
    notes: "",
  };
}

function formatDateTime(value: string) {
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) {
    return "Recently";
  }

  return new Intl.DateTimeFormat("en-AU", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(timestamp);
}

function formatDate(value?: string | null) {
  if (!value) {
    return "No target date";
  }

  const timestamp = new Date(`${value}T00:00:00`);
  if (Number.isNaN(timestamp.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-AU", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(timestamp);
}

function buildCreatePayload(
  goal: string,
  availableMinutesPerWeek: string,
  targetDate: string,
  preferences: string,
  materials: MaterialDraft[]
): StudyPlanCreatePayload {
  const normalizedMaterials = materials
    .map((material) => ({
      title: material.title.trim(),
      materialType: material.materialType?.trim() || null,
      notes: material.notes?.trim() || null,
    }))
    .filter((material) => material.title || material.materialType || material.notes);

  const incompleteMaterial = normalizedMaterials.find((material) => !material.title);
  if (incompleteMaterial) {
    throw new Error("Each material needs a title.");
  }

  const minutes = Number.parseInt(availableMinutesPerWeek, 10);
  if (!Number.isFinite(minutes) || minutes < 30) {
    throw new Error("Weekly availability must be at least 30 minutes.");
  }

  return {
    goal: goal.trim(),
    availableMinutesPerWeek: minutes,
    targetDate: targetDate || null,
    preferences: preferences.trim() || null,
    materials: normalizedMaterials,
  };
}

function replacePlan(plans: StudyPlanRecord[], plan: StudyPlanRecord) {
  const existingIndex = plans.findIndex((item) => item.planUuid === plan.planUuid);
  if (existingIndex === -1) {
    return [plan, ...plans];
  }

  return plans.map((item) => (item.planUuid === plan.planUuid ? plan : item));
}

function StudyPlannerPage() {
  const { currentUser } = useOutletContext<HomeOutletContext>();
  const [plans, setPlans] = useState<StudyPlanRecord[]>([]);
  const [activePlanUuid, setActivePlanUuid] = useState<string | null>(null);
  const [goal, setGoal] = useState("");
  const [availableMinutesPerWeek, setAvailableMinutesPerWeek] = useState("300");
  const [targetDate, setTargetDate] = useState("");
  const [preferences, setPreferences] = useState("");
  const [materials, setMaterials] = useState<MaterialDraft[]>([emptyMaterialDraft()]);
  const [draftTitle, setDraftTitle] = useState("");
  const [draftOverview, setDraftOverview] = useState("");
  const [draftRationale, setDraftRationale] = useState("");
  const [draftNotes, setDraftNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState<"create" | "save" | "regenerate" | "archive" | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [noticeMessage, setNoticeMessage] = useState<string | null>(null);

  const activePlan = useMemo(
    () => plans.find((plan) => plan.planUuid === activePlanUuid) ?? plans[0] ?? null,
    [activePlanUuid, plans]
  );

  useEffect(() => {
    let cancelled = false;

    void listStudyPlans()
      .then((loadedPlans) => {
        if (cancelled) {
          return;
        }
        setPlans(loadedPlans);
        setActivePlanUuid((currentUuid) => currentUuid ?? loadedPlans[0]?.planUuid ?? null);
      })
      .catch((error) => {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : "Failed to load study plans.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!activePlan) {
      setDraftTitle("");
      setDraftOverview("");
      setDraftRationale("");
      setDraftNotes("");
      return;
    }

    setDraftTitle(activePlan.title);
    setDraftOverview(activePlan.planContent.overview);
    setDraftRationale(activePlan.planContent.rationale);
    setDraftNotes(activePlan.adjustmentNotes ?? "");
  }, [activePlan]);

  if (currentUser.identity !== "Learner") {
    return <Navigate to="/home" replace />;
  }

  function updateMaterial(id: string, patch: Partial<MaterialDraft>) {
    setMaterials((currentMaterials) =>
      currentMaterials.map((material) => (material.id === id ? { ...material, ...patch } : material))
    );
  }

  function removeMaterial(id: string) {
    setMaterials((currentMaterials) =>
      currentMaterials.length === 1
        ? [emptyMaterialDraft()]
        : currentMaterials.filter((material) => material.id !== id)
    );
  }

  async function handleCreatePlan() {
    setErrorMessage(null);
    setNoticeMessage(null);
    setBusyAction("create");

    try {
      const payload = buildCreatePayload(goal, availableMinutesPerWeek, targetDate, preferences, materials);
      const createdPlan = await createStudyPlan(payload);
      setPlans((currentPlans) => replacePlan(currentPlans, createdPlan));
      setActivePlanUuid(createdPlan.planUuid);
      setGoal("");
      setPreferences("");
      setTargetDate("");
      setMaterials([emptyMaterialDraft()]);
      setNoticeMessage("Study plan generated.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to generate a study plan.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleSaveAdjustments() {
    if (!activePlan) {
      return;
    }

    const title = draftTitle.trim();
    const overview = draftOverview.trim();
    const rationale = draftRationale.trim();
    if (!title || !overview || !rationale) {
      setErrorMessage("Title, overview, and rationale are required.");
      return;
    }

    setErrorMessage(null);
    setNoticeMessage(null);
    setBusyAction("save");

    const planContent: StudyPlanContent = {
      ...activePlan.planContent,
      overview,
      rationale,
    };

    try {
      const updatedPlan = await updateStudyPlan(activePlan.planUuid, {
        title,
        planContent,
        adjustmentNotes: draftNotes.trim() || null,
      });
      setPlans((currentPlans) => replacePlan(currentPlans, updatedPlan));
      setNoticeMessage("Study plan saved.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to save the study plan.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleRegeneratePlan() {
    if (!activePlan) {
      return;
    }

    setErrorMessage(null);
    setNoticeMessage(null);
    setBusyAction("regenerate");

    try {
      const regeneratedPlan = await regenerateStudyPlan(activePlan.planUuid);
      setPlans((currentPlans) => replacePlan(currentPlans, regeneratedPlan));
      setActivePlanUuid(regeneratedPlan.planUuid);
      setNoticeMessage("Study plan regenerated.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to regenerate the study plan.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleArchivePlan() {
    if (!activePlan) {
      return;
    }

    setErrorMessage(null);
    setNoticeMessage(null);
    setBusyAction("archive");

    try {
      const updatedPlan = await updateStudyPlan(activePlan.planUuid, {
        status: activePlan.status === "archived" ? "active" : "archived",
      });
      setPlans((currentPlans) => replacePlan(currentPlans, updatedPlan));
      setNoticeMessage(updatedPlan.status === "archived" ? "Study plan archived." : "Study plan restored.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to update the study plan.");
    } finally {
      setBusyAction(null);
    }
  }

  return (
    <section className="study-planner-page">
      <div className="study-planner-heading">
        <div>
          <span className="home-content-badge">Learner</span>
          <h1>Study Planner</h1>
        </div>
        <div className="study-planner-heading-meta">
          <span>{plans.length} plans</span>
          <span>{activePlan ? formatDateTime(activePlan.updatedAt) : "No plan selected"}</span>
        </div>
      </div>

      {errorMessage ? <div className="study-planner-alert study-planner-alert-error">{errorMessage}</div> : null}
      {noticeMessage ? <div className="study-planner-alert study-planner-alert-success">{noticeMessage}</div> : null}

      <div className="study-planner-layout">
        <aside className="study-planner-sidebar">
          <section className="study-planner-panel">
            <div className="study-planner-panel-heading">
              <h2>Generate</h2>
              <LuSparkles size={18} aria-hidden="true" />
            </div>

            <label className="study-planner-field">
              <span>Goal</span>
              <textarea
                value={goal}
                rows={3}
                maxLength={500}
                onChange={(event) => setGoal(event.target.value)}
                placeholder="Pass the algorithms final with graph and DP confidence"
              />
            </label>

            <div className="study-planner-form-grid">
              <label className="study-planner-field">
                <span>Weekly minutes</span>
                <input
                  type="number"
                  min={30}
                  max={10080}
                  value={availableMinutesPerWeek}
                  onChange={(event) => setAvailableMinutesPerWeek(event.target.value)}
                />
              </label>
              <label className="study-planner-field">
                <span>Target date</span>
                <input
                  type="date"
                  value={targetDate}
                  onChange={(event) => setTargetDate(event.target.value)}
                />
              </label>
            </div>

            <label className="study-planner-field">
              <span>Preferences</span>
              <textarea
                value={preferences}
                rows={3}
                maxLength={1000}
                onChange={(event) => setPreferences(event.target.value)}
                placeholder="Short weekday sessions, longer Sunday review"
              />
            </label>

            <div className="study-planner-materials-heading">
              <span>Materials</span>
              <button
                type="button"
                className="study-planner-icon-button"
                onClick={() => setMaterials((currentMaterials) => [...currentMaterials, emptyMaterialDraft()])}
                aria-label="Add material"
                title="Add material"
              >
                <LuPlus size={16} aria-hidden="true" />
              </button>
            </div>

            <div className="study-planner-material-list">
              {materials.map((material) => (
                <div className="study-planner-material-row" key={material.id}>
                  <input
                    value={material.title}
                    onChange={(event) => updateMaterial(material.id, { title: event.target.value })}
                    placeholder="Material title"
                  />
                  <input
                    value={material.materialType ?? ""}
                    onChange={(event) => updateMaterial(material.id, { materialType: event.target.value })}
                    placeholder="Type"
                  />
                  <button
                    type="button"
                    className="study-planner-icon-button study-planner-icon-button-danger"
                    onClick={() => removeMaterial(material.id)}
                    aria-label="Remove material"
                    title="Remove material"
                  >
                    <LuTrash2 size={15} aria-hidden="true" />
                  </button>
                  <textarea
                    value={material.notes ?? ""}
                    rows={2}
                    onChange={(event) => updateMaterial(material.id, { notes: event.target.value })}
                    placeholder="Notes"
                  />
                </div>
              ))}
            </div>

            <button
              type="button"
              className="study-planner-primary-button"
              onClick={() => void handleCreatePlan()}
              disabled={busyAction !== null}
            >
              <LuSparkles size={17} aria-hidden="true" />
              <span>{busyAction === "create" ? "Generating..." : "Generate plan"}</span>
            </button>
          </section>

          <section className="study-planner-panel study-planner-list-panel">
            <div className="study-planner-panel-heading">
              <h2>Plans</h2>
              <span>{loading ? "Loading" : plans.length}</span>
            </div>

            <div className="study-planner-plan-list">
              {!loading && plans.length === 0 ? (
                <p className="study-planner-muted">No plans yet.</p>
              ) : null}
              {plans.map((plan) => (
                <button
                  type="button"
                  key={plan.planUuid}
                  className={`study-planner-plan-item ${
                    activePlan?.planUuid === plan.planUuid ? "study-planner-plan-item-active" : ""
                  }`}
                  onClick={() => setActivePlanUuid(plan.planUuid)}
                >
                  <strong>{plan.title}</strong>
                  <span>{formatDateTime(plan.updatedAt)}</span>
                  <small>{plan.status === "archived" ? "Archived" : "Active"}</small>
                </button>
              ))}
            </div>
          </section>
        </aside>

        <section className="study-planner-detail">
          {activePlan ? (
            <>
              <div className="study-planner-detail-toolbar">
                <div>
                  <span className="study-planner-status">{activePlan.status}</span>
                  {activePlan.generation.usedFallback ? (
                    <span className="study-planner-fallback">Fallback</span>
                  ) : null}
                </div>
                <div className="study-planner-detail-actions">
                  <button
                    type="button"
                    className="study-planner-secondary-button"
                    onClick={() => void handleRegeneratePlan()}
                    disabled={busyAction !== null}
                  >
                    <LuRefreshCw size={16} aria-hidden="true" />
                    <span>{busyAction === "regenerate" ? "Regenerating..." : "Regenerate"}</span>
                  </button>
                  <button
                    type="button"
                    className="study-planner-secondary-button"
                    onClick={() => void handleArchivePlan()}
                    disabled={busyAction !== null}
                  >
                    <LuArchive size={16} aria-hidden="true" />
                    <span>{activePlan.status === "archived" ? "Restore" : "Archive"}</span>
                  </button>
                  <button
                    type="button"
                    className="study-planner-primary-button study-planner-primary-button-compact"
                    onClick={() => void handleSaveAdjustments()}
                    disabled={busyAction !== null}
                  >
                    <LuSave size={16} aria-hidden="true" />
                    <span>{busyAction === "save" ? "Saving..." : "Save"}</span>
                  </button>
                </div>
              </div>

              <div className="study-planner-edit-grid">
                <label className="study-planner-field">
                  <span>Title</span>
                  <input value={draftTitle} onChange={(event) => setDraftTitle(event.target.value)} />
                </label>
                <label className="study-planner-field">
                  <span>Overview</span>
                  <textarea
                    value={draftOverview}
                    rows={4}
                    onChange={(event) => setDraftOverview(event.target.value)}
                  />
                </label>
                <label className="study-planner-field">
                  <span>Rationale</span>
                  <textarea
                    value={draftRationale}
                    rows={4}
                    onChange={(event) => setDraftRationale(event.target.value)}
                  />
                </label>
                <label className="study-planner-field">
                  <span>Adjustment notes</span>
                  <textarea
                    value={draftNotes}
                    rows={4}
                    onChange={(event) => setDraftNotes(event.target.value)}
                  />
                </label>
              </div>

              <div className="study-planner-summary-strip">
                <span>
                  <LuClock size={16} aria-hidden="true" />
                  {activePlan.planContent.weeklyCommitmentMinutes} min/week
                </span>
                <span>
                  <LuCalendar size={16} aria-hidden="true" />
                  {formatDate(activePlan.input.targetDate)}
                </span>
                <span>{activePlan.generation.provider ?? "unknown provider"}</span>
              </div>

              <div className="study-planner-sections">
                <article className="study-planner-section">
                  <h2>Phases</h2>
                  <div className="study-planner-phase-list">
                    {activePlan.planContent.phases.map((phase, index) => (
                      <div className="study-planner-phase" key={`${phase.title}-${index}`}>
                        <span>{phase.durationDays} days</span>
                        <h3>{phase.title}</h3>
                        <p>{phase.focus}</p>
                        <ul>
                          {phase.outcomes.map((outcome) => (
                            <li key={outcome}>{outcome}</li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                </article>

                <article className="study-planner-section">
                  <h2>Topic Order</h2>
                  <div className="study-planner-topic-list">
                    {activePlan.planContent.topics.map((topic, index) => (
                      <div className="study-planner-topic" key={`${topic.title}-${index}`}>
                        <span>{index + 1}</span>
                        <div>
                          <h3>{topic.title}</h3>
                          <p>{topic.reason}</p>
                          {topic.materials.length > 0 ? <small>{topic.materials.join(", ")}</small> : null}
                        </div>
                      </div>
                    ))}
                  </div>
                </article>

                <article className="study-planner-section">
                  <h2>Review Rhythm</h2>
                  <div className="study-planner-review-list">
                    {activePlan.planContent.revisionSchedule.map((item) => (
                      <div className="study-planner-review" key={`${item.cadence}-${item.activity}`}>
                        <strong>{item.cadence}</strong>
                        <span>{item.activity}</span>
                      </div>
                    ))}
                  </div>
                </article>
              </div>
            </>
          ) : (
            <div className="study-planner-empty-detail">
              <LuSparkles size={26} aria-hidden="true" />
              <h2>No study plan selected</h2>
              <p>Generated plans will appear here.</p>
            </div>
          )}
        </section>
      </div>
    </section>
  );
}

export default StudyPlannerPage;
