type ManagementSidebarSummaryProps = {
  title: string;
  summary: string;
};

function ManagementSidebarSummary({ title, summary }: ManagementSidebarSummaryProps) {
  return (
    <div className="course-management-sidebar-card">
      <span className="course-surface-badge">课程管理器</span>
      <h1>{title}</h1>
      <p>{summary}</p>
    </div>
  );
}

export default ManagementSidebarSummary;
