import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, Navigate, NavLink, Outlet, useLocation, useNavigate, useParams } from "react-router-dom";
import type { CSSProperties, MouseEvent as ReactMouseEvent } from "react";
import { LuBot, LuChevronDown, LuChevronUp, LuLock, LuMenu, LuX } from "react-icons/lu";

import HomeNotificationsMenu from "../../components/home/HomeNotificationsMenu";
import { getStoredCurrentUser } from "../../services/api";
import {
  dropMyEnrollment,
  enrollInCourse,
  getCourseByUuid,
  getManagedCourseByUuid,
  getManagedCourses,
  getMyEnrolledCourses,
  getMyEnrolledCourseUuids,
} from "../../services/course";
import type { CourseRecord } from "../../types/course";
import { emitAppRefresh, subscribeAppRefresh } from "../../utils/refreshEvents";
import CourseChatSidebar from "./CourseChatSidebar";
import "./CoursePages.css";

export type CourseOutletContext = {
  course: CourseRecord;
  forumCourses: CourseRecord[];
  forumCoursesLoading: boolean;
  forumCoursesError: string | null;
  isChatOpen: boolean;
  setQuizGuard: (active: boolean, submitFn?: () => Promise<void>) => void;
  markModuleCompleted: (moduleUuid: string) => void;
  refreshCourse: () => Promise<void>;
};

type PendingEnrollmentAction = "enroll" | "cancel";

function getEnrollmentActionErrorMessage(error: unknown, action: PendingEnrollmentAction) {
  const fallback =
    action === "cancel"
      ? "无法取消报名，请稍后重试。"
      : "无法加入该课程，请稍后重试。";

  if (!(error instanceof Error)) {
    return fallback;
  }

  const message = error.message.trim();
  if (!message) {
    return fallback;
  }

  if (message.toLowerCase().includes("private")) {
    return "这门课程为私有课程，请向教师索要邀请链接。";
  }

  if (message.toLowerCase().includes("published")) {
    return "这门课程尚未开放报名。";
  }

  if (message.toLowerCase().includes("already")) {
    return "你的报名状态已经变化，刷新课程后可查看最新状态。";
  }

  return message;
}

function getCourseLoadErrorMessage(error: unknown) {
  if (!(error instanceof Error) || !error.message.trim()) {
    return "无法加载这门课程，请从课程列表重试。";
  }

  return error.message;
}

