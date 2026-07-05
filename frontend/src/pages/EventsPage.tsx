import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type {
  EventCreate,
  EventDetail,
  EventItem,
  EventType,
  NotificationTargetCreate,
  RsvpStatus,
} from "../api/types";
import { RecipientTargets, recipientLabel } from "../components/RecipientTargets";

type Role = "trainer" | "parent";

type Props = {
  role: Role;
  selfId: number;
  homePath: string;
};

const EVENT_TYPES: { value: EventType; label: string }[] = [
  { value: "tournament", label: "Turnaj" },
  { value: "training", label: "Trénink" },
  { value: "meeting", label: "Schůzka" },
  { value: "seminar", label: "Školení" },
  { value: "other", label: "Jiné" },
];

const TYPE_LABEL: Record<EventType, string> = {
  tournament: "Turnaj",
  training: "Trénink",
  meeting: "Schůzka",
  seminar: "Školení",
  other: "Jiné",
};

const RSVP_LABEL: Record<RsvpStatus, string> = {
  yes: "Přijdu",
  no: "Nepřijdu",
  maybe: "Možná",
};

function toDatetimeLocalValue(date: Date) {
  const offsetMs = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("cs-CZ", {
    day: "numeric",
    month: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} kB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function startOfDay(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function countdownLabel(startsAt: string): { text: string; today: boolean } | null {
  const now = startOfDay(new Date());
  const start = startOfDay(new Date(startsAt));
  const diffDays = Math.round((start.getTime() - now.getTime()) / 86_400_000);
  if (diffDays < 0) return null;
  if (diffDays === 0) return { text: "Dnes", today: true };
  if (diffDays === 1) return { text: "Zítra", today: false };
  return { text: `za ${diffDays} dní`, today: false };
}

export function EventsPage({ role, selfId, homePath }: Props) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [view, setView] = useState<"list" | "calendar">("list");
  const [activeId, setActiveId] = useState<number | null>(null);
  const [composeOpen, setComposeOpen] = useState(false);
  const [composeDate, setComposeDate] = useState<Date | null>(null);

  const eventsQuery = useQuery({
    queryKey: ["events", role, selfId],
    queryFn: () => api.events(role),
    refetchInterval: 30_000,
  });

  const events = eventsQuery.data ?? [];

  return (
    <div className="app-shell notification-board events-page">
      <header className="page-header">
        <div className="page-header__row">
          <div>
            <p className="page-header__eyebrow">Plánovač</p>
            <h1 className="page-header__title">Akce</h1>
            <p className="page-header__sub">Turnaje, tréninky, schůzky</p>
          </div>
          <button type="button" className="board-link" onClick={() => navigate(homePath)}>Menu</button>
        </div>
      </header>

      <div className="events-toolbar">
        <div className="events-view-toggle">
          <button
            type="button"
            className={view === "list" ? "is-active" : ""}
            onClick={() => setView("list")}
          >
            Seznam
          </button>
          <button
            type="button"
            className={view === "calendar" ? "is-active" : ""}
            onClick={() => setView("calendar")}
          >
            Kalendář
          </button>
        </div>
        {role === "trainer" && (
          <button type="button" className="btn btn--primary" onClick={() => setComposeOpen((v) => !v)}>
            {composeOpen ? "Zavřít" : "Nová akce"}
          </button>
        )}
      </div>

      {composeOpen && role === "trainer" && (
        <EventCompose
          key={composeDate ? composeDate.toISOString() : "new"}
          initialStart={composeDate}
          onDone={() => {
            setComposeOpen(false);
            setComposeDate(null);
            queryClient.invalidateQueries({ queryKey: ["events"] });
          }}
        />
      )}

      {eventsQuery.isLoading && <div className="loading">Načítám…</div>}
      {eventsQuery.isError && <div className="error-box">{String(eventsQuery.error)}</div>}

      {view === "calendar" ? (
        <CalendarView
          events={events}
          onSelect={setActiveId}
          activeId={activeId}
          onSelectDay={
            role === "trainer"
              ? (day) => {
                  setComposeDate(day);
                  setComposeOpen(true);
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }
              : undefined
          }
        />
      ) : (
        <section className="events-list">
          {!eventsQuery.isLoading && events.length === 0 && (
            <div className="loading">Zatím tu nejsou žádné akce.</div>
          )}
          {events.map((event) => (
            <EventRow
              key={event.id}
              event={event}
              role={role}
              selfId={selfId}
              expanded={activeId === event.id}
              onToggle={() => setActiveId((cur) => (cur === event.id ? null : event.id))}
              onDeleted={() => setActiveId(null)}
            />
          ))}
        </section>
      )}

      {view === "calendar" && activeId != null && (
        <section className="events-list events-list--calendar-detail">
          {events
            .filter((event) => event.id === activeId)
            .map((event) => (
              <EventRow
                key={event.id}
                event={event}
                role={role}
                selfId={selfId}
                expanded
                onToggle={() => setActiveId(null)}
                onDeleted={() => setActiveId(null)}
              />
            ))}
        </section>
      )}
    </div>
  );
}

function EventCompose({ onDone, initialStart }: { onDone: () => void; initialStart?: Date | null }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [eventType, setEventType] = useState<EventType>("tournament");
  const [location, setLocation] = useState("");
  const [startsAt, setStartsAt] = useState(() => {
    if (initialStart) {
      const d = new Date(initialStart);
      d.setHours(18, 0, 0, 0);
      return toDatetimeLocalValue(d);
    }
    return toDatetimeLocalValue(new Date(Date.now() + 24 * 60 * 60 * 1000));
  });
  const [endsAt, setEndsAt] = useState("");
  const [targets, setTargets] = useState<NotificationTargetCreate[]>([]);

  const branchesQuery = useQuery({ queryKey: ["branches"], queryFn: () => api.branches() });
  const branches = branchesQuery.data ?? [];

  const createEvent = useMutation({
    mutationFn: () => {
      const payload: EventCreate = {
        title,
        description,
        event_type: eventType,
        location,
        starts_at: new Date(startsAt).toISOString(),
        ends_at: endsAt ? new Date(endsAt).toISOString() : null,
        targets,
      };
      return api.createEvent(payload);
    },
    onSuccess: onDone,
  });

  const missing: string[] = [];
  if (!title.trim()) missing.push("název");
  if (!startsAt) missing.push("začátek");
  if (targets.length === 0) missing.push("alespoň jednoho příjemce");
  const canSend = missing.length === 0;

  return (
    <section className="notification-compose">
      <h2>Nová akce</h2>
      <label className="notification-field">
        Název
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Např. Krajský přebor" />
      </label>
      <div className="events-compose__row">
        <label className="notification-field">
          Typ akce
          <select value={eventType} onChange={(e) => setEventType(e.target.value as EventType)}>
            {EVENT_TYPES.map((type) => (
              <option key={type.value} value={type.value}>{type.label}</option>
            ))}
          </select>
        </label>
        <label className="notification-field">
          Místo konání
          <input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Adresa / hala" />
        </label>
      </div>
      <div className="events-compose__row">
        <label className="notification-field">
          Začátek
          <input type="datetime-local" value={startsAt} onChange={(e) => setStartsAt(e.target.value)} />
        </label>
        <label className="notification-field">
          Konec (nepovinné)
          <input type="datetime-local" value={endsAt} onChange={(e) => setEndsAt(e.target.value)} />
        </label>
      </div>
      <label className="notification-field">
        Informace
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          placeholder="Podrobnosti, kategorie, sraz…"
        />
      </label>

      <div className="notification-section">
        <h3 className="notification-section__title">Komu se akce zobrazí</h3>
        <RecipientTargets branches={branches} targets={targets} onChange={setTargets} />
      </div>

      <div className={`notification-compose__actions${canSend ? "" : " notification-compose__actions--single"}`}>
        <button type="button" className="btn btn--ghost" onClick={onDone}>Zrušit</button>
        {canSend && (
          <button
            type="button"
            className="btn btn--primary"
            disabled={createEvent.isPending}
            onClick={() => createEvent.mutate()}
          >
            {createEvent.isPending ? "Vytvářím…" : "Vytvořit akci"}
          </button>
        )}
      </div>
      {!canSend && (
        <p className="notification-compose__missing">Ještě chybí: {missing.join(", ")}.</p>
      )}
      {createEvent.isError && <div className="error-box">{String(createEvent.error)}</div>}
    </section>
  );
}

type RowProps = {
  event: EventItem;
  role: Role;
  selfId: number;
  expanded: boolean;
  onToggle: () => void;
  onDeleted: () => void;
};

function EventRow({ event, role, selfId, expanded, onToggle, onDeleted }: RowProps) {
  const countdown = countdownLabel(event.starts_at);
  return (
    <article className={`event-card event-type--${event.event_type}${countdown?.today ? " event-card--today" : ""}`}>
      <button type="button" className="event-card__head" onClick={onToggle}>
        <span className={`event-type-dot event-type-dot--${event.event_type}`} aria-hidden />
        <div className="event-card__main">
          <span className="event-card__meta">
            <span className={`event-type-badge event-type-badge--${event.event_type}`}>
              {TYPE_LABEL[event.event_type]}
            </span>
            {formatDateTime(event.starts_at)}
            {event.location ? ` · ${event.location}` : ""}
          </span>
          <h3>{event.title}</h3>
          <small>
            {event.targets.map((t) => recipientLabel(t)).join(", ") || "Bez příjemců"}
          </small>
        </div>
        <div className="event-card__side">
          {countdown && (
            <span className={`event-countdown${countdown.today ? " event-countdown--today" : ""}`}>
              {countdown.text}
            </span>
          )}
          {event.my_rsvp && <span className={`event-rsvp-chip event-rsvp-chip--${event.my_rsvp}`}>{RSVP_LABEL[event.my_rsvp]}</span>}
          <span className="notification-card__chevron">{expanded ? "▲" : "▼"}</span>
        </div>
      </button>
      {expanded && (
        <EventDetailPanel eventId={event.id} role={role} selfId={selfId} onDeleted={onDeleted} />
      )}
    </article>
  );
}

function EventDetailPanel({
  eventId,
  role,
  selfId,
  onDeleted,
}: {
  eventId: number;
  role: Role;
  selfId: number;
  onDeleted: () => void;
}) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const detailQuery = useQuery({
    queryKey: ["event", eventId, role, selfId],
    queryFn: () => api.event(eventId, role),
    retry: false,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["event", eventId] });
    queryClient.invalidateQueries({ queryKey: ["events"] });
  };

  const setRsvp = useMutation({
    mutationFn: (status: RsvpStatus) => api.setRsvp(eventId, status, role),
    onSuccess: invalidate,
  });
  const deleteEvent = useMutation({
    mutationFn: () => api.deleteEvent(eventId),
    onSuccess: () => {
      // Collapse the panel first so its detail query unmounts and never refetches the deleted event.
      onDeleted();
      queryClient.removeQueries({ queryKey: ["event", eventId] });
      queryClient.invalidateQueries({ queryKey: ["events"] });
    },
  });

  if (detailQuery.isLoading) return <div className="event-detail"><div className="loading">Načítám…</div></div>;
  if (detailQuery.isError || !detailQuery.data) {
    return <div className="event-detail"><div className="error-box">{String(detailQuery.error)}</div></div>;
  }
  const event = detailQuery.data;

  if (editing) {
    return (
      <div className="event-detail">
        <EventEditForm
          event={event}
          onCancel={() => setEditing(false)}
          onSaved={() => {
            setEditing(false);
            invalidate();
          }}
        />
      </div>
    );
  }

  return (
    <div className="event-detail">
      {event.description && <p className="event-detail__description">{event.description}</p>}
      <dl className="event-detail__facts">
        <div>
          <dt>Kdy</dt>
          <dd>
            {formatDateTime(event.starts_at)}
            {event.ends_at ? ` – ${formatDateTime(event.ends_at)}` : ""}
          </dd>
        </div>
        {event.location && (
          <div>
            <dt>Kde</dt>
            <dd>{event.location}</dd>
          </div>
        )}
      </dl>

      <div className="event-rsvp">
        <span className="event-rsvp__label">Zúčastníš se?</span>
        <div className="event-rsvp__buttons">
          {(["yes", "maybe", "no"] as RsvpStatus[]).map((status) => (
            <button
              key={status}
              type="button"
              className={`event-rsvp__btn event-rsvp__btn--${status}${event.my_rsvp === status ? " is-active" : ""}`}
              disabled={setRsvp.isPending}
              onClick={() => setRsvp.mutate(status)}
            >
              {RSVP_LABEL[status]}
            </button>
          ))}
        </div>
      </div>

      {event.rsvp_summary && <RsvpSummaryView summary={event.rsvp_summary} />}

      <EventAttachments event={event} role={role} onChange={invalidate} />

      <EventComments event={event} role={role} onChange={invalidate} />

      {event.can_edit && (
        <div className="event-detail__owner-actions">
          <button type="button" className="btn btn--ghost" onClick={() => setEditing(true)}>
            Upravit akci
          </button>
          <button
            type="button"
            className="notification-delete"
            disabled={deleteEvent.isPending}
            onClick={() => deleteEvent.mutate()}
          >
            Smazat akci
          </button>
        </div>
      )}
    </div>
  );
}

