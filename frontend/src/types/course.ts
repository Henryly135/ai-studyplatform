export type CourseMaterial = {
  materialUuid: string;
  materialId?: number;
  title: string;
  materialType: string;
  resourceUrl: string;
  sortOrder: number;
  metadataJson: Record<string, unknown> | null;
};

export type CourseModule = {
  moduleUuid: string;
  moduleId?: number;
  sortOrder?: number;
  slug: string;
  title: string;
  summary: string;
  content?: string;
  durationLabel: string;
  status: "available" | "locked" | "draft";
  visibility?: string;
  classId?: string | null;
  prerequisiteModuleUuid?: string | null;
  prerequisiteModuleTitle?: string | null;
  isLocked?: boolean;
  lockMessage?: string | null;
  materials: CourseMaterial[];
  hasPublishedQuiz?: boolean;
  quizTitle?: string | null;
  quizTimeLimitSeconds?: number | null;
  progressStatus?: string | null;
  isCompleted?: boolean;
  completedAt?: string | null;
};

export type CourseRecord = {
  courseUuid: string;
  courseId: number;
  educatorUuid: string;
  educatorId?: number;
  title: string;
  subtitle: string;
  description: string;
  category: string;
  languageCode: string;
  estimatedMinutes: number | null;
  difficultyLevel: string;
  isPublic: boolean;
  coverImageUrl: string | null;
  educatorName: string;
  educatorEmail?: string;
  educatorUserName?: string;
  termLabel: string;
  courseCode: string;
  schoolName: string;
  status?: string;
  publishedAt?: string | null;
  moduleCount?: number;
  learningPathId?: number | null;
  learningPathTitle?: string;
  learningPathDescription?: string;
  modules: CourseModule[];
};

export type LearnerProgressQuizSummary = {
  totalQuizzes: number;
  attemptedQuizzes: number;
  passedQuizzes: number;
  totalAttempts: number;
  averageBestScorePercent: number | null;
  latestScorePercent: number | null;
  latestSubmittedAt: string | null;
};

export type LearnerProgressNextModule = {
  moduleId: number;
  moduleUuid: string;
  title: string;
};

export type LearnerProgressCourseItem = {
  courseId: number;
  courseUuid: string;
  title: string;
  courseCode: string | null;
  category: string | null;
  enrollmentStatus: string;
  progressPercent: number;
  completedModuleCount: number;
  totalModuleCount: number;
  lastAccessedAt: string | null;
  completedAt: string | null;
  nextModule: LearnerProgressNextModule | null;
  quiz: LearnerProgressQuizSummary;
};

export type LearnerProgressActivityItem = {
  activityType: string;
  occurredAt: string;
  courseId: number;
  courseUuid: string;
  courseTitle: string;
  moduleId: number | null;
  moduleUuid: string | null;
  moduleTitle: string | null;
  title: string;
  detail: string | null;
  scorePercent: number | null;
  isPassed: boolean | null;
};

export type LearnerProgressOverview = {
  totalCourses: number;
  totalModules: number;
  completedModules: number;
  averageProgressPercent: number;
  quiz: LearnerProgressQuizSummary;
  courses: LearnerProgressCourseItem[];
  recentActivity: LearnerProgressActivityItem[];
};

export type QuizOptionDraft = {
  optionUuid: string | null;
  optionLabel: string;
  optionText: string;
  sortOrder: number;
  isCorrect: boolean;
};

export type QuizQuestionDraft = {
  questionUuid: string | null;
  questionText: string;
  explanationText: string;
  sortOrder: number;
  isActive: boolean;
  options: QuizOptionDraft[];
};

export type QuizRecord = {
  quizUuid: string;
  title: string;
  description: string;
  status: "draft" | "published" | "archived";
  timeLimitSeconds: number | null;
  questionCountPerAttempt: number;
  availableQuestionCount: number;
  shuffleQuestions: boolean;
  shuffleOptions: boolean;
  questions: QuizQuestionDraft[];
};

