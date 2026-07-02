import "./App.css";
import { useEffect } from "react";
import { matchPath, useLocation } from "react-router-dom";
import AppRoutes from "./routes/route";

const DEFAULT_APP_TITLE = "学习平台";

function getPageTitle(pathname: string) {
  if (pathname === "/") {
    return `首页 | ${DEFAULT_APP_TITLE}`;
  }

  if (pathname === "/login") {
    return `登录 | ${DEFAULT_APP_TITLE}`;
  }

  if (pathname.startsWith("/register")) {
    return `注册 | ${DEFAULT_APP_TITLE}`;
  }

  if (pathname === "/forgot-password") {
    return `忘记密码 | ${DEFAULT_APP_TITLE}`;
  }

  if (pathname === "/reset-password") {
    return `重置密码 | ${DEFAULT_APP_TITLE}`;
  }

  if (pathname === "/change-password") {
    return `修改密码 | ${DEFAULT_APP_TITLE}`;
  }

  if (pathname === "/verify-email") {
    return `邮箱验证 | ${DEFAULT_APP_TITLE}`;
  }

  if (pathname === "/terms") {
    return `服务条款 | ${DEFAULT_APP_TITLE}`;
  }

  const homeTitles: Record<string, string> = {
    "/home": "工作台",
    "/home/course-center": "课程大厅",
    "/home/my-courses": "我的课程",
    "/home/managed-courses": "管理课程",
    "/home/communication": "通知",
    "/home/progress": "学习进度",
    "/home/ai": "智能工作区",
    "/home/analytics": "教学分析",
    "/home/course-management": "课程管理",
    "/home/user-management": "用户管理",
  };

  if (homeTitles[pathname]) {
    return `${homeTitles[pathname]} | ${DEFAULT_APP_TITLE}`;
  }

  if (pathname === "/courses/join") {
    return `加入课程 | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid/forum/:postUuid", pathname) || matchPath("/course/:courseUuid/forum", pathname)) {
    return `课程论坛 | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid/modules/:moduleUuid/materials/:materialUuid", pathname)) {
    return `课程资料 | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid/modules/:moduleUuid/quiz", pathname)) {
    return `课程测验 | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid/modules/:moduleUuid", pathname)) {
    return `课程模块 | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid/management/modules/new", pathname)) {
    return `创建模块 | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid/management/modules/:moduleUuid/quiz", pathname)) {
    return `模块测验管理 | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid/management/modules/:moduleUuid", pathname)) {
    return `模块管理 | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid/management/modules", pathname)) {
    return `课程模块 | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid/management/enrolments", pathname)) {
    return `课程报名 | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid/management/materials", pathname)) {
    return `课程资料 | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid/management/publishing", pathname)) {
    return `课程发布 | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid/management", pathname)) {
    return `课程管理 | ${DEFAULT_APP_TITLE}`;
  }

  if (matchPath("/course/:courseUuid", pathname)) {
    return `课程概览 | ${DEFAULT_APP_TITLE}`;
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
