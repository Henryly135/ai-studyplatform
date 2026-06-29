import { useEffect, useMemo, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  LuBookOpen,
  LuBot,
  LuChartBar,
  LuBell,
  LuBellRing,
  LuGraduationCap,
  LuLayoutDashboard,
  LuLibrary,
  LuShieldCheck,
  LuSparkles,
  LuUserCheck,
  LuUsers,
} from "react-icons/lu";
import type { ReactNode } from "react";

import HomeNotificationsMenu from "../../components/home/HomeNotificationsMenu";
import HomeSidebarItem from "../../components/home/HomeSidebarItem";
import { getCurrentUser } from "../../services/auth";
import type { CurrentUserResponse } from "../../types/auth";
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
  "educator-requests": <LuUserCheck size={18} />,
  "communication-management": <LuBellRing size={18} />,
};

const SIDEBAR_GROUPS_BY_IDENTITY: Record<CurrentUserResponse["identity"], SidebarGroup[]> = {
  Learner: [
    {
      label: "Learn",
      items: [
        { sectionId: "course-center" },
        { sectionId: "my-courses" },
      ],
    },
    {
      label: "Growth",
      items: [
        { sectionId: "progress" },
        { sectionId: "ai" },
      ],
    },
    {
      label: "Updates",
      items: [
        { sectionId: "communication" },
      ],
    },
  ],
  Educator: [
    {
      label: "Courses",
      items: [
        { sectionId: "course-center" },
        { sectionId: "managed-courses" },
      ],
    },
    {
      label: "Insights",
      items: [
        { sectionId: "analytics" },
        { sectionId: "ai" },
      ],
    },
    {
      label: "Updates",
      items: [
        { sectionId: "communication" },
      ],
    },
  ],
  Admin: [
    {
      label: "Courses",
      items: [
        { sectionId: "course-center" },
        { sectionId: "course-management" },
      ],
    },
    {
      label: "Admin",
      items: [
        { sectionId: "user-management" },
        { sectionId: "educator-requests" },
      ],
    },
    {
      label: "Communication Management",
      items: [
        { sectionId: "communication", label: "Notifications" },
        {
          sectionId: "communication-management",
          label: "Notification Management",
        },
      ],
    },
    {
      label: "Tools",
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
      title: "Admin workspace",
      description: `${toolCount} platform tools available`,
      actionLabel: "Review requests",
      actionPath: "/home/educator-requests",
    };
  }

  if (user.identity === "Educator") {
    return {
      title: "Educator workspace",
      description: "Build and manage course experiences",
      actionLabel: "Manage courses",
      actionPath: "/home/managed-courses",
    };
  }

  return {
    title: "Learner workspace",
    description: "Keep learning with guided support",
    actionLabel: "Explore courses",
    actionPath: "/home/course-center",
  };
}

function HomePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [currentUser, setCurrentUser] = useState<CurrentUserResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const clearSession = () => {
    localStorage.removeItem("accessToken");
    localStorage.removeItem("tokenType");
    localStorage.removeItem("currentUser");
  };

  const handleLogout = () => {
    clearSession();
    navigate("/", { replace: true });
  };

  useEffect(() => {
    let cancelled = false;

    const loadWorkspace = async () => {
      const accessToken = localStorage.getItem("accessToken");
      if (!accessToken) {
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

        clearSession();
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
      return "Notifications";
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
        <div className="home-loading">Loading workspace...</div>
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
            <strong>Learning Hub</strong>
          </Link>
        </div>

        <nav className="home-sidebar-nav" aria-label="Home navigation">
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
            <span className="home-topbar-label">Workspace</span>
            <h2>{activeTitle}</h2>
          </div>

          <div className="home-topbar-actions">
            {canUseNotifications ? <HomeNotificationsMenu /> : null}

            <button
              type="button"
              className="home-topbar-logout"
              onClick={handleLogout}
            >
              Log out
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
