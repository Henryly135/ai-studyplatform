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
        <h1>学习工作区</h1>
        <p>在一个工作区中管理课程学习、角色权限和智能辅助学习。
        </p>
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
          <strong>账号待审批。</strong>你的教师账号正在等待管理员审核。审核通过前可以浏览平台，但不能创建或修改课程。
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
            <span>打开工作区</span>
          </Link>
        ))}
      </div>
    </section>
  );
}

export default HomeOverviewPage;
