type ManagementStatCardProps = {
  label: string;
  value: string;
  valueClassName?: string;
};

function ManagementStatCard({ label, value, valueClassName }: ManagementStatCardProps) {
  return (
    <article className="course-management-stat-card">
      <span>{label}</span>
      <strong className={valueClassName}>{value}</strong>
    </article>
  );
}

export default ManagementStatCard;
