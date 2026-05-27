import type { AttendanceStatus, AttendanceSummary } from "./types";
import { parseApiError } from "../lib/apiError";
import { getTrainerToken } from "../lib/auth";

const BASE = import.meta.env.VITE_API_URL ?? "/api";
const WRITE_KEY = import.meta.env.VITE_API_WRITE_KEY ?? "";

function buildHeaders(mutating: boolean): HeadersInit {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (mutating && WRITE_KEY) {
    headers["X-API-Key"] = WRITE_KEY;
  }
  if (mutating) {
    const token = getTrainerToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

async function request<T>(path: string, init?: RequestInit, mutating = false): Promise<T> {
  const attempt = async () => {
    const res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        ...buildHeaders(mutating),
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
