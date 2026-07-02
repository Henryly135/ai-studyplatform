import { useState } from "react";
import { useNavigate } from "react-router-dom";

import AuthField from "../../components/auth/AuthField";
import AuthHeader from "../../components/auth/AuthHeader";
import AuthLayout from "../../components/auth/AuthLayout";
import AuthMessage from "../../components/auth/AuthMessage";
import { clearStoredSession } from "../../services/api";
import { changePassword } from "../../services/auth";
import { isUsableAccessToken } from "../../utils/accessToken";
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
      setError("请填写所有字段。");
      return;
    }

    const pwdError = validatePassword(form.newPassword);
    if (pwdError) {
      setError(pwdError);
      return;
    }

    if (form.newPassword !== form.confirmPassword) {
      setError("两次输入的新密码不一致。");
      return;
    }

    const accessToken = localStorage.getItem("accessToken");
    if (!accessToken || !isUsableAccessToken(accessToken)) {
      clearStoredSession();
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
        setError("发生未知错误。");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <AuthHeader
        badge="账号"
        title="修改密码"
        description="输入当前密码并设置新密码。"
      />
      <form className="auth-form" onSubmit={handleSubmit}>
        <AuthField
          label="当前密码"
          type="password"
          name="currentPassword"
          placeholder="请输入当前密码"
          value={form.currentPassword}
          onChange={handleChange}
        />
        <AuthField
          label="新密码"
          type="password"
          name="newPassword"
          placeholder={PASSWORD_HINT}
          value={form.newPassword}
          onChange={handleChange}
        />
        <AuthField
          label="确认新密码"
          type="password"
          name="confirmPassword"
          placeholder="请再次输入新密码"
          value={form.confirmPassword}
          onChange={handleChange}
        />

        {error && <AuthMessage tone="error" message={error} />}
        {success && <AuthMessage tone="success" message={success} />}

        <button className="primary-btn auth-submit-btn" type="submit" disabled={loading}>
          {loading ? "修改中..." : "修改密码"}
        </button>
      </form>
    </AuthLayout>
  );
}

export default ChangePassword;
