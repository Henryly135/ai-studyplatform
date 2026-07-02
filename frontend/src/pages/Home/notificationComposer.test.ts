import { describe, expect, it } from "vitest";

import type { AdminUserResponse } from "../../types/admin";
import {
  buildNotificationCreatePayload,
  buildNotificationUpdatePayload,
  parseNotificationComposerMetadata,
  type NotificationComposerState,
} from "./notificationComposer";

const baseComposer: NotificationComposerState = {
  notificationType: " course_update ",
  title: " New module ",
  body: " Please review the next lesson. ",
  targetType: " course ",
  targetId: " course_1 ",
  metadataJson: "",
};

const recipient: AdminUserResponse = {
  id: 1,
  userUuid: "learner_1",
  email: "learner@example.test",
  userName: "Learner One",
  identity: "Learner",
  roleCodes: ["learner"],
  emailVerified: true,
  accountStatus: "active",
  createdAt: "2026-07-02T00:00:00Z",
  updatedAt: "2026-07-02T00:00:00Z",
  lastLoginAt: null,
};

describe("notification composer payload helpers", () => {
  it("trims notification fields and maps selected recipients for creates", () => {
    const payload = buildNotificationCreatePayload(
      {
        ...baseComposer,
        metadataJson: '{ "frontendPath": "/course/course_1", "actionLabel": "Open course" }',
      },
      [recipient]
    );

    expect(payload).toEqual({
      notificationType: "course_update",
      title: "New module",
      body: "Please review the next lesson.",
      targetType: "course",
      targetId: "course_1",
      metadataJson: {
        frontendPath: "/course/course_1",
        actionLabel: "Open course",
      },
      recipients: [
        {
          recipientUserUuid: "learner_1",
          recipientEmail: "learner@example.test",
          recipientName: "Learner One",
        },
      ],
    });
  });

  it("uses null metadata and optional target fields for updates", () => {
    const payload = buildNotificationUpdatePayload({
      ...baseComposer,
      targetType: " ",
      targetId: "",
      metadataJson: " ",
    });

    expect(payload.metadataJson).toBeNull();
    expect(payload.targetType).toBeNull();
    expect(payload.targetId).toBeNull();
  });

  it("rejects malformed or non-object metadata before API submission", () => {
    expect(() => parseNotificationComposerMetadata("{ bad-json")).toThrow(
      "Metadata JSON must be valid JSON."
    );
    expect(() => parseNotificationComposerMetadata("[1,2,3]")).toThrow(
      "Metadata JSON must be a JSON object."
    );
  });
});
