import type { UserItem, UserRoleFilter } from "./types";

export function filterUsers(
  users: UserItem[],
  search: string,
  roleFilter: UserRoleFilter
) {
  const keyword = search.trim().toLowerCase();

  return users.filter((user) => {
    const matchesSearch =
      user.name.toLowerCase().includes(keyword) ||
      user.email.toLowerCase().includes(keyword);

    const matchesRole = roleFilter === "All" || user.role === roleFilter;

    return matchesSearch && matchesRole;
  });
}
