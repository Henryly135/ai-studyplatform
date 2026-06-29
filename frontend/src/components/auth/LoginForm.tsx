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
          label="Email"
          type="email"
          name="email"
          placeholder="Enter your email"
          value={form.email}
          onChange={onChange}
        />

        <AuthField
          label="Password"
          type="password"
          name="password"
          placeholder="Enter your password"
          value={form.password}
          onChange={onChange}
        />

        {error && <AuthMessage tone="error" message={error} />}

        <button className="primary-btn auth-submit-btn" type="submit" disabled={loading}>
          {loading ? "Logging in..." : "Log in"}
        </button>
      </form>

      <div className="auth-footer-links">
        <Link to="/forgot-password" className="text-link">
          Forgot password?
        </Link>
      </div>

      <div className="auth-footer-links">
        Don&apos;t have an account? Sign up as a{" "}
        <Link to="/register/learner" className="text-link">
          Learner
        </Link>{" "}
        or{" "}
        <Link to="/register/educator" className="text-link">
          Educator
        </Link>
        .
      </div>
    </>
  );
}

export default LoginForm;
