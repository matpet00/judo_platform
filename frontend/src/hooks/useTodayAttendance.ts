import { useQuery } from "@tanstack/react-query";
import { api, todayIso } from "../api/client";
import type { SessionWithProgress } from "../api/types";
import { countMarked, pickNearestActiveGroup, groupsWithoutSession, sessionForGroup } from "../lib/sessionRouting";
import { countByStatus } from "../lib/attendance";

export function useTodayAttendance() {
  const date = todayIso();

  const groupsQuery = useQuery({
    queryKey: ["training-groups"],
    queryFn: () => api.trainingGroups(),
  });

  const sessionsQuery = useQuery({
    queryKey: ["training-sessions", date],
    queryFn: () => api.listSessions(date),
    enabled: groupsQuery.isSuccess,
  });

  const groups = groupsQuery.data ?? [];
  const sessions = sessionsQuery.data ?? [];

  const sessionsWithProgressQuery = useQuery({
    queryKey: ["today-sessions-progress", date, sessions.map((s) => s.id).join(",")],
    queryFn: async (): Promise<SessionWithProgress[]> => {
      const details = await Promise.all(sessions.map((s) => api.session(s.id)));
      return sessions.map((s, i) => {
        const { marked, total } = countMarked(details[i].students);
        const counts = countByStatus(details[i].students);
        return {
          ...s,
          marked,
          total,
          present: counts.present,
          absent: counts.absent,
          excused: counts.excused,
        };
      });
    },
    enabled: sessions.length > 0,
  });

  const activeGroup = groups.length ? pickNearestActiveGroup(groups) : null;
  const activeSession = activeGroup ? sessionForGroup(sessions, activeGroup.id) : undefined;
  const existingSessions = sessionsWithProgressQuery.data ?? [];
  const slotsWithoutSession = groupsWithoutSession(groups, sessions);

  return {
    date,
    groups,
    sessions,
    existingSessions,
    activeGroup,
    activeSession,
    slotsWithoutSession,
    isLoading: groupsQuery.isLoading || sessionsQuery.isLoading,
    isError: groupsQuery.isError || sessionsQuery.isError,
    error: groupsQuery.error ?? sessionsQuery.error,
    refetch: () => {
      groupsQuery.refetch();
      sessionsQuery.refetch();
    },
  };
}

export type TodayAttendance = ReturnType<typeof useTodayAttendance>;
