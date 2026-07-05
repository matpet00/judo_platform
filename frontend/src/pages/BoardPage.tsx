import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { AgeGroup, Notification, NotificationDurationUnit, NotificationTargetCreate } from "../api/types";
import { TrainerSwitcher } from "../components/TrainerSwitcher";
import { useTrainer } from "../context/TrainerContext";

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

type ScopeValue = number | "all";
type RecipientValue = "everyone" | "trainer" | "parent";

const AGE_GROUPS: AgeGroup[] = ["U8", "U10", "U12", "U14", "U16", "U18"];

function formatDate(value: string) {
  return new Date(value).toLocaleString("cs-CZ", {
    day: "numeric",
    month: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function targetKey(target: NotificationTargetCreate) {
  return `${target.audience}:${target.branch_id ?? "all"}:${target.age_group ?? "all"}`;
}

function recipientLabel(target: NotificationTargetCreate) {
  if (target.audience === "trainer") return "Trenéři";
  return target.age_group ? `Rodiče (${target.age_group})` : "Rodiče";
}

function toDatetimeLocalValue(date: Date) {
  const offsetMs = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
}

const durationUnits: { value: NotificationDurationUnit; label: string }[] = [
  { value: "seconds", label: "sekund" },
  { value: "minutes", label: "minut" },
  { value: "hours", label: "hodin" },
  { value: "days", label: "dnů" },
  { value: "weeks", label: "týdnů" },
  { value: "months", label: "měsíců" },
];

export function BoardPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { trainer, isAuthenticated, isLoading } = useTrainer();
  const [composeOpen, setComposeOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [scope, setScope] = useState<ScopeValue>("all");
  const [recipient, setRecipient] = useState<RecipientValue>("everyone");
  const [categories, setCategories] = useState<AgeGroup[]>([]);
  const [targets, setTargets] = useState<NotificationTargetCreate[]>([]);
  const [expiryMode, setExpiryMode] = useState<"duration" | "exact">("duration");
  const [durationAmount, setDurationAmount] = useState(7);
  const [durationUnit, setDurationUnit] = useState<NotificationDurationUnit>("days");
  const [visibleUntil, setVisibleUntil] = useState(() => toDatetimeLocalValue(new Date(Date.now() + 7 * 24 * 60 * 60 * 1000)));
  const [keepAfterExpiry, setKeepAfterExpiry] = useState(false);
  const [graceAmount, setGraceAmount] = useState(7);
  const [graceUnit, setGraceUnit] = useState<NotificationDurationUnit>("days");

  const branchesQuery = useQuery({
    queryKey: ["branches"],
    queryFn: () => api.branches(),
    enabled: isAuthenticated,
  });
  const notificationsQuery = useQuery({
    queryKey: ["notifications", trainer?.id],
    queryFn: () => api.notifications(),
    enabled: isAuthenticated,
  });

  const branches = branchesQuery.data ?? [];
  const branchName = useMemo(() => {
    const lookup = new Map(branches.map((row) => [row.id, row.name]));
    return (branchId: number | null | undefined) =>
      branchId == null ? "Všechny pobočky" : lookup.get(branchId) ?? `Pobočka #${branchId}`;
  }, [branches]);

  const resetCompose = () => {
    setComposeOpen(false);
    setTitle("");
    setBody("");
    setScope("all");
    setRecipient("everyone");
    setCategories([]);
    setTargets([]);
    setExpiryMode("duration");
    setDurationAmount(7);
    setDurationUnit("days");
    setVisibleUntil(toDatetimeLocalValue(new Date(Date.now() + 7 * 24 * 60 * 60 * 1000)));
    setKeepAfterExpiry(false);
    setGraceAmount(7);
    setGraceUnit("days");
  };

  const addTarget = () => {
    const branchId = scope === "all" ? null : scope;
    const additions: NotificationTargetCreate[] = [];
    if (recipient === "everyone" || recipient === "trainer") {
      additions.push({ audience: "trainer", branch_id: branchId });
    }
    if (recipient === "everyone" || recipient === "parent") {
      const parentGroups: (AgeGroup | null)[] = categories.length > 0 ? categories : [null];
      for (const age of parentGroups) {
        additions.push({ audience: "parent", branch_id: branchId, age_group: age });
      }
    }
    setTargets((current) => {
      const existing = new Set(current.map(targetKey));
      const merged = [...current];
      for (const target of additions) {
        if (!existing.has(targetKey(target))) {
          merged.push(target);
          existing.add(targetKey(target));
        }
      }
      return merged;
    });
  };

  const removeTarget = (key: string) => {
    setTargets((current) => current.filter((target) => targetKey(target) !== key));
  };

  const toggleCategory = (age: AgeGroup) => {
    setCategories((current) =>
      current.includes(age) ? current.filter((row) => row !== age) : [...current, age],
    );
  };

  const createNotification = useMutation({
    mutationFn: () =>
      api.createNotification({
        title,
        body,
        targets,
        ...(expiryMode === "duration"
          ? { duration_amount: durationAmount, duration_unit: durationUnit }
          : { visible_until: new Date(visibleUntil).toISOString() }),
        keep_after_expiry: keepAfterExpiry,
        ...(keepAfterExpiry ? { grace_amount: graceAmount, grace_unit: graceUnit } : {}),
      }),
    onSuccess: () => {
      resetCompose();
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const deleteNotification = useMutation({
    mutationFn: (id: number) => api.deleteNotification(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  if (!isLoading && !isAuthenticated) {
    navigate("/", { replace: true });
  }

  if (!isAuthenticated || !trainer) {
    return <div className="loading app-shell">Načítám…</div>;
  }

  const hasTarget = targets.length > 0;
  const hasValidExpiry =
    (expiryMode === "duration" ? durationAmount >= 1 : Boolean(visibleUntil)) &&
    (!keepAfterExpiry || graceAmount >= 1);

  const missing: string[] = [];
  if (!title.trim()) missing.push("předmět");
  if (!body.trim()) missing.push("text zprávy");
  if (!hasTarget) missing.push("alespoň jednoho příjemce");
  if (!hasValidExpiry) missing.push("platnou dobu zobrazení");
  const canSend = missing.length === 0;

  return (
    <div className="app-shell notification-board">
      <header className="page-header">
        <div className="page-header__row">
          <div>
            <p className="page-header__eyebrow">Board</p>
            <h1 className="page-header__title">Notifikace</h1>
            <p className="page-header__sub">Zprávy pro trenéry a rodiče</p>
          </div>
          <Link className="board-link" to="/">Menu</Link>
        </div>
      </header>

      <TrainerSwitcher variant="bar" />

      <div className="notification-actions">
        <button type="button" className="btn btn--primary" onClick={() => setComposeOpen(true)}>
          Nová notifikace
        </button>
      </div>

      {composeOpen && (
        <section className="notification-compose">
          <h2>Nová notifikace</h2>

          <label className="notification-field">
            Předmět
            <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Předmět zprávy" />
          </label>
          <label className="notification-field">
            Text
            <textarea value={body} onChange={(event) => setBody(event.target.value)} placeholder="Text zprávy" rows={4} />
          </label>

          <div className="notification-section">
            <h3 className="notification-section__title">Příjemci</h3>
            <div className="notification-targeting">
              <div className="notification-targeting__row">
                <label>
                  Pobočka
                  <select
                    value={scope === "all" ? "all" : String(scope)}
                    onChange={(event) =>
                      setScope(event.target.value === "all" ? "all" : Number(event.target.value))
                    }
                  >
                    <option value="all">Všechny pobočky</option>
                    {branches.map((branch) => (
                      <option key={branch.id} value={branch.id}>{branch.name}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Příjemci
                  <select
                    value={recipient}
                    onChange={(event) => setRecipient(event.target.value as RecipientValue)}
                  >
                    <option value="everyone">Všichni (trenéři + rodiče)</option>
                    <option value="trainer">Jen trenéři</option>
                    <option value="parent">Jen rodiče</option>
                  </select>
                </label>
              </div>
              {recipient !== "trainer" && (
                <div className="notification-categories">
                  <span className="notification-categories__label">
                    Kategorie rodičů {categories.length === 0 ? "(všechny)" : ""}
                  </span>
                  <div className="notification-categories__chips">
                    {AGE_GROUPS.map((age) => (
                      <button
                        key={age}
                        type="button"
                        className={categories.includes(age) ? "is-active" : ""}
                        onClick={() => toggleCategory(age)}
                      >
                        {age}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <button type="button" className="btn btn--ghost notification-compose__add" onClick={addTarget}>
                Přidat příjemce k odeslání
              </button>
              {targets.length > 0 && (
                <div className="notification-chips">
                  {targets.map((target) => {
                    const key = targetKey(target);
                    return (
                      <button key={key} type="button" onClick={() => removeTarget(key)}>
                        {branchName(target.branch_id)} · {recipientLabel(target)} ×
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {hasTarget && (
            <div className="notification-section">
              <h3 className="notification-section__title">Expirace zprávy</h3>
              <div className="notification-expiry">
                <div className="notification-expiry__modes">
                  <button
                    type="button"
                    className={expiryMode === "duration" ? "is-active" : ""}
                    onClick={() => setExpiryMode("duration")}
                  >
                    Délka
                  </button>
                  <button
                    type="button"
                    className={expiryMode === "exact" ? "is-active" : ""}
                    onClick={() => setExpiryMode("exact")}
                  >
                    Konkrétní datum
                  </button>
                </div>
                {expiryMode === "duration" ? (
                  <div className="notification-expiry__row">
                    <input
                      type="number"
                      min={1}
                      value={durationAmount}
                      onChange={(event) => setDurationAmount(Number(event.target.value))}
                    />
                    <select
                      value={durationUnit}
                      onChange={(event) => setDurationUnit(event.target.value as NotificationDurationUnit)}
                    >
                      {durationUnits.map((unit) => (
                        <option key={unit.value} value={unit.value}>{unit.label}</option>
                      ))}
                    </select>
                  </div>
                ) : (
                  <input
                    type="datetime-local"
                    value={visibleUntil}
                    onChange={(event) => setVisibleUntil(event.target.value)}
                  />
                )}
              </div>

              <div className="notification-grace">
                <label className="notification-grace__toggle">
                  <input
                    type="checkbox"
                    checked={keepAfterExpiry}
                    onChange={(event) => setKeepAfterExpiry(event.target.checked)}
                  />
                  Zobrazit i po expiraci
                </label>
                {keepAfterExpiry ? (
                  <div className="notification-expiry__row">
                    <input
                      type="number"
                      min={1}
                      value={graceAmount}
                      onChange={(event) => setGraceAmount(Number(event.target.value))}
                    />
                    <select
                      value={graceUnit}
                      onChange={(event) => setGraceUnit(event.target.value as NotificationDurationUnit)}
                    >
                      {durationUnits.map((unit) => (
                        <option key={unit.value} value={unit.value}>{unit.label}</option>
                      ))}
                    </select>
                  </div>
                ) : (
                  <p className="notification-grace__hint">Po expiraci se notifikace rovnou smaže.</p>
                )}
              </div>
            </div>
          )}

          <div className={`notification-compose__actions${canSend ? "" : " notification-compose__actions--single"}`}>
            <button
              className="btn btn--ghost"
              type="button"
              onClick={resetCompose}
            >
              Zrušit
            </button>
            {canSend && (
              <button
                className="btn btn--primary"
                type="button"
                disabled={createNotification.isPending}
                onClick={() => createNotification.mutate()}
              >
                {createNotification.isPending ? "Odesílám…" : "Odeslat"}
              </button>
            )}
          </div>
          {!canSend && (
            <p className="notification-compose__missing">
              Pro odeslání ještě chybí vyplnit: {missing.join(", ")}.
            </p>
          )}
          {createNotification.isError && <div className="error-box">{String(createNotification.error)}</div>}
        </section>
      )}

      <section className="notification-list">
        <h2>Existující notifikace</h2>
        {notificationsQuery.isLoading && <div className="loading">Načítám…</div>}
        {notificationsQuery.isError && <div className="error-box">{String(notificationsQuery.error)}</div>}
        {(notificationsQuery.data ?? []).map((notification) => (
          <NotificationCard
            key={notification.id}
            notification={notification}
            branchName={branchName}
            currentTrainerId={trainer.id}
            onDelete={(id) => deleteNotification.mutate(id)}
            deletePending={deleteNotification.isPending}
          />
        ))}
        {!notificationsQuery.isLoading && (notificationsQuery.data ?? []).length === 0 && (
          <div className="loading">Zatím tu nejsou žádné notifikace.</div>
        )}
      </section>
    </div>
  );
}

type NotificationCardProps = {
  notification: Notification;
  branchName: (branchId: number | null | undefined) => string;
  currentTrainerId: number;
  onDelete: (id: number) => void;
  deletePending: boolean;
};

function NotificationCard({ notification, branchName, currentTrainerId, onDelete, deletePending }: NotificationCardProps) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(false);
  const [reply, setReply] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editText, setEditText] = useState("");

  const commentsQuery = useQuery({
    queryKey: ["notification-comments", notification.id, currentTrainerId],
    queryFn: () => api.notificationComments(notification.id),
    enabled: expanded,
  });

  const markRead = useMutation({
    mutationFn: () => api.markNotificationRead(notification.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const addComment = useMutation({
    mutationFn: (body: string) => api.addNotificationComment(notification.id, body),
    onSuccess: () => {
      setReply("");
      queryClient.invalidateQueries({ queryKey: ["notification-comments", notification.id] });
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const deleteComment = useMutation({
    mutationFn: (commentId: number) => api.deleteNotificationComment(notification.id, commentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notification-comments", notification.id] });
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const updateComment = useMutation({
    mutationFn: ({ commentId, body }: { commentId: number; body: string }) =>
      api.updateNotificationComment(notification.id, commentId, body),
    onSuccess: () => {
      setEditingId(null);
      setEditText("");
      queryClient.invalidateQueries({ queryKey: ["notification-comments", notification.id] });
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const startEdit = (commentId: number, body: string) => {
    setEditingId(commentId);
    setEditText(body);
  };

  const toggle = () => {
    const next = !expanded;
    setExpanded(next);
    if (next && notification.unread) markRead.mutate();
  };

  const badge = stateBadge[notificationState(notification)];
  const comments = commentsQuery.data ?? [];
  const isExpired = notification.visibility_state === "expired";

  return (
    <article
      className={`notification-card${notification.visibility_state === "expired" ? " notification-card--expired" : ""}`}
    >
      <button type="button" className="notification-card__head" onClick={toggle}>
        <div>
          <span className="notification-card__meta">
            {formatDate(notification.created_at)}
            {notification.author_trainer ? ` · ${notification.author_trainer.first_name} ${notification.author_trainer.last_name}` : ""}
          </span>
          <h3>{notification.title}</h3>
          <p>{notification.body}</p>
          <small>
            {notification.targets
              .map((target) => `${branchName(target.branch_id)} · ${recipientLabel(target)}`)
              .join(", ") || "Bez příjemců"}
            {" · "}
            {notification.visibility_state === "expired" ? "expired" : `visible do ${formatDate(notification.visible_until)}`}
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
              navigate(`/events?event=${notification.event_id}`);
            }}
          >
            Otevřít akci
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
                  <textarea
                    value={editText}
                    onChange={(event) => setEditText(event.target.value)}
                    rows={2}
                  />
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
                          onClick={() => startEdit(comment.id, comment.body)}
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

          {notification.can_delete && (
            <button
              type="button"
              className="notification-delete"
              disabled={deletePending}
              onClick={() => onDelete(notification.id)}
            >
              Smazat notifikaci
            </button>
          )}
        </div>
      )}
    </article>
  );
}
