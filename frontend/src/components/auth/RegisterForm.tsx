import { Link } from "react-router-dom";
import AuthField from "./AuthField";
import AuthMessage from "./AuthMessage";
import { PASSWORD_HINT } from "../../utils/password";

interface RegisterFormValues {
  usrName: string;
  email: string;
  password: string;
  confirmPassword: string;
}

interface RegisterFormProps {
  form: RegisterFormValues;
  error: string;
  success: string;
  loading?: boolean;
  agreedToTerms: boolean;
  onAgreeChange: (checked: boolean) => void;
  onChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
}

function RegisterForm({
  form,
  error,
  success,
  loading,
  agreedToTerms,
  onAgreeChange,
  onChange,
  onSubmit,
}: RegisterFormProps) {
  return (
    <>
      <form className="auth-form" onSubmit={onSubmit}>
        <AuthField
          label="用户名"
          type="text"
          name="usrName"
          placeholder="请输入用户名"
          value={form.usrName}
          onChange={onChange}
        />

        <AuthField
          label="邮箱"
          type="email"
          name="email"
          placeholder="请输入邮箱"
          value={form.email}
          onChange={onChange}
        />

        <AuthField
          label="密码"
          type="password"
          name="password"
          placeholder={PASSWORD_HINT}
          value={form.password}
          onChange={onChange}
        />

        <AuthField
          label="确认密码"
          type="password"
          name="confirmPassword"
          placeholder="请再次输入密码"
          value={form.confirmPassword}
          onChange={onChange}
        />

        <label className="terms-checkbox">
          <input
            type="checkbox"
            checked={agreedToTerms}
            onChange={(e) => onAgreeChange(e.target.checked)}
          />
          <span>我同意{" "}
            <Link to="/terms" target="_blank" className="text-link">服务条款
            </Link>
          </span>
        </label>

        {error && <AuthMessage tone="error" message={error} />}
        {success && <AuthMessage tone="success" message={success} />}

        <button className="primary-btn auth-submit-btn" type="submit" disabled={loading}>
          {loading ? "正在创建账号..." : "创建账号"}
        </button>
      </form>

      <div className="auth-footer-links">已有账号？{" "}
        <Link to="/login" className="text-link">登录
        </Link>
      </div>
    </>
  );
}

export default RegisterForm;
