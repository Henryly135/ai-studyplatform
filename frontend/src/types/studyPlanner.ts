export type StudyPlannerMaterialInput = {
  title: string;
  materialType?: string | null;
  notes?: string | null;
};

export type StudyPlanCreatePayload = {
  goal: string;
  availableMinutesPerWeek: number;
  targetDate?: string | null;
  preferences?: string | null;
  materials: StudyPlannerMaterialInput[];
};

export type StudyPlanPhase = {
  title: string;
  focus: string;
  durationDays: number;
  outcomes: string[];
};

export type StudyPlanTopic = {
  title: string;
  reason: string;
  materials: string[];
};

export type StudyPlanRevisionItem = {
  cadence: string;
  activity: string;
};

export type StudyPlanContent = {
  overview: string;
  weeklyCommitmentMinutes: number;
  phases: StudyPlanPhase[];
  topics: StudyPlanTopic[];
  revisionSchedule: StudyPlanRevisionItem[];
  rationale: string;
};

export type StudyPlanGenerationMetadata = {
  provider?: string | null;
  model?: string | null;
  usedFallback: boolean;
  fallbackReason?: string | null;
};

export type StudyPlanRecord = {
  planUuid: string;
  learnerId: number;
  title: string;
  status: "active" | "archived";
  input: StudyPlanCreatePayload;
  planContent: StudyPlanContent;
  generation: StudyPlanGenerationMetadata;
  adjustmentNotes?: string | null;
  createdAt: string;
  updatedAt: string;
};

export type StudyPlanUpdatePayload = {
  title?: string;
  status?: "active" | "archived";
  planContent?: StudyPlanContent;
  adjustmentNotes?: string | null;
};
