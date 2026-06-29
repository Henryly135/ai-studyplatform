import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import AuthHeader from "../../components/auth/AuthHeader";
import AuthLayout from "../../components/auth/AuthLayout";
import LoginForm from "../../components/auth/LoginForm";
import { loginUser } from "../../services/auth";

const POST_AUTH_REDIRECT_STORAGE_KEY = "postAuthRedirect";
const PENDING_COURSE_INVITE_TOKEN_KEY = "pendingCourseInviteToken";
const POST_PROFILE_INIT_REDIRECT_STORAGE_KEY = "postProfileInitRedirect";

function getLoginErrorMessage(error: unknown): string {
  if (!(error instanceof Error)) {
    return "An unknown error occurred.";
  }

  switch (error.message) {
    case "Invalid credentials":
      return "Incorrect email or password.";
    case "Email not verified":
      return "Your email has not been verified yet. Please verify your email before signing in.";
    case "Account pending approval":
      return "Your account is awaiting admin approval.";
    case "Account rejected":
      return "Your account application was rejected. Please contact an administrator.";
    case "Account deactivated":
      return "Your account has been deactivated. Please contact an administrator.";
    default:
      return error.message;
  }
}

function Login() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const redirectPath = searchParams.get("redirect");
  const storedRedirectPath = localStorage.getItem(POST_AUTH_REDIRECT_STORAGE_KEY);

  const [form, setForm] = useState({
    email: "",
    password: "",
  });

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setForm({
      ...form,
      [event.target.name]: event.target.value,
    });
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");

    console.log("[login] submit", {
      email: form.email,
    });

    if (!form.email || !form.password) {
      setError("Please enter email and password.");
      return;
    }

    try {
      setLoading(true);

      const response = await loginUser({
        email: form.email,
        password: form.password,
      });

      console.log("[login] success", response);

      localStorage.setItem("accessToken", response.accessToken);
      localStorage.setItem("tokenType", response.tokenType);
      localStorage.setItem("currentUser", JSON.stringify(response.user));
      localStorage.removeItem(POST_AUTH_REDIRECT_STORAGE_KEY);
      localStorage.removeItem(PENDING_COURSE_INVITE_TOKEN_KEY);

      const postLoginTarget = redirectPath || storedRedirectPath || "/home";
      const shouldShowProfileInit =
        response.user.identity === "Learner" &&
        response.shouldShowGlobalProfileInitPrompt === true;

      if (shouldShowProfileInit) {
        localStorage.setItem(POST_PROFILE_INIT_REDIRECT_STORAGE_KEY, postLoginTarget);
        navigate("/home/ai/profile-init", { replace: true });
        return;
      }

      localStorage.removeItem(POST_PROFILE_INIT_REDIRECT_STORAGE_KEY);
      navigate(postLoginTarget, { replace: true });
    } catch (err) {
      console.error("[login] failed", err);
      setError(getLoginErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <AuthHeader
        title="Welcome back"
        description="Sign in to continue your learning journey." badge={""}      />
      <LoginForm
        form={form}
        error={error}
        loading={loading}
        onChange={handleChange}
        onSubmit={handleSubmit}
      />
    </AuthLayout>
  );
}

export default Login;
