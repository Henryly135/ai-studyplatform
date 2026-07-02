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
      setError("重置令牌无效或缺失，请重新申请重置链接。");
      return;
    }

    if (!form.newPassword || !form.confirmPassword) {
      setError("请填写所有字段。");
      return;
    }

    const pwdError = validatePassword(form.newPassword);
    if (pwdError) {
      setError(pwdError);
      return;
    }

    if (form.newPassword !== form.confirmPassword) {
      setError("两次输入的密码不一致。");
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
        title="重置密码"
        description="请在下方输入新密码。"
      />
      <form className="auth-form" onSubmit={handleSubmit}>
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
          {loading ? "重置中..." : "重置密码"}
        </button>
      </form>

      <div className="auth-footer-links">
        <Link to="/login" className="text-link">
          返回登录
        </Link>
      </div>
    </AuthLayout>
  );
}

export default ResetPassword;
