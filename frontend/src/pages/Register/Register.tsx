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
    return "发生未知错误。";
  }

  switch (error.message) {
    case "Account pending approval":
      return "你的账号已经在等待管理员审批，不能重复注册。";
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
    identity === "Educator" ? "创建教师账号" : "创建学生账号";

  const description =
    identity === "Educator"
      ? "设置教师资料，用于创建课程并支持学生学习。"
      : "创建学生账号，加入课程并追踪学习进度。";

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
      setError("请填写所有字段。");
      return;
    }

    if (!agreedToTerms) {
      setError("请先同意服务条款。");
      return;
    }

    const pwdError = validatePassword(form.password);
    if (pwdError) {
      setError(pwdError);
      return;
    }

    if (form.password !== form.confirmPassword) {
      setError("两次输入的密码不一致。");
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
      setResendMessage("验证邮件已重新发送，请检查收件箱。");
    } catch (err) {
      setResendMessage(err instanceof Error ? err.message : "邮件重新发送失败。");
    } finally {
      setResendLoading(false);
    }
  };

  if (registeredEmail) {
    return (
      <AuthLayout>
        <AuthHeader
          title="请检查邮箱"
          description={`我们已向 ${registeredEmail} 发送验证链接。请点击链接激活账号。`}
        />
        <div style={{ textAlign: "center", padding: "0.5rem 0" }}>
          {resendMessage && (
            <AuthMessage
              tone={resendMessage.startsWith("验证邮件已重新发送") ? "success" : "error"}
              message={resendMessage}
            />
          )}
          <p style={{ marginBottom: "1rem", color: "var(--color-text-muted, #6b7280)", fontSize: "0.9rem" }}>
            没有收到邮件？
          </p>
          <button
            className="primary-btn auth-submit-btn"
            onClick={handleResend}
            disabled={resendLoading}
          >
            {resendLoading ? "发送中..." : "重新发送验证邮件"}
          </button>
          <div className="auth-footer-links" style={{ marginTop: "1rem" }}>
            <Link
              to={redirectPath ? `/login?redirect=${encodeURIComponent(redirectPath)}` : "/login"}
              className="text-link"
            >
              返回登录
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
