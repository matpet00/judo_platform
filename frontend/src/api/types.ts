export type AgeGroup = "U8" | "U10" | "U12" | "U14" | "U16" | "U18";
export type AttendanceStatus = "present" | "absent" | "excused";

export interface BranchBrief {
  id: number;
  name: string;
  address: string;
}

export interface Trainer {
  id: number;
  first_name: string;
  last_name: string;
  branches: BranchBrief[];
}

export interface TrainerAuthToken {
  access_token: string;
  token_type: string;
  expires_at: string;
  trainer_id: number;
}

export interface AttendanceRecordRead {
  id: number;
  session_id: number;
  student_id: number;
  status: AttendanceStatus;
  recorded_by_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface TrainingGroup {
  id: number;
  branch_id: number;
  name: string;
  start_time: string;
  end_time: string;
  weekdays: number[] | null;
  branch: { id: number; name: string; address: string };
  students: StudentBrief[];
}

export interface StudentBrief {
  id: number;
  first_name: string;
  last_name: string;
  age_group: AgeGroup;
}

export interface AttendanceSummary {
  id: number;
  status: AttendanceStatus;
  recorded_by_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface SessionStudent {
  id: number;
  first_name: string;
  last_name: string;
  age_group: AgeGroup;
  attendance: AttendanceSummary | null;
}

export interface TrainingSessionSummary {
  id: number;
  branch_id: number;
  training_group_id: number;
  trainer_id: number | null;
  starts_at: string;
  notes: string | null;
  branch: { id: number; name: string; address: string };
  training_group: {
    id: number;
    branch_id: number;
    name: string;
    start_time: string;
    end_time: string;
    weekdays: number[] | null;
  };
}

export interface TrainingSessionDetail {
  id: number;
  branch_id: number;
  training_group_id: number;
  trainer_id: number | null;
  starts_at: string;
  notes: string | null;
  training_group: {
    id: number;
    name: string;
    start_time: string;
    end_time: string;
  };
  branch: { id: number; name: string };
  students: SessionStudent[];
}

export interface SessionWithProgress extends TrainingSessionSummary {
  marked: number;
  total: number;
  present: number;
  absent: number;
  excused: number;
}
