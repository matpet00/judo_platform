import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useTrainer } from "../context/TrainerContext";
import { useParent } from "../context/ParentContext";
import type { Notification } from "../api/types";

type Role = "trainer" | "parent";

function formatWhen(value: string): string {
  return new Date(value).toLocaleString("cs-CZ", {
    day: "numeric",
    month: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function NotificationBell() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { trainer, isAuthenticated: trainerAuth } = useTrainer();
  const { parent, isAuthenticated: parentAuth } = useParent();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  const role: Role | null = trainerAuth && trainer ? "trainer" : parentAuth && parent ? "parent" : null;
  const queryKey = role === "parent" ? ["parent-notifications", parent?.id] : ["notifications"];

  const notificationsQuery = useQuery({
    queryKey,
    queryFn: () => api.notifications(role ?? "trainer"),
    enabled: role != null,
    refetchInterval: 30_000,
  });

  const markRead = useMutation({
    mutationFn: (id: number) => api.markNotificationRead(id, role ?? "trainer"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  const markAllRead = useMutation({
    mutationFn: async (ids: number[]) => {
      await Promise.all(ids.map((id) => api.markNotificationRead(id, role ?? "trainer")));
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  // Opening the panel means the badge items have been seen: mark them read.
  useEffect(() => {
    if (!open) return;
    const unreadIds = (notificationsQuery.data ?? []).filter((n) => n.unread).map((n) => n.id);
    if (unreadIds.length > 0) markAllRead.mutate(unreadIds);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (role == null) return null;

  const items = [...(notificationsQuery.data ?? [])].sort(
    (a, b) => new Date(b.last_activity_at).getTime() - new Date(a.last_activity_at).getTime(),
  );
  const unread = items.filter((n) => n.unread).length;

  const openItem = (n: Notification) => {
    if (n.unread) markRead.mutate(n.id);
    setOpen(false);
    if (n.event_id != null) {
      navigate(`${role === "parent" ? "/parent/events" : "/events"}?event=${n.event_id}`);
    } else {
      navigate(`${role === "parent" ? "/parent/board" : "/board"}?notif=${n.id}`);
    }
  };

  return (
    <div className="notif-bell" ref={rootRef}>
      <button
        type="button"
        className="notif-bell__btn"
        aria-label="Notifikace"
        onClick={() => setOpen((o) => !o)}
      >
        <span aria-hidden>🔔</span>
        {unread > 0 && <span className="notif-bell__count">{unread > 99 ? "99+" : unread}</span>}
      </button>

      {open && (
        <div className="notif-bell__panel">
          <div className="notif-bell__head">
            Notifikace
            {unread > 0 && <span className="notif-bell__head-count">{unread} nepřečtených</span>}
          </div>
          <div className="notif-bell__list">
            {notificationsQuery.isLoading && <div className="notif-bell__empty">Načítám…</div>}
            {!notificationsQuery.isLoading && items.length === 0 && (
              <div className="notif-bell__empty">Žádné notifikace.</div>
            )}
            {items.slice(0, 20).map((n) => {
              const isReply = n.comment_count > 0 && n.last_comment_preview != null;
              return (
                <button
                  key={n.id}
                  type="button"
                  className={`notif-bell__item${n.unread ? " is-unread" : ""}`}
                  onClick={() => openItem(n)}
                >
                  {n.unread && <span className="notif-bell__dot" aria-hidden />}
                  {isReply && <span className="notif-bell__tag">Nová odpověď ve vlákně</span>}
                  <span className="notif-bell__item-title">{n.title}</span>
                  {n.author_trainer && (
                    <span className="notif-bell__item-author">
                      od {n.author_trainer.first_name} {n.author_trainer.last_name}
                    </span>
                  )}
                  <span className="notif-bell__item-body">
                    {isReply ? `${n.last_comment_author}: ${n.last_comment_preview}` : n.body}
                  </span>
                  <span className="notif-bell__item-time">{formatWhen(n.last_activity_at)}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
