import type { Identity } from "../../types/auth";

export type HomeSection = {
  id: string;
  title: string;
  path: string;
};

export const COURSE_CENTER_SECTION: HomeSection = {
  id: "course-center",
  title: "课程大厅",
  path: "course-center",
};

export const MY_COURSES_SECTION: HomeSection = {
  id: "my-courses",
  title: "我的课程",
  path: "my-courses",
};

export const MANAGED_COURSES_SECTION: HomeSection = {
  id: "managed-courses",
  title: "管理课程",
  path: "managed-courses",
};

export const COMMUNICATION_SECTION: HomeSection = {
  id: "communication",
  title: "通知",
  path: "communication",
};

export const PROGRESS_SECTION: HomeSection = {
  id: "progress",
  title: "学习进度",
  path: "progress",
};

export const AI_SECTION: HomeSection = {
  id: "ai",
  title: "智能工作区",
  path: "ai",
};

export const ANALYTICS_SECTION: HomeSection = {
  id: "analytics",
  title: "教学分析",
  path: "analytics",
};

export const COURSE_MANAGEMENT_SECTION: HomeSection = {
  id: "course-management",
  title: "课程管理",
  path: "course-management",
};

export const USER_MANAGEMENT_SECTION: HomeSection = {
  id: "user-management",
  title: "用户管理",
  path: "user-management",
};

const HOME_SECTIONS_BY_IDENTITY: Record<Identity, HomeSection[]> = {
  Learner: [
    COURSE_CENTER_SECTION,
    MY_COURSES_SECTION,
    PROGRESS_SECTION,
    COMMUNICATION_SECTION,
    AI_SECTION,
  ],
  Educator: [
    COURSE_CENTER_SECTION,
    MANAGED_COURSES_SECTION,
    ANALYTICS_SECTION,
    AI_SECTION,
    COMMUNICATION_SECTION,
  ],
  Admin: [
    COURSE_CENTER_SECTION,
    COURSE_MANAGEMENT_SECTION,
    USER_MANAGEMENT_SECTION,
    AI_SECTION,
  ],
};

export function getAllowedHomeSections(identity: Identity): HomeSection[] {
  return HOME_SECTIONS_BY_IDENTITY[identity];
}
