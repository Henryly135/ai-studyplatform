import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, Navigate, NavLink, Outlet, useLocation, useNavigate, useParams } from "react-router-dom";
import type { CSSProperties, MouseEvent as ReactMouseEvent } from "react";
import { LuBot, LuChevronDown, LuChevronUp, LuLock, LuMenu, LuX } from "react-icons/lu";

import HomeNotificationsMenu from "../../components/home/HomeNotificationsMenu";
import type { CurrentUserResponse } from "../../types/auth";
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

function CourseLayout() {
  const { courseUuid, moduleUuid, materialUuid } = useParams();
  const location = useLocation();
  const [course, setCourse] = useState<CourseRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [chatWidth, setChatWidth] = useState(380);
  const [isResizingChat, setIsResizingChat] = useState(false);
  const currentUser = useMemo(() => {
    const raw = localStorage.getItem("currentUser");
    if (!raw) {
      return null;
    }

    try {
      return JSON.parse(raw) as CurrentUserResponse;
    } catch {
      return null;
    }
  }, []);
  const isLearner = currentUser?.identity === "Learner";
  const canUseNotifications =
    currentUser?.identity === "Learner" || currentUser?.identity === "Educator";
  const [forumCourses, setForumCourses] = useState<CourseRecord[]>([]);
  const [forumCoursesLoading, setForumCoursesLoading] = useState(false);
  const [forumCoursesError, setForumCoursesError] = useState<string | null>(null);
  const [isEnrolled, setIsEnrolled] = useState(false);
  const [isEnrolling, setIsEnrolling] = useState(false);
  const [pendingEnrollmentAction, setPendingEnrollmentAction] = useState<PendingEnrollmentAction | null>(null);
  const [quizGuardActive, setQuizGuardActive] = useState(false);
  const [pendingNavTarget, setPendingNavTarget] = useState<string | null>(null);
  const [isQuizLeaving, setIsQuizLeaving] = useState(false);
  const [expandedModuleUuids, setExpandedModuleUuids] = useState<string[]>([]);
  const [completedModuleUuids, setCompletedModuleUuids] = useState<string[]>([]);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const quizSubmitRef = useRef<(() => Promise<void>) | null>(null);
  const allowNextPopstateRef = useRef(false);
  const quizPageUrlRef = useRef('');
  const navigate = useNavigate();

  const handleSidebarNavigation = (
    event: ReactMouseEvent<HTMLElement>,
    target: string
  ) => {
    if (quizGuardActive) {
      event.preventDefault();
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
      ? "Back to my courses"
      : source === "managed-courses"
        ? "Back to managed courses"
        : "Back to course lobby";

  const refreshCourse = useCallback(async () => {
    if (!courseUuid) {
      return;
    }

    const shouldLoadManagedCourse =
      currentUser?.identity !== "Learner" && isManagedCourseSource;
    const data = shouldLoadManagedCourse
      ? await getManagedCourseByUuid(courseUuid)
      : await getCourseByUuid(courseUuid);
    setCourse(data);
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
        void refreshCourse();
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
            error instanceof Error ? error.message : "Failed to load your course forums."
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
      return "Course";
    }

    const currentModule = moduleUuid
      ? course.modules.find((module) => module.moduleUuid === moduleUuid)
      : null;
    const currentMaterial =
      currentModule && materialUuid
        ? currentModule.materials.find((material) => material.materialUuid === materialUuid)
        : null;

    return currentMaterial?.title ?? currentModule?.title ?? "Overview";
  }, [course, moduleUuid, materialUuid]);

  const activeModule = useMemo(() => {
    if (!course || !moduleUuid) {
      return null;
    }

    return course.modules.find((module) => module.moduleUuid === moduleUuid) ?? null;
  }, [course, moduleUuid]);

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
    } catch (error) {
      console.error(error);
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

  if (loading) {
    return (
      <div className="course-layout-shell course-layout-loading">
        <div className="home-loading">Loading course...</div>
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
          aria-label="Hide course navigation"
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
            <h1>Course</h1>
            <p>{course.title}</p>
          </div>
        ) : null}

        {isForumRoute && canAccessForum ? (
          <div className="course-layout-forum-sidebar">
            <div className="course-layout-forum-sidebar-header">
              <h3>Switch course forums</h3>
            </div>
            <div className="course-layout-forum-sidebar-list">
              {forumCoursesLoading ? (
                <div className="course-layout-forum-sidebar-empty">
                  <strong>Loading courses...</strong>
                </div>
              ) : null}
              {!forumCoursesLoading && forumCoursesError ? (
                <div className="course-layout-forum-sidebar-empty">
                  <strong>Unable to load your courses.</strong>
                  <p>{forumCoursesError}</p>
                </div>
              ) : null}
              {!forumCoursesLoading && !forumCoursesError && forumCourses.length === 0 ? (
                <div className="course-layout-forum-sidebar-empty">
                  <strong>No course forums yet</strong>
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
          <nav className="course-layout-nav" aria-label="Course navigation">
            <NavLink
              to={`/course/${course.courseUuid}${courseSearchSuffix}`}
              end
              className={({ isActive }) =>
                isActive ? "course-layout-nav-item course-layout-nav-item-active" : "course-layout-nav-item"
              }
              onClick={(e) => handleSidebarNavigation(e, `/course/${course.courseUuid}${courseSearchSuffix}`)}
            >
              Overview
            </NavLink>

            {canAccessForum ? (
              <NavLink
                to={`/course/${course.courseUuid}/forum${courseSearchSuffix}`}
                className={({ isActive }) =>
                  isActive ? "course-layout-nav-item course-layout-nav-item-active" : "course-layout-nav-item"
                }
                onClick={(e) => handleSidebarNavigation(e, `/course/${course.courseUuid}/forum${courseSearchSuffix}`)}
              >
                Forum
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
                    <small>{module.lockMessage ?? "Locked"}</small>
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
                    aria-label={expandedModuleUuids.includes(module.moduleUuid) ? "Collapse module materials" : "Expand module materials"}
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
                        <span>{module.quizTitle ?? "Quiz"}</span>
                        <small>quiz</small>
                      </NavLink>
                    )}
                    {module.hasPublishedShortAnswer && (
                      <NavLink
                        to={`/course/${course.courseUuid}/modules/${module.moduleUuid}/short-answer${courseSearchSuffix}`}
                        className={({ isActive }) =>
                          isActive
                            ? "course-layout-material-item course-layout-material-item-active"
                            : "course-layout-material-item"
                        }
                        onClick={(e) => handleSidebarNavigation(e, `/course/${course.courseUuid}/modules/${module.moduleUuid}/short-answer${courseSearchSuffix}`)}
                      >
                        <span>{module.shortAnswerTitle ?? "Short-answer assessment"}</span>
                        <small>assessment</small>
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
              <span className="home-topbar-label">Course Workspace</span>
              <div className="course-layout-header-title-row">
                <h2>{activeTitle}</h2>
                <button
                  type="button"
                  className="course-layout-sidebar-toggle"
                  onClick={() => setIsMobileSidebarOpen(true)}
                  aria-label="Show course navigation"
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
                        ? "Cancelling..."
                        : "Enrolling..."
                      : isEnrolled
                        ? "Cancel enrollment"
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
                  aria-label={isChatOpen ? "Close chatbot" : "Open chatbot"}
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
          onClick={() => setPendingNavTarget(null)}
        >
          <div
            className="course-confirm-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="quiz-leave-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="course-confirm-modal-header">
              <h3 id="quiz-leave-title">Leave quiz in progress?</h3>
              <p>Your current attempt will be submitted with answers selected so far.</p>
            </div>
            <p className="course-confirm-modal-copy">
              Unanswered questions will be marked as incorrect. You can start a new attempt later.
            </p>
            <div className="course-confirm-modal-actions">
              <button
                type="button"
                className="course-secondary-link"
                onClick={() => setPendingNavTarget(null)}
                disabled={isQuizLeaving}
              >
                Stay in quiz
              </button>
              <button
                type="button"
                className="course-enroll-button"
                onClick={() => void handleQuizLeaveConfirm()}
                disabled={isQuizLeaving}
              >
                {isQuizLeaving ? "Submitting…" : "Leave and submit"}
              </button>
            </div>
          </div>
        </div>
      )}

      {pendingEnrollmentAction ? (
        <div
          className="course-confirm-modal-overlay"
          role="presentation"
          onClick={() => setPendingEnrollmentAction(null)}
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
                {pendingEnrollmentAction === "cancel" ? "Cancel enrollment?" : "Enroll in this course?"}
              </h3>
              <p>{course.title}</p>
            </div>

            <p className="course-confirm-modal-copy">
              {pendingEnrollmentAction === "cancel"
                ? "This course will be removed from your learner workspace until you enroll again. Your existing learning progress will be kept."
                : "This course will be added to your learner workspace and course list."}
            </p>

            <div className="course-confirm-modal-actions">
              <button
                type="button"
                className="course-secondary-link"
                onClick={() => setPendingEnrollmentAction(null)}
                disabled={isEnrolling}
              >
                Back
              </button>
              <button
                type="button"
                className={`course-enroll-button${pendingEnrollmentAction === "cancel" ? "" : " course-enroll-button-primary"}`}
                onClick={() => void confirmEnrollmentAction()}
                disabled={isEnrolling}
              >
                {isEnrolling
                  ? pendingEnrollmentAction === "cancel"
                    ? "Cancelling..."
                    : "Enrolling..."
                  : pendingEnrollmentAction === "cancel"
                    ? "Cancel enrollment"
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
