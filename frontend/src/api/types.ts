export type AgeGroup = "U8" | "U10" | "U12" | "U14" | "U16" | "U18";
export type AttendanceStatus = "present" | "absent" | "excused";
export type NotificationAudience = "trainer" | "parent";
export type NotificationDurationUnit = "seconds" | "minutes" | "hours" | "days" | "weeks" | "months";
export type NotificationVisibilityState = "active" | "expired";

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

export interface Parent {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
}

export interface TrainerAuthToken {
  access_token: string;
  token_type: string;
  expires_at: string;
  trainer_id: number;
}

export interface ParentAuthToken {
  access_token: string;
  token_type: string;
  expires_at: string;
  parent_id: number;
}

export interface ParentChild {
  id: number;
  first_name: string;
  last_name: string;
  age_group: AgeGroup;
  branches: BranchBrief[];
}

export interface ParentSelf {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  username: string | null;
  children: ParentChild[];
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

export interface TrainerBrief {
  id: number;
  first_name: string;
  last_name: string;
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

export interface NotificationTarget {
  id: number;
  audience: NotificationAudience;
  branch_id: number | null;
  age_group: AgeGroup | null;
}

export interface Notification {
  id: number;
  title: string;
  body: string;
  author_trainer_id: number | null;
  visible_until: string;
  hide_after: string;
  visibility_state: NotificationVisibilityState;
  last_activity_at: string;
  created_at: string;
  updated_at: string;
  author_trainer: TrainerBrief | null;
  targets: NotificationTarget[];
  can_delete: boolean;
  unread: boolean;
  has_read: boolean;
  comment_count: number;
}

export interface ParentBrief {
  id: number;
  first_name: string;
  last_name: string;
}

export type ChatParticipantKind = "trainer" | "parent";

export interface ChatContact {
  kind: ChatParticipantKind;
  id: number;
  name: string;
  subtitle: string | null;
}

export interface ChatParticipantBrief {
  kind: ChatParticipantKind;
  id: number;
  name: string;
}

export interface ChatMessage {
  id: number;
  conversation_id: number;
  sender_kind: ChatParticipantKind | null;
  sender_id: number | null;
  sender_name: string | null;
  body: string;
  created_at: string;
  updated_at: string;
}

export interface ChatConversation {
  id: number;
  is_group: boolean;
  counterpart: ChatParticipantBrief | null;
  last_message: ChatMessage | null;
  last_message_at: string | null;
  unread_count: number;
  created_at: string;
}

export interface NotificationComment {
  id: number;
  notification_id: number;
  author_trainer_id: number | null;
  author_parent_id: number | null;
  body: string;
  created_at: string;
  updated_at: string;
  author_trainer: TrainerBrief | null;
  author_parent: ParentBrief | null;
  can_delete: boolean;
  can_edit: boolean;
}

export interface NotificationTargetCreate {
  audience: NotificationAudience;
  branch_id?: number | null;
  age_group?: AgeGroup | null;
}

export interface NotificationCreate {
  title: string;
  body: string;
  targets: NotificationTargetCreate[];
  visible_until?: string | null;
  duration_amount?: number | null;
  duration_unit?: NotificationDurationUnit | null;
  keep_after_expiry?: boolean;
  grace_amount?: number | null;
  grace_unit?: NotificationDurationUnit | null;
}
