export type UserRole = "Admin" | "Educator" | "Learner";

export type UserRoleFilter = "All" | UserRole;

export type UserAccountStatus =
  | "active"
  | "deactivated";

export type UserItem = {
  id: number;
  userUuid: string;
  name: string;
  email: string;
  role: UserRole;
  identity: UserRole;
  roleCodes: string[];
  emailVerified: boolean;
  accountStatus: UserAccountStatus;
  createdAt: string;
  updatedAt: string;
  lastLoginAt: string | null;
};
