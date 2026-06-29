import { useState } from "react";
import { useNavigate } from "react-router-dom";

import AuthField from "../../components/auth/AuthField";
import AuthHeader from "../../components/auth/AuthHeader";
import AuthLayout from "../../components/auth/AuthLayout";
import AuthMessage from "../../components/auth/AuthMessage";
import { changePassword } from "../../services/auth";
import { validatePassword, PASSWORD_HINT } from "../../utils/password";

function ChangePassword() {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    currentPassword: "",
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

    if (!form.currentPassword || !form.newPassword || !form.confirmPassword) {
      setError("Please fill in all fields.");
      return;
    }

    const pwdError = validatePassword(form.newPassword);
    if (pwdError) {
      setError(pwdError);
      return;
    }

    if (form.newPassword !== form.confirmPassword) {
      setError("New passwords do not match.");
      return;
    }

    const accessToken = localStorage.getItem("accessToken");
    if (!accessToken) {
      navigate("/login");
      return;
    }

    try {
      setLoading(true);
      const response = await changePassword(
        { currentPassword: form.currentPassword, newPassword: form.newPassword },
        accessToken
      );
      setSuccess(response.detail);
      setForm({ currentPassword: "", newPassword: "", confirmPassword: "" });
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
        title="Change Password"
        description="Enter your current password and choose a new one."
      />
      <form className="auth-form" onSubmit={handleSubmit}>
        <AuthField
          label="Current Password"
          type="password"
          name="currentPassword"
          placeholder="Enter your current password"
          value={form.currentPassword}
          onChange={handleChange}
        />
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
          {loading ? "Changing..." : "Change Password"}
        </button>
      </form>
    </AuthLayout>
  );
}

export default ChangePassword;