function EventEditForm({
  event,
  onCancel,
  onSaved,
}: {
  event: EventDetail;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [title, setTitle] = useState(event.title);
  const [description, setDescription] = useState(event.description);
  const [eventType, setEventType] = useState<EventType>(event.event_type);
  const [location, setLocation] = useState(event.location);
  const [startsAt, setStartsAt] = useState(toDatetimeLocalValue(new Date(event.starts_at)));
  const [endsAt, setEndsAt] = useState(event.ends_at ? toDatetimeLocalValue(new Date(event.ends_at)) : "");
  const [targets, setTargets] = useState<NotificationTargetCreate[]>(
    event.targets.map((t) => ({ audience: t.audience, branch_id: t.branch_id, age_group: t.age_group })),
  );

  const branchesQuery = useQuery({ queryKey: ["branches"], queryFn: () => api.branches() });
  const branches = branchesQuery.data ?? [];

  const save = useMutation({
    mutationFn: () =>
      api.updateEvent(event.id, {
        title,
        description,
        event_type: eventType,
        location,
        starts_at: new Date(startsAt).toISOString(),
        ends_at: endsAt ? new Date(endsAt).toISOString() : null,
        targets,
      }),
    onSuccess: onSaved,
  });

  const missing: string[] = [];
  if (!title.trim()) missing.push("název");
  if (!startsAt) missing.push("začátek");
  if (targets.length === 0) missing.push("alespoň jednoho příjemce");
  const endsBeforeStart = Boolean(endsAt) && new Date(endsAt) < new Date(startsAt);
  if (endsBeforeStart) missing.push("konec po začátku");
  const canSave = missing.length === 0;

  return (
    <section className="notification-compose">
      <h2>Upravit akci</h2>
      <label className="notification-field">
        Název
        <input value={title} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <div className="events-compose__row">
        <label className="notification-field">
          Typ akce
          <select value={eventType} onChange={(e) => setEventType(e.target.value as EventType)}>
            {EVENT_TYPES.map((type) => (
              <option key={type.value} value={type.value}>{type.label}</option>
            ))}
          </select>
        </label>
        <label className="notification-field">
          Místo konání
          <input value={location} onChange={(e) => setLocation(e.target.value)} />
        </label>
      </div>
      <div className="events-compose__row">
        <label className="notification-field">
          Začátek
          <input type="datetime-local" value={startsAt} onChange={(e) => setStartsAt(e.target.value)} />
        </label>
        <label className="notification-field">
          Konec (nepovinné)
          <input type="datetime-local" value={endsAt} onChange={(e) => setEndsAt(e.target.value)} />
        </label>
      </div>
      <label className="notification-field">
        Informace
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
      </label>

      <div className="notification-section">
        <h3 className="notification-section__title">Komu se akce zobrazí</h3>
        <RecipientTargets branches={branches} targets={targets} onChange={setTargets} />
      </div>

      <div className={`notification-compose__actions${canSave ? "" : " notification-compose__actions--single"}`}>
        <button type="button" className="btn btn--ghost" onClick={onCancel}>Zrušit</button>
        {canSave && (
          <button
            type="button"
            className="btn btn--primary"
            disabled={save.isPending}
            onClick={() => save.mutate()}
          >
            {save.isPending ? "Ukládám…" : "Uložit změny"}
          </button>
        )}
      </div>
      {!canSave && <p className="notification-compose__missing">Ještě chybí: {missing.join(", ")}.</p>}
      {save.isError && <div className="error-box">{String(save.error)}</div>}
    </section>
  );
}

function RsvpSummaryView({ summary }: { summary: NonNullable<EventDetail["rsvp_summary"]> }) {
  return (
    <div className="event-summary">
      <div className="event-summary__counts">
        <span className="event-summary__count event-summary__count--yes">Přijde: {summary.yes}</span>
        <span className="event-summary__count event-summary__count--maybe">Možná: {summary.maybe}</span>
        <span className="event-summary__count event-summary__count--no">Nepřijde: {summary.no}</span>
      </div>
      {summary.participants.length > 0 && (
        <ul className="event-summary__list">
          {summary.participants.map((p) => (
            <li key={`${p.kind}:${p.id}`} className={`event-summary__person event-summary__person--${p.status}`}>
              {p.name} {p.kind === "parent" ? "(rodič)" : "(trenér)"} — {RSVP_LABEL[p.status]}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function EventAttachments({ event, role, onChange }: { event: EventDetail; role: Role; onChange: () => void }) {
  const upload = useMutation({
    mutationFn: (file: File) => api.uploadEventAttachment(event.id, file, role),
    onSuccess: onChange,
  });
  const remove = useMutation({
    mutationFn: (attachmentId: number) => api.deleteEventAttachment(event.id, attachmentId, role),
    onSuccess: onChange,
  });
  const download = useMutation({
    mutationFn: ({ id, filename }: { id: number; filename: string }) =>
      api.downloadEventAttachment(event.id, id, filename, role),
  });

  return (
    <div className="event-attachments">
      <h4 className="event-detail__subtitle">Přílohy</h4>
      {event.attachments.length === 0 && <p className="event-attachments__empty">Zatím žádné přílohy.</p>}
      <ul className="event-attachments__list">
        {event.attachments.map((att) => (
          <li key={att.id} className="event-attachment">
            <button
              type="button"
              className="event-attachment__name"
              onClick={() => download.mutate({ id: att.id, filename: att.filename })}
            >
              📎 {att.filename}
            </button>
            <span className="event-attachment__size">{formatFileSize(att.size_bytes)}</span>
            {att.can_delete && (
              <button
                type="button"
                className="event-attachment__delete"
                disabled={remove.isPending}
                onClick={() => remove.mutate(att.id)}
              >
                ×
              </button>
            )}
          </li>
        ))}
      </ul>
      <label className="event-attachments__upload">
        <input
          type="file"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) upload.mutate(file);
            e.target.value = "";
          }}
        />
        <span className="btn btn--ghost">{upload.isPending ? "Nahrávám…" : "Nahrát přílohu"}</span>
      </label>
      {upload.isError && <div className="error-box">{String(upload.error)}</div>}
    </div>
  );
}

function EventComments({ event, role, onChange }: { event: EventDetail; role: Role; onChange: () => void }) {
  const [reply, setReply] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editText, setEditText] = useState("");

  const addComment = useMutation({
    mutationFn: (body: string) => api.addEventComment(event.id, body, role),
    onSuccess: () => {
      setReply("");
      onChange();
    },
  });
  const updateComment = useMutation({
    mutationFn: ({ commentId, body }: { commentId: number; body: string }) =>
      api.updateEventComment(event.id, commentId, body, role),
    onSuccess: () => {
      setEditingId(null);
      setEditText("");
      onChange();
    },
  });
  const deleteComment = useMutation({
    mutationFn: (commentId: number) => api.deleteEventComment(event.id, commentId, role),
    onSuccess: onChange,
  });

  return (
    <div className="notification-thread">
      <h4 className="event-detail__subtitle">Dotazy a připomínky</h4>
      {event.comments.map((comment) => (
        <div className="notification-comment" key={comment.id}>
          <span className="notification-comment__meta">
            {comment.author_trainer
              ? `${comment.author_trainer.first_name} ${comment.author_trainer.last_name}`
              : comment.author_parent
                ? `${comment.author_parent.first_name} ${comment.author_parent.last_name} (rodič)`
                : "Neznámý"}
            {" · "}
            {formatDateTime(comment.created_at)}
            {comment.updated_at !== comment.created_at ? " · upraveno" : ""}
          </span>
          {editingId === comment.id ? (
            <div className="notification-comment__edit">
              <textarea value={editText} onChange={(e) => setEditText(e.target.value)} rows={2} />
              <div className="notification-comment__edit-actions">
                <button type="button" className="btn btn--ghost" onClick={() => setEditingId(null)}>Zrušit</button>
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
      {event.comments.length === 0 && <div className="notification-thread__empty">Zatím žádné dotazy.</div>}
      <div className="notification-thread__reply">
        <textarea value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Napiš dotaz…" rows={2} />
        <button
          type="button"
          className="btn btn--primary"
          disabled={!reply.trim() || addComment.isPending}
          onClick={() => addComment.mutate(reply)}
        >
          {addComment.isPending ? "Odesílám…" : "Odeslat"}
        </button>
      </div>
    </div>
  );
}

function CalendarView({
  events,
  onSelect,
  activeId,
  onSelectDay,
}: {
  events: EventItem[];
  onSelect: (id: number) => void;
  activeId: number | null;
  onSelectDay?: (day: Date) => void;
}) {
  const [month, setMonth] = useState(() => startOfDay(new Date()));

  const grid = useMemo(() => {
    const first = new Date(month.getFullYear(), month.getMonth(), 1);
    const startWeekday = (first.getDay() + 6) % 7; // Monday=0
    const start = new Date(first);
    start.setDate(first.getDate() - startWeekday);
    const days: Date[] = [];
    for (let i = 0; i < 42; i += 1) {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      days.push(d);
    }
    return days;
  }, [month]);

  const byDay = useMemo(() => {
    const map = new Map<string, EventItem[]>();
    for (const event of events) {
      const d = startOfDay(new Date(event.starts_at));
      const key = d.toDateString();
      const list = map.get(key) ?? [];
      list.push(event);
      map.set(key, list);
    }
    return map;
  }, [events]);

  const today = startOfDay(new Date()).toDateString();
  const monthLabel = month.toLocaleDateString("cs-CZ", { month: "long", year: "numeric" });

  return (
    <section className="event-calendar">
      <div className="event-calendar__header">
        <button
          type="button"
          className="btn btn--ghost"
          onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}
        >
          ‹
        </button>
        <span className="event-calendar__title">{monthLabel}</span>
        <button
          type="button"
          className="btn btn--ghost"
          onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}
        >
          ›
        </button>
      </div>
      <div className="event-calendar__weekdays">
        {["Po", "Út", "St", "Čt", "Pá", "So", "Ne"].map((d) => (
          <span key={d}>{d}</span>
        ))}
      </div>
      <div className="event-calendar__grid">
        {grid.map((day) => {
          const key = day.toDateString();
          const dayEvents = byDay.get(key) ?? [];
          const isOtherMonth = day.getMonth() !== month.getMonth();
          return (
            <div
              key={key}
              className={`event-calendar__cell${isOtherMonth ? " is-muted" : ""}${key === today ? " is-today" : ""}${onSelectDay ? " is-clickable" : ""}`}
              onClick={onSelectDay ? () => onSelectDay(new Date(day)) : undefined}
              role={onSelectDay ? "button" : undefined}
              title={onSelectDay ? "Naplánovat akci na tento den" : undefined}
            >
              <span className="event-calendar__day">{day.getDate()}</span>
              <div className="event-calendar__events">
                {dayEvents.map((event) => (
                  <button
                    key={event.id}
                    type="button"
                    className={`event-calendar__pill event-type--${event.event_type}${activeId === event.id ? " is-active" : ""}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelect(event.id);
                    }}
                    title={event.title}
                  >
                    {event.title}
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
