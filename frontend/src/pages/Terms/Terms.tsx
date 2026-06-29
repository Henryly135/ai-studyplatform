import { Link } from "react-router-dom";
import "./Terms.css";

function Terms() {
  return (
    <div className="terms-page">
      <div className="terms-container">
        <div className="terms-header">
          <h1>Terms of Service</h1>
          <p className="terms-effective">Effective date: March 2026</p>
        </div>

        <section>
          <h2>1. About EduLearning</h2>
          <p>
            EduLearning is a school-facing online learning platform that connects Learners,
            Educators, and Administrators. By registering for an account, you agree to these
            Terms of Service. If you do not agree, please do not use the platform.
          </p>
        </section>

        <section>
          <h2>2. User Accounts</h2>
          <ul>
            <li>You must provide a valid email address and verify it before accessing the platform.</li>
            <li>You are responsible for keeping your account credentials secure.</li>
            <li>You must not share your account with others or use another person's account.</li>
            <li>
              There are three account types: <strong>Learner</strong>, <strong>Educator</strong>,
              and <strong>Admin</strong>. Each has different permissions managed by the platform.
            </li>
          </ul>
        </section>

        <section>
          <h2>3. User Conduct</h2>
          <p>All users agree not to:</p>
          <ul>
            <li>Upload or share content that is illegal, harmful, abusive, or discriminatory.</li>
            <li>Infringe on the intellectual property rights of others.</li>
            <li>Use the platform for any purpose other than educational activities.</li>
            <li>Attempt to disrupt, hack, or gain unauthorised access to the platform or other users' accounts.</li>
            <li>Impersonate any person or organisation.</li>
          </ul>
        </section>

        <section>
          <h2>4. Content</h2>
          <ul>
            <li>
              Educators may upload course materials including videos, documents, and text.
              You retain ownership of content you upload, but grant EduLearning a licence
              to host and display it to enrolled users.
            </li>
            <li>
              You are solely responsible for the content you upload. EduLearning does not
              review all content in advance but reserves the right to remove content that
              violates these Terms.
            </li>
            <li>
              Learners may only access content within courses they are enrolled in.
              Redistribution of course materials outside the platform is not permitted.
            </li>
          </ul>
        </section>

        <section>
          <h2>5. Privacy & Data</h2>
          <ul>
            <li>We collect your name, email address, and account activity to operate the platform.</li>
            <li>Your data is not sold to third parties.</li>
            <li>
              We use your email address to send account verification, password reset, and
              platform-related notifications only.
            </li>
            <li>You may request deletion of your account and associated data by contacting an Administrator.</li>
          </ul>
        </section>

        <section>
          <h2>6. Account Termination</h2>
          <p>
            EduLearning reserves the right to suspend or terminate accounts that violate these Terms,
            engage in misconduct, or are inactive for an extended period. Administrators may manage
            user accounts within their institution.
          </p>
        </section>

        <section>
          <h2>7. Disclaimer</h2>
          <p>
            EduLearning is provided as-is for educational purposes. We do not guarantee
            uninterrupted availability and are not liable for any loss of data or access.
            The platform is currently provided free of charge with no payment obligations.
          </p>
        </section>

        <section>
          <h2>8. Changes to Terms</h2>
          <p>
            We may update these Terms from time to time. Continued use of the platform after
            changes are posted constitutes acceptance of the updated Terms.
          </p>
        </section>

        <section>
          <h2>9. Contact</h2>
          <p>
            If you have questions about these Terms, please contact your institution's Administrator.
          </p>
        </section>

        <div className="terms-back">
          <Link to="/register" className="text-link">← Back to Register</Link>
        </div>
      </div>
    </div>
  );
}

export default Terms;
