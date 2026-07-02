import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  deactivateCourseInviteLink,
  enrolViaCourseInvite,
  generateCourseInviteLink,
  getCourses,
  getEducatorAnalytics,
  getEducatorMaterialBriefs,
  getEducatorQuizAnalytics,
  getEducatorTeachingInsights,
  getMultipartManagedModuleMaterialPartUploadUrl,
  getQuizAttemptHistory,
  submitQuizAttempt,
  getActiveQuizSession,
  getQuizAttemptDetail,
  initMultipartManagedModuleMaterialUpload,
  getMyProgressOverview,
  listCourseInviteLinks,
  listQuizAuthoringQuestions,
  validateCourseInviteToken,
} from "./course";

const NOW_MS = 1_800_000_000_000;

function base64UrlEncode(value: unknown) {
  return btoa(JSON.stringify(value)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/u, "");
}

function makeToken(exp: number) {
  return `${base64UrlEncode({ alg: "HS256", typ: "JWT" })}.${base64UrlEncode({ exp })}.signature`;
}

function createMemoryStorage(): Storage {
  const values = new Map<string, string>();

  return {
    get length() {
      return values.size;
    },
    clear() {
      values.clear();
    },
    getItem(key: string) {
      return values.get(key) ?? null;
    },
    key(index: number) {
      return Array.from(values.keys())[index] ?? null;
    },
    removeItem(key: string) {
      values.delete(key);
    },
    setItem(key: string, value: string) {
      values.set(key, String(value));
    },
  };
}

function mockJsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("course pagination service normalization", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(NOW_MS));
    vi.stubGlobal("localStorage", createMemoryStorage());
    vi.stubGlobal("window", {
      location: {
        pathname: "/course-center",
        assign: vi.fn(),
      },
    });
    localStorage.setItem("accessToken", makeToken(NOW_MS / 1000 + 60));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("normalizes malformed course list pagination metadata", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockJsonResponse({
          items: [
            {
              courseId: 42,
              courseUuid: "course_1",
              title: "Biology",
            },
          ],
          page: "bad-page",
          pageSize: "0",
          total: "not-total",
          totalPages: -4,
        })
      )
    );

    const result = await getCourses();

    expect(result.page).toBe(1);
    expect(result.pageSize).toBe(1);
    expect(result.total).toBe(1);
    expect(result.totalPages).toBe(1);
    expect(result.items[0].courseUuid).toBe("course_1");
  });

  it("normalizes malformed quiz question pagination metadata", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockJsonResponse({
          items: [
            {
              questionUuid: "question_1",
              questionText: "Question?",
              sortOrder: "bad-order",
              options: [
                {
                  optionUuid: "option_1",
                  optionLabel: "A",
                  optionText: "Answer",
                  sortOrder: "bad-option-order",
                },
              ],
            },
          ],
          page: "2",
          page_size: "0",
          total: -8,
          total_pages: "bad-pages",
        })
      )
    );

    const result = await listQuizAuthoringQuestions("course_1", "module_1");

    expect(result.page).toBe(2);
    expect(result.pageSize).toBe(1);
    expect(result.total).toBe(0);
    expect(result.totalPages).toBe(1);
    expect(result.items[0].sortOrder).toBe(1);
    expect(result.items[0].options[0].sortOrder).toBe(1);
  });
});

