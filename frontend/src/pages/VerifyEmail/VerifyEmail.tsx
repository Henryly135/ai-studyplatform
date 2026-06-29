import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import AuthHeader from "../../components/auth/AuthHeader";
import AuthLayout from "../../components/auth/AuthLayout";
import AuthMessage from "../../components/auth/AuthMessage";
import { verifyEmail } from "../../services/auth";

const POST_AUTH_REDIRECT_STORAGE_KEY = "postAuthRedirect";

function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const redirectPath = localStorage.getItem(POST_AUTH_REDIRECT_STORAGE_KEY) ?? "";
  const loginLink = redirectPath
    ? `/login?redirect=${encodeURIComponent(redirectPath)}`
    : "/login";

  const [status, setStatus] = useState<"loading" | "success" | "error">(
    () => (token ? "loading" : "error")
  );
  const [message, setMessage] = useState(
    () => (token ? "" : "Invalid or missing verification token.")
  );
  const called = useRef(false);

  useEffect(() => {
    if (!token || called.current) return;
    called.current = true;

    verifyEmail(token)
      .then((res) => {
        setMessage(res.detail);
        setStatus("success");
      })
      .catch((err) => {
        setMessage(err instanceof Error ? err.message : "Email verification failed.");
        setStatus("error");
      });
  }, [token]);

  return (
    <AuthLayout>
      <AuthHeader
        
        title="Email Verification"
        description="Verifying your email address."
      />

      <div>
        {status === "loading" && <p>Verifying...</p>}
        {status === "success" && (
          <>
            <AuthMessage tone="success" message="Email verified successfully! You can now log in." />
            <div className="auth-footer-links">
              <Link to={loginLink} className="text-link">
                Continue to Login
              </Link>
            </div>
          </>
        )}
        {status === "error" && (
          <>
            <AuthMessage tone="error" message={message} />
            <div className="auth-footer-links">
              <Link to="/login" className="text-link">Back to Login</Link>
            </div>
          </>
        )}
      </div>
    </AuthLayout>
  );
}

export default VerifyEmail;
