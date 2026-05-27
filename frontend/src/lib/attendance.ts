import type { AttendanceStatus, SessionStudent } from "../api/types";

export const STATUS_LABELS: Record<AttendanceStatus, string> = {
  present: "Přítomen",
  absent: "Nepřítomen",
  excused: "Omluven",
};

export const STATUS_SHORT: Record<AttendanceStatus, string> = {
  present: "Přít.",
  absent: "Nepř.",
  excused: "Oml.",
};

export type AttendanceCounts = {
  present: number;
  absent: number;
  excused: number;
  unmarked: number;
  total: number;
};

export function countByStatus(students: SessionStudent[]): AttendanceCounts {
  const counts: AttendanceCounts = {
    present: 0,
    absent: 0,
    excused: 0,
    unmarked: 0,
    total: students.length,
  };

  for (const student of students) {
    if (!student.attendance) {
      counts.unmarked += 1;
      continue;
    }
    counts[student.attendance.status] += 1;
  }

  return counts;
}

export function sortStudentsByName(students: SessionStudent[]): SessionStudent[] {
  return [...students].sort((a, b) =>
    `${a.last_name} ${a.first_name}`.localeCompare(`${b.last_name} ${b.first_name}`, "cs"),
  );
}
