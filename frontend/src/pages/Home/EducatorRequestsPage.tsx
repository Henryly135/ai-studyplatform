import { useEffect, useMemo, useRef, useState } from "react";
import { LuX } from "react-icons/lu";

import "./EducatorRequestsPage.css";
import {
  generateEducatorInviteToken,
  getEducatorApprovalDetail,
  getPendingEducatorApprovals,
  getReviewedEducatorApprovals,
  reviewEducatorApproval,
  sendEducatorInviteEmail,
} from "../../services/admin";
import { copyTextToClipboard } from "../../utils/clipboard";
import type {
  EducatorApprovalAction,
  EducatorApprovalResponse,
  EducatorInviteTokenGenerateResponse,
} from "../../types/admin";
import { emitAppRefresh, subscribeAppRefresh } from "../../utils/refreshEvents";

function formatDateTime(value: string | null) {
  if (!value) return "Not available";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat("en-AU", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function statusLabel(status: string) {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function EducatorRequestsPage() {
  const [pendingRequests, setPendingRequests] = useState<EducatorApprovalResponse[]>([]);
  const [reviewedRequests, setReviewedRequests] = useState<EducatorApprovalResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [selectedRequestUuid, setSelectedRequestUuid] = useState<string | null>(null);
  const [selectedRequest, setSelectedRequest] = useState<EducatorApprovalResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [reviewComment, setReviewComment] = useState("");
  const [submittingAction, setSubmittingAction] = useState<EducatorApprovalAction | null>(null);

  // Educator invite link state
  const [inviteToken, setInviteToken] = useState<EducatorInviteTokenGenerateResponse | null>(null);
  const [generatingInvite, setGeneratingInvite] = useState(false);
  const [inviteError, setInviteError] = useState("");
  const [inviteCopyError, setInviteCopyError] = useState("");
  const [inviteCopied, setInviteCopied] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [sendingEmail, setSendingEmail] = useState(false);
  const [emailSentMessage, setEmailSentMessage] = useState("");
  const inviteLinkRef = useRef<HTMLInputElement>(null);

  const loadRequests = async () => {
    const accessToken = localStorage.getItem("accessToken");

    if (!accessToken) {
      setErrorMessage("Missing access token. Please log in again.");
      setLoading(false);
      return;
    }

    try {
      setLoading(true);

      const [pendingData, reviewedData] = await Promise.all([
        getPendingEducatorApprovals(accessToken),
        getReviewedEducatorApprovals(accessToken, "reviewed"),
      ]);

      setPendingRequests(pendingData.requests);
      setReviewedRequests(reviewedData.requests);
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Failed to fetch educator approval requests."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadRequests();
  }, []);

  useEffect(() => {
    return subscribeAppRefresh(["admin:educator-requests"], () => {
      void loadRequests();
    });
  }, []);

  useEffect(() => {
    if (!successMessage) return;

    const timer = window.setTimeout(() => setSuccessMessage(""), 2400);
    return () => window.clearTimeout(timer);
  }, [successMessage]);

  const selectedSummary = useMemo(() => {
    if (!selectedRequestUuid) return null;

    return (
      pendingRequests.find((item) => item.requestUuid === selectedRequestUuid) ??
      reviewedRequests.find((item) => item.requestUuid === selectedRequestUuid) ??
      null
    );
  }, [pendingRequests, reviewedRequests, selectedRequestUuid]);

  const openRequestDetail = async (requestUuid: string) => {
    const accessToken = localStorage.getItem("accessToken");

    setSelectedRequestUuid(requestUuid);
    setDetailLoading(true);
    setDetailError("");
    setReviewComment("");

    if (!accessToken) {
      setDetailLoading(false);
      setDetailError("Missing access token. Please log in again.");
      return;
    }

    try {
      const detail = await getEducatorApprovalDetail(accessToken, requestUuid);
      setSelectedRequest(detail);
      setReviewComment(detail.reviewComment ?? "");
    } catch (error) {
      setSelectedRequest(null);
      setDetailError(
        error instanceof Error
          ? error.message
          : "Failed to fetch educator request details."
      );
    } finally {
      setDetailLoading(false);
    }
  };

  const closeDetail = () => {
    setSelectedRequestUuid(null);
    setSelectedRequest(null);
    setDetailError("");
    setReviewComment("");
    setSubmittingAction(null);
  };

  const handleReview = async (action: EducatorApprovalAction) => {
    if (!selectedRequestUuid) return;

    const accessToken = localStorage.getItem("accessToken");
    if (!accessToken) {
      setDetailError("Missing access token. Please log in again.");
      return;
    }

    try {
      setSubmittingAction(action);
      const updatedRequest = await reviewEducatorApproval(accessToken, selectedRequestUuid, {
        action,
        reviewComment: reviewComment.trim() || undefined,
      });

      setPendingRequests((current) =>
        current.filter((item) => item.requestUuid !== selectedRequestUuid)
      );
      setReviewedRequests((current) => [
        updatedRequest,
        ...current.filter((item) => item.requestUuid !== selectedRequestUuid),
      ]);
      setSelectedRequest(updatedRequest);
      setReviewComment(updatedRequest.reviewComment ?? "");
      setDetailError("");
      await loadRequests();
      emitAppRefresh({ scope: "admin:educator-requests" });
      emitAppRefresh({ scope: "admin:users" });
      setSuccessMessage(
        action === "approve"
          ? "Educator request approved successfully."
          : "Educator request rejected successfully."
      );
    } catch (error) {
      setDetailError(
        error instanceof Error ? error.message : "Failed to review educator request."
      );
    } finally {
      setSubmittingAction(null);
    }
  };

  const handleGenerateInvite = async () => {
    const accessToken = localStorage.getItem("accessToken");
    if (!accessToken) return;
    setGeneratingInvite(true);
    setInviteError("");
    setInviteCopyError("");
    setInviteCopied(false);
    setEmailSentMessage("");
    try {
      const result = await generateEducatorInviteToken(accessToken);
      setInviteToken(result);
    } catch (err) {
      setInviteError(err instanceof Error ? err.message : "Failed to generate invite link.");
    } finally {
      setGeneratingInvite(false);
    }
  };

  const handleCopyInviteLink = async () => {
    if (!inviteToken?.inviteUrl) return;

    const copied = await copyTextToClipboard(inviteToken.inviteUrl);
    if (copied) {
      setInviteCopied(true);
      setInviteCopyError("");
      setTimeout(() => setInviteCopied(false), 2000);
      return;
    }

    setInviteCopyError("Failed to copy the invite link. Please select it manually and copy again.");
  };

  const handleSendInviteEmail = async () => {
    if (!inviteToken || !inviteEmail.trim()) return;
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(inviteEmail.trim())) {
      setEmailSentMessage("Please enter a valid email address.");
      return;
    }
    const accessToken = localStorage.getItem("accessToken");
    if (!accessToken) return;
    setSendingEmail(true);
    setEmailSentMessage("");
    try {
      await sendEducatorInviteEmail(accessToken, inviteToken.inviteUuid, {
        recipientEmail: inviteEmail.trim(),
        inviteUrl: inviteToken.inviteUrl,
      });
      setEmailSentMessage(`Invite email sent to ${inviteEmail.trim()}`);
      setInviteEmail("");
    } catch (err) {
      setEmailSentMessage(err instanceof Error ? err.message : "Failed to send email.");
    } finally {
      setSendingEmail(false);
    }
  };

  const renderRequestTable = (
    title: string,
    description: string,
    requests: EducatorApprovalResponse[],
    emptyMessage: string
  ) => (
    <section className="educator-requests-panel">
      <div className="educator-requests-panel-header">
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        <span className="educator-requests-count">{requests.length}</span>
      </div>

      <div className="educator-requests-table-wrapper">
        <table className="educator-requests-table">
          <thead>
            <tr>
              <th>User</th>
              <th>Email</th>
              <th>Status</th>
              <th>Submitted</th>
              <th>Updated</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {requests.length === 0 ? (
              <tr>
                <td colSpan={6} className="educator-requests-empty">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              requests.map((request) => (
                <tr key={request.requestUuid}>
                  <td>
                    <strong>{request.userName}</strong>
                  </td>
                  <td>{request.email}</td>
                  <td>
                    <span className={`educator-requests-status educator-requests-status-${request.requestStatus}`}>
                      {statusLabel(request.requestStatus)}
                    </span>
                  </td>
                  <td>{formatDateTime(request.submittedAt)}</td>
                  <td>{formatDateTime(request.updatedAt)}</td>
                  <td>
                    <button
                      type="button"
                      className="educator-requests-link"
                      onClick={() => void openRequestDetail(request.requestUuid)}
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );

  const activeRequest = selectedRequest ?? selectedSummary;
  const isPending = activeRequest?.requestStatus === "pending";

  return (
    <section className="educator-requests-page">
      {successMessage ? (
        <div className="educator-requests-toast" role="status" aria-live="polite">
          <strong>Success</strong>
          <span>{successMessage}</span>
        </div>
      ) : null}

      <div className="educator-requests-card">
        {loading ? (
          <p className="educator-requests-feedback">Loading educator requests...</p>
        ) : null}

        {!loading && errorMessage ? (
          <p className="educator-requests-feedback educator-requests-feedback-error">
            {errorMessage}
          </p>
        ) : null}

        <div className="educator-requests-panel" style={{ marginBottom: "1.5rem" }}>
          <div className="educator-requests-panel-header">
            <div>
              <h2>Educator Invite Links</h2>
              <p>Generate a one-time link to invite someone to register as an educator directly (no approval required).</p>
            </div>
          </div>
          <div style={{ padding: "1rem 1.5rem" }}>
            <button
              type="button"
              className="educator-requests-action educator-requests-action-approve"
              onClick={() => void handleGenerateInvite()}
              disabled={generatingInvite}
              style={{ marginBottom: "1rem" }}
            >
              {generatingInvite ? "Generating..." : "Generate Educator Invite Link"}
            </button>

            {inviteError && (
              <p className="educator-requests-feedback educator-requests-feedback-error">{inviteError}</p>
            )}

            {inviteCopyError && (
              <p className="educator-requests-feedback educator-requests-feedback-error">{inviteCopyError}</p>
            )}

            {inviteToken && (
              <div style={{ marginTop: "0.75rem" }}>
                <p style={{ fontSize: "0.85rem", color: "var(--color-text-muted, #6b7280)", marginBottom: "0.5rem" }}>
                  This link is one-time use and expires in 7 days. Share it directly or send via email below.
                </p>
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginBottom: "0.75rem" }}>
                  <input
                    ref={inviteLinkRef}
                    type="text"
                    readOnly
                    value={inviteToken.inviteUrl}
                    style={{
                      flex: 1,
                      padding: "0.5rem 0.75rem",
                      border: "1px solid var(--color-border, #e5e7eb)",
                      borderRadius: "6px",
                      fontSize: "0.85rem",
                      background: "var(--color-surface, #f9fafb)",
                    }}
                    onClick={(e) => (e.target as HTMLInputElement).select()}
                  />
                  <button
                    type="button"
                    className="educator-requests-action educator-requests-action-approve"
                    onClick={() => void handleCopyInviteLink()}
                    style={{ whiteSpace: "nowrap" }}
                  >
                    {inviteCopied ? "Copied!" : "Copy Link"}
                  </button>
                </div>

                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <input
                    type="email"
                    placeholder="Send to email address (optional)"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    style={{
                      flex: 1,
                      padding: "0.5rem 0.75rem",
                      border: "1px solid var(--color-border, #e5e7eb)",
                      borderRadius: "6px",
                      fontSize: "0.85rem",
                    }}
                  />
                  <button
                    type="button"
                    className="educator-requests-action educator-requests-action-approve"
                    onClick={() => void handleSendInviteEmail()}
                    disabled={!inviteEmail.trim() || sendingEmail}
                    style={{ whiteSpace: "nowrap" }}
                  >
                    {sendingEmail ? "Sending..." : "Send Email"}
                  </button>
                </div>

                {emailSentMessage && (
                  <p style={{
                    marginTop: "0.5rem",
                    fontSize: "0.85rem",
                    color: emailSentMessage.startsWith("Invite email sent") ? "#22c55e" : "#ef4444",
                  }}>
                    {emailSentMessage}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>

        {!loading && !errorMessage ? (
          <div className="educator-requests-grid">
            {renderRequestTable(
              "Pending Requests",
              "Applications waiting for admin review.",
              pendingRequests,
              "No pending educator requests."
            )}
            {renderRequestTable(
              "Reviewed Requests",
              "Applications that have already been approved or rejected.",
              reviewedRequests,
              "No reviewed educator requests."
            )}
          </div>
        ) : null}
      </div>

      {selectedRequestUuid ? (
        <div className="educator-requests-modal-backdrop" onClick={closeDetail}>
          <div
            className="educator-requests-modal"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="educator-requests-modal-header">
              <div>
                <span className="educator-requests-modal-kicker">Request Details</span>
                <h2>{activeRequest?.userName ?? "Educator request"}</h2>
              </div>
              <button
                type="button"
                className="educator-requests-close"
                onClick={closeDetail}
                aria-label="Close request details"
              >
                <LuX size={18} aria-hidden="true" />
              </button>
            </div>

            <div className="educator-requests-modal-body">
              {detailLoading ? (
                <p className="educator-requests-feedback">Loading request details...</p>
              ) : null}

              {!detailLoading && detailError ? (
                <p className="educator-requests-feedback educator-requests-feedback-error">
                  {detailError}
                </p>
              ) : null}

              {!detailLoading && !detailError && activeRequest ? (
                <div className="educator-requests-detail">
                  <div className="educator-requests-detail-grid">
                    <div className="educator-requests-detail-card">
                      <h3>Applicant</h3>
                      <dl>
                        <div><dt>Name</dt><dd>{activeRequest.userName}</dd></div>
                        <div><dt>Email</dt><dd>{activeRequest.email}</dd></div>
                        <div><dt>Identity</dt><dd>{activeRequest.identity}</dd></div>
                        <div><dt>Email Verified</dt><dd>{activeRequest.emailVerified ? "Yes" : "No"}</dd></div>
                      </dl>
                    </div>

                    <div className="educator-requests-detail-card">
                      <h3>Request</h3>
                      <dl>
                        <div>
                          <dt>Status</dt>
                          <dd>
                            <span className={`educator-requests-status educator-requests-status-${activeRequest.requestStatus}`}>
                              {statusLabel(activeRequest.requestStatus)}
                            </span>
                          </dd>
                        </div>
                        <div><dt>Submitted</dt><dd>{formatDateTime(activeRequest.submittedAt)}</dd></div>
                        <div><dt>Reviewed</dt><dd>{formatDateTime(activeRequest.reviewedAt)}</dd></div>
                        <div>
                          <dt>Reviewer</dt>
                          <dd>{activeRequest.reviewerName ?? activeRequest.reviewerEmail ?? "Not reviewed yet"}</dd>
                        </div>
                      </dl>
                    </div>
                  </div>

                  <div className="educator-requests-detail-card">
                    <h3>Supporting Information</h3>
                    <p className="educator-requests-supporting-text">
                      {activeRequest.supportingInfo?.trim() || "No supporting information was provided."}
                    </p>
                    {activeRequest.supportingFileUrl ? (
                      <a
                        className="educator-requests-file-link"
                        href={activeRequest.supportingFileUrl}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Open supporting file
                      </a>
                    ) : null}
                  </div>

                  <div className="educator-requests-detail-card">
                    <h3>Review Comment</h3>
                    <textarea
                      className="educator-requests-textarea"
                      value={reviewComment}
                      onChange={(event) => setReviewComment(event.target.value)}
                      placeholder="Leave an optional review comment."
                      disabled={!isPending || submittingAction !== null}
                    />

                    {isPending ? (
                      <div className="educator-requests-actions">
                        <button
                          type="button"
                          className="educator-requests-action educator-requests-action-reject"
                          onClick={() => void handleReview("reject")}
                          disabled={submittingAction !== null}
                        >
                          {submittingAction === "reject" ? "Rejecting..." : "Reject"}
                        </button>
                        <button
                          type="button"
                          className="educator-requests-action educator-requests-action-approve"
                          onClick={() => void handleReview("approve")}
                          disabled={submittingAction !== null}
                        >
                          {submittingAction === "approve" ? "Approving..." : "Approve"}
                        </button>
                      </div>
                    ) : (
                      <p className="educator-requests-reviewed-note">
                        This request has already been reviewed and is read-only now.
                      </p>
                    )}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

export default EducatorRequestsPage;
