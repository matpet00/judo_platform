import type { Notification } from "../api/types";

type Role = "trainer" | "parent";

export const TRAINING_SCHEDULE_ALERT_TITLES = new Set(["Zrušený trénink", "Trénink zrušen"]);

export function isTrainingScheduleAlert(notification: Notification): boolean {
  return TRAINING_SCHEDULE_ALERT_TITLES.has(notification.title);
}

/** Akce v plánovači: eventy + zrušené/změněné tréninky */
export function isPlannerNotification(notification: Notification): boolean {
  if (notification.event_id != null) return true;
  if (notification.training_group_id != null && notification.training_date != null) return true;
  return isTrainingScheduleAlert(notification);
}

export function isBoardNotification(notification: Notification): boolean {
  return !isPlannerNotification(notification);
}

export function countUnreadPlanner(notifications: Notification[]): number {
  return notifications.filter((n) => n.unread && isPlannerNotification(n)).length;
}

export function countUnreadBoard(notifications: Notification[]): number {
  return notifications.filter((n) => n.unread && isBoardNotification(n)).length;
}

export function occurrenceListKey(groupId: number, dateStr: string): string {
  const date = dateStr.split("T")[0];
  return `training:${groupId}:${date}`;
}

export function trainingOccurrenceEventsPath(
  role: Role,
  groupId: number,
  dateStr: string,
): string {
  const base = role === "parent" ? "/parent/events" : "/events";
  const date = dateStr.split("T")[0];
  return `${base}?training=${groupId}&date=${date}`;
}

export function notificationDestination(notification: Notification, role: Role): string {
  const eventsHome = role === "parent" ? "/parent/events" : "/events";
  if (notification.training_group_id != null && notification.training_date) {
    return trainingOccurrenceEventsPath(role, notification.training_group_id, notification.training_date);
  }
  if (isTrainingScheduleAlert(notification)) {
    return eventsHome;
  }
  if (notification.event_id != null) {
    return `${eventsHome}?event=${notification.event_id}`;
  }
  return `${role === "parent" ? "/parent/board" : "/board"}?notif=${notification.id}`;
}

export function isTrainingCancelNotification(notification: Notification): boolean {
  return (
    (notification.training_group_id != null && notification.training_date != null)
    || isTrainingScheduleAlert(notification)
  );
}
