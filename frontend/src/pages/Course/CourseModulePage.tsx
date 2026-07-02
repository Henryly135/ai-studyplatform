import { Link, Navigate, useLocation, useOutletContext, useParams } from "react-router-dom";
import { LuLock } from "react-icons/lu";

import type { CourseOutletContext } from "./CourseLayout";

function CourseModulePage() {
  const { moduleUuid } = useParams();
  const location = useLocation();
  const { course } = useOutletContext<CourseOutletContext>();

  const module = course.modules.find((item) => item.moduleUuid === moduleUuid);

  if (!module) {
    return <Navigate to={`/course/${course.courseUuid}`} replace />;
  }

  const isLocked = module.isLocked;
  const source = new URLSearchParams(location.search).get("from");
  const shouldShowQuizLink = source !== "course-center";

  return (
    <section className="course-detail-page">
      <div className="course-module-hero">
        <span className="course-surface-badge">{module.status}</span>
        <h1>{module.title}</h1>
        <p>{module.summary}</p>
      </div>

      {isLocked ? (
        <div className="course-module-locked-banner">
          <LuLock size={20} aria-hidden="true" />
          <div>
            <strong>模块已锁定</strong>
            <p>{module.lockMessage ?? `Complete "${module.prerequisiteModuleTitle}" to unlock this module.`}</p>
          </div>
        </div>
      ) : null}

      <div className="course-detail-grid">
        <article className="course-panel">
          <div className="course-panel-heading">
            <h3>模块概览</h3>
          </div>
          {module.durationLabel ? <p>预计时间： {module.durationLabel}</p> : null}
          <p>状态： {module.status}</p>
          {module.classId ? <p>班级： {module.classId}</p> : null}
          {module.prerequisiteModuleTitle ? (
            <p>前置条件： {module.prerequisiteModuleTitle}</p>
          ) : null}
        </article>

        {!isLocked ? (
          <article className="course-panel">
            <div className="course-panel-heading">
              <h3>学习重点</h3>
            </div>
            <p>{module.content || module.summary}</p>
            <div className="course-material-list">
              {module.materials.map((material) => (
                <article key={material.materialUuid} className="course-material-card">
                  <strong>{material.title}</strong>
                  {material.materialType ? <span>{material.materialType}</span> : null}
                </article>
              ))}
              {module.hasPublishedQuiz && shouldShowQuizLink && (
                <Link
                  to={`/course/${course.courseUuid}/modules/${module.moduleUuid}/quiz`}
                  className="course-material-card course-material-card-link course-material-card-quiz"
                >
                  <strong>{module.quizTitle ?? "测验"}</strong>
                  <span>测验</span>
                </Link>
              )}
            </div>
          </article>
        ) : null}
      </div>
    </section>
  );
}

export default CourseModulePage;
