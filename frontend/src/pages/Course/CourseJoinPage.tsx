import { useEffect, useEffectEvent, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { enrolViaCourseInvite, validateCourseInviteToken } from "../../services/course";
import type { CourseInviteValidateResponse } from "../../types/admin";
import { emitAppRefresh } from "../../utils/refreshEvents";

const POST_AUTH_REDIRECT_STORAGE_KEY = "postAuthRedirect";
const PENDING_COURSE_INVITE_TOKEN_KEY = "pendingCourseInviteToken";

function CourseJoinPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const navigate = useNavigate();
  const autoEnrolAttemptedRef = useRef(false);

  const [courseInfo, setCourseInfo] = useState<CourseInviteValidateResponse | null>(null);
  const [validating, setValidating] = useState(true);
  const [tokenError, setTokenError] = useState("");
  const [enrolling, setEnrolling] = useState(false);
  const [enrollSuccess, setEnrollSuccess] = useState("");
  const [enrollError, setEnrollError] = useState("");

  const accessToken = localStorage.getItem("accessToken");
  const isLoggedIn = Boolean(accessToken);
  const redirectPath = `/courses/join?token=${encodeURIComponent(token)}`;

  useEffect(() => {
    if (!token) {
      setTokenError("No invite token provided.");
      setValidating(false);
      return;
    }

    const validate = async () => {
      try {
        const info = await validateCourseInviteToken(token);
        setCourseInfo(info);
      } catch (err) {
        setTokenError(err instanceof Error ? err.message : "Invalid or expired invite link.");
      } finally {
        setValidating(false);
      }
    };

    void validate();
  }, [token]);

  const runEnrol = async () => {
    if (!token) return;
    setEnrolling(true);
    setEnrollError("");
    try {
      const result = await enrolViaCourseInvite(token);
      setEnrollSuccess(result.detail);
      emitAppRefresh({ scope: "course:enrollment", courseUuid: result.courseUuid });
      emitAppRefresh({ scope: "course:catalog", courseUuid: result.courseUuid });
      localStorage.removeItem(POST_AUTH_REDIRECT_STORAGE_KEY);
      localStorage.removeItem(PENDING_COURSE_INVITE_TOKEN_KEY);
      // Navigate to the course after a short delay
      setTimeout(() => {
        navigate(`/course/${result.courseUuid}`);
      }, 1500);
    } catch (err) {
      setEnrollError(err instanceof Error ? err.message : "Failed to enrol.");
    } finally {
      setEnrolling(false);
    }
  };

  const performEnrol = useEffectEvent(async () => {
    await runEnrol();
  });

  const handleEnrol = () => {
    void runEnrol();
  };

  useEffect(() => {
    if (!token) {
      autoEnrolAttemptedRef.current = false;
      return;
    }
  }, [token]);

  useEffect(() => {
    if (!isLoggedIn || !courseInfo || !token || autoEnrolAttemptedRef.current || enrollSuccess) {
      return;
    }

    autoEnrolAttemptedRef.current = true;
    void performEnrol();
  }, [courseInfo, enrollSuccess, isLoggedIn, token]);

  const persistInviteContinuation = () => {
    localStorage.setItem(PENDING_COURSE_INVITE_TOKEN_KEY, token);
    localStorage.setItem(POST_AUTH_REDIRECT_STORAGE_KEY, redirectPath);
  };

  const handleLoginRedirect = () => {
    persistInviteContinuation();
    navigate(`/login?redirect=${encodeURIComponent(redirectPath)}`);
  };

  if (validating) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "60vh" }}>
        <p>Validating invite link...</p>
      </div>
    );
  }

  if (tokenError) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", minHeight: "60vh", padding: "2rem" }}>
        <h2>Invalid invite link</h2>
        <p style={{ color: "#ef4444", marginBottom: "1rem" }}>{tokenError}</p>
        <Link to="/" className="text-link">Go to home</Link>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", minHeight: "60vh", padding: "2rem" }}>
      <div style={{ maxWidth: "480px", width: "100%", textAlign: "center" }}>
        <span style={{
          display: "inline-block",
          background: "var(--color-accent, #3b82f6)",
          color: "white",
          padding: "2px 10px",
          borderRadius: "4px",
          fontSize: "0.75rem",
          fontWeight: 600,
          marginBottom: "1rem",
          letterSpacing: "0.05em",
        }}>
          COURSE INVITE
        </span>

        <h1 style={{ marginBottom: "0.5rem" }}>
          You've been invited to join
        </h1>
        <h2 style={{ color: "var(--color-accent, #3b82f6)", marginBottom: "1.5rem" }}>
          {courseInfo?.courseTitle}
        </h2>

        {enrollSuccess ? (
          <div>
            <p style={{ color: "#22c55e", fontWeight: 600, marginBottom: "0.5rem" }}>{enrollSuccess}</p>
            <p style={{ color: "var(--color-text-muted, #6b7280)", fontSize: "0.9rem" }}>
              Redirecting you to the course...
            </p>
          </div>
        ) : isLoggedIn ? (
          <div>
            {!enrollError && (
              <p style={{ marginBottom: "1rem", color: "var(--color-text-muted, #6b7280)" }}>
                Signing you up for this course now...
              </p>
            )}
            {enrollError && (
              <p style={{ color: "#ef4444", marginBottom: "1rem" }}>{enrollError}</p>
            )}
            {enrollError && (
              <button
                className="primary-btn"
                style={{ padding: "0.75rem 2rem", fontSize: "1rem" }}
                onClick={handleEnrol}
                disabled={enrolling}
              >
                {enrolling ? "Enrolling..." : "Try joining again"}
              </button>
            )}
            <div style={{ marginTop: "1rem" }}>
              <Link to="/home" className="text-link">Go to my courses instead</Link>
            </div>
          </div>
        ) : (
          <div>
            <p style={{ marginBottom: "1.5rem", color: "var(--color-text-muted, #6b7280)" }}>
              You need to log in or create an account to join this course.
            </p>
            <div style={{ display: "flex", gap: "1rem", justifyContent: "center", flexWrap: "wrap" }}>
              <button
                className="primary-btn"
                style={{ padding: "0.75rem 2rem" }}
                onClick={handleLoginRedirect}
              >
                Log in to join
              </button>
              <Link
                to={`/register/learner?redirect=${encodeURIComponent(redirectPath)}`}
                className="primary-btn"
                style={{ padding: "0.75rem 2rem", textDecoration: "none", display: "inline-block" }}
                onClick={persistInviteContinuation}
              >
                Create account
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default CourseJoinPage;
