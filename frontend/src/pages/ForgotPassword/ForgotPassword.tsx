import { useState } from "react";
import { Link } from "react-router-dom";

import AuthField from "../../components/auth/AuthField";
import AuthHeader from "../../components/auth/AuthHeader";
import AuthLayout from "../../components/auth/AuthLayout";
import AuthMessage from "../../components/auth/AuthMessage";
import { forgotPassword } from "../../services/auth";

function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setSuccess("");

    if (!email) {
      setError("请输入邮箱地址。");
      return;
    }

    try {
      setLoading(true);
      const response = await forgotPassword(email);
      setSuccess(response.detail);
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
        title="忘记密码"
        description="输入邮箱后，我们会向你发送重置链接。"
      />
      <form className="auth-form" onSubmit={handleSubmit}>
        <AuthField
          label="邮箱"
          type="email"
          name="email"
          placeholder="请输入邮箱"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />

        {error && <AuthMessage tone="error" message={error} />}
        {success && <AuthMessage tone="success" message={success} />}

        <button className="primary-btn auth-submit-btn" type="submit" disabled={loading}>
          {loading ? "发送中..." : "发送重置链接"}
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

export default ForgotPassword;