describe("course progress service normalization", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(NOW_MS));
    vi.stubGlobal("localStorage", createMemoryStorage());
    vi.stubGlobal("window", {
      location: {
        pathname: "/home/progress",
        assign: vi.fn(),
      },
    });
    localStorage.setItem("accessToken", makeToken(NOW_MS / 1000 + 60));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("normalizes malformed learner progress metrics to finite display-safe values", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockJsonResponse({
          totalCourses: "not-a-count",
          totalModules: -4,
          completedModules: "3",
          averageProgressPercent: 140,
          quiz: {
            totalQuizzes: "bad-total",
            attemptedQuizzes: -2,
            passedQuizzes: "2",
            totalAttempts: "4",
            averageBestScorePercent: "not-a-score",
            latestScorePercent: 125,
          },
          courses: [
            {
              courseId: "bad-course",
              courseUuid: "course_1",
              title: "Biology",
              progressPercent: "110",
              completedModuleCount: "bad-completed",
              totalModuleCount: -6,
              nextModule: {
                moduleId: "bad-module",
                moduleUuid: "module_1",
                title: "Cells",
              },
              quiz: {
                totalQuizzes: "3",
                attemptedQuizzes: "not-attempted",
                passedQuizzes: -1,
                totalAttempts: "2",
                averageBestScorePercent: -15,
                latestScorePercent: "95",
              },
            },
          ],
          recentActivity: [
            {
              activityType: "quiz",
              occurredAt: "2026-07-02T00:00:00Z",
              courseId: "7",
              courseUuid: "course_1",
              courseTitle: "Biology",
              moduleId: "bad-module",
              scorePercent: "not-a-score",
              isPassed: "yes",
            },
          ],
        })
      )
    );

    const result = await getMyProgressOverview();

    expect(result.totalCourses).toBe(0);
    expect(result.totalModules).toBe(0);
    expect(result.completedModules).toBe(3);
    expect(result.averageProgressPercent).toBe(100);
    expect(result.quiz.totalQuizzes).toBe(0);
    expect(result.quiz.attemptedQuizzes).toBe(0);
    expect(result.quiz.passedQuizzes).toBe(2);
    expect(result.quiz.totalAttempts).toBe(4);
    expect(result.quiz.averageBestScorePercent).toBeNull();
    expect(result.quiz.latestScorePercent).toBe(100);
    expect(result.courses[0].courseId).toBe(0);
    expect(result.courses[0].progressPercent).toBe(100);
    expect(result.courses[0].completedModuleCount).toBe(0);
    expect(result.courses[0].totalModuleCount).toBe(0);
    expect(result.courses[0].nextModule?.moduleId).toBe(0);
    expect(result.courses[0].quiz.totalQuizzes).toBe(3);
    expect(result.courses[0].quiz.attemptedQuizzes).toBe(0);
    expect(result.courses[0].quiz.passedQuizzes).toBe(0);
    expect(result.courses[0].quiz.averageBestScorePercent).toBe(0);
    expect(result.courses[0].quiz.latestScorePercent).toBe(95);
    expect(result.recentActivity[0].courseId).toBe(7);
    expect(result.recentActivity[0].moduleId).toBe(0);
    expect(result.recentActivity[0].scorePercent).toBeNull();
    expect(result.recentActivity[0].isPassed).toBeNull();
  });
});

describe("course quiz service normalization", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(NOW_MS));
    vi.stubGlobal("localStorage", createMemoryStorage());
    vi.stubGlobal("window", {
      location: {
        pathname: "/course/course_1/modules/module_1/quiz",
        assign: vi.fn(),
      },
    });
    localStorage.setItem("accessToken", makeToken(NOW_MS / 1000 + 60));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("normalizes malformed active quiz session metrics", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockJsonResponse({
          quizUuid: "quiz_1",
          moduleUuid: "module_1",
          attemptSessionToken: "attempt_token",
          attemptNumber: "bad-attempt",
          questionCount: "bad-count",
          timeLimitSeconds: -60,
          questions: [
            {
              questionId: "bad-question",
              questionUuid: "question_1",
              questionText: "Question?",
              questionOrder: -2,
              options: [
                {
                  optionId: "bad-option",
                  optionUuid: "option_1",
                  optionText: "Answer",
                  sortOrder: -4,
                },
              ],
            },
          ],
        })
      )
    );

    const result = await getActiveQuizSession("course_1", "module_1");

    expect(result?.attemptNumber).toBe(1);
    expect(result?.questionCount).toBe(1);
    expect(result?.timeLimitSeconds).toBeNull();
    expect(result?.questions[0].questionId).toBe(0);
    expect(result?.questions[0].questionOrder).toBe(1);
    expect(result?.questions[0].options[0].optionId).toBe(0);
    expect(result?.questions[0].options[0].sortOrder).toBe(0);
  });

  it("normalizes malformed quiz attempt result scores and boolean states", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockJsonResponse({
          quizAttemptUuid: "attempt_1",
          quizUuid: "quiz_1",
          moduleUuid: "module_1",
          attemptNumber: "bad-attempt",
          questionCount: "bad-question-count",
          correctCount: -2,
          scorePercent: 150,
          isPassed: "false",
          isTimedOut: "true",
          moduleCompleted: "false",
          timeLimitSeconds: "not-a-limit",
          durationSeconds: -12,
          answers: [
            {
              questionUuid: "question_1",
              questionOrder: "bad-order",
              questionText: "Question?",
              correctOptionUuid: "option_1",
              correctOptionText: "Answer",
              isCorrect: "false",
            },
          ],
        })
      )
    );

    const result = await submitQuizAttempt("course_1", "module_1", "attempt_token", []);

    expect(result.attemptNumber).toBe(1);
    expect(result.questionCount).toBe(0);
    expect(result.correctCount).toBe(0);
    expect(result.scorePercent).toBe("100");
    expect(result.isPassed).toBe(false);
    expect(result.isTimedOut).toBe(true);
    expect(result.moduleCompleted).toBe(false);
    expect(result.timeLimitSeconds).toBeNull();
    expect(result.durationSeconds).toBeNull();
    expect(result.answers[0].questionOrder).toBe(0);
    expect(result.answers[0].isCorrect).toBe(false);
  });

  it("normalizes malformed quiz history and attempt detail values", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        mockJsonResponse({
          quizUuid: "quiz_1",
          moduleUuid: "module_1",
          title: "Quiz",
          timeLimitSeconds: "bad-limit",
          passedOnce: "false",
          attempts: [
            {
              quizAttemptUuid: "attempt_1",
              attemptNumber: "3",
              questionCount: "bad-count",
              correctCount: "2",
              scorePercent: "not-a-score",
              isPassed: "false",
              isTimedOut: "false",
              durationSeconds: "bad-duration",
            },
          ],
        })
      )
      .mockResolvedValueOnce(
        mockJsonResponse({
          quizAttemptUuid: "attempt_1",
          quizUuid: "quiz_1",
          moduleUuid: "module_1",
          attemptNumber: "2",
          questionCount: "4",
          correctCount: "3",
          scorePercent: -10,
          isPassed: "true",
          isTimedOut: "false",
          moduleCompleted: "true",
          durationSeconds: "90",
          answers: [],
        })
      );
    vi.stubGlobal("fetch", fetchMock);

    const history = await getQuizAttemptHistory("course_1", "module_1");
    const detail = await getQuizAttemptDetail("course_1", "module_1", "attempt_1");

    expect(history?.timeLimitSeconds).toBeNull();
    expect(history?.passedOnce).toBe(false);
    expect(history?.attempts[0].attemptNumber).toBe(3);
    expect(history?.attempts[0].questionCount).toBe(0);
    expect(history?.attempts[0].correctCount).toBe(2);
    expect(history?.attempts[0].scorePercent).toBe("0");
    expect(history?.attempts[0].isPassed).toBe(false);
    expect(history?.attempts[0].isTimedOut).toBe(false);
    expect(history?.attempts[0].durationSeconds).toBeNull();
    expect(detail.questionCount).toBe(4);
    expect(detail.correctCount).toBe(3);
    expect(detail.scorePercent).toBe("0");
    expect(detail.isPassed).toBe(true);
    expect(detail.isTimedOut).toBe(false);
    expect(detail.moduleCompleted).toBe(true);
    expect(detail.durationSeconds).toBe(90);
  });
});

