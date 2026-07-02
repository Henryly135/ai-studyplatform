import { useEffect, useEffectEvent, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { clearStoredSession } from "../../services/api";
import { enrolViaCourseInvite, validateCourseInviteToken } from "../../services/course";
import type { CourseInviteValidateResponse } from "../../types/admin";
import { isUsableAccessToken } from "../../utils/accessToken";
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
  const isLoggedIn = isUsableAccessToken(accessToken);
  const redirectPath = `/courses/join?token=${encodeURIComponent(token)}`;
  const courseCenterRedirectPath = "/home/course-center";
  const courseCenterPath = isLoggedIn
    ? courseCenterRedirectPath
    : `/login?redirect=${encodeURIComponent(courseCenterRedirectPath)}`;

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
        setTokenError(err instanceof Error ? err.message : "邀请链接无效或已过期。");
      } finally {
        setValidating(false);
      }
    };

    void validate();
  }, [token]);

  useEffect(() => {
    if (accessToken && !isLoggedIn) {
      clearStoredSession();
    }
  }, [accessToken, isLoggedIn]);

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
        <p>正在验证邀请链接...</p>
      </div>
    );
  }

  if (tokenError) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", minHeight: "60vh", padding: "2rem" }}>
        <h2>{token ? "Invite link unavailable" : "Invite link missing"}</h2>
        <p style={{ color: "#ef4444", marginBottom: "1rem" }}>{tokenError}</p>
        <p style={{ color: "var(--color-text-muted, #6b7280)", maxWidth: "32rem", textAlign: "center", marginBottom: "1rem" }}>请向教师索要新的邀请链接，或前往课程大厅浏览可加入课程。
        </p>
        <div style={{ display: "flex", gap: "1rem", justifyContent: "center", flexWrap: "wrap" }}>
          <Link to={courseCenterPath} className="primary-btn" style={{ textDecoration: "none", display: "inline-block" }}>前往课程大厅
          </Link>
          <Link to="/" className="text-link">返回首页</Link>
        </div>
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
        }}>课程邀请
        </span>

        <h1 style={{ marginBottom: "0.5rem" }}>你已受邀加入
        </h1>
        <h2 style={{ color: "var(--color-accent, #3b82f6)", marginBottom: "1.5rem" }}>
          {courseInfo?.courseTitle}
        </h2>

        {enrollSuccess ? (
          <div>
            <p style={{ color: "#22c55e", fontWeight: 600, marginBottom: "0.5rem" }}>{enrollSuccess}</p>
            <p style={{ color: "var(--color-text-muted, #6b7280)", fontSize: "0.9rem" }}>正在跳转到课程...
            </p>
          </div>
        ) : isLoggedIn ? (
          <div>
            {!enrollError && (
              <p style={{ marginBottom: "1rem", color: "var(--color-text-muted, #6b7280)" }}>正在为你加入该课程...
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
                {enrolling ? "报名中..." : "Try joining again"}
              </button>
            )}
            <div style={{ marginTop: "1rem" }}>
              <Link to="/home" className="text-link">改去我的课程</Link>
            </div>
          </div>
        ) : (
          <div>
            <p style={{ marginBottom: "1.5rem", color: "var(--color-text-muted, #6b7280)" }}>你需要登录或创建账号后才能加入这门课程。
            </p>
            <div style={{ display: "flex", gap: "1rem", justifyContent: "center", flexWrap: "wrap" }}>
              <button
                className="primary-btn"
                style={{ padding: "0.75rem 2rem" }}
                onClick={handleLoginRedirect}
              >登录并加入
              </button>
              <Link
                to={`/register/learner?redirect=${encodeURIComponent(redirectPath)}`}
                className="primary-btn"
                style={{ padding: "0.75rem 2rem", textDecoration: "none", display: "inline-block" }}
                onClick={persistInviteContinuation}
              >创建账号
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default CourseJoinPage;
