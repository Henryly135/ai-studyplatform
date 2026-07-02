import type { AdminUserResponse } from "../../types/admin";
import type {
  NotificationCreateRequest,
  NotificationUpdateRequest,
} from "../../types/notification";

export type NotificationComposerState = {
  notificationType: string;
  title: string;
  body: string;
  targetType: string;
  targetId: string;
  metadataJson: string;
};

export const INITIAL_COMPOSER_STATE: NotificationComposerState = {
  notificationType: "",
  title: "",
  body: "",
  targetType: "",
  targetId: "",
  metadataJson: "",
};

export function parseNotificationComposerMetadata(value: string): Record<string, unknown> | null {
  const trimmedValue = value.trim();
  if (!trimmedValue) {
    return null;
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmedValue);
  } catch {
    throw new Error("Metadata JSON must be valid JSON.");
  }

  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Metadata JSON must be a JSON object.");
  }

  return parsed as Record<string, unknown>;
}

function buildNotificationBasePayload(composer: NotificationComposerState) {
  return {
    notificationType: composer.notificationType.trim(),
    title: composer.title.trim(),
    body: composer.body.trim(),
    targetType: composer.targetType.trim() || null,
    targetId: composer.targetId.trim() || null,
    metadataJson: parseNotificationComposerMetadata(composer.metadataJson),
  };
}

export function buildNotificationCreatePayload(
  composer: NotificationComposerState,
  recipients: AdminUserResponse[]
): NotificationCreateRequest {
  return {
    ...buildNotificationBasePayload(composer),
    recipients: recipients.map((recipient) => ({
      recipientUserUuid: recipient.userUuid,
      recipientEmail: recipient.email,
      recipientName: recipient.userName,
    })),
  };
}

export function buildNotificationUpdatePayload(
  composer: NotificationComposerState
): NotificationUpdateRequest {
  return buildNotificationBasePayload(composer);
}
