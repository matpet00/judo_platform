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
  active_from?: string | null;
  active_until?: string | null;
  branch: { id: number; name: string; address: string };
  students: StudentBrief[];
  trainers: TrainerBrief[];
}

export interface TrainingGroupCreate {
  branch_id: number;
  name: string;
  start_time: string;
  end_time: string;
  weekdays: number[] | null;
  active_from?: string | null;
  active_until?: string | null;
  student_ids: number[];
  trainer_ids?: number[];
}

export interface TrainingGroupUpdate {
  branch_id?: number;
  name?: string;
  start_time?: string;
  end_time?: string;
  weekdays?: number[] | null;
  active_from?: string | null;
  active_until?: string | null;
}

export interface TrainingOccurrence {
  group_id: number;
  name: string;
  branch_id: number;
  date: string;
  start_time: string;
  end_time: string;
  session_id: number | null;
  canceled: boolean;
  roster_count: number;
  marked_count: number;
  guest_count: number;
}

export interface TrainingOccurrenceComment {
  id: number;
  training_group_id: number;
  training_date: string;
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

export interface AttendanceMonthlyReportRow {
  student_id: number;
  name: string;
  present: number;
  absent: number;
  excused: number;
  sessions: number;
  is_guest?: boolean;
}

export interface AttendanceMonthlyReport {
  group_id?: number | null;
  branch_id?: number | null;
  month: string;
  sessions: number;
  group_count?: number;
  rows: AttendanceMonthlyReportRow[];
}

export interface StudentGuardian {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
}

export interface StudentWithBranches {
  id: number;
  first_name: string;
  last_name: string;
  age_group: AgeGroup;
  birth_date?: string | null;
  birth_number?: string | null;
  health_insurance?: string | null;
  branches: BranchBrief[];
  parents?: StudentGuardian[];
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

export interface BranchDetail extends BranchBrief {
  created_at?: string;
  updated_at?: string;
  students?: StudentBrief[];
  trainers?: TrainerBrief[];
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
  is_guest?: boolean;
  home_branch?: string | null;
}

export interface SessionTrainer {
  id: number;
  first_name: string;
  last_name: string;
  attendance: AttendanceSummary | null;
  branches?: string | null;
  is_guest?: boolean;
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
  canceled?: boolean;
  training_group: {
    id: number;
    name: string;
    start_time: string;
    end_time: string;
  };
  branch: { id: number; name: string };
  students: SessionStudent[];
  trainers: SessionTrainer[];
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
  author_parent_id: number | null;
  event_id: number | null;
  training_group_id: number | null;
  training_date: string | null;
  visible_until: string;
  hide_after: string;
  visibility_state: NotificationVisibilityState;
  last_activity_at: string;
  created_at: string;
  updated_at: string;
  author_trainer: TrainerBrief | null;
  author_parent: ParentBrief | null;
  targets: NotificationTarget[];
  can_delete: boolean;
  can_edit: boolean;
  unread: boolean;
  has_read: boolean;
  comment_count: number;
  last_comment_author: string | null;
  last_comment_preview: string | null;
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

export type EventType = "tournament" | "training" | "meeting" | "seminar" | "other";
export type RsvpStatus = "yes" | "no" | "maybe";

export interface EventTarget {
  id: number;
  audience: NotificationAudience;
  branch_id: number | null;
  age_group: AgeGroup | null;
}

export interface EventComment {
  id: number;
  event_id: number;
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

export interface EventAttachment {
  id: number;
  event_id: number;
  filename: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
  can_delete: boolean;
}

export interface EventRsvpParticipant {
  kind: ChatParticipantKind;
  id: number;
  name: string;
  status: RsvpStatus;
  student_id?: number | null;
  child_name?: string | null;
}

export interface EventChildRsvp {
  student_id: number;
  name: string;
  status: RsvpStatus | null;
}

export interface EventRsvpResponse {
  student_id: number | null;
  status: RsvpStatus;
}

export interface EventRsvpSummary {
  yes: number;
  no: number;
  maybe: number;
  participants: EventRsvpParticipant[];
}

export interface EventItem {
  id: number;
  title: string;
  description: string;
  event_type: EventType;
  location: string;
  starts_at: string;
  ends_at: string | null;
  author_trainer_id: number | null;
  created_at: string;
  updated_at: string;
  author_trainer: TrainerBrief | null;
  targets: EventTarget[];
  can_edit: boolean;
  my_rsvp: RsvpStatus | null;
  my_child_rsvps: EventChildRsvp[];
  comment_count: number;
  attachment_count: number;
}

export interface EventDetail extends EventItem {
  comments: EventComment[];
  attachments: EventAttachment[];
  rsvp_summary: EventRsvpSummary | null;
}

export interface EventTargetCreate {
  audience: NotificationAudience;
  branch_id?: number | null;
  age_group?: AgeGroup | null;
}

export interface EventCreate {
  title: string;
  description?: string;
  event_type: EventType;
  location?: string;
  starts_at: string;
  ends_at?: string | null;
  targets: EventTargetCreate[];
}

export interface ChildRegistrationInput {
  first_name: string;
  last_name: string;
  birth_date: string;
  birth_number: string;
  health_insurance: string;
  branch_ids: number[];
}

export interface ClubRegistrationCreate {
  parent_first_name: string;
  parent_last_name: string;
  email: string;
  phone: string;
  second_guardian?: {
    first_name: string;
    last_name: string;
    email: string;
    phone: string;
  } | null;
  children: ChildRegistrationInput[];
}

export interface GuardianCredentialsRead {
  parent_id: number;
  first_name: string;
  last_name: string;
  email: string;
  username: string;
  password: string | null;
  credentials_created: boolean;
  credentials_email_sent: boolean;
  credentials_email_error: string | null;
}

export interface ClubRegistrationRead {
  parent_id: number;
  students: StudentWithBranches[];
  existing_parent: boolean;
  username: string | null;
  password: string | null;
  credentials_created: boolean;
  credentials_email_sent: boolean;
  credentials_email_error: string | null;
  second_guardian: GuardianCredentialsRead | null;
  access_token: string | null;
  token_type: string | null;
  expires_at: string | null;
  parent_id_token: number | null;
  message: string | null;
}

export interface RegistrationSubmittedRead {
  request_id: number;
  message: string;
  confirmation_email_sent: boolean;
  confirmation_email_error: string | null;
}

export interface RegistrationStatusRead {
  status: "none" | "pending" | "approved" | "rejected";
  message: string;
  rejection_reason: string | null;
  request_id: number | null;
  reviewed_at: string | null;
}

export interface RegistrationRequestChildRead {
  first_name: string;
  last_name: string;
  birth_date: string;
  birth_number: string;
  health_insurance: string;
  branch_names: string[];
  age_group: AgeGroup;
}

export interface RegistrationRequestListItem {
  id: number;
  status: "pending" | "approved" | "rejected";
  parent_first_name: string;
  parent_last_name: string;
  parent_email: string;
  parent_phone: string;
  children_count: number;
  has_second_guardian: boolean;
  created_at: string;
  reviewed_at: string | null;
}

export interface RegistrationRequestDetail extends RegistrationRequestListItem {
  children: RegistrationRequestChildRead[];
  second_guardian: {
    first_name: string;
    last_name: string;
    email: string;
    phone: string;
  } | null;
  rejection_reason: string | null;
  approved_parent_id: number | null;
}

export interface ParentEmailStatus {
  exists: boolean;
  has_login: boolean;
}

export interface BirthNumberStatus {
  available: boolean;
}

export interface AdminAuthToken {
  access_token: string;
  token_type: string;
  expires_at: string;
}

export interface AdminCountRow {
  label: string;
  count: number;
}

export interface AdminStats {
  trainers: number;
  students: number;
  parents: number;
  branches: number;
  training_groups: number;
  parents_without_login: number;
  pending_registrations: number;
  students_per_branch: AdminCountRow[];
  students_per_age_group: AdminCountRow[];
}

export interface ResendCredentialsRead {
  parent_id: number;
  username: string;
  password: string | null;
  email: string;
  email_sent: boolean;
  email_error: string | null;
}

export interface AdminEventParticipantRow {
  kind: "trainer" | "student";
  person_id: number;
  name: string;
  status: RsvpStatus;
  age_group?: string | null;
  parent_name?: string | null;
}

export interface AdminEventParticipation {
  event_id: number;
  title: string;
  event_type: string;
  starts_at: string;
  location: string;
  yes_count: number;
  no_count: number;
  maybe_count: number;
  trainer_yes: number;
  student_yes: number;
  participants: AdminEventParticipantRow[];
}

export interface ParentRow {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  created_at?: string;
  updated_at?: string;
}

export interface TrainerCreate {
  first_name: string;
  last_name: string;
  branch_ids: number[];
}

export interface TrainerPatch {
  first_name?: string;
  last_name?: string;
  branch_ids?: number[];
  pin?: string;
}

export interface StudentParentInput {
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
}

export interface StudentCreate {
  first_name: string;
  last_name: string;
  age_group: AgeGroup;
  birth_date?: string | null;
  birth_number?: string | null;
  health_insurance?: string | null;
  branch_ids: number[];
  parents?: StudentParentInput[];
}

export interface StudentPatch {
  first_name?: string;
  last_name?: string;
  age_group?: AgeGroup;
  birth_date?: string | null;
  birth_number?: string | null;
  health_insurance?: string | null;
  branch_ids?: number[];
  parents?: StudentParentInput[];
}

export interface BranchCreate {
  name: string;
  address: string;
}

export interface ParentPatch {
  first_name?: string;
  last_name?: string;
  email?: string;
  phone?: string;
}

export interface AgeGroupPreview {
  birth_date: string;
  reference_year: number;
  age_at_year_end: number;
  age_group: AgeGroup;
}
