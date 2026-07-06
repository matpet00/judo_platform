import type { AttendanceStatus, AttendanceSummary, NotificationCreate } from "./types";
import { parseApiError } from "../lib/apiError";
import { getParentToken, getTrainerToken } from "../lib/auth";

const BASE = import.meta.env.VITE_API_URL ?? "/api";
const WRITE_KEY = import.meta.env.VITE_API_WRITE_KEY ?? "";

type Role = "trainer" | "parent";

function buildHeaders(mutating: boolean, authenticated = false, role: Role = "trainer"): HeadersInit {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (mutating && WRITE_KEY) {
    headers["X-API-Key"] = WRITE_KEY;
  }
  if (mutating || authenticated) {
    const token = role === "parent" ? getParentToken() : getTrainerToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

async function request<T>(
  path: string,
  init?: RequestInit,
  mutating = false,
  authenticated = false,
  role: Role = "trainer",
): Promise<T> {
  const attempt = async () => {
    const res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        ...buildHeaders(mutating, authenticated, role),
        ...(init?.headers as Record<string, string> | undefined),
      },
    });
    return res;
  };

  let res = await attempt();
  if (!res.ok && mutating && res.status >= 502 && res.status <= 504) {
    res = await attempt();
  }

  if (!res.ok) {
    const detail = await res.text();
    throw new Error(parseApiError(detail, res.statusText));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

async function uploadRequest<T>(path: string, formData: FormData, role: Role = "trainer"): Promise<T> {
  const headers: Record<string, string> = {};
  if (WRITE_KEY) headers["X-API-Key"] = WRITE_KEY;
  const token = role === "parent" ? getParentToken() : getTrainerToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { method: "POST", body: formData, headers });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(parseApiError(detail, res.statusText));
  }
  return res.json() as Promise<T>;
}

async function downloadRequest(path: string, filename: string, role: Role = "trainer"): Promise<void> {
  const headers: Record<string, string> = {};
  const token = role === "parent" ? getParentToken() : getTrainerToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { headers });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(parseApiError(detail, res.statusText));
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export { todayIso } from "../lib/sessionRouting";

