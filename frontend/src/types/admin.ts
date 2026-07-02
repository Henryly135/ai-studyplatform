import type { Identity } from "./auth";

export interface AdminUserResponse {
  id: number;
  userUuid: string;
  email: string;
  userName: string;
  identity: Identity;
  roleCodes: string[];
  emailVerified: boolean;
  accountStatus: string;
  createdAt: string;
  updatedAt: string;
  lastLoginAt: string | null;
}

export interface AdminUserListResponse {
  users: AdminUserResponse[];
}

export interface AdminUpdateUserIdentityRequest {
  identity: Identity;
}

export interface AdminUpdateUserStatusRequest {
  accountStatus: string;
}

export type EducatorApprovalStatus = "pending" | "approved" | "rejected";

export type EducatorApprovalHistoryStatus = "reviewed" | "approved" | "rejected";

export type EducatorApprovalAction = "approve" | "reject";

export interface EducatorApprovalResponse {
  requestUuid: string;
  requestStatus: EducatorApprovalStatus;
  submittedAt: string;
  updatedAt: string;
  reviewedAt: string | null;
  reviewComment: string | null;
  supportingInfo: string | null;
  supportingFileUrl: string | null;
  userId: number;
  userUuid: string;
  email: string;
  userName: string;
  identity: Identity;
  accountStatus: string;
  emailVerified: boolean;
  reviewerUserId: number | null;
  reviewerUserUuid: string | null;
  reviewerEmail: string | null;
  reviewerName: string | null;
}

export interface EducatorApprovalListResponse {
  requests: EducatorApprovalResponse[];
}

export interface ReviewEducatorApprovalRequest {
  action: EducatorApprovalAction;
  reviewComment?: string;
}

export interface EducatorInviteTokenResponse {
  inviteUuid: string;
  createdAt: string;
  expiresAt: string;
  usedAt: string | null;
  isUsed: boolean;
}

export interface EducatorInviteTokenListResponse {
  tokens: EducatorInviteTokenResponse[];
}

export interface EducatorInviteTokenGenerateResponse {
  inviteUuid: string;
  rawToken: string;
  expiresAt: string;
  inviteUrl: string;
}

export interface SendEducatorInviteEmailRequest {
  recipientEmail: string;
  inviteUrl: string;
}

export interface EducatorInviteEmailDelivery {
  attempted: boolean;
  delivered: boolean;
  reason: string | null;
}

export interface SendEducatorInviteEmailResponse {
  detail: string;
  emailDelivery: EducatorInviteEmailDelivery;
}

export interface AdminAiProviderCredential {
  provider: string;
  label: string;
  backendSupported: boolean;
  configured: boolean;
  keyPreview: string | null;
  defaultModelId: string | null;
  status: string;
  lastHealthCheckAt: string | null;
  lastHealthStatus: string | null;
  updatedAt: string | null;
}

export interface AdminAiProviderCredentialListResponse {
  credentials: AdminAiProviderCredential[];
}

export interface SaveAdminAiProviderCredentialRequest {
  provider: string;
  apiKey: string;
  defaultModelId?: string | null;
}

export interface AdminAiProviderCredentialHealthResponse {
  provider: string;
  status: string;
  ok: boolean;
  checkedAt: string;
  message: string | null;
}

export interface SetAdminAiDefaultModelRequest {
  modelId: string;
}

export interface AdminAiDefaultModelResponse {
  modelId: string;
  provider: string | null;
}

export interface CourseInviteLinkResponse {
  inviteUuid: string;
  courseUuid: string;
  inviteUrl?: string;
  isActive: boolean;
  createdAt: string;
  expiresAt: string | null;
}

export interface CourseInviteValidateResponse {
  valid: boolean;
  courseUuid: string;
  courseTitle: string;
  inviteUuid: string;
}

export interface CourseInviteEnrolResponse {
  detail: string;
  courseUuid: string;
  courseTitle: string;
}
