import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { LuDownload, LuRefreshCw, LuSearch } from "react-icons/lu";

import {
  checkAdminAiProviderCredentialHealth,
  deleteAdminAiProviderCredential,
  getAdminUsers,
  listAdminAiProviderCredentials,
  saveAdminAiProviderCredential,
  setAdminAiDefaultModel,
} from "../../services/admin";
import {
  getAdminAiGovernance,
  getAdminAiProviderConfig,
  getAdminAiProviderHealth,
  getAdminAiTelemetryAnomalies,
  getAdminAiTelemetrySummary,
  getAdminAiTelemetryTrends,
  getAiModelCatalog,
  getAiRuntimeHealth,
  exportAdminAiTelemetryFailures,
  getChatSessionDetail,
  listChatSessions,
  retryAdminAiIndexJob,
  searchAdminAiTelemetryFailures,
  sendChatMessage,
} from "../../services/chat";
import {
  getEducatorAnalytics,
  getEducatorMaterialBriefs,
  getEducatorQuizAnalytics,
  getEducatorTeachingInsights,
  getCourseByUuid,
  getManagedCourseByUuid,
  getManagedCourses,
  getMyEnrolledCourses,
} from "../../services/course";
import type { AdminAiProviderCredential, AdminUserResponse } from "../../types/admin";
import type {
  AdminAiGovernance,
  AdminAiProviderConfig,
  AdminAiProviderHealth,
  AdminAiTelemetryAnomalyInsight,
  AdminAiTelemetryFailureItem,
  AdminAiTelemetryFailureFilters,
  AdminAiTelemetrySummary,
  AdminAiTelemetryTrendPoint,
  AiModelCatalog,
  AiModelCatalogModel,
  AiRuntimeHealth,
  ChatSessionDetail,
  ChatSessionSummary,
} from "../../types/chat";
import type {
  CourseRecord,
  EducatorAnalytics,
  EducatorMaterialBriefItem,
  EducatorMaterialBriefs,
  EducatorQuizAnalytics,
  EducatorTeachingInsights,
  TeachingInsightItem,
} from "../../types/course";
import type { HomeOutletContext } from "./HomeSectionPage";
import {
  formatRagOptionSuffix,
  isChatModelSelectable,
  resolveChatModelSelection,
} from "../Course/courseChatModels";
import { HomeAiConversationPanel } from "./HomeAiConversationPanel";
import {
  getLearnerAiModuleEntries,
  hydrateLearnerAiCourses,
} from "./learnerAiWorkspace";
import "./HomePage.css";

type RoleAiDashboardState = {
  managedCourses: CourseRecord[];
  educatorAnalytics: EducatorAnalytics | null;
  quizAnalytics: EducatorQuizAnalytics | null;
  teachingInsights: EducatorTeachingInsights | null;
  materialBriefs: EducatorMaterialBriefs | null;
  adminUsers: AdminUserResponse[];
  aiHealth: AiRuntimeHealth | null;
  aiHealthError: string | null;
  aiModelCatalog: AiModelCatalog | null;
  aiProviderCredentials: AdminAiProviderCredential[];
  aiGovernance: AdminAiGovernance | null;
  aiProviderConfig: AdminAiProviderConfig | null;
  aiProviderHealth: AdminAiProviderHealth | null;
  aiTelemetry: AdminAiTelemetrySummary | null;
  aiTrends: AdminAiTelemetryTrendPoint[];
  aiAnomalies: AdminAiTelemetryAnomalyInsight[];
  aiFailures: AdminAiTelemetryFailureItem[];
};

const EMPTY_ROLE_AI_DASHBOARD: RoleAiDashboardState = {
  managedCourses: [],
  educatorAnalytics: null,
  quizAnalytics: null,
  teachingInsights: null,
  materialBriefs: null,
  adminUsers: [],
  aiHealth: null,
  aiHealthError: null,
  aiModelCatalog: null,
  aiProviderCredentials: [],
  aiGovernance: null,
  aiProviderConfig: null,
  aiProviderHealth: null,
  aiTelemetry: null,
  aiTrends: [],
  aiAnomalies: [],
  aiFailures: [],
};

const DEFAULT_ADMIN_FAILURE_FILTERS: AdminAiTelemetryFailureFilters = {
  limit: 20,
  kind: "",
  status: "",
  userId: "",
  courseId: "",
  moduleId: "",
  since: "",
  until: "",
};

function formatSessionTimestamp(value: string | null) {
  if (!value) {
    return "暂无活动";
  }

  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) {
    return "最近";
  }

  return new Intl.DateTimeFormat("en-AU", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(timestamp);
}

function formatTrendDate(value: string) {
  const timestamp = new Date(`${value}T00:00:00`);
  if (Number.isNaN(timestamp.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-AU", {
    month: "short",
    day: "numeric",
  }).format(timestamp);
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-AU").format(value);
}

