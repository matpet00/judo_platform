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
  branches: () => request<import("./types").BranchBrief[]>("/branches"),
  verifyPin: (trainerId: number, pin: string) =>
    request<import("./types").TrainerAuthToken>(`/trainers/${trainerId}/verify-pin`, {
      method: "POST",
      body: JSON.stringify({ pin }),
    }, true),
  trainingGroups: (branchId?: number) =>
    request<import("./types").TrainingGroup[]>(
      branchId ? `/training-groups?branch_id=${branchId}` : "/training-groups",
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
