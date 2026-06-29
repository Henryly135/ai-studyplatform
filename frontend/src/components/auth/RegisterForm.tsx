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
          label="Username"
          type="text"
          name="usrName"
          placeholder="Enter your username"
          value={form.usrName}
          onChange={onChange}
        />

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
          placeholder={PASSWORD_HINT}
          value={form.password}
          onChange={onChange}
        />

        <AuthField
          label="Confirm Password"
          type="password"
          name="confirmPassword"
          placeholder="Re-enter your password"
          value={form.confirmPassword}
          onChange={onChange}
        />

        <label className="terms-checkbox">
          <input
            type="checkbox"
            checked={agreedToTerms}
            onChange={(e) => onAgreeChange(e.target.checked)}
          />
          <span>
            I agree to the{" "}
            <Link to="/terms" target="_blank" className="text-link">
              Terms of Service
            </Link>
          </span>
        </label>

        {error && <AuthMessage tone="error" message={error} />}
        {success && <AuthMessage tone="success" message={success} />}

        <button className="primary-btn auth-submit-btn" type="submit" disabled={loading}>
          {loading ? "Creating account..." : "Create account"}
        </button>
      </form>

      <div className="auth-footer-links">
        Already have an account?{" "}
        <Link to="/login" className="text-link">
          Log in
        </Link>
      </div>
    </>
  );
}

export default RegisterForm;
