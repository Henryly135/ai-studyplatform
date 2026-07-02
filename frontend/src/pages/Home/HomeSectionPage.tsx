import { lazy, Suspense, useMemo } from "react";
import type { ReactNode } from "react";
import { Navigate, useOutletContext } from "react-router-dom";

import type { CurrentUserResponse } from "../../types/auth";
import type { HomeSection } from "./homeConfig";

const CourseCenterPage = lazy(() => import("../Course/CourseCenterPage"));
const ManagedCoursesPage = lazy(() => import("../Course/ManagedCoursesPage"));
const MyCoursesPage = lazy(() => import("../Course/MyCoursesPage"));
const AnalyticsPage = lazy(() => import("./AnalyticsPage"));
const HomeProgressPage = lazy(() => import("./HomeProgressPage"));
const NotificationsPage = lazy(() => import("./NotificationsPage"));
const UserManagementPage = lazy(() => import("./UserManagementPage"));

export type HomeOutletContext = {
  currentUser: CurrentUserResponse;
  allowedSections: HomeSection[];
};

type HomeSectionPageProps = {
  sectionId: string;
};

const SECTION_MESSAGE: Record<string, string> = {
  "course-center": "所有可用课程。",
  "my-courses": "你已加入的课程。",
  "managed-courses": "与你关联的课程。",
  communication: "课程相关通知。",
  progress: "你的课程进度。",
  analytics: "课程进度和分析。",
  "course-management": "管理全部课程信息。",
  "user-management": "用户角色和权限。",
};

function HomeSectionPage({ sectionId }: HomeSectionPageProps) {
  const { currentUser, allowedSections } = useOutletContext<HomeOutletContext>();

  const section = useMemo(() => {
    if (
      sectionId === "communication" &&
      (currentUser.identity === "Learner" || currentUser.identity === "Educator")
    ) {
      return {
        id: "communication",
        title: "通知",
        path: "communication",
      };
    }

    return allowedSections.find((item) => item.id === sectionId);
  }, [allowedSections, currentUser.identity, sectionId]);

  if (!section) {
    return <Navigate to="/home" replace />;
  }

  let content: ReactNode;

  if (section.id === "managed-courses") {
    content = <ManagedCoursesPage />;
  } else if (section.id === "course-management") {
    content = <ManagedCoursesPage variant="admin" />;
  } else if (section.id === "my-courses") {
    content = <MyCoursesPage />;
  } else if (section.id === "progress") {
    content = <HomeProgressPage />;
  } else if (section.id === "user-management") {
    content = <UserManagementPage />;
  } else if (section.id === "communication") {
    content = <NotificationsPage mode="recipient" currentUser={currentUser} />;
  } else if (section.id === "analytics") {
    content = <AnalyticsPage />;
  } else if (section.id === "course-center") {
    content = <CourseCenterPage currentUser={currentUser} />;
  } else {
    content = (
      <section className="home-content-card">
        <span className="home-content-badge">{currentUser.identity}</span>
        <h1>{section.title}</h1>
        <p>{SECTION_MESSAGE[section.id] ?? currentUser.userName}</p>
      </section>
    );
  }

  return (
    <Suspense fallback={<section className="home-content-card">加载中...</section>}>
      {content}
    </Suspense>
  );
}

export default HomeSectionPage;