describe("course invite service normalization", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(NOW_MS));
    vi.stubGlobal("localStorage", createMemoryStorage());
    vi.stubGlobal("window", {
      location: {
        pathname: "/courses/join",
        assign: vi.fn(),
      },
    });
    localStorage.setItem("accessToken", makeToken(NOW_MS / 1000 + 60));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("normalizes course invite links and filters malformed list entries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        mockJsonResponse({
          invite_uuid: "invite_1",
          course_uuid: "course_1",
          invite_url: 123,
          is_active: "false",
          created_at: 456,
          expires_at: null,
        })
      )
      .mockResolvedValueOnce(
        mockJsonResponse([
          {
            invite_uuid: "invite_2",
            course_uuid: "course_1",
            invite_url: "/courses/join?token=invite_2",
            is_active: "true",
            created_at: "2026-07-02T00:00:00Z",
            expires_at: "2026-07-09T00:00:00Z",
          },
          {
            invite_uuid: "",
            course_uuid: "course_1",
            is_active: true,
            created_at: "2026-07-02T00:00:00Z",
          },
        ])
      )
      .mockResolvedValueOnce(mockJsonResponse({ detail: 123 }));
    vi.stubGlobal("fetch", fetchMock);

    const generated = await generateCourseInviteLink("course_1");
    const list = await listCourseInviteLinks("course_1");
    const deactivated = await deactivateCourseInviteLink("invite_1");

    expect(generated.inviteUuid).toBe("invite_1");
    expect(generated.inviteUrl).toBe("123");
    expect(generated.isActive).toBe(false);
    expect(generated.createdAt).toBe("456");
    expect(generated.expiresAt).toBeNull();
    expect(list).toHaveLength(1);
    expect(list[0].isActive).toBe(true);
    expect(list[0].expiresAt).toBe("2026-07-09T00:00:00Z");
    expect(deactivated.detail).toBe("123");
  });

  it("rejects invalid course invite validation payloads and malformed enrol responses", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        mockJsonResponse({
          valid: "true",
          course_uuid: "course_1",
          course_title: "Biology",
          invite_uuid: "invite_1",
        })
      )
      .mockResolvedValueOnce(
        mockJsonResponse({
          valid: "false",
          course_uuid: "course_1",
          course_title: "Biology",
          invite_uuid: "invite_1",
        })
      )
      .mockResolvedValueOnce(
        mockJsonResponse({
          detail: 123,
          course_uuid: "course_1",
          course_title: "Biology",
        })
      )
      .mockResolvedValueOnce(
        mockJsonResponse({
          detail: "Enrolled successfully",
          course_title: "Biology",
        })
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(validateCourseInviteToken("invite_1")).resolves.toEqual({
      valid: true,
      courseUuid: "course_1",
      courseTitle: "Biology",
      inviteUuid: "invite_1",
    });
    await expect(validateCourseInviteToken("invite_1")).rejects.toThrow("Invalid or expired invite link.");

    const enrolment = await enrolViaCourseInvite("invite_1");
    expect(enrolment.detail).toBe("123");
    expect(enrolment.courseUuid).toBe("course_1");
    expect(enrolment.courseTitle).toBe("Biology");
    await expect(enrolViaCourseInvite("invite_1")).rejects.toThrow(
      "Course invite enrolment response was invalid"
    );
  });
});

