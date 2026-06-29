import { useMemo } from "react";
import { Navigate, useOutletContext } from "react-router-dom";

import CourseCenterPage from "../Course/CourseCenterPage";
import ManagedCoursesPage from "../Course/ManagedCoursesPage";
import MyCoursesPage from "../Course/MyCoursesPage";
import AnalyticsPage from "./AnalyticsPage";
import EducatorRequestsPage from "./EducatorRequestsPage";
import NotificationsPage from "./NotificationsPage";
import UserManagementPage from "./UserManagementPage";
import type { CurrentUserResponse } from "../../types/auth";
import type { HomeSection } from "./homeConfig";

export type HomeOutletContext = {
  currentUser: CurrentUserResponse;
  allowedSections: HomeSection[];
};

type HomeSectionPageProps = {
  sectionId: string;
};

const SECTION_MESSAGE: Record<string, string> = {
  "course-center": "All available courses.",
  "my-courses": "Courses you enrolled in.",
  "managed-courses": "Courses linked to you.",
  communication: "Course-related notifications.",
  progress: "Your course progress.",
  analytics: "Course progress and analysis.",
  "course-management": "Manage all course information.",
  "user-management": "User roles and permissions.",
  "educator-requests": "Educator registration requests.",
  "communication-management": "Manage all notification content.",
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
        title: "Notifications",
        path: "communication",
      };
    }

    return allowedSections.find((item) => item.id === sectionId);
  }, [allowedSections, currentUser.identity, sectionId]);

  if (!section) {
    return <Navigate to="/home" replace />;
  }

  if (section.id === "course-center") {
    return <CourseCenterPage currentUser={currentUser} />;
  }

  if (section.id === "managed-courses") {
    return <ManagedCoursesPage />;
  }

  if (section.id === "course-management") {
    return <ManagedCoursesPage variant="admin" />;
  }

  if (section.id === "my-courses") {
    return <MyCoursesPage />;
  }

  if (section.id === "user-management") {
    return <UserManagementPage />;
  }

  if (section.id === "communication") {
    return <NotificationsPage mode="recipient" currentUser={currentUser} />;
  }

  if (section.id === "communication-management") {
    return <NotificationsPage mode="admin" currentUser={currentUser} />;
  }

  if (section.id === "educator-requests") {
    return <EducatorRequestsPage />;
  }

  if (section.id === "analytics") {
    return <AnalyticsPage />;
  }

  return (
    <section className="home-content-card">
      <span className="home-content-badge">{currentUser.identity}</span>
      <h1>{section.title}</h1>
      <p>{SECTION_MESSAGE[section.id] ?? currentUser.userName}</p>
    </section>
  );
}

export default HomeSectionPage;
