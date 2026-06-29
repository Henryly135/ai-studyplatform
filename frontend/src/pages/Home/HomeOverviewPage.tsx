import { Link, useOutletContext } from "react-router-dom";

import type { HomeOutletContext } from "./HomeSectionPage";

function HomeOverviewPage() {
  const { currentUser, allowedSections } = useOutletContext<HomeOutletContext>();
  const isPendingEducator =
    currentUser.identity === "Educator" && currentUser.accountStatus === "pending";

  return (
    <section className="home-overview">
      <div className="home-overview-hero">
        <span className="home-content-badge">{currentUser.identity}</span>
        <h1>Home</h1>
        <p>Choose a workspace area below.</p>
      </div>

      {isPendingEducator && (
        <div style={{
          background: "#fef9c3",
          border: "1px solid #fde047",
          borderRadius: "8px",
          padding: "0.75rem 1rem",
          marginBottom: "1.25rem",
          fontSize: "0.9rem",
          color: "#854d0e",
        }}>
          <strong>Account pending approval.</strong> Your educator account is awaiting admin review.
          You can browse the platform but cannot create or modify courses until approved.
        </div>
      )}

      <div className="home-overview-grid">
        {allowedSections.map((section) => (
          <Link
            key={section.id}
            to={`/home/${section.path}`}
            className="home-overview-card"
          >
            <strong>{section.title}</strong>
            <span>Open</span>
          </Link>
        ))}
      </div>
    </section>
  );
}

export default HomeOverviewPage;
