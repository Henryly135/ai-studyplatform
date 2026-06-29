import { useEffect, useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { LuChevronDown, LuChevronUp } from "react-icons/lu";

import {
  deactivateCourseInviteLink,
  generateCourseInviteLink,
  getManagedCourseEnrollments,
  listCourseInviteLinks,
} from "../../services/course";
import type { CourseEnrollmentLearnerRecord } from "../../types/course";
import type { CourseInviteLinkResponse } from "../../types/admin";
import type { CourseManagementOutletContext } from "./CourseManagementLayout";
import type { CurrentUserResponse } from "../../types/auth";
import { copyTextToClipboard } from "../../utils/clipboard";

function formatDateTime(value: string | null) {
  if (!value) {
    return "Not available yet";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString("en-AU", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatProgress(record: CourseEnrollmentLearnerRecord) {
  const normalized = Number(record.progressPercent);
  const progressLabel = Number.isFinite(normalized)
    ? `${Math.round(normalized)}%`
    : `${record.progressPercent}%`;

  return `${progressLabel} · ${record.completedModuleCount}/${record.totalModuleCount} modules`;
}

function CourseManagementUserEnrolmentsPage() {
  const { course } = useOutletContext<CourseManagementOutletContext>();
  const [enrollments, setEnrollments] = useState<CourseEnrollmentLearnerRecord[]>([]);
  const [expandedLearnerUuid, setExpandedLearnerUuid] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const currentUser = useMemo(() => {
    const raw = localStorage.getItem("currentUser");
    if (!raw) {
      return null;
    }

    try {
      return JSON.parse(raw) as CurrentUserResponse;
    } catch {
      return null;
    }
  }, []);
  const isAdmin = currentUser?.identity === "Admin";
  const isEducator = currentUser?.identity === "Educator";

  // Invite link state
  const [inviteLinks, setInviteLinks] = useState<CourseInviteLinkResponse[]>([]);
  const [generatingInvite, setGeneratingInvite] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [inviteCopyError, setInviteCopyError] = useState<string | null>(null);
  const [copiedUuid, setCopiedUuid] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadEnrollments = async () => {
      setLoading(true);

      try {
        const data = await getManagedCourseEnrollments(course.courseUuid);
        if (!cancelled) {
          setEnrollments(data);
          setExpandedLearnerUuid((current) =>
            current && data.some((item) => item.learnerUuid === current) ? current : null
          );
          setError(null);
        }
      } catch (loadError) {
        if (!cancelled) {
          setEnrollments([]);
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Failed to load learner enrollments."
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadEnrollments();

    return () => {
      cancelled = true;
    };
  }, [course.courseUuid]);

  useEffect(() => {
    if (!isEducator && !isAdmin) return;
    listCourseInviteLinks(course.courseUuid)
      .then(setInviteLinks)
      .catch(() => setInviteLinks([]));
  }, [course.courseUuid, isEducator, isAdmin]);

  const handleGenerateInviteLink = async () => {
    setGeneratingInvite(true);
    setInviteError(null);
    setInviteCopyError(null);
    try {
      const link = await generateCourseInviteLink(course.courseUuid);
      setInviteLinks((prev) => [link, ...prev]);
    } catch (err) {
      setInviteError(err instanceof Error ? err.message : "Failed to generate invite link.");
    } finally {
      setGeneratingInvite(false);
    }
  };

  const handleCopyLink = async (link: CourseInviteLinkResponse) => {
    const inviteUrl = link.inviteUrl ?? "";
    if (!inviteUrl) {
      setInviteError("Invite URL is missing. Please regenerate the invite link.");
      return;
    }

    const copied = await copyTextToClipboard(inviteUrl);
    if (copied) {
      setCopiedUuid(link.inviteUuid);
      setInviteCopyError(null);
      setTimeout(() => setCopiedUuid(null), 2000);
      return;
    }

    setInviteCopyError("Failed to copy the invite link. Please select it manually and copy again.");
  };

  const handleDeactivateLink = async (inviteUuid: string) => {
    try {
      await deactivateCourseInviteLink(inviteUuid);
      setInviteLinks((prev) =>
        prev.map((l) => (l.inviteUuid === inviteUuid ? { ...l, isActive: false } : l))
      );
    } catch (err) {
      setInviteError(err instanceof Error ? err.message : "Failed to deactivate invite link.");
    }
  };

  const summaryLabel = useMemo(() => {
    if (loading) {
      return "Loading learner list...";
    }

    if (enrollments.length === 0) {
      return "No learners enrolled yet.";
    }

    return `${enrollments.length} active learner${enrollments.length === 1 ? "" : "s"}`;
  }, [enrollments.length, loading]);

  const isCoursePublished = course.status?.toLowerCase() === "published";

  return (
    <section className="course-management-page">
      <div className="course-management-section-heading">
        <div>
          <span className="course-surface-badge">User Enrolments</span>
          <h1>Track enrolled learners</h1>
          <p>Review the active learner list for this course and monitor enrollment progress at a glance.</p>
          {isAdmin && course.educatorName ? <p>Created by {course.educatorName}</p> : null}
        </div>
      </div>

      <div className="course-management-toolbar">
        <strong>{summaryLabel}</strong>
        <span>
          {loading
            ? "Syncing learner records from the current course."
            : "This list only includes current non-dropped enrollments."}
        </span>
      </div>

      {(isEducator || isAdmin) ? (
        <div className="course-management-panel" style={{ marginBottom: "1.5rem", padding: "1.25rem 1.5rem" }}>
          <h3 style={{ marginTop: 0, marginBottom: "0.5rem" }}>Invite Students</h3>
          <p style={{ color: "var(--color-text-muted, #6b7280)", fontSize: "0.875rem", marginBottom: "1rem" }}>
            Generate a shareable link for learners to self-enrol in this course.
          </p>
          {!isCoursePublished && (
            <p style={{ color: "#f59e0b", fontSize: "0.875rem", marginBottom: "0.75rem" }}>
              The course must be published before invite links can be generated.
            </p>
          )}
          <button
            type="button"
            className="primary-btn"
            onClick={() => void handleGenerateInviteLink()}
            disabled={generatingInvite || !isCoursePublished}
            style={{ marginBottom: "0.75rem" }}
          >
            {generatingInvite ? "Generating..." : "Generate Invite Link"}
          </button>

          {inviteError && (
            <div className="course-management-inline-alert" style={{ marginBottom: "0.75rem" }}>
              <span>{inviteError}</span>
            </div>
          )}
          {inviteCopyError && (
            <div className="course-management-inline-alert" style={{ marginBottom: "0.75rem" }}>
              <span>{inviteCopyError}</span>
            </div>
          )}

          {inviteLinks.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {inviteLinks.map((link) => {
                const inviteUrl = link.inviteUrl ?? "";
                return (
                  <div
                    key={link.inviteUuid}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.5rem",
                      padding: "0.5rem 0.75rem",
                      background: link.isActive ? "var(--color-surface, #f9fafb)" : "#f3f4f6",
                      border: "1px solid var(--color-border, #e5e7eb)",
                      borderRadius: "6px",
                      opacity: link.isActive ? 1 : 0.6,
                    }}
                  >
                    <input
                      type="text"
                      readOnly
                      value={inviteUrl}
                      style={{
                        flex: 1,
                        background: "transparent",
                        border: "none",
                        fontSize: "0.8rem",
                        color: "var(--color-text, #111827)",
                        outline: "none",
                        cursor: "text",
                      }}
                      onClick={(e) => (e.target as HTMLInputElement).select()}
                    />
                    <span style={{
                      fontSize: "0.75rem",
                      padding: "1px 6px",
                      borderRadius: "4px",
                      background: link.isActive ? "#dcfce7" : "#f3f4f6",
                      color: link.isActive ? "#16a34a" : "#6b7280",
                      whiteSpace: "nowrap",
                    }}>
                      {link.isActive ? "Active" : "Inactive"}
                    </span>
                    {link.isActive && (
                      <>
                          <button
                            type="button"
                            onClick={() => void handleCopyLink(link)}
                            style={{
                              padding: "3px 10px",
                              fontSize: "0.75rem",
                            borderRadius: "4px",
                            border: "1px solid var(--color-border, #e5e7eb)",
                            background: "white",
                            cursor: "pointer",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {copiedUuid === link.inviteUuid ? "Copied!" : "Copy"}
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleDeactivateLink(link.inviteUuid)}
                          style={{
                            padding: "3px 10px",
                            fontSize: "0.75rem",
                            borderRadius: "4px",
                            border: "1px solid #fca5a5",
                            background: "#fef2f2",
                            color: "#dc2626",
                            cursor: "pointer",
                            whiteSpace: "nowrap",
                          }}
                        >
                          Deactivate
                        </button>
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ) : null}

      {error ? (
        <div className="course-management-inline-alert">
          <strong>Unable to load enrolled learners.</strong>
          <span>{error}</span>
        </div>
      ) : null}

      {!loading && enrollments.length === 0 ? (
        <div className="course-empty-state">
          <strong>No enrolled learners yet</strong>
          <p>This course does not have active learner enrollments at the moment.</p>
        </div>
      ) : null}

      {enrollments.length > 0 ? (
        <div className="course-management-list">
          {enrollments.map((enrollment) => (
            <article key={enrollment.learnerUuid} className="course-management-panel course-management-enrolment-card">
              <div className="course-management-enrolment-summary course-management-enrolment-summary-single-row">
                <strong>{enrollment.learnerName}</strong>
                <span>{formatProgress(enrollment)}</span>
                <span>{formatDateTime(enrollment.enrolledAt)}</span>
                <div className="course-management-enrolment-actions">
                  <span className="course-management-enrolment-status">
                    {enrollment.enrollmentStatus}
                  </span>
                  <button
                    type="button"
                    className="course-management-enrolment-toggle"
                    onClick={() =>
                      setExpandedLearnerUuid((current) =>
                        current === enrollment.learnerUuid ? null : enrollment.learnerUuid
                      )
                    }
                    aria-expanded={expandedLearnerUuid === enrollment.learnerUuid}
                    aria-label={
                      expandedLearnerUuid === enrollment.learnerUuid
                        ? `Collapse details for ${enrollment.learnerName}`
                        : `Expand details for ${enrollment.learnerName}`
                    }
                  >
                    {expandedLearnerUuid === enrollment.learnerUuid ? (
                      <LuChevronUp size={18} aria-hidden="true" />
                    ) : (
                      <LuChevronDown size={18} aria-hidden="true" />
                    )}
                  </button>
                </div>
              </div>
              {expandedLearnerUuid === enrollment.learnerUuid ? (
                <div className="course-management-enrolment-grid">
                  <div className="course-management-key-value">
                    <span>Email</span>
                    <strong>{enrollment.learnerEmail || "Not provided"}</strong>
                  </div>
                  <div className="course-management-key-value">
                    <span>Identity</span>
                    <strong>{enrollment.learnerIdentity || "Learner"}</strong>
                  </div>
                  <div className="course-management-key-value">
                    <span>Account status</span>
                    <strong>{enrollment.learnerAccountStatus || "Unknown"}</strong>
                  </div>
                  <div className="course-management-key-value">
                    <span>Email verified</span>
                    <strong>{enrollment.learnerEmailVerified ? "Verified" : "Pending"}</strong>
                  </div>
                  <div className="course-management-key-value">
                    <span>Progress</span>
                    <strong>{formatProgress(enrollment)}</strong>
                  </div>
                  <div className="course-management-key-value">
                    <span>Enrolled at</span>
                    <strong>{formatDateTime(enrollment.enrolledAt)}</strong>
                  </div>
                  <div className="course-management-key-value">
                    <span>Last accessed</span>
                    <strong>{formatDateTime(enrollment.lastAccessedAt)}</strong>
                  </div>
                  <div className="course-management-key-value">
                    <span>Completed at</span>
                    <strong>{formatDateTime(enrollment.completedAt)}</strong>
                  </div>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}

export default CourseManagementUserEnrolmentsPage;
