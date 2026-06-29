interface AuthMessageProps {
  tone: "error" | "success";
  message: string;
}

function AuthMessage({ tone, message }: AuthMessageProps) {
  return (
    <div
      className={`form-message ${
        tone === "error" ? "error-message" : "success-message"
      }`}
    >
      {message}
    </div>
  );
}

export default AuthMessage;
