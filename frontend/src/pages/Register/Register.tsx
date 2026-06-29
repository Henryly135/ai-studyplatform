import { useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import AuthHeader from "../../components/auth/AuthHeader";
import AuthLayout from "../../components/auth/AuthLayout";
import AuthMessage from "../../components/auth/AuthMessage";
import RegisterForm from "../../components/auth/RegisterForm";
import { registerUser, resendVerification } from "../../services/auth";
import type { Identity } from "../../types/auth";
import { validatePassword } from "../../utils/password";

const POST_AUTH_REDIRECT_STORAGE_KEY = "postAuthRedirect";

function getRegisterErrorMessage(error: unknown): string {
  if (!(error instanceof Error)) {
    return "An unknown error occurred.";
  }

  switch (error.message) {
    case "Account pending approval":
      return "Your account is already pending admin approval and cannot be registered again.";
    default:
      return error.message;
  }
}

function Register() {
  const { role } = useParams();
  const [searchParams] = useSearchParams();
  const redirectPath = searchParams.get("redirect") ?? "";

  const identity: Identity = useMemo(() => {
    if (role === "educator" || role === "teacher") return "Educator";
    return "Learner";
  }, [role]);

  const title =
    identity === "Educator" ? "Create educator account" : "Create learner account";

  const description =
    identity === "Educator"
      ? "Set up your educator profile to create courses and support learners."
      : "Create your learner account to join classes and track your progress.";

  const [form, setForm] = useState({
    usrName: "",
    email: "",
    password: "",
    confirmPassword: "",
  });

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [agreedToTerms, setAgreedToTerms] = useState(false);
  const [registeredEmail, setRegisteredEmail] = useState("");
  const [resendMessage, setResendMessage] = useState("");
  const [resendLoading, setResendLoading] = useState(false);

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({
      ...prev,
      [event.target.name]: event.target.value,
    }));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");

    if (!form.usrName || !form.email || !form.password || !form.confirmPassword) {
      setError("Please fill in all fields.");
      return;
    }

    if (!agreedToTerms) {
      setError("Please agree to the Terms of Service to continue.");
      return;
    }

    const pwdError = validatePassword(form.password);
    if (pwdError) {
      setError(pwdError);
      return;
    }

    if (form.password !== form.confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    try {
      setLoading(true);
      if (redirectPath) {
        localStorage.setItem(POST_AUTH_REDIRECT_STORAGE_KEY, redirectPath);
      }
      await registerUser({
        userName: form.usrName,
        email: form.email,
        password: form.password,
        identity: identity,
      });
      setRegisteredEmail(form.email);
    } catch (err) {
      setError(getRegisterErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setResendMessage("");
    setResendLoading(true);
    try {
      await resendVerification(registeredEmail);
      setResendMessage("Verification email resent. Please check your inbox.");
    } catch (err) {
      setResendMessage(err instanceof Error ? err.message : "Failed to resend email.");
    } finally {
      setResendLoading(false);
    }
  };

  if (registeredEmail) {
    return (
      <AuthLayout>
        <AuthHeader
          title="Check your email"
          description={`We've sent a verification link to ${registeredEmail}. Click the link to activate your account.`}
        />
        <div style={{ textAlign: "center", padding: "0.5rem 0" }}>
          {resendMessage && (
            <AuthMessage
              tone={resendMessage.startsWith("Verification email resent") ? "success" : "error"}
              message={resendMessage}
            />
          )}
          <p style={{ marginBottom: "1rem", color: "var(--color-text-muted, #6b7280)", fontSize: "0.9rem" }}>
            Didn't receive it?
          </p>
          <button
            className="primary-btn auth-submit-btn"
            onClick={handleResend}
            disabled={resendLoading}
          >
            {resendLoading ? "Resending..." : "Resend verification email"}
          </button>
          <div className="auth-footer-links" style={{ marginTop: "1rem" }}>
            <Link
              to={redirectPath ? `/login?redirect=${encodeURIComponent(redirectPath)}` : "/login"}
              className="text-link"
            >
              Back to Login
            </Link>
          </div>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <AuthHeader badge="" title={title} description={description} />
      <RegisterForm
        form={form}
        error={error}
        success=""
        loading={loading}
        agreedToTerms={agreedToTerms}
        onAgreeChange={setAgreedToTerms}
        onChange={handleChange}
        onSubmit={handleSubmit}
      />
    </AuthLayout>
  );
}

export default Register;