describe("educator analytics service normalization", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(NOW_MS));
    vi.stubGlobal("localStorage", createMemoryStorage());
    vi.stubGlobal("window", {
      location: {
        pathname: "/home/ai",
        assign: vi.fn(),
      },
    });
    localStorage.setItem("accessToken", makeToken(NOW_MS / 1000 + 60));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("normalizes malformed educator course and quiz analytics metrics", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        mockJsonResponse({
          courses: [
            {
              course_uuid: "course_1",
              course_title: "Biology",
              status: 123,
              total_enrollments: "-4",
              active_enrollments: "2",
              completed_enrollments: "bad-completed",
              avg_progress_percent: 140,
            },
          ],
          total_courses: "bad-total",
          total_enrollments: "9",
          total_active_enrollments: -1,
          total_completed_enrollments: "3",
        })
      )
      .mockResolvedValueOnce(
        mockJsonResponse({
          items: [
            {
              course_uuid: "course_1",
              course_title: "Biology",
              module_uuid: "module_1",
              module_title: "Cells",
              quiz_title: 456,
              total_attempts: "-2",
              unique_learners: "5",
              avg_score_percent: "not-a-score",
              pass_rate: 130,
              avg_duration_seconds: -12,
            },
          ],
        })
      );
    vi.stubGlobal("fetch", fetchMock);

    const analytics = await getEducatorAnalytics();
    const quizAnalytics = await getEducatorQuizAnalytics();

    expect(analytics.totalCourses).toBe(1);
    expect(analytics.totalEnrollments).toBe(9);
    expect(analytics.totalActiveEnrollments).toBe(0);
    expect(analytics.totalCompletedEnrollments).toBe(3);
    expect(analytics.courses[0].status).toBe("123");
    expect(analytics.courses[0].totalEnrollments).toBe(0);
    expect(analytics.courses[0].activeEnrollments).toBe(2);
    expect(analytics.courses[0].completedEnrollments).toBe(0);
    expect(analytics.courses[0].avgProgressPercent).toBe(100);
    expect(quizAnalytics.items[0].quizTitle).toBe("456");
    expect(quizAnalytics.items[0].totalAttempts).toBe(0);
    expect(quizAnalytics.items[0].uniqueLearners).toBe(5);
    expect(quizAnalytics.items[0].avgScorePercent).toBeNull();
    expect(quizAnalytics.items[0].passRate).toBe(100);
    expect(quizAnalytics.items[0].avgDurationSeconds).toBeNull();
  });

  it("normalizes malformed teaching insights and material briefs", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        mockJsonResponse({
          generated_at: 123,
          total_insights: "bad-total",
          high_priority_count: -2,
          items: [
            {
              priority: "high",
              category: 456,
              title: null,
              detail: 789,
              action_label: null,
              course_uuid: "",
              metric_label: "Pass rate",
              metric_value: 42,
            },
          ],
        })
      )
      .mockResolvedValueOnce(
        mockJsonResponse({
          generated_at: "2026-07-02T00:00:00Z",
          total_briefs: "bad-total",
          high_priority_count: "2",
          items: [
            {
              priority: "medium",
              course_uuid: "course_1",
              course_title: "Biology",
              module_uuid: "module_1",
              module_title: "Cells",
              module_status: 123,
              material_count: -5,
              material_types: ["pdf", 7, ""],
              quiz_title: null,
              pass_rate: "bad-rate",
              average_score_percent: 101,
              summary: 456,
              difficulty_signal: null,
              recommended_action: undefined,
            },
          ],
        })
      );
    vi.stubGlobal("fetch", fetchMock);

    const insights = await getEducatorTeachingInsights();
    const briefs = await getEducatorMaterialBriefs();

    expect(insights.generatedAt).toBe("123");
    expect(insights.totalInsights).toBe(1);
    expect(insights.highPriorityCount).toBe(0);
    expect(insights.items[0].insightId).toBe("insight-1");
    expect(insights.items[0].category).toBe("456");
    expect(insights.items[0].title).toBe("Insight 1");
    expect(insights.items[0].detail).toBe("789");
    expect(insights.items[0].actionLabel).toBe("Review");
    expect(insights.items[0].courseUuid).toBeNull();
    expect(insights.items[0].metricValue).toBe("42");
    expect(briefs.totalBriefs).toBe(1);
    expect(briefs.highPriorityCount).toBe(2);
    expect(briefs.items[0].briefId).toBe("brief-1");
    expect(briefs.items[0].moduleStatus).toBe("123");
    expect(briefs.items[0].materialCount).toBe(0);
    expect(briefs.items[0].materialTypes).toEqual(["pdf", "7"]);
    expect(briefs.items[0].passRate).toBeNull();
    expect(briefs.items[0].averageScorePercent).toBe(100);
    expect(briefs.items[0].summary).toBe("456");
    expect(briefs.items[0].difficultySignal).toBe("");
    expect(briefs.items[0].recommendedAction).toBe("Review");
  });
});

