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
      setTokenError("缺少邀请令牌，请使用邀请邮件中的链接。");
      return;
    }

    const validate = async () => {
      try {
        await validateEducatorInviteToken(inviteToken);
        setTokenValid(true);
      } catch (err) {
        setTokenValid(false);
        setTokenError(err instanceof Error ? err.message : "邀请链接无效或已过期。");
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

    if (!inviteToken) {
      setError("缺少邀请信息，请使用邀请邮件中的链接。");
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
      setError(err instanceof Error ? err.message : "注册失败。");
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

  if (tokenValid === null) {
    return (
      <AuthLayout>
        <AuthHeader title="正在验证邀请链接" description="请稍候..." badge="" />
      </AuthLayout>
    );
  }

  if (tokenValid === false) {
    return (
      <AuthLayout>
        <AuthHeader
          title="邀请链接无效"
          description="该邀请链接无效、已过期或已被使用。"
        />
        <div style={{ textAlign: "center", padding: "0.5rem 0" }}>
          <AuthMessage tone="error" message={tokenError || "请联系管理员获取新的邀请链接。"} />
          <div className="auth-footer-links" style={{ marginTop: "1rem" }}>
            <Link to="/login" className="text-link">返回登录</Link>
          </div>
        </div>
      </AuthLayout>
    );
  }

  if (registeredEmail) {
    return (
      <AuthLayout>
        <AuthHeader
          title="请检查邮箱"
          description={`我们已向 ${registeredEmail} 发送验证链接。请点击链接激活账号并使用教师功能。`}
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
            <Link to="/login" className="text-link">返回登录</Link>
          </div>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <AuthHeader
        badge="邀请注册"
        title="创建教师账号"
        description="你已受邀以教师身份加入。完成账号设置后即可开始使用，无需再次审批。"
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
