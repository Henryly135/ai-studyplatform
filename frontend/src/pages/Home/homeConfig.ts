import type { Identity } from "../../types/auth";

export type HomeSection = {
  id: string;
  title: string;
  path: string;
};

export const COURSE_CENTER_SECTION: HomeSection = {
  id: "course-center",
  title: "Course Center",
  path: "course-center",
};

export const MY_COURSES_SECTION: HomeSection = {
  id: "my-courses",
  title: "My Courses",
  path: "my-courses",
};

export const MANAGED_COURSES_SECTION: HomeSection = {
  id: "managed-courses",
  title: "Managed Courses",
  path: "managed-courses",
};

export const COMMUNICATION_SECTION: HomeSection = {
  id: "communication",
  title: "Notifications",
  path: "communication",
};

export const PROGRESS_SECTION: HomeSection = {
  id: "progress",
  title: "Progress",
  path: "progress",
};

export const STUDY_PLANNER_SECTION: HomeSection = {
  id: "study-planner",
  title: "Study Planner",
  path: "study-planner",
};

export const AI_SECTION: HomeSection = {
  id: "ai",
  title: "AI",
  path: "ai",
};

export const ANALYTICS_SECTION: HomeSection = {
  id: "analytics",
  title: "Analytics",
  path: "analytics",
};

export const COURSE_MANAGEMENT_SECTION: HomeSection = {
  id: "course-management",
  title: "Course Management",
  path: "course-management",
};

export const USER_MANAGEMENT_SECTION: HomeSection = {
  id: "user-management",
  title: "User Management",
  path: "user-management",
};

export const EDUCATOR_REQUESTS_SECTION: HomeSection = {
  id: "educator-requests",
  title: "Educator Requests",
  path: "educator-requests",
};

export const COMMUNICATION_MANAGEMENT_SECTION: HomeSection = {
  id: "communication-management",
  title: "Notification Management",
  path: "communication-management",
};

const HOME_SECTIONS_BY_IDENTITY: Record<Identity, HomeSection[]> = {
  Learner: [
    COURSE_CENTER_SECTION,
    MY_COURSES_SECTION,
    STUDY_PLANNER_SECTION,
    COMMUNICATION_SECTION,
    AI_SECTION,
  ],
  Educator: [
    COURSE_CENTER_SECTION,
    MANAGED_COURSES_SECTION,
    ANALYTICS_SECTION,
    COMMUNICATION_SECTION,
  ],
  Admin: [
    COURSE_CENTER_SECTION,
    COURSE_MANAGEMENT_SECTION,
    USER_MANAGEMENT_SECTION,
    EDUCATOR_REQUESTS_SECTION,
    COMMUNICATION_SECTION,
    COMMUNICATION_MANAGEMENT_SECTION,
  ],
};

export function getAllowedHomeSections(identity: Identity): HomeSection[] {
  return HOME_SECTIONS_BY_IDENTITY[identity];
}
