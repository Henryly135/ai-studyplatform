import type { CourseRecord } from "../../types/course";

type CourseDetailLoader = (courseUuid: string) => Promise<CourseRecord | null>;

export async function hydrateLearnerAiCourses(
  courses: CourseRecord[],
  loadCourse: CourseDetailLoader
) {
  return Promise.all(
    courses.map(async (course) => {
      try {
        return (await loadCourse(course.courseUuid)) ?? course;
      } catch {
        return course;
      }
    })
  );
}

export function getLearnerAiModuleEntries(courses: CourseRecord[]) {
  return courses.flatMap((course) =>
    course.modules
      .filter((module) => !module.isLocked)
      .map((module) => ({ course, module }))
  );
}
