import type { CSSProperties, ReactNode } from "react";

type ManagementPanelProps = {
  title: string;
  children: ReactNode;
  bodyClassName?: string;
  actions?: ReactNode;
  style?: CSSProperties;
};

function ManagementPanel({ title, children, bodyClassName = "", actions, style }: ManagementPanelProps) {
  return (
    <article className="course-management-panel" style={style}>
      <div className={`course-panel-heading${actions ? " course-panel-heading-with-actions" : ""}`}>
        <h3>{title}</h3>
        {actions ? <div className="course-panel-heading-actions">{actions}</div> : null}
      </div>
      <div className={`course-management-panel-body${bodyClassName ? ` ${bodyClassName}` : ""}`}>{children}</div>
    </article>
  );
}

export default ManagementPanel;