describe("multipart material upload service normalization", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(NOW_MS));
    vi.stubGlobal("localStorage", createMemoryStorage());
    vi.stubGlobal("window", {
      location: {
        pathname: "/course/course_1/management/modules/module_1",
        assign: vi.fn(),
      },
    });
    localStorage.setItem("accessToken", makeToken(NOW_MS / 1000 + 60));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("normalizes multipart upload init and part URL responses", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        mockJsonResponse({
          upload_session_uuid: "upload_session_1",
          upload_id: "multipart_1",
          bucket: "learning-materials",
          object_key: "course_1/module_1/large.pdf",
          storage_provider: "minio",
          part_url_expires_seconds: "3600",
        })
      )
      .mockResolvedValueOnce(
        mockJsonResponse({
          uploadSessionUuid: "upload_session_1",
          partNumber: "2",
          method: "put",
          uploadUrl: "/learning-materials/course_1/module_1/large.pdf?uploadId=multipart_1&partNumber=2",
          expiresSeconds: "3600",
        })
      );
    vi.stubGlobal("fetch", fetchMock);

    const init = await initMultipartManagedModuleMaterialUpload("course_1", "module_1", {
      fileName: "large.pdf",
      contentType: "application/pdf",
      sizeBytes: 150 * 1024 * 1024,
    });
    const partUrl = await getMultipartManagedModuleMaterialPartUploadUrl(
      "course_1",
      "module_1",
      init.uploadSessionUuid,
      2
    );

    expect(init).toEqual({
      uploadSessionUuid: "upload_session_1",
      uploadId: "multipart_1",
      bucket: "learning-materials",
      objectKey: "course_1/module_1/large.pdf",
      storageProvider: "minio",
      partUrlExpiresSeconds: 3600,
    });
    expect(partUrl).toEqual({
      uploadSessionUuid: "upload_session_1",
      partNumber: 2,
      method: "PUT",
      uploadUrl: "/learning-materials/course_1/module_1/large.pdf?uploadId=multipart_1&partNumber=2",
      expiresSeconds: 3600,
    });
  });

  it("rejects malformed multipart upload responses before continuing upload", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        mockJsonResponse({
          upload_id: "multipart_1",
          object_key: "course_1/module_1/large.pdf",
          storage_provider: "minio",
          part_url_expires_seconds: 3600,
        })
      )
      .mockResolvedValueOnce(
        mockJsonResponse({
          uploadSessionUuid: "other_session",
          partNumber: 3,
          method: "POST",
          uploadUrl: "not-a-url",
          expiresSeconds: 3600,
        })
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      initMultipartManagedModuleMaterialUpload("course_1", "module_1", {
        fileName: "large.pdf",
        contentType: "application/pdf",
        sizeBytes: 150 * 1024 * 1024,
      })
    ).rejects.toThrow("Multipart upload initialization response was invalid");

    await expect(
      getMultipartManagedModuleMaterialPartUploadUrl("course_1", "module_1", "upload_session_1", 2)
    ).rejects.toThrow("Multipart upload URL response was invalid");
  });
});
