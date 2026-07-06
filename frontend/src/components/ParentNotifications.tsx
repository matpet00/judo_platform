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
  const queryClient = useQueryClient();
  const notificationsQuery = useQuery({
    queryKey: parentNotificationsKey(parentId),
    queryFn: () => api.notifications("parent"),
    refetchInterval: 5_000,
    refetchOnWindowFocus: true,
  });
  const branchesQuery = useQuery({
    queryKey: ["branches"],
    queryFn: () => api.branches(),
  });

  const notifications = notificationsQuery.data ?? [];
  const boardNotifications = notifications.filter(isBoardNotification);
  const pending = boardNotifications.filter((n) => n.unread).length;
  const branches = branchesQuery.data ?? [];

  const [composeOpen, setComposeOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [scope, setScope] = useState<number | "all">("all");

  const resetCompose = () => {
    setComposeOpen(false);
    setTitle("");
    setBody("");
    setScope("all");
  };

  const createMessage = useMutation({
    mutationFn: () =>
      api.createParentNotification({
        title: title.trim(),
        body: body.trim(),
        branch_id: scope === "all" ? null : scope,
      }),
    onSuccess: () => {
      resetCompose();
      queryClient.invalidateQueries({ queryKey: ["parent-notifications"] });
    },
  });

  const canSend = Boolean(title.trim()) && Boolean(body.trim());

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

      <div className="notification-actions">
        {composeOpen ? null : (
          <button type="button" className="btn btn--primary" onClick={() => setComposeOpen(true)}>
            Napsat trenérům
          </button>
        )}
      </div>

      {composeOpen && (
        <section className="notification-compose">
          <h2>Napsat trenérům</h2>
          <label className="notification-field">
            Předmět
            <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Předmět zprávy" />
          </label>
          <label className="notification-field">
            Text
            <textarea value={body} onChange={(event) => setBody(event.target.value)} placeholder="Text zprávy" rows={4} />
          </label>
          <label className="notification-field">
            Komu
            <select
              value={scope === "all" ? "all" : String(scope)}
              onChange={(event) => setScope(event.target.value === "all" ? "all" : Number(event.target.value))}
            >
              <option value="all">Všem trenérům</option>
              {branches.map((branch) => (
                <option key={branch.id} value={branch.id}>
                  Trenéři – {branch.name}
                </option>
              ))}
            </select>
          </label>
          <div className="notification-compose__actions">
            <button type="button" className="btn btn--ghost" onClick={resetCompose}>
              Zrušit
            </button>
            <button
              type="button"
              className="btn btn--primary"
              disabled={!canSend || createMessage.isPending}
              onClick={() => createMessage.mutate()}
            >
              {createMessage.isPending ? "Odesílám…" : "Odeslat"}
            </button>
          </div>
          {createMessage.isError && <div className="error-box">{String(createMessage.error)}</div>}
        </section>
      )}

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
  const [editingNotif, setEditingNotif] = useState(false);
  const [notifTitle, setNotifTitle] = useState(notification.title);
  const [notifBody, setNotifBody] = useState(notification.body);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["parent-notification-comments", notification.id] });
    queryClient.invalidateQueries({ queryKey: ["parent-notifications"] });
  };

  const updateNotif = useMutation({
    mutationFn: () =>
      api.updateNotification(notification.id, { title: notifTitle.trim(), body: notifBody.trim() }, "parent"),
    onSuccess: () => {
      setEditingNotif(false);
      queryClient.invalidateQueries({ queryKey: ["parent-notifications"] });
    },
  });

  const deleteNotif = useMutation({
    mutationFn: () => api.deleteNotification(notification.id, "parent"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["parent-notifications"] }),
  });

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
              : notification.author_parent
                ? ` · ${notification.author_parent.first_name} ${notification.author_parent.last_name} (rodič)`
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
                {comment.author_trainer ? (
                  <>
                    {comment.author_trainer.first_name} {comment.author_trainer.last_name}
                    <span className="role-badge role-badge--trainer">trenér</span>
                  </>
                ) : comment.author_parent ? (
                  <>
                    {comment.author_parent.first_name} {comment.author_parent.last_name}
                    <span className="role-badge role-badge--parent">rodič</span>
                  </>
                ) : (
                  "Neznámý"
                )}
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

          {(notification.can_edit || notification.can_delete) && (
            <div className="notification-owner-actions">
              {editingNotif ? (
                <div className="notification-owner-edit">
                  <input value={notifTitle} onChange={(event) => setNotifTitle(event.target.value)} />
                  <textarea value={notifBody} onChange={(event) => setNotifBody(event.target.value)} rows={3} />
                  <div className="notification-comment__edit-actions">
                    <button
                      type="button"
                      className="btn btn--ghost"
                      onClick={() => {
                        setEditingNotif(false);
                        setNotifTitle(notification.title);
                        setNotifBody(notification.body);
                      }}
                    >
                      Zrušit
                    </button>
                    <button
                      type="button"
                      className="btn btn--primary"
                      disabled={!notifTitle.trim() || !notifBody.trim() || updateNotif.isPending}
                      onClick={() => updateNotif.mutate()}
                    >
                      {updateNotif.isPending ? "Ukládám…" : "Uložit"}
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  {notification.can_edit && (
                    <button
                      type="button"
                      className="notification-comment__edit-btn"
                      onClick={() => {
                        setEditingNotif(true);
                        setNotifTitle(notification.title);
                        setNotifBody(notification.body);
                      }}
                    >
                      Upravit zprávu
                    </button>
                  )}
                  {notification.can_delete && (
                    <button
                      type="button"
                      className="notification-delete"
                      disabled={deleteNotif.isPending}
                      onClick={() => deleteNotif.mutate()}
                    >
                      Smazat zprávu
                    </button>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      )}
    </article>
  );
}
