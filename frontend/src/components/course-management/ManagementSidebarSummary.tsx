type ManagementSidebarSummaryProps = {
  title: string;
  summary: string;
};

function ManagementSidebarSummary({ title, summary }: ManagementSidebarSummaryProps) {
  return (
    <div className="course-management-sidebar-card">
      <span className="course-surface-badge">Course Manager</span>
      <h1>{title}</h1>
      <p>{summary}</p>
    </div>
  );
}

export default ManagementSidebarSummary;