export type QuizQuestionPage = {
  items: QuizQuestionDraft[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
};

export type QuizSessionOption = {
  optionId: number;
  optionUuid: string;
  optionLabel: string | null;
  optionText: string;
  sortOrder: number;
};

export type QuizSessionQuestion = {
  questionId: number;
  questionUuid: string;
  questionText: string;
  explanationText: string | null;
  questionOrder: number;
  options: QuizSessionOption[];
};

export type QuizAttemptSession = {
  quizUuid: string;
  moduleUuid: string;
  attemptSessionToken: string;
  attemptNumber: number;
  questionCount: number;
  timeLimitSeconds: number | null;
  startedAt: string;
  expiresAt: string | null;
  questions: QuizSessionQuestion[];
};

export type QuizGenerationProgressEvent = {
  event: string;
  message: string;
  step: string | null;
  timestamp: string;
  data: Record<string, unknown>;
};

export type QuizGenerationRun = {
  runId: string;
  status: "queued" | "running" | "completed" | "failed";
  currentStep: string | null;
  message: string | null;
  error: string | null;
  attemptStartResponse: QuizAttemptSession | null;
  events: QuizGenerationProgressEvent[];
};

export type QuizAuthoringGenerationResult = {
  createdQuestionCount: number;
  createdQuestionUuids: string[];
  plannedQuestionCount: number;
  usedRetrieval: boolean;
  retrievalChunkCount: number;
  planOverview: string;
};

export type QuizAttemptAnswerResult = {
  questionUuid: string;
  questionOrder: number;
  questionText: string;
  explanationText: string | null;
  selectedOptionUuid: string | null;
  selectedOptionText: string | null;
  correctOptionUuid: string;
  correctOptionText: string;
  isCorrect: boolean;
};

export type QuizAttemptResult = {
  quizAttemptUuid: string;
  quizUuid: string;
  moduleUuid: string;
  attemptNumber: number;
  questionCount: number;
  correctCount: number;
  scorePercent: string;
  isPassed: boolean;
  isTimedOut: boolean;
  moduleCompleted: boolean;
  timeLimitSeconds: number | null;
  startedAt: string;
  submittedAt: string;
  durationSeconds: number | null;
  answers: QuizAttemptAnswerResult[];
};

export type QuizAttemptHistoryEntry = {
  quizAttemptUuid: string;
  attemptNumber: number;
  questionCount: number;
  correctCount: number;
  scorePercent: string;
  isPassed: boolean;
  isTimedOut: boolean;
  startedAt: string;
  submittedAt: string;
  durationSeconds: number | null;
};

export type QuizAttemptHistory = {
  quizUuid: string;
  moduleUuid: string;
  title: string;
  timeLimitSeconds: number | null;
  passedOnce: boolean;
  attempts: QuizAttemptHistoryEntry[];
};

export type CourseEnrollmentLearnerRecord = {
  enrollmentId: number;
  courseId: number;
  courseUuid: string;
  learnerId: number;
  learnerUuid: string;
  learnerName: string;
  learnerEmail: string;
  learnerIdentity: string;
  learnerAccountStatus: string;
  learnerEmailVerified: boolean | null;
  enrollmentStatus: string;
  progressPercent: string;
  completedModuleCount: number;
  totalModuleCount: number;
  enrolledAt: string;
  lastAccessedAt: string | null;
  completedAt: string | null;
};

export type EducatorCourseAnalyticsItem = {
  courseUuid: string;
  courseTitle: string;
  status: string;
  totalEnrollments: number;
  activeEnrollments: number;
  completedEnrollments: number;
  avgProgressPercent: number | null;
};

export type EducatorAnalytics = {
  courses: EducatorCourseAnalyticsItem[];
  totalCourses: number;
  totalEnrollments: number;
  totalActiveEnrollments: number;
  totalCompletedEnrollments: number;
};

export type QuizModuleStatsItem = {
  courseUuid: string;
  courseTitle: string;
  moduleUuid: string;
  moduleTitle: string;
  quizTitle: string;
  totalAttempts: number;
  uniqueLearners: number;
  avgScorePercent: number | null;
  passRate: number | null;
  avgDurationSeconds: number | null;
};

export type EducatorQuizAnalytics = {
  items: QuizModuleStatsItem[];
};

export type TeachingInsightItem = {
  insightId: string;
  priority: "high" | "medium" | "low" | string;
  category: string;
  title: string;
  detail: string;
  actionLabel: string;
  courseUuid: string | null;
  courseTitle: string | null;
  moduleUuid: string | null;
  moduleTitle: string | null;
  metricLabel: string | null;
  metricValue: string | null;
};

export type EducatorTeachingInsights = {
  generatedAt: string;
  totalInsights: number;
  highPriorityCount: number;
  items: TeachingInsightItem[];
};

export type EducatorMaterialBriefItem = {
  briefId: string;
  priority: "high" | "medium" | "low" | string;
  courseUuid: string;
  courseTitle: string;
  moduleUuid: string;
  moduleTitle: string;
  moduleStatus: string;
  materialCount: number;
  materialTypes: string[];
  quizTitle: string | null;
  passRate: number | null;
  averageScorePercent: number | null;
  summary: string;
  difficultySignal: string;
  recommendedAction: string;
};

export type EducatorMaterialBriefs = {
  generatedAt: string;
  totalBriefs: number;
  highPriorityCount: number;
  items: EducatorMaterialBriefItem[];
};
