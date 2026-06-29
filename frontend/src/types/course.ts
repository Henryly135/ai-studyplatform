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
