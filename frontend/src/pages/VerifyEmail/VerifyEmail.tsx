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
    () => (token ? "" : "验证令牌无效或缺失。")
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
        setMessage(err instanceof Error ? err.message : "邮箱验证失败。");
        setStatus("error");
      });
  }, [token]);

  return (
    <AuthLayout>
      <AuthHeader
        
        title="邮箱验证"
        description="正在验证你的邮箱地址。"
      />

      <div>
        {status === "loading" && <p>验证中...</p>}
        {status === "success" && (
          <>
            <AuthMessage tone="success" message="邮箱验证成功，现在可以登录了。" />
            <div className="auth-footer-links">
              <Link to={loginLink} className="text-link">
                前往登录
              </Link>
            </div>
          </>
        )}
        {status === "error" && (
          <>
            <AuthMessage tone="error" message={message} />
            <div className="auth-footer-links">
              <Link to="/login" className="text-link">返回登录</Link>
            </div>
          </>
        )}
      </div>
    </AuthLayout>
  );
}

export default VerifyEmail;
