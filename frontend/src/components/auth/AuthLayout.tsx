import type { ReactNode } from "react";
import { Link } from "react-router-dom";

interface AuthLayoutProps {
  children: ReactNode;
}

function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="auth-page">
      <div className="auth-card">
        <Link to="/" className="auth-back-link">返回首页
        </Link>
        {children}
      </div>
    </div>
  );
}

export default AuthLayout;