export const api = {
  health: () => request<{ status: string }>("/health"),
  trainers: () => request<import("./types").Trainer[]>("/trainers"),
  parents: () => request<import("./types").Parent[]>("/parents"),
  parentLogin: (username: string, password: string) =>
    request<import("./types").ParentAuthToken>("/parents/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }, true),
  parentMe: () => request<import("./types").ParentSelf>("/parents/me", undefined, false, true, "parent"),
  parentEmailStatus: (email: string) =>
    request<import("./types").ParentEmailStatus>(
      `/register/parent-status?email=${encodeURIComponent(email)}`,
    ),
  registerToClub: (payload: import("./types").ClubRegistrationCreate) =>
    request<import("./types").ClubRegistrationRead>("/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }, true),
  previewAgeGroup: (birthDate: string, referenceYear?: number) => {
    const params = new URLSearchParams({ birth_date: birthDate });
    if (referenceYear) params.set("reference_year", String(referenceYear));
    return request<import("./types").AgeGroupPreview>(`/age-group?${params}`);
  },
  branches: () => request<import("./types").BranchBrief[]>("/branches"),
  verifyPin: (trainerId: number, pin: string) =>
    request<import("./types").TrainerAuthToken>(`/trainers/${trainerId}/verify-pin`, {
      method: "POST",
      body: JSON.stringify({ pin }),
    }, true),
  trainingGroups: (branchId?: number) =>
    request<import("./types").TrainingGroup[]>(
      branchId ? `/training-groups?branch_id=${branchId}` : "/training-groups",
      undefined,
      false,
      true,
    ),
  students: () => request<import("./types").StudentWithBranches[]>("/students"),
  trainingGroup: (id: number) =>
    request<import("./types").TrainingGroup>(`/training-groups/${id}`, undefined, false, true),
  createTrainingGroup: (payload: import("./types").TrainingGroupCreate) =>
    request<import("./types").TrainingGroup>("/training-groups", {
      method: "POST",
      body: JSON.stringify(payload),
    }, true),
  updateTrainingGroup: (id: number, payload: import("./types").TrainingGroupUpdate) =>
    request<import("./types").TrainingGroup>(`/training-groups/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }, true),
  replaceGroupStudents: (id: number, studentIds: number[]) =>
    request<import("./types").TrainingGroup>(`/training-groups/${id}/students`, {
      method: "PUT",
      body: JSON.stringify({ student_ids: studentIds }),
    }, true),
  deleteTrainingGroup: (id: number) =>
    request<void>(`/training-groups/${id}`, { method: "DELETE" }, true),
  trainingOccurrences: (fromIso: string, toIso: string, role: Role = "trainer") => {
    const params = new URLSearchParams({ from: fromIso, to: toIso });
    return request<import("./types").TrainingOccurrence[]>(
      `/training-groups/occurrences?${params}`,
      undefined,
      false,
      true,
      role,
    );
  },
  trainingOccurrenceComments: (groupId: number, date: string, role: Role = "trainer") =>
    request<import("./types").TrainingOccurrenceComment[]>(
      `/training-groups/${groupId}/occurrences/${date}/comments`,
      undefined,
      false,
      true,
      role,
    ),
  addTrainingOccurrenceComment: (groupId: number, date: string, body: string, role: Role = "trainer") =>
    request<import("./types").TrainingOccurrenceComment>(
      `/training-groups/${groupId}/occurrences/${date}/comments`,
      {
        method: "POST",
        body: JSON.stringify({ body }),
      },
      true,
      false,
      role,
    ),
  updateTrainingOccurrenceComment: (
    groupId: number,
    date: string,
    commentId: number,
    body: string,
    role: Role = "trainer",
  ) =>
    request<import("./types").TrainingOccurrenceComment>(
      `/training-groups/${groupId}/occurrences/${date}/comments/${commentId}`,
      {
        method: "PATCH",
        body: JSON.stringify({ body }),
      },
      true,
      false,
      role,
    ),
  deleteTrainingOccurrenceComment: (groupId: number, date: string, commentId: number, role: Role = "trainer") =>
    request<void>(
      `/training-groups/${groupId}/occurrences/${date}/comments/${commentId}`,
      { method: "DELETE" },
      true,
      false,
      role,
    ),
  cancelOccurrence: (sessionId: number, canceled: boolean) =>
    request<import("./types").TrainingSessionSummary>(
      `/training-sessions/${sessionId}/cancel?canceled=${canceled}`,
      { method: "POST" },
      true,
    ),
  attendanceReport: (groupId: number, month: string) =>
    request<import("./types").AttendanceMonthlyReport>(
      `/training-groups/${groupId}/attendance-report?month=${month}`,
      undefined,
      false,
      true,
    ),
  listSessions: (sessionDate: string, branchId?: number) => {
    const params = new URLSearchParams({ session_date: sessionDate });
    if (branchId) params.set("branch_id", String(branchId));
    return request<import("./types").TrainingSessionSummary[]>(`/training-sessions?${params}`);
  },
  openGroupSession: (groupId: number, sessionDate: string, trainerId?: number) =>
    request<import("./types").TrainingSessionSummary>(`/training-groups/${groupId}/sessions`, {
      method: "POST",
      body: JSON.stringify({
        session_date: sessionDate,
        ...(trainerId ? { trainer_id: trainerId } : {}),
      }),
    }, true),
  session: (id: number) =>
    request<import("./types").TrainingSessionDetail>(`/training-sessions/${id}`),
  setAttendance: async (
    sessionId: number,
    studentId: number,
    status: AttendanceStatus,
    attendanceId?: number,
    recordedById?: number,
  ): Promise<AttendanceSummary> => {
    const trainerField = recordedById ? { recorded_by_id: recordedById } : {};

    const patch = (id: number) =>
      request<import("./types").AttendanceRecordRead>(
        `/training-sessions/${sessionId}/attendance/${id}`,
        { method: "PATCH", body: JSON.stringify({ status, ...trainerField }) },
        true,
      );

    const post = () =>
      request<import("./types").AttendanceRecordRead>(`/training-sessions/${sessionId}/attendance`, {
        method: "POST",
        body: JSON.stringify({ student_id: studentId, status, ...trainerField }),
      }, true);

    if (attendanceId != null && attendanceId > 0) {
      const record = await patch(attendanceId);
      return toSummary(record);
    }

    try {
      const record = await post();
      return toSummary(record);
    } catch (error) {
      const message = String(error);
      if (!message.includes("already exists") && !message.includes("409")) throw error;
      const session = await request<import("./types").TrainingSessionDetail>(`/training-sessions/${sessionId}`);
      const student = session.students.find((s) => s.id === studentId);
      if (!student?.attendance?.id) throw error;
      const record = await patch(student.attendance.id);
      return toSummary(record);
    }
  },
  deleteAttendance: (sessionId: number, attendanceId: number) =>
    request<void>(
      `/training-sessions/${sessionId}/attendance/${attendanceId}`,
      { method: "DELETE" },
      true,
    ),
  notifications: (role: Role = "trainer") =>
    request<import("./types").Notification[]>("/notifications", undefined, false, true, role),
  createNotification: (payload: NotificationCreate) =>
    request<import("./types").Notification>("/notifications", {
      method: "POST",
      body: JSON.stringify(payload),
    }, true),
  deleteNotification: (id: number) =>
    request<void>(`/notifications/${id}`, { method: "DELETE" }, true),
  markNotificationRead: (id: number, role: Role = "trainer") =>
    request<import("./types").Notification>(`/notifications/${id}/read`, { method: "POST" }, true, false, role),
  notificationComments: (id: number, role: Role = "trainer") =>
    request<import("./types").NotificationComment[]>(`/notifications/${id}/comments`, undefined, false, true, role),
  addNotificationComment: (id: number, body: string, role: Role = "trainer") =>
    request<import("./types").NotificationComment>(`/notifications/${id}/comments`, {
      method: "POST",
      body: JSON.stringify({ body }),
    }, true, false, role),
  updateNotificationComment: (notificationId: number, commentId: number, body: string, role: Role = "trainer") =>
    request<import("./types").NotificationComment>(`/notifications/${notificationId}/comments/${commentId}`, {
      method: "PATCH",
      body: JSON.stringify({ body }),
    }, true, false, role),
  deleteNotificationComment: (notificationId: number, commentId: number, role: Role = "trainer") =>
    request<void>(`/notifications/${notificationId}/comments/${commentId}`, { method: "DELETE" }, true, false, role),
  chatContacts: (role: Role = "trainer") =>
    request<import("./types").ChatContact[]>("/chat/contacts", undefined, false, true, role),
  chatConversations: (role: Role = "trainer") =>
    request<import("./types").ChatConversation[]>("/chat/conversations", undefined, false, true, role),
  startConversation: (counterpartKind: import("./types").ChatParticipantKind, counterpartId: number, role: Role = "trainer") =>
    request<import("./types").ChatConversation>("/chat/conversations", {
      method: "POST",
      body: JSON.stringify({ counterpart_kind: counterpartKind, counterpart_id: counterpartId }),
    }, true, false, role),
  chatMessages: (conversationId: number, role: Role = "trainer", afterId?: number) =>
    request<import("./types").ChatMessage[]>(
      `/chat/conversations/${conversationId}/messages${afterId ? `?after_id=${afterId}` : ""}`,
      undefined,
      false,
      true,
      role,
    ),
  sendChatMessage: (conversationId: number, body: string, role: Role = "trainer") =>
    request<import("./types").ChatMessage>(`/chat/conversations/${conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify({ body }),
    }, true, false, role),
  markConversationRead: (conversationId: number, role: Role = "trainer") =>
    request<import("./types").ChatConversation>(`/chat/conversations/${conversationId}/read`, {
      method: "POST",
    }, true, false, role),
  deleteConversation: (conversationId: number, role: Role = "trainer") =>
    request<void>(`/chat/conversations/${conversationId}`, { method: "DELETE" }, true, false, role),
  editChatMessage: (conversationId: number, messageId: number, body: string, role: Role = "trainer") =>
    request<import("./types").ChatMessage>(`/chat/conversations/${conversationId}/messages/${messageId}`, {
      method: "PATCH",
      body: JSON.stringify({ body }),
    }, true, false, role),
  deleteChatMessage: (conversationId: number, messageId: number, role: Role = "trainer") =>
    request<void>(`/chat/conversations/${conversationId}/messages/${messageId}`, { method: "DELETE" }, true, false, role),
  events: (role: Role = "trainer") =>
    request<import("./types").EventItem[]>("/events", undefined, false, true, role),
  event: (id: number, role: Role = "trainer") =>
    request<import("./types").EventDetail>(`/events/${id}`, undefined, false, true, role),
  createEvent: (payload: import("./types").EventCreate) =>
    request<import("./types").EventDetail>("/events", {
      method: "POST",
      body: JSON.stringify(payload),
    }, true),
  updateEvent: (id: number, payload: Partial<import("./types").EventCreate>) =>
    request<import("./types").EventDetail>(`/events/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }, true),
  deleteEvent: (id: number) =>
    request<void>(`/events/${id}`, { method: "DELETE" }, true),
  setRsvp: (id: number, responses: import("./types").EventRsvpResponse[], role: Role = "trainer") =>
    request<import("./types").EventDetail>(`/events/${id}/rsvp`, {
      method: "POST",
      body: JSON.stringify({ responses }),
    }, true, false, role),
  addEventComment: (id: number, body: string, role: Role = "trainer") =>
    request<import("./types").EventComment>(`/events/${id}/comments`, {
      method: "POST",
      body: JSON.stringify({ body }),
    }, true, false, role),
  updateEventComment: (eventId: number, commentId: number, body: string, role: Role = "trainer") =>
    request<import("./types").EventComment>(`/events/${eventId}/comments/${commentId}`, {
      method: "PATCH",
      body: JSON.stringify({ body }),
    }, true, false, role),
  deleteEventComment: (eventId: number, commentId: number, role: Role = "trainer") =>
    request<void>(`/events/${eventId}/comments/${commentId}`, { method: "DELETE" }, true, false, role),
  uploadEventAttachment: (eventId: number, file: File, role: Role = "trainer") => {
    const form = new FormData();
    form.append("file", file);
    return uploadRequest<import("./types").EventAttachment>(`/events/${eventId}/attachments`, form, role);
  },
  downloadEventAttachment: (eventId: number, attachmentId: number, filename: string, role: Role = "trainer") =>
    downloadRequest(`/events/${eventId}/attachments/${attachmentId}/download`, filename, role),
  deleteEventAttachment: (eventId: number, attachmentId: number, role: Role = "trainer") =>
    request<void>(`/events/${eventId}/attachments/${attachmentId}`, { method: "DELETE" }, true, false, role),
};

function toSummary(record: import("./types").AttendanceRecordRead): AttendanceSummary {
  return {
    id: record.id,
    status: record.status,
    recorded_by_id: record.recorded_by_id,
    created_at: record.created_at,
    updated_at: record.updated_at,
  };
}
