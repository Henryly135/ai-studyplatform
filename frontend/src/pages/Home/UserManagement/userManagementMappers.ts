import type { AdminUserResponse } from "../../../types/admin";
import type { UserAccountStatus, UserItem, UserRole } from "./types";

function normalizeRole(identity: string): UserRole {
  if (identity === "Admin" || identity === "Educator" || identity === "Learner") {
    return identity;
  }

  return "Learner";
}

function normalizeAccountStatus(accountStatus: string): UserAccountStatus {
  if (accountStatus === "active" || accountStatus === "deactivated") {
    return accountStatus;
  }

  return "deactivated";
}

export function mapAdminUserToUserItem(user: AdminUserResponse): UserItem {
  const normalizedRole = normalizeRole(user.identity);

  return {
    id: user.id,
    userUuid: user.userUuid,
    name: user.userName,
    email: user.email,
    role: normalizedRole,
    identity: normalizedRole,
    roleCodes: user.roleCodes,
    emailVerified: user.emailVerified,
    accountStatus: normalizeAccountStatus(user.accountStatus),
    createdAt: user.createdAt,
    updatedAt: user.updatedAt,
    lastLoginAt: user.lastLoginAt,
  };
}
