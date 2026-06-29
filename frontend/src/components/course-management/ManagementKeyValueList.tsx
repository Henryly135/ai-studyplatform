type ManagementKeyValueItem = {
  label: string;
  value: string;
  valueClassName?: string;
};

type ManagementKeyValueListProps = {
  items: ManagementKeyValueItem[];
};

function ManagementKeyValueList({ items }: ManagementKeyValueListProps) {
  return (
    <div className="course-management-key-value-list">
      {items.map((item) => (
        <div key={item.label} className="course-management-key-value">
          <span>{item.label}</span>
          <strong className={item.valueClassName}>{item.value}</strong>
        </div>
      ))}
    </div>
  );
}

export default ManagementKeyValueList;
