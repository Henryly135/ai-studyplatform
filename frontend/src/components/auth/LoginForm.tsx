import { Link } from "react-router-dom";
import AuthField from "./AuthField";
import AuthMessage from "./AuthMessage";

interface LoginFormValues {
  email: string;
  password: string;
}

interface LoginFormProps {
  form: LoginFormValues;
  error: string;
  loading?: boolean;
  onChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
}

function LoginForm({ form, error, loading = false, onChange, onSubmit }: LoginFormProps) {
  return (
    <>
      <form className="auth-form" onSubmit={onSubmit}>
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
          placeholder="请输入密码"
          value={form.password}
          onChange={onChange}
        />

        {error && <AuthMessage tone="error" message={error} />}

        <button className="primary-btn auth-submit-btn" type="submit" disabled={loading}>
          {loading ? "登录中..." : "登录"}
        </button>
      </form>

      <div className="auth-footer-links">
        <Link to="/forgot-password" className="text-link">忘记密码？
        </Link>
      </div>

      <div className="auth-footer-links">
        还没有账号？注册为{" "}
        <Link to="/register/learner" className="text-link">学生
        </Link>{" "}
        或{" "}
        <Link to="/register/educator" className="text-link">教师
        </Link>
        。
      </div>
    </>
  );
}

export default LoginForm;
