export interface GlobalProfileInitRequest {
  supportRole: string;
  helpStyle: string;
  learningFocus: string;
  responseTone: string;
}

export interface GlobalProfileRead {
  learnerId: number;
  profileType: string;
  version: number | null;
  objectKey: string | null;
  content: string;
  isDefaultProfile: boolean;
  createdAt: string | null;
  updatedAt: string | null;
}
