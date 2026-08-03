import { describe, expect, it, vi } from "vitest";

import type { CourseRecord } from "../../types/course";
import {
  getLearnerAiModuleEntries,
  hydrateLearnerAiCourses,
} from "./learnerAiWorkspace";

const summary: CourseRecord = {
  courseUuid: "course-1",
  courseId: 1,
  educatorUuid: "educator-1",
  title: "Course one",
  subtitle: "",
  description: "",
  category: "",
  languageCode: "zh-CN",
  estimatedMinutes: 30,
  difficultyLevel: "beginner",
  isPublic: true,
  coverImageUrl: null,
  educatorName: "Educator",
  termLabel: "",
  courseCode: "",
  schoolName: "",
  modules: [],
};

const detail: CourseRecord = {
  ...summary,
  modules: [
    {
      moduleUuid: "module-1",
      title: "Published module",
      slug: "published-module",
      summary: "",
      durationLabel: "10 min",
      status: "available",
      isLocked: false,
      materials: [],
    },
    {
      moduleUuid: "module-2",
      title: "Locked module",
      slug: "locked-module",
      summary: "",
      durationLabel: "10 min",
      status: "locked",
      isLocked: true,
      materials: [],
    },
  ],
};

describe("learner AI workspace course context", () => {
  it("hydrates enrolled course summaries with module details", async () => {
    const loadCourse = vi.fn().mockResolvedValue(detail);

    await expect(hydrateLearnerAiCourses([summary], loadCourse)).resolves.toEqual([detail]);
    expect(loadCourse).toHaveBeenCalledWith("course-1");
  });

  it("offers every unlocked published module as an AI question scope", () => {
    expect(getLearnerAiModuleEntries([detail])).toEqual([
      { course: detail, module: detail.modules[0] },
    ]);
  });
});
