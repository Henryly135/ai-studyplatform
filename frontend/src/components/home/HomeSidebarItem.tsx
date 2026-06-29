import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";

type HomeSidebarItemProps = {
  to: string;
  title: string;
  icon?: ReactNode;
  className?: string;
};

function HomeSidebarItem({ to, title, icon, className }: HomeSidebarItemProps) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        [
          "home-sidebar-item",
          className,
          isActive ? "home-sidebar-item-active" : "",
        ]
          .filter(Boolean)
          .join(" ")
      }
    >
      {icon ? <span className="home-sidebar-item-icon" aria-hidden="true">{icon}</span> : null}
      <span className="home-sidebar-item-label">{title}</span>
    </NavLink>
  );
}

export default HomeSidebarItem;
