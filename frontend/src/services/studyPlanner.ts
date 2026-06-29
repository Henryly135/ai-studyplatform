import type {
  StudyPlanCreatePayload,
  StudyPlanRecord,
  StudyPlanUpdatePayload,
} from "../types/studyPlanner";
import {
  buildAuthHeaders,
  handleAuthenticationFailureFromResponse,
  parseJsonText,
} from "./api";

const STUDY_PLANS_API_URL = "/api/learning/study-plans";

type ApiErrorResponse = {
  detail?: string | { code?: string; message?: string };
  error?: { code?: string; message?: string };
};

function getErrorMessage(payload: unknown, fallbackMessage: string) {
  if (!payload || typeof payload !== "object") {
    return fallbackMessage;
  }

  const errorPayload = payload as ApiErrorResponse;
  if (errorPayload.error?.message) {
    return errorPayload.error.message;
  }

  if (typeof errorPayload.detail === "string" && errorPayload.detail.trim()) {
    return errorPayload.detail;
  }

  if (errorPayload.detail && typeof errorPayload.detail === "object" && errorPayload.detail.message) {
    return errorPayload.detail.message;
  }

  return fallbackMessage;
}

async function parseResponse<T>(response: Response): Promise<T> {
  const responseText = await response.text();
  const data: unknown = parseJsonText(responseText);
  handleAuthenticationFailureFromResponse(response.status, data);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, "Study Planner request failed."));
  }

  if (data === null) {
    throw new Error("The server returned an unexpected response.");
  }

  return data as T;
}

export async function listStudyPlans(): Promise<StudyPlanRecord[]> {
  const response = await fetch(STUDY_PLANS_API_URL, {
    headers: buildAuthHeaders(),
  });

  return parseResponse<StudyPlanRecord[]>(response);
}

export async function getStudyPlan(planUuid: string): Promise<StudyPlanRecord> {
  const response = await fetch(`${STUDY_PLANS_API_URL}/${planUuid}`, {
    headers: buildAuthHeaders(),
  });

  return parseResponse<StudyPlanRecord>(response);
}

export async function createStudyPlan(payload: StudyPlanCreatePayload): Promise<StudyPlanRecord> {
  const response = await fetch(STUDY_PLANS_API_URL, {
    method: "POST",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(payload),
  });

  return parseResponse<StudyPlanRecord>(response);
}

export async function updateStudyPlan(
  planUuid: string,
  payload: StudyPlanUpdatePayload
): Promise<StudyPlanRecord> {
  const response = await fetch(`${STUDY_PLANS_API_URL}/${planUuid}`, {
    method: "PATCH",
    headers: buildAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(payload),
  });

  return parseResponse<StudyPlanRecord>(response);
}

export async function regenerateStudyPlan(planUuid: string): Promise<StudyPlanRecord> {
  const response = await fetch(`${STUDY_PLANS_API_URL}/${planUuid}/regenerate`, {
    method: "POST",
    headers: buildAuthHeaders(),
  });

  return parseResponse<StudyPlanRecord>(response);
}
