interface AuthHeaderProps {
  badge?: string;
  title: string;
  description: string;
}

function AuthHeader({ badge, title, description }: AuthHeaderProps) {
  return (
    <div className="auth-header">
      {badge ? <span className="auth-badge">{badge}</span> : null}
      <h1>{title}</h1>
      <p>{description}</p>
    </div>
  );
}

export default AuthHeader;
