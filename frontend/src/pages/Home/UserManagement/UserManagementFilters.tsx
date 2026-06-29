import type { ChangeEvent } from "react";
import type { UserRoleFilter } from "./types";

type UserManagementFiltersProps = {
  search: string;
  roleFilter: UserRoleFilter;
  onSearchChange: (value: string) => void;
  onRoleFilterChange: (value: UserRoleFilter) => void;
};

function UserManagementFilters({
  search,
  roleFilter,
  onSearchChange,
  onRoleFilterChange,
}: UserManagementFiltersProps) {
  const handleSearchChange = (event: ChangeEvent<HTMLInputElement>) => {
    onSearchChange(event.target.value);
  };

  const handleRoleFilterChange = (event: ChangeEvent<HTMLSelectElement>) => {
    onRoleFilterChange(event.target.value as UserRoleFilter);
  };

  return (
    <div className="user-management-toolbar">
      <input
        className="user-management-search"
        type="text"
        placeholder="Search by name or email"
        value={search}
        onChange={handleSearchChange}
      />

      <select
        className="user-management-select"
        value={roleFilter}
        onChange={handleRoleFilterChange}
      >
        <option value="All">All Roles</option>
        <option value="Educator">Educator</option>
        <option value="Learner">Learner</option>
      </select>
    </div>
  );
}

export default UserManagementFilters;