function formatCompactNumber(value: number) {
  return new Intl.NumberFormat("en-AU", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function formatPercent(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "0%";
  }
  return `${Math.round(value)}%`;
}

function formatEmbeddingPair(model: AiModelCatalogModel | null) {
  if (!model) {
    return "尚未选择生成模型";
  }

  const embeddingName =
    model.pairedEmbeddingModelName || model.pairedEmbeddingModelId || "配对向量模型待目录同步";
  const dimension = model.embeddingDimension ? ` · ${model.embeddingDimension} 维` : "";
  const coverage =
    model.indexCoverage === null ? "" : ` · 索引覆盖 ${Math.round(model.indexCoverage * 100)}%`;

  if (model.ragReady === true) {
    return `${embeddingName}${dimension} · 资料检索就绪${coverage}`;
  }
  if (model.ragReady === false) {
    return `${embeddingName}${dimension} · 资料检索尚未就绪${coverage}`;
  }
  return `${embeddingName}${dimension} · 资料检索状态待确认`;
}

function formatLatency(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "暂无延迟数据";
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(value >= 10_000 ? 0 : 1)}s`;
  }
  return `${Math.round(value)}ms`;
}

function formatTrendDelta(recent: number, previous: number) {
  if (previous === 0) {
    return recent > 0 ? "新增活动" : "较前 7 天持平";
  }

  const delta = ((recent - previous) / previous) * 100;
  if (Math.abs(delta) < 1) {
    return "较前 7 天持平";
  }

  return `较前 7 天 ${delta > 0 ? "+" : ""}${Math.round(delta)}%`;
}

function normalizeStatus(value: string | undefined | null) {
  return value?.trim().toLowerCase() || "unknown";
}

function countCourseModules(course: CourseRecord) {
  return course.moduleCount ?? course.modules.length;
}

function countCourseMaterials(course: CourseRecord) {
  return course.modules.reduce((total, module) => total + module.materials.length, 0);
}

function countCoursePublishedQuizzes(course: CourseRecord) {
  return course.modules.reduce((total, module) => total + (module.hasPublishedQuiz ? 1 : 0), 0);
}

function sumTrend(
  points: AdminAiTelemetryTrendPoint[],
  selector: (point: AdminAiTelemetryTrendPoint) => number
) {
  return points.reduce((total, point) => total + selector(point), 0);
}

function getLearnerAiModulePath(courseUuid: string, moduleUuid: string) {
  return `/course/${courseUuid}/modules/${moduleUuid}?from=my-courses&openChat=1`;
}

function HomeAiPage() {
  const { currentUser } = useOutletContext<HomeOutletContext>();
  const isLearner = currentUser.identity === "Learner";
  const isEducator = currentUser.identity === "Educator";
  const isChatUser = isLearner || isEducator;
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [courses, setCourses] = useState<CourseRecord[]>([]);
  const [activeSession, setActiveSession] = useState<ChatSessionDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailErrorMessage, setDetailErrorMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [coursesErrorMessage, setCoursesErrorMessage] = useState<string | null>(null);
  const [roleDashboard, setRoleDashboard] = useState<RoleAiDashboardState>(EMPTY_ROLE_AI_DASHBOARD);
  const [roleDashboardLoading, setRoleDashboardLoading] = useState(!isLearner);
  const [roleDashboardError, setRoleDashboardError] = useState<string | null>(null);
  const [failureFilters, setFailureFilters] = useState<AdminAiTelemetryFailureFilters>(DEFAULT_ADMIN_FAILURE_FILTERS);
  const [failureAuditLoading, setFailureAuditLoading] = useState(false);
  const [failureAuditError, setFailureAuditError] = useState<string | null>(null);
  const [failureAuditNotice, setFailureAuditNotice] = useState<string | null>(null);
  const [failureAuditExporting, setFailureAuditExporting] = useState(false);
  const [retryingIndexJobId, setRetryingIndexJobId] = useState<number | null>(null);
  const [credentialDrafts, setCredentialDrafts] = useState<Record<string, string>>({});
  const [credentialActionProvider, setCredentialActionProvider] = useState<string | null>(null);
  const [credentialActionError, setCredentialActionError] = useState<string | null>(null);
  const [credentialActionNotice, setCredentialActionNotice] = useState<string | null>(null);
  const [selectedDefaultModelId, setSelectedDefaultModelId] = useState("");
  const [selectedLearnerCourseUuid, setSelectedLearnerCourseUuid] = useState("");
  const [selectedLearnerModuleUuid, setSelectedLearnerModuleUuid] = useState("");
  const [learnerModelCatalog, setLearnerModelCatalog] = useState<AiModelCatalog | null>(null);
  const [learnerModelCatalogScopeKey, setLearnerModelCatalogScopeKey] = useState("");
  const [selectedLearnerModelId, setSelectedLearnerModelId] = useState("");
  const [learnerQuestion, setLearnerQuestion] = useState("");
  const [learnerQuestionStatus, setLearnerQuestionStatus] = useState("选择课程模块后即可提问。");
  const [learnerQuestionSending, setLearnerQuestionSending] = useState(false);

  useEffect(() => {
    if (!isChatUser) {
      return;
    }

    let cancelled = false;
    setLoading(true);
    setErrorMessage(null);

    void listChatSessions()
      .then((data) => {
        if (!cancelled) {
          setSessions(data);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : "智能会话加载失败。");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [isChatUser]);

  useEffect(() => {
    if (isLearner) {
      return;
    }

    let cancelled = false;

    async function loadRoleDashboard() {
      setRoleDashboardLoading(true);
      setRoleDashboardError(null);

      const nextDashboard: RoleAiDashboardState = { ...EMPTY_ROLE_AI_DASHBOARD };
      const errors: string[] = [];

      const [managedCoursesResult, aiHealthResult] = await Promise.allSettled([
        getManagedCourses({ page: 1, pageSize: 100 }),
        getAiRuntimeHealth(),
      ]);

      if (managedCoursesResult.status === "fulfilled") {
        nextDashboard.managedCourses = managedCoursesResult.value.items;
      } else {
        errors.push(
          managedCoursesResult.reason instanceof Error
            ? managedCoursesResult.reason.message
            : "管理课程加载失败。"
        );
      }

      if (aiHealthResult.status === "fulfilled") {
        nextDashboard.aiHealth = aiHealthResult.value;
      } else {
        nextDashboard.aiHealthError =
          aiHealthResult.reason instanceof Error
            ? aiHealthResult.reason.message
            : "智能服务健康状态不可用。";
      }

      if (currentUser.identity === "Educator") {
        const [analyticsResult, quizAnalyticsResult, teachingInsightsResult, materialBriefsResult] = await Promise.allSettled([
          getEducatorAnalytics(),
          getEducatorQuizAnalytics(),
          getEducatorTeachingInsights(),
          getEducatorMaterialBriefs(),
        ]);

        if (analyticsResult.status === "fulfilled") {
          nextDashboard.educatorAnalytics = analyticsResult.value;
        } else {
          errors.push(
            analyticsResult.reason instanceof Error
              ? analyticsResult.reason.message
              : "教师分析加载失败。"
          );
        }

        if (quizAnalyticsResult.status === "fulfilled") {
          nextDashboard.quizAnalytics = quizAnalyticsResult.value;
        } else {
          errors.push(
            quizAnalyticsResult.reason instanceof Error
              ? quizAnalyticsResult.reason.message
              : "测验分析加载失败。"
          );
        }

        if (teachingInsightsResult.status === "fulfilled") {
          nextDashboard.teachingInsights = teachingInsightsResult.value;
        } else {
          errors.push(
            teachingInsightsResult.reason instanceof Error
              ? teachingInsightsResult.reason.message
              : "教学洞察加载失败。"
          );
        }

        if (materialBriefsResult.status === "fulfilled") {
          nextDashboard.materialBriefs = materialBriefsResult.value;
        } else {
          errors.push(
            materialBriefsResult.reason instanceof Error
              ? materialBriefsResult.reason.message
              : "资料摘要加载失败。"
          );
        }
      }

      if (currentUser.identity === "Admin") {
        const [
          usersResult,
          governanceResult,
          providerConfigResult,
          providerHealthResult,
          telemetryResult,
          trendsResult,
          anomaliesResult,
          failuresResult,
          modelCatalogResult,
          providerCredentialsResult,
        ] = await Promise.allSettled([
          getAdminUsers(""),
          getAdminAiGovernance(),
          getAdminAiProviderConfig(),
          getAdminAiProviderHealth(14),
          getAdminAiTelemetrySummary(),
          getAdminAiTelemetryTrends(14),
          getAdminAiTelemetryAnomalies(14),
          searchAdminAiTelemetryFailures(DEFAULT_ADMIN_FAILURE_FILTERS),
          getAiModelCatalog(),
          listAdminAiProviderCredentials(""),
        ]);

        if (usersResult.status === "fulfilled") {
          nextDashboard.adminUsers = usersResult.value.users;
        } else {
          errors.push(
            usersResult.reason instanceof Error
              ? usersResult.reason.message
            : "平台用户加载失败。"
          );
        }

        if (governanceResult.status === "fulfilled") {
          nextDashboard.aiGovernance = governanceResult.value;
        } else {
          errors.push(
            governanceResult.reason instanceof Error
              ? governanceResult.reason.message
              : "智能治理摘要加载失败。"
          );
        }

        if (providerConfigResult.status === "fulfilled") {
          nextDashboard.aiProviderConfig = providerConfigResult.value;
        } else {
          errors.push(
            providerConfigResult.reason instanceof Error
              ? providerConfigResult.reason.message
              : "智能服务配置加载失败。"
          );
        }

        if (providerHealthResult.status === "fulfilled") {
          nextDashboard.aiProviderHealth = providerHealthResult.value;
        } else {
          errors.push(
            providerHealthResult.reason instanceof Error
              ? providerHealthResult.reason.message
              : "智能服务健康状态加载失败。"
          );
        }

        if (telemetryResult.status === "fulfilled") {
          nextDashboard.aiTelemetry = telemetryResult.value;
        } else {
          errors.push(
            telemetryResult.reason instanceof Error
              ? telemetryResult.reason.message
              : "智能服务遥测加载失败。"
          );
        }

        if (trendsResult.status === "fulfilled") {
          nextDashboard.aiTrends = trendsResult.value.items;
        } else {
          errors.push(
            trendsResult.reason instanceof Error
              ? trendsResult.reason.message
              : "智能服务趋势加载失败。"
          );
        }

        if (anomaliesResult.status === "fulfilled") {
          nextDashboard.aiAnomalies = anomaliesResult.value.items;
        } else {
          errors.push(
            anomaliesResult.reason instanceof Error
              ? anomaliesResult.reason.message
              : "智能服务异常洞察加载失败。"
          );
        }

        if (failuresResult.status === "fulfilled") {
          nextDashboard.aiFailures = failuresResult.value.items;
        } else {
          errors.push(
            failuresResult.reason instanceof Error
              ? failuresResult.reason.message
              : "智能服务失败审计加载失败。"
          );
        }

        if (modelCatalogResult.status === "fulfilled") {
          nextDashboard.aiModelCatalog = modelCatalogResult.value;
        } else {
          errors.push(
            modelCatalogResult.reason instanceof Error
              ? modelCatalogResult.reason.message
              : "智能模型目录加载失败。"
          );
        }

        if (providerCredentialsResult.status === "fulfilled") {
          nextDashboard.aiProviderCredentials = providerCredentialsResult.value.credentials;
        } else {
          errors.push(
            providerCredentialsResult.reason instanceof Error
              ? providerCredentialsResult.reason.message
              : "智能供应商密钥配置加载失败。"
          );
        }
      }

      if (!cancelled) {
        setRoleDashboard(nextDashboard);
        setRoleDashboardError(errors.length > 0 ? errors.join(" ") : null);
        setRoleDashboardLoading(false);
      }
    }

    void loadRoleDashboard();

    return () => {
      cancelled = true;
    };
  }, [currentUser.identity, isLearner]);

  useEffect(() => {
    if (selectedDefaultModelId || !roleDashboard.aiModelCatalog) {
      return;
    }

    const availableModels = roleDashboard.aiModelCatalog.providers.flatMap((provider) =>
      provider.models.filter((model) => model.available)
    );
    setSelectedDefaultModelId(
      roleDashboard.aiModelCatalog.defaultModelId ??
      availableModels.find((model) => model.isDefault)?.modelId ??
      availableModels[0]?.modelId ??
      ""
    );
  }, [roleDashboard.aiModelCatalog, selectedDefaultModelId]);

  const loadFailureAudit = useCallback(
    async (filters: AdminAiTelemetryFailureFilters = failureFilters) => {
      if (currentUser.identity !== "Admin") return;
      setFailureAuditLoading(true);
      setFailureAuditError(null);
      setFailureAuditNotice(null);
      try {
        const response = await searchAdminAiTelemetryFailures(filters);
        setRoleDashboard((current) => ({
          ...current,
          aiFailures: response.items,
        }));
      } catch (error) {
        setFailureAuditError(error instanceof Error ? error.message : "智能服务失败审计加载失败。");
      } finally {
        setFailureAuditLoading(false);
      }
    },
    [currentUser.identity, failureFilters]
  );

  useEffect(() => {
    if (!isChatUser) {
      return;
    }

    let cancelled = false;

    const loadChatCourses = isLearner
      ? getMyEnrolledCourses().then((data) => hydrateLearnerAiCourses(data, getCourseByUuid))
      : getManagedCourses({ page: 1, pageSize: 100 }).then(async (response) =>
          Promise.all(
            response.items.map(async (course) => {
              try {
                return (await getManagedCourseByUuid(course.courseUuid)) ?? course;
              } catch {
                return course;
              }
            })
          )
        );

    void loadChatCourses
      .then((data) => {
        if (!cancelled) {
          setCourses(data);
          setCoursesErrorMessage(null);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setCourses([]);
          setCoursesErrorMessage(
            error instanceof Error ? error.message : "课程上下文加载失败。"
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, [isChatUser, isLearner]);

  const workspaceCopy = useMemo(() => {
    if (currentUser.identity === "Educator") {
      return {
        badge: "教师智能助手",
        title: "教学智能工作区",
        body: "查看课程、资料、测验和学生信号是否已准备好支持教学流程。",
        primaryTitle: "教学准备度",
        secondaryTitle: "智能服务运行状态",
      };
    }

    if (currentUser.identity === "Admin") {
      return {
        badge: "管理员智能治理",
        title: "智能治理",
        body: "面向管理员查看平台智能能力准备度、用户覆盖率和存储/安全信号。",
        primaryTitle: "治理快照",
        secondaryTitle: "智能服务运行状态",
      };
    }

    return {
      badge: "智能助手",
      title: "智能工作区",
      body: "选择课程模块直接提问，并基于课程资料继续学习。",
      primaryTitle: "全部会话",
      secondaryTitle: "模块推荐",
    };
  }, [currentUser.identity]);

  const courseTitleMap = useMemo(() => {
    const courseTitles = new Map<string, string>();

    courses.forEach((course) => {
      courseTitles.set(course.courseUuid, course.title);
    });

    return courseTitles;
  }, [courses]);

  const learnerAiModuleEntries = useMemo(
    () => getLearnerAiModuleEntries(courses).slice(0, 6),
    [courses]
  );

  const learnerCoursesWithModules = useMemo(
    () => courses.filter((course) => course.modules.some((module) => !module.isLocked)),
    [courses]
  );
  const effectiveSelectedLearnerCourseUuid = learnerCoursesWithModules.some(
    (course) => course.courseUuid === selectedLearnerCourseUuid
  )
    ? selectedLearnerCourseUuid
    : learnerCoursesWithModules[0]?.courseUuid ?? "";
  const selectedLearnerCourse = useMemo(
    () => courses.find((course) => course.courseUuid === effectiveSelectedLearnerCourseUuid) ?? null,
    [courses, effectiveSelectedLearnerCourseUuid]
  );
  const selectedLearnerModules = useMemo(
    () => selectedLearnerCourse?.modules.filter((module) => !module.isLocked) ?? [],
    [selectedLearnerCourse]
  );
  const effectiveSelectedLearnerModuleUuid = selectedLearnerModules.some(
    (module) => module.moduleUuid === selectedLearnerModuleUuid
  )
    ? selectedLearnerModuleUuid
    : selectedLearnerModules[0]?.moduleUuid ?? "";
  const chatCourseUuid = activeSession?.session.course_uuid ?? effectiveSelectedLearnerCourseUuid;
  const chatModuleUuid = activeSession?.session.module_uuid ?? effectiveSelectedLearnerModuleUuid;
  const learnerModelScopeKey = `${chatCourseUuid}:${chatModuleUuid}`;
  const activeLearnerModelCatalog =
    learnerModelCatalogScopeKey === learnerModelScopeKey ? learnerModelCatalog : null;
  const learnerModelOptions = useMemo(
    () =>
      activeLearnerModelCatalog?.providers.flatMap((provider) =>
        provider.models
          .filter((model) => model.capabilities.includes("chat"))
          .map((model) => ({
            value: model.modelId,
            label: `${model.name}${formatRagOptionSuffix(model)}`,
            disabled: !isChatModelSelectable(model),
          }))
      ) ?? [],
    [activeLearnerModelCatalog]
  );
  const activeLearnerQuestionStatus = !chatCourseUuid
    ? "暂无可提问的已加入课程。"
    : !chatModuleUuid
      ? "当前课程暂无可提问模块。"
      : learnerModelCatalogScopeKey !== learnerModelScopeKey
        ? "正在加载可用模型..."
        : learnerQuestionStatus;

  useEffect(() => {
    if (!isChatUser || !chatCourseUuid || !chatModuleUuid) {
      return;
    }

    let cancelled = false;
    const requestedScopeKey = `${chatCourseUuid}:${chatModuleUuid}`;
    void getAiModelCatalog({
      courseUuid: chatCourseUuid,
      moduleUuid: chatModuleUuid,
    })
      .then((catalog) => {
        if (cancelled) {
          return;
        }
        setLearnerModelCatalog(catalog);
        setLearnerModelCatalogScopeKey(requestedScopeKey);
        setSelectedLearnerModelId((current) => resolveChatModelSelection(catalog, current));
        setLearnerQuestionStatus("可以开始提问。");
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        setLearnerModelCatalog(null);
        setLearnerModelCatalogScopeKey(requestedScopeKey);
        setSelectedLearnerModelId("");
        setLearnerQuestionStatus(error instanceof Error ? error.message : "模型目录加载失败。");
      });

    return () => {
      cancelled = true;
    };
  }, [chatCourseUuid, chatModuleUuid, isChatUser]);

  const educatorDashboard = useMemo(() => {
    const managedCourses = roleDashboard.managedCourses;
    const totalMaterials = managedCourses.reduce((total, course) => total + countCourseMaterials(course), 0);
    const publishedQuizzesFromCourses = managedCourses.reduce(
      (total, course) => total + countCoursePublishedQuizzes(course),
      0
    );
    const quizModules = roleDashboard.quizAnalytics?.items.length ?? publishedQuizzesFromCourses;

    return {
      totalCourses: roleDashboard.educatorAnalytics?.totalCourses ?? managedCourses.length,
      publishedCourses: managedCourses.filter((course) => normalizeStatus(course.status) === "published").length,
      draftCourses: managedCourses.filter((course) => normalizeStatus(course.status) === "draft").length,
      totalModules: managedCourses.reduce((total, course) => total + countCourseModules(course), 0),
      totalMaterials,
      quizModules,
      totalEnrollments: roleDashboard.educatorAnalytics?.totalEnrollments ?? 0,
      activeEnrollments: roleDashboard.educatorAnalytics?.totalActiveEnrollments ?? 0,
      completedEnrollments: roleDashboard.educatorAnalytics?.totalCompletedEnrollments ?? 0,
      averageProgress:
        roleDashboard.educatorAnalytics && roleDashboard.educatorAnalytics.courses.length > 0
          ? roleDashboard.educatorAnalytics.courses.reduce(
              (total, course) => total + (course.avgProgressPercent ?? 0),
              0
            ) / roleDashboard.educatorAnalytics.courses.length
          : null,
    };
  }, [roleDashboard]);

  const adminDashboard = useMemo(() => {
    const managedCourses = roleDashboard.managedCourses;
    const users = roleDashboard.adminUsers;

    return {
      totalCourses: managedCourses.length,
      publishedCourses: managedCourses.filter((course) => normalizeStatus(course.status) === "published").length,
      draftCourses: managedCourses.filter((course) => normalizeStatus(course.status) === "draft").length,
      totalModules: managedCourses.reduce((total, course) => total + countCourseModules(course), 0),
      totalMaterials: managedCourses.reduce((total, course) => total + countCourseMaterials(course), 0),
      totalUsers: users.length,
      learners: users.filter((user) => user.identity === "Learner").length,
      educators: users.filter((user) => user.identity === "Educator").length,
      admins: users.filter((user) => user.identity === "Admin").length,
      inactiveUsers: users.filter((user) => user.accountStatus !== "active").length,
      aiPromptCalls: roleDashboard.aiTelemetry?.promptCalls.total ?? 0,
      aiPromptFailures:
        (roleDashboard.aiTelemetry?.promptCalls.failed ?? 0) +
        (roleDashboard.aiTelemetry?.promptCalls.timeout ?? 0),
      aiRetrievals: roleDashboard.aiTelemetry?.retrievals.total ?? 0,
      aiIndexFailures: roleDashboard.aiTelemetry?.indexJobs.failed ?? 0,
      aiIndexRunning:
        (roleDashboard.aiTelemetry?.indexJobs.running ?? 0) +
        (roleDashboard.aiTelemetry?.indexJobs.queued ?? 0) +
        (roleDashboard.aiTelemetry?.indexJobs.blocked ?? 0),
    };
  }, [roleDashboard]);

  const adminTrendSummary = useMemo(() => {
    const trends = roleDashboard.aiTrends;
    const recent = trends.slice(-7);
    const previous = trends.slice(Math.max(0, trends.length - 14), Math.max(0, trends.length - 7));
    const recentPromptCalls = sumTrend(recent, (point) => point.promptCalls);
    const previousPromptCalls = sumTrend(previous, (point) => point.promptCalls);
    const recentRetrievals = sumTrend(recent, (point) => point.retrievals);
    const recentIndexFailures = sumTrend(recent, (point) => point.indexFailures);
    const recentFailures = sumTrend(
      recent,
      (point) => point.promptFailures + point.promptTimeouts + point.embeddingFailures + point.indexFailures
    );
    const recentEvents = sumTrend(
      recent,
      (point) => point.promptCalls + point.embeddingCalls + point.indexJobs
    );
    const failureRate = recentEvents > 0 ? (recentFailures / recentEvents) * 100 : null;
    const recentDays = trends.slice(-5);
    const maxDailyActivity = Math.max(
      1,
      ...recentDays.map((point) => point.promptCalls + point.retrievals + point.embeddingCalls + point.indexJobs)
    );

    return {
      recentPromptCalls,
      recentPromptDelta: formatTrendDelta(recentPromptCalls, previousPromptCalls),
      recentRetrievals,
      recentFailures,
      recentIndexFailures,
      failureRate,
      recentDays,
      maxDailyActivity,
    };
  }, [roleDashboard.aiTrends]);

  const aiRuntimeStatus = roleDashboard.aiHealth?.configured ? "已配置" : "需要配置";
  const aiRuntimeDetail = roleDashboard.aiHealth
    ? `${roleDashboard.aiHealth.provider} / ${roleDashboard.aiHealth.model}`
    : roleDashboard.aiHealthError ?? "智能服务健康状态不可用。";
  const roleCourseQueue = roleDashboard.managedCourses.slice(0, 4);
  const teachingInsights = roleDashboard.teachingInsights?.items ?? [];
  const teachingInsightCount = roleDashboard.teachingInsights?.totalInsights ?? teachingInsights.length;
  const materialBriefs = roleDashboard.materialBriefs?.items ?? [];
  const materialBriefCount = roleDashboard.materialBriefs?.totalBriefs ?? materialBriefs.length;
  const providerConfigItems = roleDashboard.aiProviderConfig?.items ?? [];
  const providerConfigIssues = providerConfigItems.filter((item) => item.status !== "ready");
  const providerConfigStatus = roleDashboard.aiProviderConfig?.overallStatus ?? "unknown";
  const providerConfigDetail = roleDashboard.aiProviderConfig
    ? `${roleDashboard.aiProviderConfig.provider} / ${roleDashboard.aiProviderConfig.model}`
    : "尚未加载";
  const providerHealth = roleDashboard.aiProviderHealth;
  const providerHealthItems = providerHealth?.items ?? [];
  const providerHealthAnomalies = providerHealth?.anomalies ?? [];
  const providerHealthStatus = providerHealth?.overallStatus ?? "unknown";
  const aiAnomalies = roleDashboard.aiAnomalies;
  const governanceMetrics = roleDashboard.aiGovernance?.metrics ?? [];
  const governanceAlerts = roleDashboard.aiGovernance?.alerts ?? [];
  const governanceStatus = roleDashboard.aiGovernance?.overallStatus ?? "unknown";
  const modelCatalog = roleDashboard.aiModelCatalog;
  const availableDefaultModelOptions =
    modelCatalog?.providers.flatMap((provider) =>
      provider.models
        .filter((model) => model.available && model.capabilities.includes("chat"))
        .map((model) => ({
          provider: provider.provider,
          providerLabel: provider.label,
          modelId: model.modelId,
          name: model.name,
          isDefault: model.isDefault || model.modelId === modelCatalog.defaultModelId,
          pairedEmbeddingModelId: model.pairedEmbeddingModelId,
          pairedEmbeddingModelName: model.pairedEmbeddingModelName,
        }))
    ) ?? [];
  const selectedDefaultModel =
    modelCatalog?.providers
      .flatMap((provider) => provider.models)
      .find((model) => model.modelId === selectedDefaultModelId) ?? null;
  const credentialByProvider = new Map(roleDashboard.aiProviderCredentials.map((item) => [item.provider, item]));
  const providerCredentialEntries =
    modelCatalog?.providers.map((provider) => {
      const credential = credentialByProvider.get(provider.provider) ?? null;
      return {
        provider: provider.provider,
        label: credential?.label || provider.label,
        backendSupported: provider.backendSupported || Boolean(credential?.backendSupported),
        configured: provider.configured,
        models: provider.models,
        credential,
      };
    }) ??
    roleDashboard.aiProviderCredentials.map((credential) => ({
      provider: credential.provider,
      label: credential.label || credential.provider,
      backendSupported: credential.backendSupported,
      configured: credential.configured,
      models: [],
      credential,
    }));

  function getSessionContextLabel(session: ChatSessionSummary) {
    const courseLabel = session.course_uuid
      ? courseTitleMap.get(session.course_uuid) ?? "未知课程"
      : "未知课程";
    const moduleLabel = session.course_uuid && session.module_uuid
      ? courses
          .find((course) => course.courseUuid === session.course_uuid)
          ?.modules.find((module) => module.moduleUuid === session.module_uuid)?.title
      : null;
    return moduleLabel ? `${courseLabel} · ${moduleLabel}` : courseLabel;
  }

  function handleStartNewConversation() {
    setActiveSession(null);
    setDetailErrorMessage(null);
    setDetailLoading(false);
    setLearnerQuestion("");
    setLearnerQuestionStatus("选择课程模块后即可提问。");
  }

  function handleOpenSession(sessionUuid: string) {
    if (activeSession?.session.session_uuid === sessionUuid || detailLoading) {
      return;
    }

    setActiveSession(null);
    setDetailLoading(true);
    setDetailErrorMessage(null);
    setLearnerQuestionStatus("正在加载历史会话...");

    void getChatSessionDetail(sessionUuid)
      .then((detail) => {
        setActiveSession(detail);
        if (detail.session.course_uuid) {
          setSelectedLearnerCourseUuid(detail.session.course_uuid);
        }
        if (detail.session.module_uuid) {
          setSelectedLearnerModuleUuid(detail.session.module_uuid);
        }
        setLearnerQuestionStatus("可以继续提问。");
      })
      .catch((error) => {
        setDetailErrorMessage(
          error instanceof Error ? error.message : "所选会话加载失败。"
        );
      })
      .finally(() => {
        setDetailLoading(false);
      });
  }

  async function handleLearnerQuestionSubmit() {
    const message = learnerQuestion.trim();
    const requestCourseUuid = activeSession?.session.course_uuid ?? effectiveSelectedLearnerCourseUuid;
    const requestModuleUuid = activeSession?.session.module_uuid ?? effectiveSelectedLearnerModuleUuid;
    const continuingSessionUuid = activeSession?.session.session_uuid ?? null;
    if (
      !message ||
      !requestCourseUuid ||
      !requestModuleUuid ||
      !selectedLearnerModelId ||
      learnerQuestionSending
    ) {
      return;
    }

    setLearnerQuestion("");
    setLearnerQuestionSending(true);
    setLearnerQuestionStatus(continuingSessionUuid ? "正在继续当前会话..." : "正在创建新会话...");

    try {
      const response = await sendChatMessage({
        courseUuid: requestCourseUuid,
        moduleUuid: requestModuleUuid,
        message,
        sessionUuid: continuingSessionUuid,
        modelId: selectedLearnerModelId,
      });
      if (continuingSessionUuid && response.session_uuid !== continuingSessionUuid) {
        throw new Error("服务器未继续当前历史会话，请重试。 ");
      }
      const [detail, updatedSessions] = await Promise.all([
        getChatSessionDetail(response.session_uuid),
        listChatSessions(),
      ]);
      setActiveSession(detail);
      setSessions(updatedSessions);
      setDetailErrorMessage(null);
      setLearnerQuestionStatus("助手已回复。");
    } catch (error) {
      setLearnerQuestion(message);
      setLearnerQuestionStatus(error instanceof Error ? error.message : "消息发送失败。");
    } finally {
      setLearnerQuestionSending(false);
    }
  }

  function formatTelemetryKind(value: string) {
    const labels: Record<string, string> = {
      ready: "正常",
      warning: "警告",
      blocked: "阻塞",
      failed: "失败",
      quota: "额度受限",
      unknown: "未知",
      not_configured: "未配置",
      provider_adapter: "供应商适配器",
      multi_provider: "多供应商",
      gemini: "Gemini",
      glm: "GLM",
      openrouter: "OpenRouter",
    };
    if (labels[value]) {
      return labels[value];
    }
    return value
      .split("_")
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  }

  function getTeachingInsightPath(insight: TeachingInsightItem) {
    if (!insight.courseUuid) {
      return "/home/ai";
    }
    if (insight.moduleUuid) {
      return `/course/${insight.courseUuid}/management/modules/${insight.moduleUuid}`;
    }
    return `/course/${insight.courseUuid}/management`;
  }

  function getMaterialBriefPath(brief: EducatorMaterialBriefItem) {
    return `/course/${brief.courseUuid}/management/modules/${brief.moduleUuid}`;
  }

  function updateFailureFilter<K extends keyof AdminAiTelemetryFailureFilters>(
    field: K,
    value: AdminAiTelemetryFailureFilters[K]
  ) {
    setFailureFilters((current) => ({ ...current, [field]: value }));
  }

  function handleFailureFilterSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void loadFailureAudit();
  }

  function handleFailureFilterReset() {
    setFailureFilters(DEFAULT_ADMIN_FAILURE_FILTERS);
    void loadFailureAudit(DEFAULT_ADMIN_FAILURE_FILTERS);
  }

  async function handleRetryIndexJob(jobId: number) {
    if (currentUser.identity !== "Admin" || retryingIndexJobId !== null) return;
    setRetryingIndexJobId(jobId);
    setFailureAuditError(null);
    setFailureAuditNotice(null);
    try {
      const response = await retryAdminAiIndexJob(jobId);
      await loadFailureAudit();
      setFailureAuditNotice(
        response.dispatched
          ? `索引任务 #${response.jobId} 已重新入队。`
          : `索引任务 #${response.jobId} 已更新为 ${response.status}。`
      );
    } catch (error) {
      setFailureAuditError(error instanceof Error ? error.message : "重试索引任务失败。");
    } finally {
      setRetryingIndexJobId(null);
    }
  }

  function updateCredentialDraft(provider: string, value: string) {
    setCredentialDrafts((current) => ({ ...current, [provider]: value }));
  }

  async function refreshProviderConfiguration() {
    const [credentialsResponse, catalog] = await Promise.all([
      listAdminAiProviderCredentials(""),
      getAiModelCatalog(),
    ]);
    setRoleDashboard((current) => ({
      ...current,
      aiProviderCredentials: credentialsResponse.credentials,
      aiModelCatalog: catalog,
    }));
    const availableModels = catalog.providers.flatMap((provider) =>
      provider.models.filter((model) => model.available && model.capabilities.includes("chat"))
    );
    setSelectedDefaultModelId((current) =>
      availableModels.some((model) => model.modelId === current)
        ? current
        : catalog.defaultModelId ??
          availableModels.find((model) => model.isDefault)?.modelId ??
          availableModels[0]?.modelId ??
          ""
    );
  }

  async function handleSaveProviderCredential(provider: string) {
    if (currentUser.identity !== "Admin" || credentialActionProvider) return;
    const apiKey = credentialDrafts[provider]?.trim() ?? "";
    if (!apiKey) {
      setCredentialActionError("请输入供应商 API 密钥后再保存。");
      return;
    }

    setCredentialActionProvider(provider);
    setCredentialActionError(null);
    setCredentialActionNotice(null);
    try {
      const credential = await saveAdminAiProviderCredential("", {
        provider,
        apiKey,
        defaultModelId: selectedDefaultModelId || null,
      });
      setCredentialDrafts((current) => ({ ...current, [provider]: "" }));
      await refreshProviderConfiguration();
      setCredentialActionNotice(`${credential.label || credential.provider} 密钥已保存。`);
    } catch (error) {
      setCredentialActionError(error instanceof Error ? error.message : "保存供应商密钥失败。");
    } finally {
      setCredentialActionProvider(null);
    }
  }

  async function handleDeleteProviderCredential(provider: string) {
    if (currentUser.identity !== "Admin" || credentialActionProvider) return;
    setCredentialActionProvider(provider);
    setCredentialActionError(null);
    setCredentialActionNotice(null);
    try {
      await deleteAdminAiProviderCredential("", provider);
      await refreshProviderConfiguration();
      setCredentialActionNotice(`${formatTelemetryKind(provider)} 密钥已删除。`);
    } catch (error) {
      setCredentialActionError(error instanceof Error ? error.message : "删除供应商密钥失败。");
    } finally {
      setCredentialActionProvider(null);
    }
  }

  async function handleProviderHealthCheck(provider: string) {
    if (currentUser.identity !== "Admin" || credentialActionProvider) return;
    setCredentialActionProvider(provider);
    setCredentialActionError(null);
    setCredentialActionNotice(null);
    try {
      const result = await checkAdminAiProviderCredentialHealth("", provider);
      await refreshProviderConfiguration();
      setCredentialActionNotice(
        `${formatTelemetryKind(provider)} 健康检查：${formatTelemetryKind(result.status)}${
          result.message ? ` · ${result.message}` : ""
        }`
      );
    } catch (error) {
      setCredentialActionError(error instanceof Error ? error.message : "供应商健康检查失败。");
    } finally {
      setCredentialActionProvider(null);
    }
  }

  async function handleSetDefaultModel() {
    if (currentUser.identity !== "Admin" || credentialActionProvider || !selectedDefaultModelId) return;
    setCredentialActionProvider("default-model");
    setCredentialActionError(null);
    setCredentialActionNotice(null);
    try {
      const response = await setAdminAiDefaultModel("", { modelId: selectedDefaultModelId });
      await refreshProviderConfiguration();
      setCredentialActionNotice(`默认模型已设置为 ${response.modelId}。`);
    } catch (error) {
      setCredentialActionError(error instanceof Error ? error.message : "设置默认模型失败。");
    } finally {
      setCredentialActionProvider(null);
    }
  }

  async function handleFailureAuditExport() {
    if (currentUser.identity !== "Admin") return;
    setFailureAuditExporting(true);
    setFailureAuditError(null);
    setFailureAuditNotice(null);
    try {
      const blob = await exportAdminAiTelemetryFailures(failureFilters);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `ai-failure-audit-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      setFailureAuditError(error instanceof Error ? error.message : "智能服务失败审计导出失败。");
    } finally {
      setFailureAuditExporting(false);
    }
  }

  if (!isLearner) {
    const isEducator = currentUser.identity === "Educator";
    const metrics = isEducator
      ? [
          { label: "课程", value: formatNumber(educatorDashboard.totalCourses), detail: `${educatorDashboard.publishedCourses} 门已发布` },
          { label: "模块", value: formatNumber(educatorDashboard.totalModules), detail: `${educatorDashboard.totalMaterials} 份资料` },
          { label: "测验信号", value: formatNumber(educatorDashboard.quizModules), detail: "已发布或已追踪模块" },
          { label: "活跃学生", value: formatNumber(educatorDashboard.activeEnrollments), detail: `平均进度 ${formatPercent(educatorDashboard.averageProgress)}` },
        ]
      : [
          { label: "课程", value: formatNumber(adminDashboard.totalCourses), detail: `${adminDashboard.publishedCourses} 门已发布` },
          { label: "模块", value: formatNumber(adminDashboard.totalModules), detail: `${adminDashboard.totalMaterials} 份待索引资料` },
          { label: "智能服务调用", value: formatNumber(adminDashboard.aiPromptCalls), detail: `${adminDashboard.aiPromptFailures} 次失败或超时` },
          { label: "检索", value: formatNumber(adminDashboard.aiRetrievals), detail: `${adminDashboard.aiIndexRunning} 个索引任务活跃` },
        ];

    return (
      <section className="home-ai-page">
        <div className="home-ai-hero">
          <span className="home-content-badge">{workspaceCopy.badge}</span>
          <h1>{workspaceCopy.title}</h1>
          <p>{workspaceCopy.body}</p>
        </div>

        {roleDashboardError ? <p className="home-progress-alert">{roleDashboardError}</p> : null}

        {isEducator ? (
          <HomeAiConversationPanel
            title="教师智能对话"
            sessionCountLabel={loading ? "加载中..." : `${sessions.length} 个会话`}
            sessions={sessions}
            sessionsLoading={loading}
            sessionsError={errorMessage}
            activeSession={activeSession}
            detailLoading={detailLoading}
            detailErrorMessage={detailErrorMessage}
            sessionContextLabel={getSessionContextLabel}
            activeSessionContextLabel={activeSession ? getSessionContextLabel(activeSession.session) : ""}
            courses={learnerCoursesWithModules.map((course) => ({
              value: course.courseUuid,
              label: course.title,
            }))}
            modules={selectedLearnerModules.map((module) => ({
              value: module.moduleUuid,
              label: module.title,
            }))}
            models={learnerModelOptions}
            selectedCourseUuid={chatCourseUuid}
            selectedModuleUuid={chatModuleUuid}
            selectedModelId={selectedLearnerModelId}
            question={learnerQuestion}
            status={activeLearnerQuestionStatus}
            isSending={learnerQuestionSending || detailLoading}
            onCourseChange={(value) => {
              setSelectedLearnerCourseUuid(value);
              handleStartNewConversation();
            }}
            onModuleChange={(value) => {
              setSelectedLearnerModuleUuid(value);
              handleStartNewConversation();
            }}
            onModelChange={setSelectedLearnerModelId}
            onQuestionChange={setLearnerQuestion}
            onSubmit={() => void handleLearnerQuestionSubmit()}
            onOpenSession={handleOpenSession}
            onStartNewConversation={handleStartNewConversation}
          />
        ) : null}

        <div className="home-ai-grid">
          <article className="home-ai-panel">
            <div className="home-ai-panel-heading">
              <h2>{workspaceCopy.primaryTitle}</h2>
              <span>{roleDashboardLoading ? "加载中..." : "Live"}</span>
            </div>

            <div className="home-ai-metric-list">
              {metrics.map((metric) => (
                <div key={metric.label} className="home-ai-metric-row">
                  <span>{metric.label}</span>
                  <strong>{metric.value}</strong>
                  <small>{metric.detail}</small>
                </div>
              ))}
            </div>

            <div className="home-ai-worklist">
              <div className="home-ai-worklist-heading">
                <h3>{isEducator ? "Teaching Queue" : "Governance Queue"}</h3>
                <span>{roleCourseQueue.length}已显示</span>
              </div>

              {roleDashboardLoading ? <p className="home-ai-muted">正在加载工作区信号...</p> : null}
              {!roleDashboardLoading && roleCourseQueue.length === 0 ? (
                <p className="home-ai-muted">
                  {isEducator ? "No managed courses found." : "No courses found for governance review."}
                </p>
              ) : null}

              {roleCourseQueue.map((course) => (
                <Link
                  key={course.courseUuid}
                  to={isEducator ? `/course/${course.courseUuid}/management` : "/home/course-management"}
                  className="home-ai-worklist-row"
                >
                  <span>
                    <strong>{course.title}</strong>
                    <small>{course.status ?? "状态未知"} · {countCourseModules(course)} 个模块</small>
                  </span>
                  <em>
                    {isEducator
                      ? `${countCoursePublishedQuizzes(course)} 个测验模块`
                      : course.educatorName || "未分配教师"}
                  </em>
                </Link>
              ))}
            </div>
          </article>

          <article className="home-ai-panel">
            <div className="home-ai-panel-heading">
              <h2>{workspaceCopy.secondaryTitle}</h2>
              <span className={roleDashboard.aiHealth?.configured ? "home-ai-status-ok" : "home-ai-status-warn"}>
                {aiRuntimeStatus}
              </span>
            </div>

            <div className="home-ai-runtime">
              <span>服务提供方</span>
              <strong>{roleDashboard.aiHealth?.provider ?? "Gemini"}</strong>
              <p>{aiRuntimeDetail}</p>
            </div>

            <div className="home-ai-checklist">
              {(isEducator
                ? [
                    {
                      label: "课程上下文",
                      value: `${formatNumber(educatorDashboard.totalCourses)} 门管理课程`,
                    },
                    {
                      label: "学生信号",
                      value: `${formatNumber(educatorDashboard.totalEnrollments)} 个选课记录`,
                    },
                    {
                      label: "测验证据",
                      value: `${formatNumber(educatorDashboard.quizModules)} 个已追踪测验模块`,
                    },
                  ]
                : [
                    {
                      label: "角色覆盖",
                      value: `${adminDashboard.learners} 名学生 · ${adminDashboard.educators} 名教师`,
                    },
                    {
                      label: "服务配置",
                      value: `${formatTelemetryKind(providerConfigStatus)} · ${providerConfigDetail}`,
                    },
                    {
                      label: "服务健康",
                      value: `${formatTelemetryKind(providerHealthStatus)} · ${formatPercent(providerHealth?.successRatePercent)} 成功率`,
                    },
                    {
                      label: "异常洞察",
                      value: `${aiAnomalies.length} 条信号`,
                    },
                    {
                      label: "成本护栏",
                      value: `${formatTelemetryKind(governanceStatus)} · ${governanceAlerts.length} 条提醒`,
                    },
                    {
                      label: "索引失败",
                      value: `${adminDashboard.aiIndexFailures} failed jobs`,
                    },
                    {
                      label: "遥测安全",
                      value: "仅聚合指标",
                    },
                  ]).map((item) => (
                <div key={item.label} className="home-ai-checklist-row">
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                  </div>
              ))}
            </div>

            {isEducator ? (
              <div className="home-ai-audit-list">
                <div className="home-ai-worklist-heading">
                  <h3>教学洞察</h3>
                  <span>{teachingInsightCount}总计</span>
                </div>

                {roleDashboardLoading ? <p className="home-ai-muted">正在加载教学洞察...</p> : null}
                {!roleDashboardLoading && teachingInsights.length === 0 ? (
                  <p className="home-ai-muted">暂无需要关注的教学洞察。</p>
                ) : null}

                {teachingInsights.map((insight) => (
                  <Link
                    key={insight.insightId}
                    to={getTeachingInsightPath(insight)}
                    className="home-ai-worklist-row home-ai-insight-row"
                  >
                    <span>
                      <strong>{insight.title}</strong>
                      <small>
                        {formatTelemetryKind(insight.priority)} · {formatTelemetryKind(insight.category)}
                      </small>
                      <small>{insight.detail}</small>
                    </span>
                    <em>{insight.metricLabel && insight.metricValue ? `${insight.metricLabel}: ${insight.metricValue}` : insight.actionLabel}</em>
                  </Link>
                ))}
              </div>
            ) : null}

            {isEducator ? (
              <div className="home-ai-audit-list">
                <div className="home-ai-worklist-heading">
                  <h3>资料简报</h3>
                  <span>{materialBriefCount} 个模块</span>
                </div>

                {roleDashboardLoading ? <p className="home-ai-muted">正在加载资料简报...</p> : null}
                {!roleDashboardLoading && materialBriefs.length === 0 ? (
                  <p className="home-ai-muted">暂无可用资料简报。</p>
                ) : null}

                {materialBriefs.map((brief) => (
                  <Link
                    key={brief.briefId}
                    to={getMaterialBriefPath(brief)}
                    className="home-ai-worklist-row home-ai-insight-row"
                  >
                    <span>
                      <strong>{brief.moduleTitle}</strong>
                      <small>
                        {formatTelemetryKind(brief.priority)} · {brief.materialCount}份资料 · {brief.materialTypes.join(", ") || "no types"}
                      </small>
                      <small>{brief.summary}</small>
                      <small>{brief.difficultySignal}</small>
                    </span>
                    <em>{brief.recommendedAction}</em>
                  </Link>
                ))}
              </div>
            ) : null}

            {!isEducator ? (
              <div className="home-ai-config-summary">
                <div className="home-ai-worklist-heading">
                  <h3>服务配置</h3>
                  <span>{formatTelemetryKind(providerConfigStatus)}</span>
                </div>

                {roleDashboardLoading ? <p className="home-ai-muted">正在加载服务配置...</p> : null}
                {!roleDashboardLoading && providerConfigItems.length === 0 ? (
                  <p className="home-ai-muted">服务配置状态不可用。</p>
                ) : null}
                {!roleDashboardLoading && providerConfigItems.length > 0 && providerConfigIssues.length === 0 ? (
                  <div className="home-ai-config-row">
                    <span>
                      <strong>所有检查已就绪</strong>
                      <small>未发现配置警告或阻塞项。</small>
                    </span>
                    <em>{roleDashboard.aiProviderConfig?.storageProvider ?? "storage"}</em>
                  </div>
                ) : null}

                {providerConfigIssues.slice(0, 4).map((item) => (
                  <div key={item.key} className="home-ai-config-row">
                    <span>
                      <strong>{item.label}</strong>
                      <small>
                        {formatTelemetryKind(item.status)} · {item.detail}
                      </small>
                      {item.recommendation ? <small>{item.recommendation}</small> : null}
                    </span>
                    <em>{formatTelemetryKind(item.status)}</em>
                  </div>
                ))}
              </div>
            ) : null}

            {!isEducator ? (
              <div className="home-ai-config-summary">
                <div className="home-ai-worklist-heading">
                  <h3>供应商密钥管理</h3>
                  <span>{providerCredentialEntries.length} 个供应商</span>
                </div>

                {roleDashboardLoading ? <p className="home-ai-muted">正在加载供应商密钥配置...</p> : null}
                {credentialActionError ? <p className="home-ai-muted">{credentialActionError}</p> : null}
                {credentialActionNotice ? <p className="home-ai-muted">{credentialActionNotice}</p> : null}

                {availableDefaultModelOptions.length > 0 ? (
                  <div className="home-ai-default-model-row">
                    <label>
                      <span>默认模型</span>
                      <select
                        value={selectedDefaultModelId}
                        onChange={(event) => setSelectedDefaultModelId(event.target.value)}
                        disabled={credentialActionProvider !== null}
                      >
                        {availableDefaultModelOptions.map((model) => (
                          <option key={model.modelId} value={model.modelId}>
                            {model.providerLabel}: {model.name}
                            {model.pairedEmbeddingModelName || model.pairedEmbeddingModelId
                              ? ` → ${
                                  model.pairedEmbeddingModelName || model.pairedEmbeddingModelId
                                }`
                              : ""}
                            {model.isDefault ? " (当前)" : ""}
                          </option>
                        ))}
                      </select>
                      <small
                        className={`home-ai-default-model-pair${
                          selectedDefaultModel?.ragReady === false
                            ? " home-ai-default-model-pair-warning"
                            : ""
                        }`}
                      >
                        配对向量：{formatEmbeddingPair(selectedDefaultModel)}
                      </small>
                    </label>
                    <button
                      type="button"
                      onClick={() => void handleSetDefaultModel()}
                      disabled={
                        credentialActionProvider !== null ||
                        !selectedDefaultModelId ||
                        selectedDefaultModelId === modelCatalog?.defaultModelId
                      }
                    >
                      保存默认
                    </button>
                  </div>
                ) : null}

                {!roleDashboardLoading && providerCredentialEntries.length === 0 ? (
                  <p className="home-ai-muted">模型目录暂不可用，供应商密钥配置入口无法展示。</p>
                ) : null}

                {providerCredentialEntries.map((entry) => {
                  const configured = entry.credential?.configured ?? entry.configured;
                  const actionBusy = credentialActionProvider === entry.provider;
                  const backendSupported = entry.backendSupported;
                  const availableModels = entry.models.filter((model) => model.available);
                  const unavailableModels = entry.models.filter((model) => !model.available);

                  return (
                    <div key={entry.provider} className="home-ai-provider-card">
                      <div className="home-ai-provider-card-header">
                        <span>
                          <strong>{entry.label || entry.provider}</strong>
                          <small>
                            {!backendSupported ? "本版本暂未接入" : configured ? "密钥已配置" : "缺少密钥"}
                            {entry.credential?.keyPreview ? ` · ${entry.credential.keyPreview}` : ""}
                          </small>
                          {entry.credential?.lastHealthStatus ? (
                            <small>健康状态：{formatTelemetryKind(entry.credential.lastHealthStatus)}</small>
                          ) : null}
                        </span>
                        <em>{formatTelemetryKind(entry.credential?.status ?? (configured ? "ready" : "blocked"))}</em>
                      </div>

                      <div className="home-ai-model-chip-list">
                        {availableModels.map((model) => (
                          <span key={model.modelId} className="home-ai-model-chip home-ai-model-chip-ready">
                            {model.name}
                          </span>
                        ))}
                        {unavailableModels.map((model) => (
                          <span key={model.modelId} className="home-ai-model-chip home-ai-model-chip-disabled">
                            {model.name}: {model.unavailableReason || "不可用"}
                          </span>
                        ))}
                      </div>

                      <div className="home-ai-provider-actions">
                        <input
                          type="password"
                          autoComplete="off"
                          value={credentialDrafts[entry.provider] ?? ""}
                          onChange={(event) => updateCredentialDraft(entry.provider, event.target.value)}
                          placeholder={
                            backendSupported
                              ? configured
                                ? "粘贴新密钥以替换"
                                : "粘贴供应商 API 密钥"
                              : "本版本暂不支持配置"
                          }
                          disabled={credentialActionProvider !== null || !backendSupported}
                        />
                        <button
                          type="button"
                          onClick={() => void handleSaveProviderCredential(entry.provider)}
                          disabled={
                            credentialActionProvider !== null ||
                            !backendSupported ||
                            !(credentialDrafts[entry.provider] ?? "").trim()
                          }
                        >
                          {actionBusy ? "保存中" : "保存"}
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleProviderHealthCheck(entry.provider)}
                          disabled={credentialActionProvider !== null || !backendSupported || !configured}
                        >
                          健康检查
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleDeleteProviderCredential(entry.provider)}
                          disabled={credentialActionProvider !== null || !configured}
                        >
                          删除
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : null}

            {!isEducator ? (
              <div className="home-ai-config-summary">
                <div className="home-ai-worklist-heading">
                  <h3>服务健康</h3>
                  <span>{formatTelemetryKind(providerHealthStatus)}</span>
                </div>

                {roleDashboardLoading ? <p className="home-ai-muted">正在加载服务健康状态...</p> : null}
                {!roleDashboardLoading && !providerHealth ? (
                  <p className="home-ai-muted">服务健康状态不可用。</p>
                ) : null}

                {providerHealth ? (
                  <div className="home-ai-config-row">
                    <span>
                      <strong>{formatPercent(providerHealth.successRatePercent)}成功</strong>
                      <small>
                        {formatCompactNumber(providerHealth.totalCalls)}次调用，周期 {providerHealth.days}天 ·{" "}
                        {formatLatency(providerHealth.averageLatencyMs)}平均延迟
                      </small>
                    </span>
                    <em>{formatTelemetryKind(providerHealth.overallStatus)}</em>
                  </div>
                ) : null}

                {providerHealthAnomalies.slice(0, 3).map((anomaly) => (
                  <div key={anomaly.key} className="home-ai-config-row">
                    <span>
                      <strong>{anomaly.title}</strong>
                      <small>{anomaly.detail}</small>
                      <small>{anomaly.recommendation}</small>
                    </span>
                    <em>{formatTelemetryKind(anomaly.severity)}</em>
                  </div>
                ))}

                {providerHealthItems.slice(0, 3).map((item) => (
                  <div key={item.key} className="home-ai-config-row">
                    <span>
                      <strong>
                        {item.modelName} · {formatTelemetryKind(item.callType)}
                      </strong>
                      <small>
                        {formatPercent(item.successRatePercent)}成功 · {formatCompactNumber(item.totalCalls)}次调用 ·{" "}
                        {formatLatency(item.averageLatencyMs)}
                      </small>
                      {item.recommendation ? <small>{item.recommendation}</small> : null}
                    </span>
                    <em>{formatTelemetryKind(item.status)}</em>
                  </div>
                ))}
              </div>
            ) : null}

            {!isEducator ? (
              <div className="home-ai-config-summary">
                <div className="home-ai-worklist-heading">
                  <h3>异常洞察</h3>
                  <span>{aiAnomalies.length}信号</span>
                </div>

                {roleDashboardLoading ? <p className="home-ai-muted">正在加载异常洞察...</p> : null}
                {!roleDashboardLoading && aiAnomalies.length === 0 ? (
                  <div className="home-ai-config-row">
                    <span>
                      <strong>未检测到趋势异常</strong>
                      <small>失败率、延迟、检索、索引和令牌使用量均在近期基线范围内。</small>
                    </span>
                    <em>正常</em>
                  </div>
                ) : null}

                {aiAnomalies.slice(0, 4).map((insight) => (
                  <div key={insight.key} className="home-ai-config-row">
                    <span>
                      <strong>{insight.title}</strong>
                      <small>
                        {insight.metricLabel}: {insight.currentValue}
                        {insight.baselineValue ? ` · baseline ${insight.baselineValue}` : ""}
                      </small>
                      <small>{insight.detail}</small>
                      <small>{insight.recommendation}</small>
                    </span>
                    <em>{formatTelemetryKind(insight.severity)}</em>
                  </div>
                ))}
              </div>
            ) : null}

            {!isEducator ? (
              <div className="home-ai-config-summary">
                <div className="home-ai-worklist-heading">
                  <h3>成本与告警</h3>
                  <span>{formatTelemetryKind(governanceStatus)}</span>
                </div>

                {roleDashboardLoading ? <p className="home-ai-muted">正在加载治理护栏...</p> : null}
                {!roleDashboardLoading && governanceMetrics.length === 0 ? (
                  <p className="home-ai-muted">智能治理摘要不可用。</p>
                ) : null}

                {governanceMetrics.slice(0, 4).map((metric) => (
                  <div key={metric.key} className="home-ai-config-row">
                    <span>
                      <strong>{metric.label}</strong>
                      <small>{metric.detail}</small>
                    </span>
                    <em>{metric.value}</em>
                  </div>
                ))}

                {!roleDashboardLoading && governanceAlerts.length === 0 && governanceMetrics.length > 0 ? (
                  <div className="home-ai-config-row">
                    <span>
                      <strong>暂无活跃治理告警</strong>
                      <small>成本、令牌、失败和索引护栏均在配置限制内。</small>
                    </span>
                    <em>正常</em>
                  </div>
                ) : null}

                {governanceAlerts.slice(0, 3).map((alert) => (
                  <div key={`${alert.severity}-${alert.title}`} className="home-ai-config-row">
                    <span>
                      <strong>{alert.title}</strong>
                      <small>{alert.detail}</small>
                      <small>{alert.recommendation}</small>
                    </span>
                    <em>{formatTelemetryKind(alert.severity)}</em>
                  </div>
                ))}
              </div>
            ) : null}

            {!isEducator ? (
              <div className="home-ai-trend-block">
                <div className="home-ai-worklist-heading">
                  <h3>14 天智能服务趋势</h3>
                  <span>{roleDashboard.aiTrends.length}天</span>
                </div>

                <div className="home-ai-trend-metrics">
                  <div>
                    <span>调用</span>
                    <strong>{formatCompactNumber(adminTrendSummary.recentPromptCalls)}</strong>
                    <small>{adminTrendSummary.recentPromptDelta}</small>
                  </div>
                  <div>
                    <span>失败率</span>
                    <strong>{formatPercent(adminTrendSummary.failureRate)}</strong>
                    <small>{formatCompactNumber(adminTrendSummary.recentFailures)}次失败</small>
                  </div>
                  <div>
                    <span>检索</span>
                    <strong>{formatCompactNumber(adminTrendSummary.recentRetrievals)}</strong>
                    <small>最近 7 天</small>
                  </div>
                  <div>
                    <span>索引失败</span>
                    <strong>{formatCompactNumber(adminTrendSummary.recentIndexFailures)}</strong>
                    <small>最近 7 天</small>
                  </div>
                </div>

                <div className="home-ai-trend-days" aria-label="近期智能服务每日活动">
                  {adminTrendSummary.recentDays.map((point) => {
                    const activity = point.promptCalls + point.retrievals + point.embeddingCalls + point.indexJobs;
                    const failures =
                      point.promptFailures + point.promptTimeouts + point.embeddingFailures + point.indexFailures;
                    const width = Math.max(6, Math.round((activity / adminTrendSummary.maxDailyActivity) * 100));
                    return (
                      <div key={point.date} className="home-ai-trend-day-row">
                        <span>{formatTrendDate(point.date)}</span>
                        <div>
                          <i style={{ width: `${width}%` }} />
                        </div>
                        <strong>
                          {formatCompactNumber(activity)}活动 · {formatCompactNumber(failures)}失败
                        </strong>
                      </div>
                    );
                  })}
                  {!roleDashboardLoading && adminTrendSummary.recentDays.length === 0 ? (
                    <p className="home-ai-muted">暂无智能服务趋势数据。</p>
                  ) : null}
                </div>
              </div>
            ) : null}

            {!isEducator ? (
              <div className="home-ai-audit-list">
                <div className="home-ai-worklist-heading">
                  <h3>失败审计</h3>
                  <span>{roleDashboard.aiFailures.length}近期</span>
                </div>

                <form className="home-ai-audit-filters" onSubmit={handleFailureFilterSubmit}>
                  <label>
                    <span>类型</span>
                    <select
                      value={failureFilters.kind}
                      onChange={(event) => updateFailureFilter("kind", event.target.value as AdminAiTelemetryFailureFilters["kind"])}
                    >
                      <option value="">全部</option>
                      <option value="prompt">提示词</option>
                      <option value="embedding">向量化</option>
                      <option value="index_job">索引任务</option>
                    </select>
                  </label>
                  <label>
                    <span>状态</span>
                    <select
                      value={failureFilters.status}
                      onChange={(event) => updateFailureFilter("status", event.target.value as AdminAiTelemetryFailureFilters["status"])}
                    >
                      <option value="">全部</option>
                      <option value="failed">失败</option>
                      <option value="timeout">超时</option>
                    </select>
                  </label>
                  <label>
                    <span>用户编号</span>
                    <input
                      inputMode="numeric"
                      value={failureFilters.userId}
                      onChange={(event) => updateFailureFilter("userId", event.target.value)}
                      placeholder="任意"
                    />
                  </label>
                  <label>
                    <span>课程编号</span>
                    <input
                      inputMode="numeric"
                      value={failureFilters.courseId}
                      onChange={(event) => updateFailureFilter("courseId", event.target.value)}
                      placeholder="任意"
                    />
                  </label>
                  <label>
                    <span>模块编号</span>
                    <input
                      inputMode="numeric"
                      value={failureFilters.moduleId}
                      onChange={(event) => updateFailureFilter("moduleId", event.target.value)}
                      placeholder="任意"
                    />
                  </label>
                  <label>
                    <span>开始时间</span>
                    <input
                      type="datetime-local"
                      value={failureFilters.since}
                      onChange={(event) => updateFailureFilter("since", event.target.value)}
                    />
                  </label>
                  <label>
                    <span>结束时间</span>
                    <input
                      type="datetime-local"
                      value={failureFilters.until}
                      onChange={(event) => updateFailureFilter("until", event.target.value)}
                    />
                  </label>
                  <div className="home-ai-audit-filter-actions">
                    <button type="submit" disabled={failureAuditLoading}>
                      <LuSearch size={15} aria-hidden="true" />
                      <span>{failureAuditLoading ? "Filtering" : "Apply"}</span>
                    </button>
                    <button type="button" onClick={handleFailureFilterReset} disabled={failureAuditLoading}>
                      <LuRefreshCw size={15} aria-hidden="true" />
                      <span>重置</span>
                    </button>
                    <button type="button" onClick={() => void handleFailureAuditExport()} disabled={failureAuditExporting}>
                      <LuDownload size={15} aria-hidden="true" />
                      <span>{failureAuditExporting ? "Exporting" : "CSV"}</span>
                    </button>
                  </div>
                </form>

                {roleDashboardLoading || failureAuditLoading ? <p className="home-ai-muted">正在加载失败审计...</p> : null}
                {failureAuditError ? <p className="home-ai-muted">{failureAuditError}</p> : null}
                {failureAuditNotice ? <p className="home-ai-muted">{failureAuditNotice}</p> : null}
                {!roleDashboardLoading && roleDashboard.aiFailures.length === 0 ? (
                  <p className="home-ai-muted">未发现近期智能服务失败记录。</p>
                ) : null}

                {roleDashboard.aiFailures.map((failure) => (
                  <div key={`${failure.kind}-${failure.id}`} className="home-ai-audit-row">
                    <span>
                      <strong>{formatTelemetryKind(failure.kind)}</strong>
                      <small>
                        {failure.status} · {formatSessionTimestamp(failure.occurredAt)}
                      </small>
                    </span>
                    <div className="home-ai-audit-row-side">
                      <em>{failure.errorSummary || failure.callType || `#${failure.id}`}</em>
                      {failure.kind === "index_job" && failure.status === "failed" ? (
                        <button
                          type="button"
                          onClick={() => void handleRetryIndexJob(failure.id)}
                          disabled={retryingIndexJobId !== null}
                          title="重新排队该资料索引任务"
                        >
                          <LuRefreshCw size={14} aria-hidden="true" />
                          <span>{retryingIndexJobId === failure.id ? "Retrying" : "重试"}</span>
                        </button>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
          </article>
        </div>
      </section>
    );
  }

  return (
    <section className="home-ai-page">
      <div className="home-ai-hero">
        <span className="home-content-badge">{workspaceCopy.badge}</span>
        <h1>{workspaceCopy.title}</h1>
        <p>{workspaceCopy.body}</p>
      </div>

      <div className="home-ai-grid">
        <HomeAiConversationPanel
          title="我的智能对话"
          sessionCountLabel={loading ? "加载中..." : `${sessions.length} 个会话`}
          sessions={sessions}
          sessionsLoading={loading}
          sessionsError={errorMessage}
          activeSession={activeSession}
          detailLoading={detailLoading}
          detailErrorMessage={detailErrorMessage}
          sessionContextLabel={getSessionContextLabel}
          activeSessionContextLabel={activeSession ? getSessionContextLabel(activeSession.session) : ""}
          courses={learnerCoursesWithModules.map((course) => ({
            value: course.courseUuid,
            label: course.title,
          }))}
          modules={selectedLearnerModules.map((module) => ({
            value: module.moduleUuid,
            label: module.title,
          }))}
          models={learnerModelOptions}
          selectedCourseUuid={chatCourseUuid}
          selectedModuleUuid={chatModuleUuid}
          selectedModelId={selectedLearnerModelId}
          question={learnerQuestion}
          status={activeLearnerQuestionStatus}
          isSending={learnerQuestionSending || detailLoading}
          onCourseChange={(value) => {
            setSelectedLearnerCourseUuid(value);
            handleStartNewConversation();
          }}
          onModuleChange={(value) => {
            setSelectedLearnerModuleUuid(value);
            handleStartNewConversation();
          }}
          onModelChange={setSelectedLearnerModelId}
          onQuestionChange={setLearnerQuestion}
          onSubmit={() => void handleLearnerQuestionSubmit()}
          onOpenSession={handleOpenSession}
          onStartNewConversation={handleStartNewConversation}
        />

        <article className="home-ai-panel">
          <div className="home-ai-panel-heading">
            <h2>{workspaceCopy.secondaryTitle}</h2>
            <span>课程上下文</span>
          </div>
          <div className="home-ai-checklist">
            <div className="home-ai-checklist-row">
              <span>聊天范围</span>
              <strong>{sessions.length}已保存会话</strong>
            </div>
            <div className="home-ai-checklist-row">
              <span>课程地图</span>
              <strong>{courses.length}已加入课程</strong>
            </div>
            {coursesErrorMessage ? <p className="home-ai-muted">{coursesErrorMessage}</p> : null}
            <Link to="/home/ai/profile-init" className="home-ai-worklist-row">
              <span>
                <strong>学生画像</strong>
                <small>初始化或更新技能偏好</small>
              </span>
              <em>打开</em>
            </Link>
            {!coursesErrorMessage && learnerAiModuleEntries.length === 0 ? (
              <Link to="/home/my-courses" className="home-ai-worklist-row">
                <span>
                  <strong>暂无已解锁模块</strong>
                  <small>从已加入课程继续</small>
                </span>
                <em>课程</em>
              </Link>
            ) : null}
            {learnerAiModuleEntries.map(({ course, module }) => (
              <Link
                key={`${course.courseUuid}-${module.moduleUuid}`}
                to={getLearnerAiModulePath(course.courseUuid, module.moduleUuid)}
                className="home-ai-worklist-row"
              >
                <span>
                  <strong>{module.title}</strong>
                  <small>{course.title}</small>
                </span>
                <em>助手</em>
              </Link>
            ))}
          </div>
        </article>
      </div>
    </section>
  );
}

export default HomeAiPage;
