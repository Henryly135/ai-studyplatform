export type Identity = "Learner" | "Educator" | "Admin";

export interface RegisterRequest {
  userName: string;
  email: string;
  password: string;
  identity: Identity;
}

export interface RegisterSuccessResponse {
  detail: string;
  user?: {
    id: number;
    userUuid: string;
    email: string;
    userName: string;
    identity: Identity;
    emailVerified: boolean;
  };
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginSuccessResponse {
  accessToken: string;
  tokenType: "bearer";
  expiresIn: number;
  shouldShowGlobalProfileInitPrompt?: boolean;
  user: {
    id: number;
    userUuid: string;
    email: string;
    userName: string;
    identity: Identity;
    availableIdentities?: Identity[];
    emailVerified: boolean;
    accountStatus?: string;
  };
}

export interface CurrentUserResponse {
  id: number;
  userUuid: string;
  email: string;
  userName: string;
  identity: Identity;
  availableIdentities?: Identity[];
  emailVerified: boolean;
  accountStatus?: string;
}

export interface PermissionItem {
  permissionId: number;
  permissionCode: string;
  permissionName: string;
  description: string | null;
}

export interface CurrentUserPermissionsResponse {
  permissions: PermissionItem[];
}

export interface ApiErrorResponse {
  detail: string;
  field?: string;
  errors?: Array<{
    field: string;
    reason: string;
  }>;
}

export interface ChangePasswordRequest {
  currentPassword: string;
  newPassword: string;
}

export interface ResetPasswordRequest {
  token: string;
  newPassword: string;
}

export interface EducatorInviteRegisterRequest {
  userName: string;
  email: string;
  password: string;
  inviteToken: string;
}
