import "./App.css";
import { useEffect } from "react";
import { matchPath, useLocation } from "react-router-dom";
import AppRoutes from "./routes/route";

const DEFAULT_APP_TITLE = "Learning Hub";

function getPageTitle(pathname: string) {
  if (pathname === "/") {
    return `Home | ${DEFAULT_APP_TITLE}`;
  }

  if (pathname === "/login") {
    return `Login | ${DEFAULT_APP_TITLE}`;
  }

  if (pathname.startsWith("/register")) {
    return `Register | ${DEFAULT_APP_TITLE}`;
  }

  if (pathname === "/forgot-password") {
    return `Forgot Password | ${DEFAULT_APP_TITLE}`;
  }

  if (pathname === "/reset-password") {
    return `Reset Password | ${DEFAULT_APP_TITLE}`;
  }

  if (pathname === "/change-password") {
    return `Change Password | ${DEFAULT_APP_TITLE}`;
  }

  if (pathname === "/verify-email") {
    return `Verify Email | ${DEFAULT_APP_TITLE}`;
  }

  if (pathname === "/terms") {
    return `Terms | ${DEFAULT_APP_TITLE}`;
  }

  if (pathname === "/ai-demo" || pathname.startsWith("/ai-demo/")) {
    return `AI Demo | ${DEFAULT_APP_TITLE}`;
  }

  const homeTitles: Record<string, string> = {
    "/home": "Dashboard",
    "/home/course-center": "Course Center",
    "/home/my-courses": "My Courses",
    "/home/managed-courses": "Managed Courses",
    "/home/communication": "Notifications",
    "/home/progress": "Progress",
    "/home/ai": "AI Workspace",
    "/home/analytics": "Analytics",
    "/home/course-management": "Course Management",
    "/home/user-management": "User Management",
    "/home/educator-requests": "Educator Requests",
    "/home/communication-management": "Notification Management",
  };

  if (homeTitles[pathname]) {
    return `${homeTitles[pathname]} | ${DEFAULT_APP_TITLE}`;
  }

  if (pathname === "/courses/join") {
    return `Join Course | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid/forum/:postUuid", pathname) || matchPath("/course/:courseUuid/forum", pathname)) {
    return `Course Forum | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid/modules/:moduleUuid/materials/:materialUuid", pathname)) {
    return `Course Material | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid/modules/:moduleUuid/quiz", pathname)) {
    return `Course Quiz | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid/modules/:moduleUuid", pathname)) {
    return `Course Module | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid/management/modules/new", pathname)) {
    return `Create Module | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid/management/modules/:moduleUuid/quiz", pathname)) {
    return `Module Quiz Management | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid/management/modules/:moduleUuid", pathname)) {
    return `Module Management | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid/management/modules", pathname)) {
    return `Course Modules | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid/management/enrolments", pathname)) {
    return `Course Enrolments | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid/management/materials", pathname)) {
    return `Course Materials | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid/management/publishing", pathname)) {
    return `Course Publishing | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid/management", pathname)) {
    return `Course Management | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid", pathname)) {
    return `Course Overview | ${DEFAULT_APP_TITLE}`;
  }

  return DEFAULT_APP_TITLE;
}

function PageTitleManager() {
  const location = useLocation();

  useEffect(() => {
    document.title = getPageTitle(location.pathname);
  }, [location.pathname]);

  return null;
}

function App() {
  return (
    <>
      <PageTitleManager />
      <AppRoutes />
    </>
  );
}

export default App;
