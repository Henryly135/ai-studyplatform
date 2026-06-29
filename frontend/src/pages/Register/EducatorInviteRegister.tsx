import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import AuthHeader from "../../components/auth/AuthHeader";
import AuthLayout from "../../components/auth/AuthLayout";
import AuthMessage from "../../components/auth/AuthMessage";
import RegisterForm from "../../components/auth/RegisterForm";
import { registerEducatorViaInvite, resendVerification, validateEducatorInviteToken } from "../../services/auth";
import { validatePassword } from "../../utils/password";

function EducatorInviteRegister() {
  const [searchParams] = useSearchParams();
  const inviteToken = searchParams.get("token") ?? "";

  const [tokenValid, setTokenValid] = useState<boolean | null>(null);
  const [tokenError, setTokenError] = useState("");
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

  useEffect(() => {
    if (!inviteToken) {
      setTokenValid(false);
      setTokenError("No invite token provided. Please use the link from your invitation email.");
      return;
    }

    const validate = async () => {
      try {
        await validateEducatorInviteToken(inviteToken);
        setTokenValid(true);
      } catch (err) {
        setTokenValid(false);
        setTokenError(err instanceof Error ? err.message : "Invalid or expired invite link.");
      }
    };

    void validate();
  }, [inviteToken]);

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [event.target.name]: event.target.value }));
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

    if (!inviteToken) {
      setError("Missing invite information. Please use the link from your invitation email.");
      return;
    }

    try {
      setLoading(true);
      await registerEducatorViaInvite({
        userName: form.usrName,
        email: form.email,
        password: form.password,
        inviteToken: inviteToken,
      });
      setRegisteredEmail(form.email);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed.");
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

  if (tokenValid === null) {
    return (
      <AuthLayout>
        <AuthHeader title="Validating invite link" description="Please wait..." badge="" />
      </AuthLayout>
    );
  }

  if (tokenValid === false) {
    return (
      <AuthLayout>
        <AuthHeader
          title="Invalid invite link"
          description="This invite link is invalid, expired, or has already been used."
        />
        <div style={{ textAlign: "center", padding: "0.5rem 0" }}>
          <AuthMessage tone="error" message={tokenError || "Please contact your administrator for a new invite."} />
          <div className="auth-footer-links" style={{ marginTop: "1rem" }}>
            <Link to="/login" className="text-link">Back to Login</Link>
          </div>
        </div>
      </AuthLayout>
    );
  }

  if (registeredEmail) {
    return (
      <AuthLayout>
        <AuthHeader
          title="Check your email"
          description={`We've sent a verification link to ${registeredEmail}. Click the link to activate your account and access all educator features.`}
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
            <Link to="/login" className="text-link">Back to Login</Link>
          </div>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <AuthHeader
        badge="Invited"
        title="Create educator account"
        description="You've been invited to join as an educator. Set up your account to get started — no approval required."
      />
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

export default EducatorInviteRegister;
