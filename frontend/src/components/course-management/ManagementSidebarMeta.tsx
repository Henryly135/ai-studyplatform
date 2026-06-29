type ManagementSidebarMetaItem = {
  label: string;
  value: string;
  valueClassName?: string;
};

type ManagementSidebarMetaProps = {
  items: ManagementSidebarMetaItem[];
};

function ManagementSidebarMeta({ items }: ManagementSidebarMetaProps) {
  return (
    <div className="course-management-sidebar-meta">
      {items.map((item) => (
        <div key={item.label}>
          <span>{item.label}</span>
          <strong className={item.valueClassName}>{item.value}</strong>
        </div>
      ))}
    </div>
  );
}

export default ManagementSidebarMeta;
