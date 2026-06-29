import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import AuthField from "../../components/auth/AuthField";
import AuthHeader from "../../components/auth/AuthHeader";
import AuthLayout from "../../components/auth/AuthLayout";
import AuthMessage from "../../components/auth/AuthMessage";
import { resetPassword } from "../../services/auth";
import { validatePassword, PASSWORD_HINT } from "../../utils/password";

function ResetPassword() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [form, setForm] = useState({
    newPassword: "",
    confirmPassword: "",
  });

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setForm({ ...form, [event.target.name]: event.target.value });
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setSuccess("");

    if (!token) {
      setError("Invalid or missing reset token. Please request a new reset link.");
      return;
    }

    if (!form.newPassword || !form.confirmPassword) {
      setError("Please fill in all fields.");
      return;
    }

    const pwdError = validatePassword(form.newPassword);
    if (pwdError) {
      setError(pwdError);
      return;
    }

    if (form.newPassword !== form.confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    try {
      setLoading(true);
      const response = await resetPassword({ token, newPassword: form.newPassword });
      setSuccess(response.detail);
      setTimeout(() => navigate("/login"), 2000);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("An unknown error occurred.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <AuthHeader
        badge="Account"
        title="Reset Password"
        description="Enter your new password below."
      />
      <form className="auth-form" onSubmit={handleSubmit}>
        <AuthField
          label="New Password"
          type="password"
          name="newPassword"
          placeholder={PASSWORD_HINT}
          value={form.newPassword}
          onChange={handleChange}
        />
        <AuthField
          label="Confirm New Password"
          type="password"
          name="confirmPassword"
          placeholder="Re-enter your new password"
          value={form.confirmPassword}
          onChange={handleChange}
        />

        {error && <AuthMessage tone="error" message={error} />}
        {success && <AuthMessage tone="success" message={success} />}

        <button className="primary-btn auth-submit-btn" type="submit" disabled={loading}>
          {loading ? "Resetting..." : "Reset Password"}
        </button>
      </form>

      <div className="auth-footer-links">
        <Link to="/login" className="text-link">
          Back to Log in
        </Link>
      </div>
    </AuthLayout>
  );
}

export default ResetPassword;
