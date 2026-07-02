import { useEffect, useMemo, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  LuBookOpen,
  LuBot,
  LuChartBar,
  LuBell,
  LuGraduationCap,
  LuLayoutDashboard,
  LuLibrary,
  LuShieldCheck,
  LuSparkles,
  LuUsers,
} from "react-icons/lu";
import type { ReactNode } from "react";

import HomeNotificationsMenu from "../../components/home/HomeNotificationsMenu";
import HomeSidebarItem from "../../components/home/HomeSidebarItem";
import { clearStoredSession } from "../../services/api";
import { getCurrentUser } from "../../services/auth";
import type { CurrentUserResponse } from "../../types/auth";
import { isUsableAccessToken } from "../../utils/accessToken";
import type { HomeSection } from "./homeConfig";
import { getAllowedHomeSections } from "./homeConfig";
import "./HomePage.css";

function getInitials(userName: string) {
  return userName
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("") || "U";
}

type SidebarGroup = {
  label: string;
  items: SidebarGroupItem[];
};

type SidebarSection = HomeSection & {
  label: string;
};

type SidebarGroupItem = {
  sectionId: string;
  label?: string;
};

type SidebarGroupWithSections = SidebarGroup & {
  sections: SidebarSection[];
};

const SECTION_ICONS: Record<string, ReactNode> = {
  "course-center": <LuLibrary size={18} />,
  "my-courses": <LuBookOpen size={18} />,
  "managed-courses": <LuGraduationCap size={18} />,
  communication: <LuBell size={18} />,
  progress: <LuChartBar size={18} />,
  ai: <LuBot size={18} />,
  analytics: <LuChartBar size={18} />,
  "course-management": <LuLayoutDashboard size={18} />,
  "user-management": <LuUsers size={18} />,
};

const SIDEBAR_GROUPS_BY_IDENTITY: Record<CurrentUserResponse["identity"], SidebarGroup[]> = {
  Learner: [
    {
      label: "学习",
      items: [
        { sectionId: "course-center" },
        { sectionId: "my-courses" },
      ],
    },
    {
      label: "成长",
      items: [
        { sectionId: "progress" },
        { sectionId: "ai" },
      ],
    },
    {
      label: "更新",
      items: [
        { sectionId: "communication" },
      ],
    },
  ],
  Educator: [
    {
      label: "课程",
      items: [
        { sectionId: "course-center" },
        { sectionId: "managed-courses" },
      ],
    },
    {
      label: "洞察",
      items: [
        { sectionId: "analytics" },
        { sectionId: "ai" },
      ],
    },
    {
      label: "更新",
      items: [
        { sectionId: "communication" },
      ],
    },
  ],
  Admin: [
    {
      label: "课程",
      items: [
        { sectionId: "course-center" },
        { sectionId: "course-management" },
      ],
    },
    {
      label: "治理",
      items: [
        { sectionId: "user-management" },
      ],
    },
    {
      label: "智能助手",
      items: [
        { sectionId: "ai" },
      ],
    },
  ],
};

function buildSidebarGroups(
  identity: CurrentUserResponse["identity"],
  sections: HomeSection[]
): SidebarGroupWithSections[] {
  const sectionMap = new Map(sections.map((section) => [section.id, section]));
  return SIDEBAR_GROUPS_BY_IDENTITY[identity]
    .map((group) => ({
      ...group,
      sections: group.items
        .map((item) => {
          const section = sectionMap.get(item.sectionId);
          if (!section) {
            return null;
          }

          return {
            ...section,
            label: item.label ?? section.title,
          };
        })
        .filter((section): section is SidebarSection => Boolean(section)),
    }))
    .filter((group) => group.sections.length > 0);
}

function getWorkspaceSummary(user: CurrentUserResponse, toolCount: number) {
  if (user.identity === "Admin") {
    return {
      title: "管理员工作区",
      description: `${toolCount} 个平台工具可用`,
      actionLabel: "查看智能治理",
      actionPath: "/home/ai",
    };
  }

  if (user.identity === "Educator") {
    return {
      title: "教师工作区",
      description: "构建和管理课程体验",
      actionLabel: "管理课程",
      actionPath: "/home/managed-courses",
    };
  }

  return {
    title: "学生工作区",
    description: "在引导支持下继续学习",
    actionLabel: "浏览课程",
    actionPath: "/home/course-center",
  };
}

function HomePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [currentUser, setCurrentUser] = useState<CurrentUserResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const handleLogout = () => {
    clearStoredSession();
    navigate("/", { replace: true });
  };

  useEffect(() => {
    let cancelled = false;

    const loadWorkspace = async () => {
      const accessToken = localStorage.getItem("accessToken");
      if (!accessToken || !isUsableAccessToken(accessToken)) {
        clearStoredSession();
        navigate("/", { replace: true });
        return;
      }

      try {
        const user = await getCurrentUser(accessToken);

        if (cancelled) {
          return;
        }

        localStorage.setItem("currentUser", JSON.stringify(user));
        setCurrentUser(user);
      } catch {
        if (cancelled) {
          return;
        }

        clearStoredSession();
        navigate("/", { replace: true });
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadWorkspace();

    return () => {
      cancelled = true;
    };
  }, [navigate]);

  const allowedSections = useMemo(() => {
    if (!currentUser) {
      return [];
    }

    return getAllowedHomeSections(currentUser.identity);
  }, [currentUser]);

  const activeTitle = useMemo(() => {
    if (location.pathname === "/home/ai/profile-init") {
      return "Learning Profile";
    }

    if (location.pathname === "/home/communication") {
      return "通知";
    }

    const matchedSection = allowedSections.find((section) =>
      location.pathname === `/home/${section.path}`
    );

    return matchedSection?.title ?? "Home";
  }, [allowedSections, location.pathname]);

  const sidebarGroups = useMemo(() => {
    if (!currentUser) {
      return [];
    }

    return buildSidebarGroups(currentUser.identity, allowedSections);
  }, [allowedSections, currentUser]);

  if (loading) {
    return (
      <div className="home-shell home-shell-loading">
        <div className="home-loading">正在加载工作区...</div>
      </div>
    );
  }

  if (!currentUser) {
    return null;
  }

  const workspaceSummary = getWorkspaceSummary(currentUser, allowedSections.length);
  const canUseNotifications =
    currentUser.identity === "Learner" ||
    currentUser.identity === "Educator" ||
    currentUser.identity === "Admin";

  return (
    <div className="home-shell">
      <aside className="home-sidebar">
        <div className="home-sidebar-top">
          <Link to="/home" className="home-sidebar-brand">
            <span className="home-sidebar-brand-mark">C</span>
            <strong>学习平台</strong>
          </Link>
        </div>

        <nav className="home-sidebar-nav" aria-label="工作台导航">
          {sidebarGroups.map((group) => (
            <div className="home-sidebar-group" key={group.label}>
              <span className="home-sidebar-group-label">{group.label}</span>
              <div className="home-sidebar-group-list">
                {group.sections.map((section) => (
                  <HomeSidebarItem
                    key={section.id}
                    to={`/home/${section.path}`}
                    title={section.label}
                    icon={SECTION_ICONS[section.id]}
                  />
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="home-sidebar-workspace">
          <div className="home-sidebar-workspace-icon" aria-hidden="true">
            {currentUser.identity === "Admin" ? <LuShieldCheck size={18} /> : <LuSparkles size={18} />}
          </div>
          <div className="home-sidebar-workspace-copy">
            <strong>{workspaceSummary.title}</strong>
            <span>{workspaceSummary.description}</span>
          </div>
          <Link to={workspaceSummary.actionPath} className="home-sidebar-workspace-action">
            {workspaceSummary.actionLabel}
          </Link>
        </div>
      </aside>

      <div className="home-main">
        <header className="home-topbar">
          <div>
            <span className="home-topbar-label">工作区</span>
            <h2>{activeTitle}</h2>
          </div>

          <div className="home-topbar-actions">
            {canUseNotifications ? <HomeNotificationsMenu /> : null}

            <button
              type="button"
              className="home-topbar-logout"
              onClick={handleLogout}
            >退出登录
            </button>

            <div className="home-profile-card">
              <div className="home-profile-avatar">{getInitials(currentUser.userName)}</div>
              <div>
                <strong>{currentUser.userName}</strong>
                <span>{currentUser.identity}</span>
              </div>
            </div>
          </div>
        </header>

        <main className="home-content">
          <Outlet context={{ currentUser, allowedSections }} />
        </main>
      </div>
    </div>
  );
}

export default HomePage;
