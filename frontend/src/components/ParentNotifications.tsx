import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import {
  isBoardNotification,
  isTrainingCancelNotification,
  trainingOccurrenceEventsPath,
} from "../lib/notificationNavigation";
import { parentNotificationsKey } from "../api/queryKeys";
import type { Notification } from "../api/types";

type NotificationState = "new" | "reply" | "soon" | "read";

function notificationState(notification: Notification): NotificationState {
  if (notification.unread) return notification.has_read ? "reply" : "new";
  const created = new Date(notification.created_at).getTime();
  const hide = new Date(notification.hide_after).getTime();
  const total = hide - created;
  if (total > 0 && hide - Date.now() <= 0.2 * total) return "soon";
  return "read";
}

const stateBadge: Record<NotificationState, { label: string; className: string }> = {
  new: { label: "Nové", className: "notification-badge--new" },
  reply: { label: "Nová odpověď ve vlákně", className: "notification-badge--reply" },
  soon: { label: "Brzy bude smazáno", className: "notification-badge--soon" },
  read: { label: "Přečteno", className: "notification-badge--read" },
};

function formatDate(value: string): string {
  return new Date(value).toLocaleString("cs-CZ", {
    day: "numeric",
    month: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ParentNotifications({ parentId }: { parentId: number }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const notificationsQuery = useQuery({
    queryKey: parentNotificationsKey(parentId),
    queryFn: () => api.notifications("parent"),
    refetchInterval: 5_000,
    refetchOnWindowFocus: true,
  });

  const notifications = notificationsQuery.data ?? [];
  const boardNotifications = notifications.filter(isBoardNotification);
  const pending = boardNotifications.filter((n) => n.unread).length;

  const [highlightId, setHighlightId] = useState<number | null>(null);
  useEffect(() => {
    const id = Number(searchParams.get("notif"));
    if (Number.isFinite(id) && id > 0) setHighlightId(id);
    if (!searchParams.has("notif")) return;
    searchParams.delete("notif");
    setSearchParams(searchParams, { replace: true });
  }, [searchParams, setSearchParams]);

  return (
    <section className="notification-list parent-notifications">
      <h2 className="parent-notifications__title">
        Notifikace
        {pending > 0 && <span className="notification-pending">{pending}</span>}
      </h2>
      {notificationsQuery.isLoading && <div className="loading">Načítám…</div>}
      {notificationsQuery.isError && (
        <div className="error-box">Notifikace se nepodařilo načíst.</div>
      )}
      {boardNotifications.map((notification) => (
        <ParentNotificationCard
          key={notification.id}
          notification={notification}
          parentId={parentId}
          autoOpen={notification.id === highlightId}
        />
      ))}
      {!notificationsQuery.isLoading && boardNotifications.length === 0 && (
        <div className="loading">Zatím tu nejsou žádné notifikace pro tvoje děti.</div>
      )}
    </section>
  );
}

function ParentNotificationCard({
  notification,
  parentId,
  autoOpen = false,
}: {
  notification: Notification;
  parentId: number;
  autoOpen?: boolean;
}) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(false);
  const cardRef = useRef<HTMLElement | null>(null);
  const [reply, setReply] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editText, setEditText] = useState("");

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["parent-notification-comments", notification.id] });
    queryClient.invalidateQueries({ queryKey: ["parent-notifications"] });
  };

  const commentsQuery = useQuery({
    queryKey: ["parent-notification-comments", notification.id, parentId],
    queryFn: () => api.notificationComments(notification.id, "parent"),
    enabled: expanded,
  });

  const markRead = useMutation({
    mutationFn: () => api.markNotificationRead(notification.id, "parent"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["parent-notifications"] }),
  });

  const addComment = useMutation({
    mutationFn: (body: string) => api.addNotificationComment(notification.id, body, "parent"),
    onSuccess: () => {
      setReply("");
      invalidate();
    },
  });

  const deleteComment = useMutation({
    mutationFn: (commentId: number) => api.deleteNotificationComment(notification.id, commentId, "parent"),
    onSuccess: invalidate,
  });

  const updateComment = useMutation({
    mutationFn: ({ commentId, body }: { commentId: number; body: string }) =>
      api.updateNotificationComment(notification.id, commentId, body, "parent"),
    onSuccess: () => {
      setEditingId(null);
      setEditText("");
      invalidate();
    },
  });

  const toggle = () => {
    const next = !expanded;
    setExpanded(next);
    if (next && notification.unread) markRead.mutate();
  };

  useEffect(() => {
    if (!autoOpen) return;
    setExpanded(true);
    if (notification.unread) markRead.mutate();
    cardRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoOpen]);

  const badge = stateBadge[notificationState(notification)];
  const comments = commentsQuery.data ?? [];
  const isExpired = notification.visibility_state === "expired";

  return (
    <article
      ref={cardRef}
      className={`notification-card${isExpired ? " notification-card--expired" : ""}${autoOpen ? " notification-card--highlight" : ""}`}
    >
      <button type="button" className="notification-card__head" onClick={toggle}>
        <div>
          <span className="notification-card__meta">
            {formatDate(notification.created_at)}
            {notification.author_trainer
              ? ` · ${notification.author_trainer.first_name} ${notification.author_trainer.last_name}`
              : ""}
          </span>
          <h3>{notification.title}</h3>
          <p>{notification.body}</p>
          <small>
            {isExpired ? "expirováno" : `platí do ${formatDate(notification.visible_until)}`}
          </small>
        </div>
        <div className="notification-card__side">
          <span className={`notification-badge ${badge.className}`}>{badge.label}</span>
          <span className="notification-card__comments">
            {notification.comment_count > 0 ? `${notification.comment_count} 💬` : ""}
          </span>
          <span className="notification-card__chevron">{expanded ? "▲" : "▼"}</span>
        </div>
      </button>

      {notification.event_id != null && (
        <div className="notification-card__event-action">
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => {
              if (notification.unread) markRead.mutate();
              navigate(`/parent/events?event=${notification.event_id}`);
            }}
          >
            Otevřít akci a potvrdit účast
          </button>
        </div>
      )}

      {isTrainingCancelNotification(notification) && (
        <div className="notification-card__event-action">
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => {
              if (notification.unread) markRead.mutate();
              navigate(
                trainingOccurrenceEventsPath(
                  "parent",
                  notification.training_group_id as number,
                  notification.training_date as string,
                ),
              );
            }}
          >
            Zobrazit zrušený trénink
          </button>
        </div>
      )}

      {expanded && (
        <div className="notification-thread">
          {commentsQuery.isLoading && <div className="loading">Načítám…</div>}
          {comments.map((comment) => (
            <div className="notification-comment" key={comment.id}>
              <span className="notification-comment__meta">
                {comment.author_trainer
                  ? `${comment.author_trainer.first_name} ${comment.author_trainer.last_name}`
                  : comment.author_parent
                    ? `${comment.author_parent.first_name} ${comment.author_parent.last_name} (rodič)`
                    : "Neznámý"}
                {" · "}
                {formatDate(comment.created_at)}
                {comment.updated_at !== comment.created_at ? " · upraveno" : ""}
              </span>
              {editingId === comment.id ? (
                <div className="notification-comment__edit">
                  <textarea value={editText} onChange={(event) => setEditText(event.target.value)} rows={2} />
                  <div className="notification-comment__edit-actions">
                    <button
                      type="button"
                      className="btn btn--ghost"
                      onClick={() => {
                        setEditingId(null);
                        setEditText("");
                      }}
                    >
                      Zrušit
                    </button>
                    <button
                      type="button"
                      className="btn btn--primary"
                      disabled={!editText.trim() || updateComment.isPending}
                      onClick={() => updateComment.mutate({ commentId: comment.id, body: editText })}
                    >
                      {updateComment.isPending ? "Ukládám…" : "Uložit"}
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <p>{comment.body}</p>
                  {(comment.can_edit || comment.can_delete) && (
                    <div className="notification-comment__actions">
                      {comment.can_edit && (
                        <button
                          type="button"
                          className="notification-comment__edit-btn"
                          onClick={() => {
                            setEditingId(comment.id);
                            setEditText(comment.body);
                          }}
                        >
                          Upravit
                        </button>
                      )}
                      {comment.can_delete && (
                        <button
                          type="button"
                          className="notification-comment__delete"
                          disabled={deleteComment.isPending}
                          onClick={() => deleteComment.mutate(comment.id)}
                        >
                          Smazat
                        </button>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
          {!commentsQuery.isLoading && comments.length === 0 && (
            <div className="notification-thread__empty">Zatím žádné reakce.</div>
          )}

          {isExpired ? (
            <div className="notification-thread__closed">
              Notifikace expirovala – reakce už nelze přidávat.
            </div>
          ) : (
            <div className="notification-thread__reply">
              <textarea
                value={reply}
                onChange={(event) => setReply(event.target.value)}
                placeholder="Napiš reakci…"
                rows={2}
              />
              <button
                type="button"
                className="btn btn--primary"
                disabled={!reply.trim() || addComment.isPending}
                onClick={() => addComment.mutate(reply)}
              >
                {addComment.isPending ? "Odesílám…" : "Odeslat"}
              </button>
            </div>
          )}
        </div>
      )}
    </article>
  );
}