function CourseLayout() {
  const { courseUuid, moduleUuid, materialUuid } = useParams();
  const location = useLocation();
  const [course, setCourse] = useState<CourseRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [chatWidth, setChatWidth] = useState(380);
  const [isResizingChat, setIsResizingChat] = useState(false);
  const currentUser = useMemo(() => getStoredCurrentUser(), []);
  const isLearner = currentUser?.identity === "Learner";
  const canUseNotifications =
    currentUser?.identity === "Learner" ||
    currentUser?.identity === "Educator" ||
    currentUser?.identity === "Admin";
  const [forumCourses, setForumCourses] = useState<CourseRecord[]>([]);
  const [forumCoursesLoading, setForumCoursesLoading] = useState(false);
  const [forumCoursesError, setForumCoursesError] = useState<string | null>(null);
  const [isEnrolled, setIsEnrolled] = useState(false);
  const [isEnrolling, setIsEnrolling] = useState(false);
  const [pendingEnrollmentAction, setPendingEnrollmentAction] = useState<PendingEnrollmentAction | null>(null);
  const [enrollmentActionError, setEnrollmentActionError] = useState("");
  const [quizGuardActive, setQuizGuardActive] = useState(false);
  const [pendingNavTarget, setPendingNavTarget] = useState<string | null>(null);
  const [isQuizLeaving, setIsQuizLeaving] = useState(false);
  const [expandedModuleUuids, setExpandedModuleUuids] = useState<string[]>([]);
  const [completedModuleUuids, setCompletedModuleUuids] = useState<string[]>([]);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const quizSubmitRef = useRef<(() => Promise<void>) | null>(null);
  const allowNextPopstateRef = useRef(false);
  const quizPageUrlRef = useRef('');
  const openChatConsumedRef = useRef<string | null>(null);
  const quizLeaveTriggerRef = useRef<HTMLElement | null>(null);
  const enrollmentActionTriggerRef = useRef<HTMLElement | null>(null);
  const navigate = useNavigate();
  const restoreFocus = useCallback((target: HTMLElement | null) => {
    if (!target?.isConnected) {
      return;
    }

    window.setTimeout(() => target.focus(), 0);
  }, []);

  const closeQuizLeaveModal = useCallback(() => {
    if (isQuizLeaving) {
      return;
    }

    setPendingNavTarget(null);
    const trigger = quizLeaveTriggerRef.current;
    quizLeaveTriggerRef.current = null;
    restoreFocus(trigger);
  }, [isQuizLeaving, restoreFocus]);

  const closeEnrollmentActionModal = useCallback(() => {
    if (isEnrolling) {
      return;
    }

    setPendingEnrollmentAction(null);
    setEnrollmentActionError("");
    const trigger = enrollmentActionTriggerRef.current;
    enrollmentActionTriggerRef.current = null;
    restoreFocus(trigger);
  }, [isEnrolling, restoreFocus]);

  const handleSidebarNavigation = (
    event: ReactMouseEvent<HTMLElement>,
    target: string
  ) => {
    if (quizGuardActive) {
      event.preventDefault();
      quizLeaveTriggerRef.current = event.currentTarget;
      setPendingNavTarget(target);
      return;
    }

    setIsMobileSidebarOpen(false);
  };

  const setQuizGuard = (active: boolean, submitFn?: () => Promise<void>) => {
    setQuizGuardActive(active);
    quizSubmitRef.current = submitFn ?? null;
  };

  // Intercept browser back/forward while quiz is active
  useEffect(() => {
    if (!quizGuardActive) return;
    quizPageUrlRef.current = window.location.href;

    // Push a sentinel entry with the SAME URL so pressing back stays
    // on the quiz page URL (React Router won't re-render for same URL)
    window.history.pushState({ quizSentinel: true }, '', quizPageUrlRef.current);

    const handlePopState = () => {
      if (allowNextPopstateRef.current) {
        allowNextPopstateRef.current = false;
        return;
      }
      // Re-push sentinel so repeated back presses are blocked
      window.history.pushState({ quizSentinel: true }, '', quizPageUrlRef.current);
      setPendingNavTarget('__back__');
    };

    // Capture phase: runs before React Router's bubble-phase listener
    window.addEventListener('popstate', handlePopState, { capture: true });
    return () => window.removeEventListener('popstate', handlePopState, { capture: true });
  }, [quizGuardActive]);

  const handleQuizLeaveConfirm = async () => {
    setIsQuizLeaving(true);
    try {
      if (quizSubmitRef.current) await quizSubmitRef.current();
    } catch { /* ignore */ }
    setIsQuizLeaving(false);
    setQuizGuardActive(false);
    quizSubmitRef.current = null;
    const target = pendingNavTarget;
    setPendingNavTarget(null);
    if (target === '__back__') {
      allowNextPopstateRef.current = true;
      window.history.go(-2); // undo our pushState + actually go back
    } else if (target) {
      navigate(target);
    }
  };
  const source = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return params.get("from");
  }, [location.search]);
  const shouldOpenChatFromQuery = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return params.get("openChat") === "1";
  }, [location.search]);
  const isForumRoute = useMemo(() => {
    if (!courseUuid) {
      return false;
    }
    return location.pathname.startsWith(`/course/${courseUuid}/forum`);
  }, [courseUuid, location.pathname]);
  const isMyCoursesSource = source === "my-courses";
  const isManagedCourseSource = source === "managed-courses" || source === "course-management";
  const canAccessForum = isMyCoursesSource || isManagedCourseSource;
  const shouldShowLearnerQuizLinks = !isLearner || source !== "course-center";
  const shouldShowLearnerProgress = !isLearner || source !== "course-center";
  const courseSearchSuffix =
    source === "my-courses"
      ? "?from=my-courses"
      : source === "managed-courses"
        ? "?from=managed-courses"
        : source === "course-management"
          ? "?from=course-management"
          : source === "course-center"
            ? "?from=course-center"
        : "";
  const backLink =
    source === "my-courses"
      ? "/home/my-courses"
      : source === "managed-courses"
        ? "/home/managed-courses"
        : "/home/course-center";
  const backLabel =
    source === "my-courses"
      ? "返回我的课程"
      : source === "managed-courses"
        ? "返回管理课程"
        : "返回课程大厅";

  const refreshCourse = useCallback(async () => {
    if (!courseUuid) {
      return;
    }

    try {
      const shouldLoadManagedCourse =
        currentUser?.identity !== "Learner" && isManagedCourseSource;
      const data = shouldLoadManagedCourse
        ? await getManagedCourseByUuid(courseUuid)
        : await getCourseByUuid(courseUuid);
      setCourse(data);
      setLoadError(null);
    } catch (error) {
      setCourse(null);
      setLoadError(getCourseLoadErrorMessage(error));
      throw error;
    }
  }, [courseUuid, currentUser?.identity, isManagedCourseSource]);

  useEffect(() => {
    let cancelled = false;

    const loadCourse = async () => {
      if (!courseUuid) {
        setLoading(false);
        return;
      }

      try {
        const shouldLoadManagedCourse =
          currentUser?.identity !== "Learner" && isManagedCourseSource;
        const data = shouldLoadManagedCourse
          ? await getManagedCourseByUuid(courseUuid)
          : await getCourseByUuid(courseUuid);
        if (!cancelled) {
          setCourse(data);
          setLoadError(null);
        }
      } catch (error) {
        if (!cancelled) {
          setCourse(null);
          setLoadError(getCourseLoadErrorMessage(error));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadCourse();

    return () => {
      cancelled = true;
    };
  }, [courseUuid, currentUser?.identity, isManagedCourseSource]);

  useEffect(() => {
    return subscribeAppRefresh(
      ["course:detail", "course:materials", "course:progress", "course:quiz"],
      (detail) => {
        if (!courseUuid || (detail.courseUuid && detail.courseUuid !== courseUuid)) {
          return;
        }
        void refreshCourse().catch(() => undefined);
      }
    );
  }, [courseUuid, refreshCourse]);

  useEffect(() => {
    setIsMobileSidebarOpen(false);
  }, [location.pathname, location.search]);

  useEffect(() => {
    if (!course) {
      setExpandedModuleUuids([]);
      return;
    }

    setExpandedModuleUuids((current) => {
      if (current.length > 0) {
        return current;
      }
      return course.modules.map((module) => module.moduleUuid);
    });
  }, [course]);

  useEffect(() => {
    if (!moduleUuid) {
      return;
    }

    setExpandedModuleUuids((current) =>
      current.includes(moduleUuid) ? current : [...current, moduleUuid]
    );
  }, [moduleUuid]);

  useEffect(() => {
    if (!courseUuid) {
      setCompletedModuleUuids([]);
      return;
    }

    try {
      const raw = sessionStorage.getItem(`completedModules:${courseUuid}`);
      if (!raw) {
        setCompletedModuleUuids([]);
        return;
      }
      const parsed = JSON.parse(raw);
      setCompletedModuleUuids(Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : []);
    } catch {
      setCompletedModuleUuids([]);
    }
  }, [courseUuid]);

  useEffect(() => {
    if (!isForumRoute) {
      return;
    }

    let cancelled = false;

    const loadForumCourses = async () => {
      setForumCoursesLoading(true);
      try {
        const availableCourses =
          currentUser?.identity === "Learner"
            ? await getMyEnrolledCourses()
            : (await getManagedCourses({ page: 1, pageSize: 100 })).items;

        if (!cancelled) {
          setForumCourses(availableCourses);
          setForumCoursesError(null);
        }
      } catch (error) {
        if (!cancelled) {
          setForumCourses([]);
          setForumCoursesError(
            error instanceof Error ? error.message : "课程论坛加载失败。"
          );
        }
      } finally {
        if (!cancelled) {
          setForumCoursesLoading(false);
        }
      }
    };

    void loadForumCourses();

    return () => {
      cancelled = true;
    };
  }, [currentUser?.identity, isForumRoute]);

  const activeTitle = useMemo(() => {
    if (!course) {
      return "课程";
    }

    const currentModule = moduleUuid
      ? course.modules.find((module) => module.moduleUuid === moduleUuid)
      : null;
    const currentMaterial =
      currentModule && materialUuid
        ? currentModule.materials.find((material) => material.materialUuid === materialUuid)
        : null;

    return currentMaterial?.title ?? currentModule?.title ?? "概览";
  }, [course, moduleUuid, materialUuid]);

  const activeModule = useMemo(() => {
    if (!course || !moduleUuid) {
      return null;
    }

    return course.modules.find((module) => module.moduleUuid === moduleUuid) ?? null;
  }, [course, moduleUuid]);

  useEffect(() => {
    if (!activeModule || !isMyCoursesSource || !shouldOpenChatFromQuery) {
      return;
    }

    const openChatKey = `${course?.courseUuid ?? ""}:${activeModule.moduleUuid}:${location.search}`;
    if (openChatConsumedRef.current === openChatKey) {
      return;
    }

    openChatConsumedRef.current = openChatKey;
    setIsChatOpen(true);
  }, [activeModule, course?.courseUuid, isMyCoursesSource, location.search, shouldOpenChatFromQuery]);

  useEffect(() => {
    if (!course || !isLearner) {
      setIsEnrolled(false);
      return undefined;
    }

    let cancelled = false;

    const loadEnrollmentState = async () => {
      try {
        const enrolledCourseUuids = await getMyEnrolledCourseUuids();
        if (!cancelled) {
          setIsEnrolled(enrolledCourseUuids.has(course.courseUuid));
        }
      } catch {
        if (!cancelled) {
          setIsEnrolled(false);
        }
      }
    };

    void loadEnrollmentState();

    return () => {
      cancelled = true;
    };
  }, [course, isLearner]);

  const handleToggleEnrollment = () => {
    if (!course || !isLearner || isEnrolling) {
      return;
    }

    enrollmentActionTriggerRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setEnrollmentActionError("");
    setPendingEnrollmentAction(isEnrolled ? "cancel" : "enroll");
  };

  const toggleModuleExpanded = (targetModuleUuid: string) => {
    setExpandedModuleUuids((current) =>
      current.includes(targetModuleUuid)
        ? current.filter((item) => item !== targetModuleUuid)
        : [...current, targetModuleUuid]
    );
  };

  const markModuleCompleted = (targetModuleUuid: string) => {
    setCompletedModuleUuids((current) => {
      if (current.includes(targetModuleUuid)) {
        return current;
      }
      const next = [...current, targetModuleUuid];
      if (courseUuid) {
        sessionStorage.setItem(`completedModules:${courseUuid}`, JSON.stringify(next));
      }
      return next;
    });
  };

  const completedModuleUuidSet = useMemo(() => {
    const completedFromCourse =
      course?.modules.filter((module) => module.isCompleted).map((module) => module.moduleUuid) ?? [];
    return new Set([...completedFromCourse, ...completedModuleUuids]);
  }, [completedModuleUuids, course?.modules]);

  const confirmEnrollmentAction = async () => {
    if (!course || !isLearner || !pendingEnrollmentAction || isEnrolling) {
      return;
    }

    setIsEnrolling(true);
    setEnrollmentActionError("");
    try {
      if (pendingEnrollmentAction === "cancel") {
        await dropMyEnrollment(course.courseUuid);
        setIsEnrolled(false);
      } else {
        await enrollInCourse(course.courseUuid);
        setIsEnrolled(true);
      }
      await refreshCourse();
      emitAppRefresh({ scope: "course:enrollment", courseUuid: course.courseUuid });
      emitAppRefresh({ scope: "course:catalog", courseUuid: course.courseUuid });
      setPendingEnrollmentAction(null);
      const trigger = enrollmentActionTriggerRef.current;
      enrollmentActionTriggerRef.current = null;
      restoreFocus(trigger);
    } catch (error) {
      setEnrollmentActionError(getEnrollmentActionErrorMessage(error, pendingEnrollmentAction));
    } finally {
      setIsEnrolling(false);
    }
  };

  useEffect(() => {
    if (!isResizingChat) {
      return;
    }

    const handleMouseMove = (event: MouseEvent) => {
      const minWidth = 320;
      const maxWidth = Math.min(640, Math.max(minWidth, window.innerWidth - 520));
      const nextWidth = Math.min(maxWidth, Math.max(minWidth, window.innerWidth - event.clientX));
      setChatWidth(nextWidth);
    };

    const handleMouseUp = () => {
      setIsResizingChat(false);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [isResizingChat]);

  useEffect(() => {
    if (!pendingNavTarget || !quizGuardActive || isQuizLeaving) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeQuizLeaveModal();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [closeQuizLeaveModal, isQuizLeaving, pendingNavTarget, quizGuardActive]);

  useEffect(() => {
    if (!pendingEnrollmentAction || isEnrolling) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeEnrollmentActionModal();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [closeEnrollmentActionModal, isEnrolling, pendingEnrollmentAction]);

  if (loading) {
    return (
      <div className="course-layout-shell course-layout-loading">
        <div className="home-loading">正在加载课程...</div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="course-layout-shell course-layout-loading">
        <div className="course-empty-state">
          <strong>无法加载课程。</strong>
          <p>{loadError}</p>
          <Link to="/home/course-center" className="course-layout-back-link">返回课程中心
          </Link>
        </div>
      </div>
    );
  }

  if (!course || !courseUuid) {
    return <Navigate to="/home/course-center" replace />;
  }

  if (isForumRoute && !canAccessForum) {
    return <Navigate to={`/course/${course.courseUuid}${courseSearchSuffix}`} replace />;
  }

  return (
    <div
      className={`course-layout-shell${isChatOpen && activeModule ? " course-layout-shell-chat-open" : ""}${
        isResizingChat ? " course-layout-shell-chat-resizing" : ""
      }`}
      style={{ "--course-chat-width": `${chatWidth}px` } as CSSProperties}
    >
      <aside className={`course-layout-sidebar${isMobileSidebarOpen ? " course-layout-sidebar-open" : ""}`}>
        <button
          type="button"
          className="course-layout-sidebar-close"
          onClick={() => setIsMobileSidebarOpen(false)}
          aria-label="隐藏课程导航"
        >
          <LuX size={20} aria-hidden="true" />
        </button>

        <Link
          to={backLink}
          className="course-layout-back-link"
          onClick={(e) => handleSidebarNavigation(e, backLink)}
        >
          {backLabel}
        </Link>

        {!isForumRoute ? (
          <div className="course-layout-summary">
            {course.courseCode ? <span className="course-surface-badge">{course.courseCode}</span> : null}
            <h1>课程</h1>
            <p>{course.title}</p>
          </div>
        ) : null}

        {isForumRoute && canAccessForum ? (
          <div className="course-layout-forum-sidebar">
            <div className="course-layout-forum-sidebar-header">
              <h3>切换课程论坛</h3>
            </div>
            <div className="course-layout-forum-sidebar-list">
              {forumCoursesLoading ? (
                <div className="course-layout-forum-sidebar-empty">
                  <strong>正在加载课程...</strong>
                </div>
              ) : null}
              {!forumCoursesLoading && forumCoursesError ? (
                <div className="course-layout-forum-sidebar-empty">
                  <strong>无法加载你的课程。</strong>
                  <p>{forumCoursesError}</p>
                </div>
              ) : null}
              {!forumCoursesLoading && !forumCoursesError && forumCourses.length === 0 ? (
                <div className="course-layout-forum-sidebar-empty">
                  <strong>暂无课程论坛</strong>
                </div>
              ) : null}
              {forumCourses.map((item) => (
                <NavLink
                  key={item.courseUuid}
                  to={`/course/${item.courseUuid}/forum${courseSearchSuffix}`}
                  className={({ isActive }) =>
                    isActive
                      ? "course-layout-forum-course-link course-layout-forum-course-link-active"
                      : "course-layout-forum-course-link"
                  }
                  onClick={(e) => handleSidebarNavigation(e, `/course/${item.courseUuid}/forum${courseSearchSuffix}`)}
                >
                  <strong>{item.title}</strong>
                </NavLink>
              ))}
            </div>
          </div>
        ) : (
          <nav className="course-layout-nav" aria-label="课程导航">
            <NavLink
              to={`/course/${course.courseUuid}${courseSearchSuffix}`}
              end
              className={({ isActive }) =>
                isActive ? "course-layout-nav-item course-layout-nav-item-active" : "course-layout-nav-item"
              }
              onClick={(e) => handleSidebarNavigation(e, `/course/${course.courseUuid}${courseSearchSuffix}`)}
            >概览
            </NavLink>

            {canAccessForum ? (
              <NavLink
                to={`/course/${course.courseUuid}/forum${courseSearchSuffix}`}
                className={({ isActive }) =>
                  isActive ? "course-layout-nav-item course-layout-nav-item-active" : "course-layout-nav-item"
                }
                onClick={(e) => handleSidebarNavigation(e, `/course/${course.courseUuid}/forum${courseSearchSuffix}`)}
              >论坛
              </NavLink>
            ) : null}

            {course.modules.map((module) => {
              const isModuleLocked = isLearner && module.isLocked;
              return (
              <div key={module.moduleUuid} className="course-layout-nav-group">
                {isModuleLocked ? (
                  <div
                    className="course-layout-nav-item course-layout-module-toggle-row course-layout-nav-item-locked"
                    title={module.lockMessage ?? "Complete the prerequisite module to unlock this."}
                    aria-disabled="true"
                  >
                    <span>{module.title}</span>
                    <small>{module.lockMessage ?? "已锁定"}</small>
                    <strong className="course-layout-module-chevron" aria-hidden="true">
                      <LuLock size={16} />
                    </strong>
                  </div>
                ) : (
                  <button
                    type="button"
                    className={`course-layout-nav-item course-layout-module-toggle-row${
                      (moduleUuid === module.moduleUuid) ? " course-layout-nav-item-active" : ""
                    }${shouldShowLearnerProgress && completedModuleUuidSet.has(module.moduleUuid) ? " course-layout-nav-item-completed" : ""}`}
                    onClick={() => toggleModuleExpanded(module.moduleUuid)}
                    aria-label={expandedModuleUuids.includes(module.moduleUuid) ? "收起模块资料" : "展开模块资料"}
                    aria-expanded={expandedModuleUuids.includes(module.moduleUuid)}
                  >
                    <span>{module.title}</span>
                    <small>
                      {shouldShowLearnerProgress && completedModuleUuidSet.has(module.moduleUuid)
                        ? `${module.durationLabel ? `${module.durationLabel} · ` : ""}Completed`
                        : module.durationLabel}
                    </small>
                    <strong
                      className={`course-layout-module-chevron${
                        expandedModuleUuids.includes(module.moduleUuid) ? " course-layout-module-chevron-expanded" : ""
                      }`}
                      aria-hidden="true"
                    >
                      {expandedModuleUuids.includes(module.moduleUuid) ? <LuChevronUp size={18} /> : <LuChevronDown size={18} />}
                    </strong>
                  </button>
                )}

                {!isModuleLocked && (
                  <div className={`course-layout-materials${expandedModuleUuids.includes(module.moduleUuid) ? "" : " course-layout-materials-collapsed"}`}>
                    {module.materials.map((material) => (
                      <NavLink
                        key={material.materialUuid}
                        to={`/course/${course.courseUuid}/modules/${module.moduleUuid}/materials/${material.materialUuid}${courseSearchSuffix}`}
                        className={({ isActive }) =>
                          isActive
                            ? "course-layout-material-item course-layout-material-item-active"
                            : "course-layout-material-item"
                        }
                        onClick={(e) => handleSidebarNavigation(e, `/course/${course.courseUuid}/modules/${module.moduleUuid}/materials/${material.materialUuid}${courseSearchSuffix}`)}
                      >
                        <span>{material.title}</span>
                        {material.materialType ? <small>{material.materialType}</small> : null}
                      </NavLink>
                    ))}
                    {module.hasPublishedQuiz && shouldShowLearnerQuizLinks && (
                      <NavLink
                        to={`/course/${course.courseUuid}/modules/${module.moduleUuid}/quiz${courseSearchSuffix}`}
                        className={({ isActive }) =>
                          isActive
                            ? "course-layout-material-item course-layout-material-item-quiz course-layout-material-item-active"
                            : "course-layout-material-item course-layout-material-item-quiz"
                        }
                        onClick={(e) => handleSidebarNavigation(e, `/course/${course.courseUuid}/modules/${module.moduleUuid}/quiz${courseSearchSuffix}`)}
                      >
                        <span>{module.quizTitle ?? "测验"}</span>
                        <small>测验</small>
                      </NavLink>
                    )}
                  </div>
                )}
              </div>
              );
            })}
          </nav>
        )}
      </aside>

      <div className="course-layout-main">
        {!isForumRoute ? (
          <header className={`course-layout-header${isChatOpen && activeModule && isMyCoursesSource ? " course-layout-header-chat-open" : ""}`}>
            <div className="course-layout-header-title-group">
              <span className="home-topbar-label">课程工作区</span>
              <div className="course-layout-header-title-row">
                <h2>{activeTitle}</h2>
                <button
                  type="button"
                  className="course-layout-sidebar-toggle"
                  onClick={() => setIsMobileSidebarOpen(true)}
                  aria-label="显示课程导航"
                  aria-expanded={isMobileSidebarOpen}
                >
                  <LuMenu size={20} aria-hidden="true" />
                </button>
                {isLearner ? (
                  <button
                    type="button"
                    className={`course-enroll-button${isEnrolled ? " course-enroll-button-complete" : ""}`}
                    onClick={handleToggleEnrollment}
                    disabled={isEnrolling}
                  >
                    {isEnrolling
                      ? isEnrolled
                        ? "正在取消..."
                        : "报名中..."
                      : isEnrolled
                        ? "取消报名"
                        : "Enroll"}
                  </button>
                ) : null}
              </div>
            </div>

            <div className="course-layout-header-meta">
              {course.category ? <span>{course.category}</span> : null}
              {course.difficultyLevel ? <strong>{course.difficultyLevel}</strong> : null}
              {canUseNotifications ? <HomeNotificationsMenu /> : null}
              {activeModule && isMyCoursesSource ? (
                <button
                  type="button"
                  className="course-chat-launcher"
                  onClick={() => setIsChatOpen((current) => !current)}
                  aria-label={isChatOpen ? "关闭聊天助手" : "打开聊天助手"}
                  aria-pressed={isChatOpen}
                >
                  <LuBot size={20} aria-hidden="true" />
                </button>
              ) : null}
            </div>
          </header>
        ) : null}

        <main className={`course-layout-content${isChatOpen && activeModule && isMyCoursesSource ? " course-layout-content-chat-open" : ""}${isForumRoute ? " course-layout-content-forum-only" : ""}`}>
          <Outlet context={{ course, forumCourses, forumCoursesLoading, forumCoursesError, isChatOpen, setQuizGuard, markModuleCompleted, refreshCourse }} />
        </main>
      </div>

      {activeModule && isMyCoursesSource ? (
        <>
          <CourseChatSidebar
            isOpen={isChatOpen}
            courseUuid={course.courseUuid}
            moduleUuid={activeModule.moduleUuid}
            moduleTitle={activeModule.title}
            onClose={() => setIsChatOpen(false)}
            onResizeStart={() => setIsResizingChat(true)}
          />
        </>
      ) : null}

      {pendingNavTarget && quizGuardActive && (
        <div
          className="course-confirm-modal-overlay"
          role="presentation"
          onClick={closeQuizLeaveModal}
        >
          <div
            className="course-confirm-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="quiz-leave-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="course-confirm-modal-header">
              <h3 id="quiz-leave-title">要离开正在进行的测验吗？</h3>
              <p>当前尝试会使用目前已选择的答案提交。</p>
            </div>
            <p className="course-confirm-modal-copy">未作答题目会被判为错误。你之后可以重新开始一次尝试。
            </p>
            <div className="course-confirm-modal-actions">
              <button
                type="button"
                className="course-secondary-link"
                onClick={closeQuizLeaveModal}
                disabled={isQuizLeaving}
                autoFocus
              >留在测验中
              </button>
              <button
                type="button"
                className="course-enroll-button"
                onClick={() => void handleQuizLeaveConfirm()}
                disabled={isQuizLeaving}
              >
                {isQuizLeaving ? "提交中…" : "离开并提交"}
              </button>
            </div>
          </div>
        </div>
      )}

      {pendingEnrollmentAction ? (
        <div
          className="course-confirm-modal-overlay"
          role="presentation"
          onClick={closeEnrollmentActionModal}
        >
          <div
            className="course-confirm-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="course-layout-enrollment-confirm-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="course-confirm-modal-header">
              <h3 id="course-layout-enrollment-confirm-title">
                {pendingEnrollmentAction === "cancel" ? "确认取消报名？" : "确认报名该课程？"}
              </h3>
              <p>{course.title}</p>
            </div>

            <p className="course-confirm-modal-copy">
              {pendingEnrollmentAction === "cancel"
                ? "该课程会从你的学习空间移除，重新报名前不可见；已有学习进度会保留。"
                : "该课程会加入你的学习空间和课程列表。"}
            </p>
            {enrollmentActionError ? (
              <p className="course-confirm-modal-error" role="alert">
                {enrollmentActionError}
              </p>
            ) : null}

            <div className="course-confirm-modal-actions">
              <button
                type="button"
                className="course-secondary-link"
                onClick={closeEnrollmentActionModal}
                disabled={isEnrolling}
                autoFocus
              >返回
              </button>
              <button
                type="button"
                className={`course-enroll-button${pendingEnrollmentAction === "cancel" ? "" : " course-enroll-button-primary"}`}
                onClick={() => void confirmEnrollmentAction()}
                disabled={isEnrolling}
              >
                {isEnrolling
                  ? pendingEnrollmentAction === "cancel"
                    ? "正在取消..."
                    : "报名中..."
                  : pendingEnrollmentAction === "cancel"
                    ? "取消报名"
                    : "Enroll"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default CourseLayout;
