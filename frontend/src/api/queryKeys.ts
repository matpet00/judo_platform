export function trainerNotificationsKey(trainerId: number | undefined) {
  return ["notifications", trainerId] as const;
}

export function parentNotificationsKey(parentId: number | undefined) {
  return ["parent-notifications", parentId] as const;
}
