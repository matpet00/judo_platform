import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type {
  AttendanceStatus,
  EventCreate,
  EventDetail,
  EventChildRsvp,
  EventItem,
  EventRsvpResponse,
  EventType,
  NotificationTargetCreate,
  RsvpStatus,
  TrainingOccurrence,
} from "../api/types";
import { RecipientTargets, recipientLabel } from "../components/RecipientTargets";
import { AttendanceOverview } from "../components/AttendanceOverview";

type Role = "trainer" | "parent";

const WEEKDAYS: { value: number; label: string }[] = [
  { value: 1, label: "Po" },
  { value: 2, label: "Út" },
  { value: 3, label: "St" },
  { value: 4, label: "Čt" },
  { value: 5, label: "Pá" },
  { value: 6, label: "So" },
  { value: 7, label: "Ne" },
];

function toDateInputValue(date: Date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

type Props = {
  role: Role;
  selfId: number;
  homePath: string;
};

const EVENT_TYPES: { value: EventType; label: string }[] = [
  { value: "tournament", label: "Turnaj" },
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

const CHILD_RSVP_BANNER: Record<RsvpStatus, string> = {
  yes: "Dítě přihlášeno",
  no: "Dítě nepřihlášeno",
  maybe: "Dítě: možná",
};

const CHILDREN_RSVP_BANNER: Record<RsvpStatus, string> = {
  yes: "děti přihlášeny",
  no: "děti nepřihlášeny",
  maybe: "děti: možná",
};

function parentRsvpBanner(children: EventChildRsvp[]): { label: string; tone: "pending" | RsvpStatus | "mixed" } | null {
  if (children.length === 0) return null;
  const total = children.length;
  const answered = children.filter((c) => c.status != null);
  const pending = total - answered.length;

  if (pending === total) {
    return {
      label: total === 1 ? "Čeká na přihlášení dítěte" : `0/${total} čeká na přihlášení`,
      tone: "pending",
    };
  }
  if (pending > 0) {
    return {
      label: `${answered.length}/${total} čeká na odpověď`,
      tone: "pending",
    };
  }
  if (total === 1) {
    return { label: CHILD_RSVP_BANNER[answered[0].status!], tone: answered[0].status! };
  }
  const statuses = new Set(answered.map((c) => c.status));
  if (statuses.size === 1 && answered[0].status) {
    return { label: `${total}/${total} ${CHILDREN_RSVP_BANNER[answered[0].status]}`, tone: answered[0].status };
  }
  return { label: `${total}/${total} odpovězeno`, tone: "mixed" };
}

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

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" });
}

function splitLocal(value: string): { date: string; time: string } {
  const [d = "", t = ""] = value.split("T");
  return { date: d, time: t.slice(0, 5) };
}

function joinLocal(date: string, time: string): string {
  if (!date) return "";
  return `${date}T${time || "00:00"}`;
}

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

function wrap(n: number, size: number): number {
  return ((n % size) + size) % size;
}

function TimeSegment({
  value,
  size,
  step,
  label,
  onChange,
}: {
  value: number;
  size: number;
  step: number;
  label: string;
  onChange: (next: number) => void;
}) {
  const [text, setText] = useState(pad2(value));
  const lastEmitted = useRef(value);

  useEffect(() => {
    if (value === lastEmitted.current) return;
    lastEmitted.current = value;
    setText(pad2(value));
  }, [value]);

  const handleType = (raw: string) => {
    const digits = raw.replace(/\D/g, "").slice(0, 2);
    setText(digits);
    // Commit only when two digits are in — single digits stay local until blur.
    if (digits.length === 2) {
      const n = Math.min(Number(digits), size - 1);
      lastEmitted.current = n;
      onChange(n);
    }
  };

  const handleBlur = () => {
    if (text === "") {
      lastEmitted.current = 0;
      setText("00");
      onChange(0);
      return;
    }
    const n = Math.min(Number(text), size - 1);
    lastEmitted.current = n;
    setText(pad2(n));
    onChange(n);
  };

  return (
    <div className="time-field__seg">
      <input
        inputMode="numeric"
        value={text}
        onChange={(e) => handleType(e.target.value)}
        onBlur={handleBlur}
        aria-label={label}
      />
      <div className="time-field__arrows">
        <button
          type="button"
          tabIndex={-1}
          aria-label={`${label} +`}
          onClick={() => {
            const n = wrap(value + step, size);
            lastEmitted.current = n;
            setText(pad2(n));
            onChange(n);
          }}
        >
          ▲
        </button>
        <button
          type="button"
          tabIndex={-1}
          aria-label={`${label} -`}
          onClick={() => {
            const n = wrap(value - step, size);
            lastEmitted.current = n;
            setText(pad2(n));
            onChange(n);
          }}
        >
          ▼
        </button>
      </div>
    </div>
  );
}

function TimeField({ value, onChange }: { value: string; onChange: (next: string) => void }) {
  const [hRaw, mRaw] = (value && value.includes(":") ? value : "00:00").split(":");
  const hour = Number.isNaN(Number(hRaw)) ? 0 : Number(hRaw);
  const minute = Number.isNaN(Number(mRaw)) ? 0 : Number(mRaw);
  return (
    <div className="time-field">
      <TimeSegment value={hour} size={24} step={1} label="Hodiny" onChange={(h) => onChange(`${pad2(h)}:${pad2(minute)}`)} />
      <span className="time-field__colon">:</span>
      <TimeSegment value={minute} size={60} step={5} label="Minuty" onChange={(m) => onChange(`${pad2(hour)}:${pad2(m)}`)} />
    </div>
  );
}

function parseIsoDate(value: string): { d: string; mo: string; y: string } {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || "");
  return m ? { y: m[1], mo: m[2], d: m[3] } : { y: "", mo: "", d: "" };
}

// Czech-format date entry (den/měsíc/rok). Native <input type="date"> renders in the
// browser locale (often mm/dd/yyyy), which we can't control, so we roll our own.
function DateField({ value, onChange }: { value: string; onChange: (next: string) => void }) {
  const init = parseIsoDate(value);
  const [d, setD] = useState(init.d);
  const [mo, setMo] = useState(init.mo);
  const [y, setY] = useState(init.y);
  const lastEmitted = useRef(value);

  useEffect(() => {
    if (value === lastEmitted.current) return;
    lastEmitted.current = value;
    const p = parseIsoDate(value);
    setD(p.d);
    setMo(p.mo);
    setY(p.y);
  }, [value]);

  const commit = (dd: string, mm: string, yy: string) => {
    if (!dd && !mm && !yy) {
      lastEmitted.current = "";
      onChange("");
      return;
    }
    if (!dd || !mm || yy.length !== 4) return;
    const day = pad2(Math.min(31, Math.max(1, Number(dd))));
    const mon = pad2(Math.min(12, Math.max(1, Number(mm))));
    const next = `${yy}-${mon}-${day}`;
    lastEmitted.current = next;
    onChange(next);
  };

  const blurDay = () => {
    const nextD = d ? pad2(Math.min(31, Math.max(1, Number(d)))) : "";
    setD(nextD);
    commit(nextD, mo, y);
  };

  const blurMonth = () => {
    const nextMo = mo ? pad2(Math.min(12, Math.max(1, Number(mo)))) : "";
    setMo(nextMo);
    commit(d, nextMo, y);
  };

  const blurYear = () => {
    commit(d, mo, y);
  };

  return (
    <div className="date-field">
      <input
        className="date-field__seg date-field__seg--day"
        inputMode="numeric"
        placeholder="DD"
        value={d}
        aria-label="Den"
        onChange={(e) => setD(e.target.value.replace(/\D/g, "").slice(0, 2))}
        onBlur={blurDay}
      />
      <span className="date-field__dot">.</span>
      <input
        className="date-field__seg date-field__seg--month"
        inputMode="numeric"
        placeholder="MM"
        value={mo}
        aria-label="Měsíc"
        onChange={(e) => setMo(e.target.value.replace(/\D/g, "").slice(0, 2))}
        onBlur={blurMonth}
      />
      <span className="date-field__dot">.</span>
      <input
        className="date-field__seg date-field__seg--year"
        inputMode="numeric"
        placeholder="RRRR"
        value={y}
        aria-label="Rok"
        onChange={(e) => setY(e.target.value.replace(/\D/g, "").slice(0, 4))}
        onBlur={blurYear}
      />
    </div>
  );
}

function DateTimeField({ value, onChange }: { value: string; onChange: (next: string) => void }) {
  const { date, time } = splitLocal(value);
  return (
    <div className="datetime-split">
      <DateField value={date} onChange={(nextDate) => onChange(joinLocal(nextDate, time))} />
      <TimeField value={time || "00:00"} onChange={(t) => onChange(joinLocal(date, t))} />
    </div>
  );
}

function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return createPortal(
    <div className="modal-overlay" onClick={onClose} role="presentation">
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="modal__head">
          <h3 className="modal__title">{title}</h3>
          <button type="button" className="modal__close" onClick={onClose} aria-label="Zavřít">
            ✕
          </button>
        </div>
        <div className="modal__body">{children}</div>
      </div>
    </div>,
    document.body,
  );
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

type CalView = "month" | "week" | "day";

function addDays(date: Date, days: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return startOfDay(d);
}

function startOfWeek(date: Date): Date {
  const d = startOfDay(date);
  const offset = (d.getDay() + 6) % 7; // Monday=0
  return addDays(d, -offset);
}

function monthGridStart(anchor: Date): Date {
  const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
  return startOfWeek(first);
}

function computeVisibleDays(view: CalView, anchor: Date): Date[] {
  if (view === "day") return [startOfDay(anchor)];
  if (view === "week") {
    const start = startOfWeek(anchor);
    return Array.from({ length: 7 }, (_, i) => addDays(start, i));
  }
  const start = monthGridStart(anchor);
  return Array.from({ length: 42 }, (_, i) => addDays(start, i));
}

export function EventsPage({ role, selfId, homePath }: Props) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [view, setView] = useState<"list" | "calendar">("list");
  const [activeId, setActiveId] = useState<number | null>(null);
  const [composeOpen, setComposeOpen] = useState(false);
  const [composeDate, setComposeDate] = useState<Date | null>(null);
  const [calView, setCalView] = useState<CalView>("month");
  const [calAnchor, setCalAnchor] = useState(() => startOfDay(new Date()));
  const [activeOccurrence, setActiveOccurrence] = useState<TrainingOccurrence | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    const target = searchParams.get("event");
    if (!target) return;
    const id = Number(target);
    if (Number.isFinite(id)) {
      setActiveId(id);
      setView("list");
    }
    searchParams.delete("event");
    setSearchParams(searchParams, { replace: true });
  }, [searchParams, setSearchParams]);

  const eventsQuery = useQuery({
    queryKey: ["events", role, selfId],
    queryFn: () => api.events(role),
    refetchInterval: 30_000,
  });

  const visibleDays = useMemo(() => computeVisibleDays(calView, calAnchor), [calView, calAnchor]);
  const rangeFrom = visibleDays[0];
  const rangeTo = visibleDays[visibleDays.length - 1];
  const occurrencesQuery = useQuery({
    queryKey: ["occurrences", role, selfId, toDateInputValue(rangeFrom), toDateInputValue(rangeTo)],
    queryFn: () => api.trainingOccurrences(toDateInputValue(rangeFrom), toDateInputValue(rangeTo), role),
    enabled: view === "calendar",
    refetchInterval: 60_000,
  });

  const events = eventsQuery.data ?? [];
  const occurrences = occurrencesQuery.data ?? [];

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
          <div className="events-toolbar__actions">
            <button type="button" className="btn btn--primary" onClick={() => setComposeOpen((v) => !v)}>
              {composeOpen ? "Zavřít" : "Nová akce"}
            </button>
          </div>
        )}
      </div>

      {composeOpen && role === "trainer" && (
        <EventCompose
          key={composeDate ? composeDate.toISOString() : "new"}
          initialStart={composeDate}
          onDone={(createdEventId) => {
            setComposeOpen(false);
            setComposeDate(null);
            queryClient.invalidateQueries({ queryKey: ["events"] });
            queryClient.invalidateQueries({ queryKey: ["occurrences"] });
            if (createdEventId != null) {
              // Jump straight into the new event so the trainer can add attachments right away.
              setView("list");
              setActiveOccurrence(null);
              setActiveId(createdEventId);
            }
          }}
          onTrainingCreated={() => {
            setComposeOpen(false);
            setCalAnchor(startOfDay(composeDate ?? new Date()));
            setComposeDate(null);
            setView("calendar");
            queryClient.invalidateQueries({ queryKey: ["occurrences"] });
          }}
        />
      )}

      {eventsQuery.isLoading && <div className="loading">Načítám…</div>}
      {eventsQuery.isError && <div className="error-box">{String(eventsQuery.error)}</div>}
      {view === "calendar" && occurrencesQuery.isError && (
        <div className="error-box">Tréninky se nepodařilo načíst: {String(occurrencesQuery.error)}</div>
      )}

      {view === "calendar" ? (
        <CalendarView
          events={events}
          occurrences={occurrences}
          view={calView}
          anchor={calAnchor}
          visibleDays={visibleDays}
          onViewChange={setCalView}
          onAnchorChange={setCalAnchor}
          onSelect={(id) => {
            setActiveOccurrence(null);
            setActiveId(id);
          }}
          activeId={activeId}
          onSelectOccurrence={(occ) => {
            setActiveId(null);
            setActiveOccurrence(occ);
          }}
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

      {view === "calendar" && activeOccurrence != null && (
        <Modal title={activeOccurrence.name} onClose={() => setActiveOccurrence(null)}>
          <TrainingOccurrencePanel
            occurrence={activeOccurrence}
            role={role}
            onClose={() => setActiveOccurrence(null)}
            onChanged={() => queryClient.invalidateQueries({ queryKey: ["occurrences"] })}
          />
        </Modal>
      )}

      {view === "calendar" && activeId != null && (
        <Modal
          title={events.find((e) => e.id === activeId)?.title ?? "Akce"}
          onClose={() => setActiveId(null)}
        >
          <EventDetailPanel
            eventId={activeId}
            role={role}
            selfId={selfId}
            onDeleted={() => setActiveId(null)}
          />
        </Modal>
      )}
    </div>
  );
}

function ComposeModeToggle({
  mode,
  setMode,
}: {
  mode: "event" | "training";
  setMode: (m: "event" | "training") => void;
}) {
  return (
    <div className="events-compose__mode">
      <button type="button" className={mode === "event" ? "is-active" : ""} onClick={() => setMode("event")}>
        Akce
      </button>
      <button type="button" className={mode === "training" ? "is-active" : ""} onClick={() => setMode("training")}>
        Trénink
      </button>
    </div>
  );
}

function EventCompose({
  onDone,
  initialStart,
  onTrainingCreated,
}: {
  onDone: (createdEventId?: number) => void;
  initialStart?: Date | null;
  onTrainingCreated?: () => void;
}) {
  const [mode, setMode] = useState<"event" | "training">("event");
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
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);

  const branchesQuery = useQuery({ queryKey: ["branches"], queryFn: () => api.branches() });
  const branches = branchesQuery.data ?? [];

  const createEvent = useMutation({
    mutationFn: async () => {
      const payload: EventCreate = {
        title,
        description,
        event_type: eventType,
        location,
        starts_at: new Date(startsAt).toISOString(),
        ends_at: endsAt ? new Date(endsAt).toISOString() : null,
        targets,
      };
      const created = await api.createEvent(payload);
      for (const file of pendingFiles) {
        await api.uploadEventAttachment(created.id, file);
      }
      return created;
    },
    onSuccess: (created) => onDone(created.id),
  });

  const endsBeforeStart = !!(startsAt && endsAt && new Date(endsAt) < new Date(startsAt));
  const missing: string[] = [];
  if (!title.trim()) missing.push("název");
  if (!startsAt) missing.push("začátek");
  if (targets.length === 0) missing.push("alespoň jednoho příjemce");
  const canSend = missing.length === 0 && !endsBeforeStart;

  if (mode === "training") {
    return (
      <section className="notification-compose">
        <ComposeModeToggle mode={mode} setMode={setMode} />
        <TrainingSetupForm initialStart={initialStart} onDone={onTrainingCreated ?? onDone} />
      </section>
    );
  }

  return (
    <section className="notification-compose">
      <ComposeModeToggle mode={mode} setMode={setMode} />
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
          <DateTimeField value={startsAt} onChange={setStartsAt} />
        </label>
        <label className="notification-field">
          Konec (nepovinné)
          <DateTimeField value={endsAt} onChange={setEndsAt} />
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
        <h3 className="notification-section__title">Přílohy</h3>
        {pendingFiles.length === 0 && <p className="event-attachments__empty">Zatím žádné přílohy.</p>}
        {pendingFiles.length > 0 && (
          <ul className="event-attachments__list">
            {pendingFiles.map((file, index) => (
              <li key={`${file.name}-${file.size}-${index}`} className="event-attachment">
                <span className="event-attachment__name">📎 {file.name}</span>
                <span className="event-attachment__size">{formatFileSize(file.size)}</span>
                <button
                  type="button"
                  className="event-attachment__delete"
                  onClick={() => setPendingFiles((files) => files.filter((_, i) => i !== index))}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
        <label className="event-attachments__upload">
          <input
            type="file"
            multiple
            onChange={(e) => {
              const picked = Array.from(e.target.files ?? []);
              if (picked.length > 0) setPendingFiles((files) => [...files, ...picked]);
              e.target.value = "";
            }}
          />
          <span className="btn btn--ghost">Přidat přílohu</span>
        </label>
      </div>

      <div className="notification-section">
        <h3 className="notification-section__title">Komu se akce zobrazí</h3>
        <RecipientTargets branches={branches} targets={targets} onChange={setTargets} />
      </div>

      <div className={`notification-compose__actions${canSend ? "" : " notification-compose__actions--single"}`}>
        <button type="button" className="btn btn--ghost" onClick={() => onDone()}>Zrušit</button>
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
      {endsBeforeStart && (
        <p className="notification-compose__missing">Konec akce nemůže být před jejím začátkem.</p>
      )}
      {!canSend && !endsBeforeStart && missing.length > 0 && (
        <p className="notification-compose__missing">Ještě chybí: {missing.join(", ")}.</p>
      )}
      {createEvent.isError && <div className="error-box">{String(createEvent.error)}</div>}
    </section>
  );
}

function isoWeekday(date: Date): number {
  return ((date.getDay() + 6) % 7) + 1;
}

function TrainingSetupForm({ onDone, initialStart }: { onDone: () => void; initialStart?: Date | null }) {
  const base = initialStart ?? new Date();
  const [branchId, setBranchId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [startTime, setStartTime] = useState("17:00");
  const [endTime, setEndTime] = useState("18:30");
  const [weekdays, setWeekdays] = useState<Set<number>>(() => new Set([isoWeekday(base)]));
  const [activeFrom, setActiveFrom] = useState(() => toDateInputValue(base));
  const [activeUntil, setActiveUntil] = useState(() => {
    const d = new Date(base);
    d.setFullYear(d.getFullYear() + 1);
    return toDateInputValue(d);
  });
  const [studentIds, setStudentIds] = useState<Set<number>>(new Set());

  const branchesQuery = useQuery({ queryKey: ["branches"], queryFn: () => api.branches() });
  const branches = branchesQuery.data ?? [];
  const studentsQuery = useQuery({ queryKey: ["students"], queryFn: () => api.students() });
  const students = studentsQuery.data ?? [];

  const eligible = useMemo(
    () => (branchId == null ? [] : students.filter((s) => s.branches.some((b) => b.id === branchId))),
    [students, branchId],
  );

  const create = useMutation({
    mutationFn: () =>
      api.createTrainingGroup({
        branch_id: branchId as number,
        name,
        start_time: startTime,
        end_time: endTime,
        weekdays: [...weekdays].sort((a, b) => a - b),
        active_from: activeFrom || toDateInputValue(base),
        active_until: activeUntil || null,
        student_ids: [...studentIds],
      }),
    onSuccess: onDone,
  });

  const missing: string[] = [];
  if (branchId == null) missing.push("pobočka");
  if (!name.trim()) missing.push("název");
  if (weekdays.size === 0) missing.push("alespoň jeden den");
  if (endTime <= startTime) missing.push("konec po začátku");
  if (!activeFrom) missing.push("začátek opakování");
  if (activeUntil && activeFrom && activeUntil < activeFrom) missing.push("konec po začátku opakování");
  const canSave = missing.length === 0;

  const toggleWeekday = (d: number) =>
    setWeekdays((cur) => {
      const next = new Set(cur);
      if (next.has(d)) next.delete(d);
      else next.add(d);
      return next;
    });
  const toggleStudent = (id: number) =>
    setStudentIds((cur) => {
      const next = new Set(cur);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <>
      <h2>Nový trénink</h2>
      <div className="events-compose__row">
        <label className="notification-field">
          Pobočka
          <select
            value={branchId ?? ""}
            onChange={(e) => {
              setBranchId(e.target.value ? Number(e.target.value) : null);
              setStudentIds(new Set());
            }}
          >
            <option value="">Vyber pobočku…</option>
            {branches.map((b) => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </select>
        </label>
        <label className="notification-field">
          Název tréninku
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Např. Orlová mladší" />
        </label>
      </div>
      <div className="events-compose__row">
        <label className="notification-field">
          Začátek
          <TimeField value={startTime} onChange={setStartTime} />
        </label>
        <label className="notification-field">
          Konec
          <TimeField value={endTime} onChange={setEndTime} />
        </label>
      </div>

      <div className="notification-section">
        <h3 className="notification-section__title">Opakování (týdně)</h3>
        <div className="training-weekdays">
          {WEEKDAYS.map((w) => (
            <button
              key={w.value}
              type="button"
              className={`training-weekday${weekdays.has(w.value) ? " is-active" : ""}`}
              onClick={() => toggleWeekday(w.value)}
            >
              {w.label}
            </button>
          ))}
        </div>
        <div className="events-compose__row">
          <label className="notification-field">
            Opakovat od
            <DateField value={activeFrom} onChange={setActiveFrom} />
          </label>
          <label className="notification-field">
            Opakovat do
            <DateField value={activeUntil} onChange={setActiveUntil} />
          </label>
        </div>
      </div>

      <div className="notification-section">
        <h3 className="notification-section__title">Zapsané děti</h3>
        {branchId == null && <p className="notification-compose__missing">Nejdřív vyber pobočku.</p>}
        {branchId != null && eligible.length === 0 && (
          <p className="event-attachments__empty">Na této pobočce nejsou žádné děti.</p>
        )}
        <div className="training-roster">
          {eligible.map((s) => (
            <label key={s.id} className={`training-roster__item${studentIds.has(s.id) ? " is-active" : ""}`}>
              <input type="checkbox" checked={studentIds.has(s.id)} onChange={() => toggleStudent(s.id)} />
              <span>{s.first_name} {s.last_name}</span>
              <small>{s.age_group}</small>
            </label>
          ))}
        </div>
      </div>

      <div className={`notification-compose__actions${canSave ? "" : " notification-compose__actions--single"}`}>
        <button type="button" className="btn btn--ghost" onClick={onDone}>Zrušit</button>
        {canSave && (
          <button
            type="button"
            className="btn btn--primary"
            disabled={create.isPending}
            onClick={() => create.mutate()}
          >
            {create.isPending ? "Vytvářím…" : "Vytvořit trénink"}
          </button>
        )}
      </div>
      {!canSave && <p className="notification-compose__missing">Ještě chybí: {missing.join(", ")}.</p>}
      {create.isError && <div className="error-box">{String(create.error)}</div>}
    </>
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
  const parentBanner = role === "parent" ? parentRsvpBanner(event.my_child_rsvps) : null;
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
          {parentBanner && (
            <span className={`event-rsvp-banner event-rsvp-banner--${parentBanner.tone}`}>
              {parentBanner.label}
            </span>
          )}
          {role === "trainer" && event.my_rsvp && (
            <span className={`event-rsvp-chip event-rsvp-chip--${event.my_rsvp}`}>{RSVP_LABEL[event.my_rsvp]}</span>
          )}
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
  const [confirmDelete, setConfirmDelete] = useState(false);
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
    mutationFn: (responses: EventRsvpResponse[]) => api.setRsvp(eventId, responses, role),
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

      {role === "trainer" ? (
        <div className="event-rsvp">
          <span className="event-rsvp__label">Zúčastníš se?</span>
          <div className="event-rsvp__buttons">
            {(["yes", "maybe", "no"] as RsvpStatus[]).map((status) => (
              <button
                key={status}
                type="button"
                className={`event-rsvp__btn event-rsvp__btn--${status}${event.my_rsvp === status ? " is-active" : ""}`}
                disabled={setRsvp.isPending}
                onClick={() => setRsvp.mutate([{ student_id: null, status }])}
              >
                {RSVP_LABEL[status]}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <ParentRsvp
          event={event}
          pending={setRsvp.isPending}
          onSet={(responses) => setRsvp.mutate(responses)}
        />
      )}

      {event.rsvp_summary && <RsvpSummaryView summary={event.rsvp_summary} />}

      <EventAttachments event={event} role={role} onChange={invalidate} />

      <EventComments event={event} role={role} onChange={invalidate} />

      {event.can_edit && (
        confirmDelete ? (
          <div className="event-detail__confirm">
            <span className="event-detail__confirm-text">Opravdu smazat akci „{event.title}"?</span>
            <div className="event-detail__confirm-actions">
              <button type="button" className="btn btn--ghost" onClick={() => setConfirmDelete(false)}>
                Ne
              </button>
              <button
                type="button"
                className="notification-delete"
                disabled={deleteEvent.isPending}
                onClick={() => deleteEvent.mutate()}
              >
                {deleteEvent.isPending ? "Mažu…" : "Ano, smazat"}
              </button>
            </div>
          </div>
        ) : (
          <div className="event-detail__owner-actions">
            <button type="button" className="btn btn--ghost" onClick={() => setEditing(true)}>
              Upravit akci
            </button>
            <button type="button" className="notification-delete" onClick={() => setConfirmDelete(true)}>
              Smazat akci
            </button>
          </div>
        )
      )}
    </div>
  );
}

function ParentRsvp({
  event,
  pending,
  onSet,
}: {
  event: EventDetail;
  pending: boolean;
  onSet: (responses: EventRsvpResponse[]) => void;
}) {
  const children = event.my_child_rsvps;
  const statuses: RsvpStatus[] = ["yes", "maybe", "no"];
  if (children.length === 0) {
    return <p className="event-rsvp__label">Tato akce se netýká tvých dětí.</p>;
  }
  const anyPending = children.some((c) => c.status == null);
  return (
    <div className="event-rsvp event-rsvp--children">
      <span className="event-rsvp__label">Účast dětí</span>
      {anyPending && <p className="event-rsvp__pending">Ještě jsi nehlasoval/a za všechny děti.</p>}
      {children.map((child) => (
        <div key={child.student_id} className="event-rsvp__child">
          <span className="event-rsvp__child-name">{child.name}</span>
          <div className="event-rsvp__buttons">
            {statuses.map((status) => (
              <button
                key={status}
                type="button"
                className={`event-rsvp__btn event-rsvp__btn--${status}${child.status === status ? " is-active" : ""}`}
                disabled={pending}
                onClick={() => onSet([{ student_id: child.student_id, status }])}
              >
                {RSVP_LABEL[status]}
              </button>
            ))}
          </div>
        </div>
      ))}
      {children.length > 1 && (
        <div className="event-rsvp__all">
          <span className="event-rsvp__all-label">Stejné pro všechny děti:</span>
          <div className="event-rsvp__buttons">
            {statuses.map((status) => (
              <button
                key={status}
                type="button"
                className={`event-rsvp__btn event-rsvp__btn--${status}`}
                disabled={pending}
                onClick={() => onSet(children.map((c) => ({ student_id: c.student_id, status })))}
              >
                {RSVP_LABEL[status]}
              </button>
            ))}
          </div>
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
          <DateTimeField value={startsAt} onChange={setStartsAt} />
        </label>
        <label className="notification-field">
          Konec (nepovinné)
          <DateTimeField value={endsAt} onChange={setEndsAt} />
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
            <li
              key={`${p.kind}:${p.id}:${p.student_id ?? "self"}`}
              className={`event-summary__person event-summary__person--${p.status}`}
            >
              {p.kind === "parent" && p.child_name
                ? `${p.child_name} (${p.name})`
                : `${p.name} ${p.kind === "parent" ? "(rodič)" : "(trenér)"}`}
              {" — "}
              {RSVP_LABEL[p.status]}
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
      {role === "trainer" && (
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
      )}
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

function occurrenceDateKey(dateStr: string): string {
  const [y, m, d] = dateStr.split("-").map(Number);
  return new Date(y, m - 1, d).toDateString();
}

function CalendarView({
  events,
  occurrences,
  view,
  anchor,
  visibleDays,
  onViewChange,
  onAnchorChange,
  onSelect,
  activeId,
  onSelectOccurrence,
  onSelectDay,
}: {
  events: EventItem[];
  occurrences: TrainingOccurrence[];
  view: CalView;
  anchor: Date;
  visibleDays: Date[];
  onViewChange: (view: CalView) => void;
  onAnchorChange: (anchor: Date) => void;
  onSelect: (id: number) => void;
  activeId: number | null;
  onSelectOccurrence: (occ: TrainingOccurrence) => void;
  onSelectDay?: (day: Date) => void;
}) {
  const byDay = useMemo(() => {
    const map = new Map<string, EventItem[]>();
    for (const event of events) {
      const key = startOfDay(new Date(event.starts_at)).toDateString();
      const list = map.get(key) ?? [];
      list.push(event);
      map.set(key, list);
    }
    return map;
  }, [events]);

  const occByDay = useMemo(() => {
    const map = new Map<string, TrainingOccurrence[]>();
    for (const occ of occurrences) {
      const key = occurrenceDateKey(occ.date);
      const list = map.get(key) ?? [];
      list.push(occ);
      map.set(key, list);
    }
    return map;
  }, [occurrences]);

  const today = startOfDay(new Date()).toDateString();

  const step = (dir: number) => {
    if (view === "day") return onAnchorChange(addDays(anchor, dir));
    if (view === "week") return onAnchorChange(addDays(anchor, dir * 7));
    return onAnchorChange(startOfDay(new Date(anchor.getFullYear(), anchor.getMonth() + dir, 1)));
  };

  const title =
    view === "day"
      ? anchor.toLocaleDateString("cs-CZ", { weekday: "long", day: "numeric", month: "long", year: "numeric" })
      : view === "week"
        ? `${visibleDays[0].toLocaleDateString("cs-CZ", { day: "numeric", month: "short" })} – ${visibleDays[6].toLocaleDateString("cs-CZ", { day: "numeric", month: "short", year: "numeric" })}`
        : anchor.toLocaleDateString("cs-CZ", { month: "long", year: "numeric" });

  const pill = (event: EventItem) => (
    <button
      key={`e${event.id}`}
      type="button"
      className={`event-calendar__pill event-type--${event.event_type}${activeId === event.id ? " is-active" : ""}`}
      onClick={(e) => {
        e.stopPropagation();
        onSelect(event.id);
      }}
      title={event.title}
    >
      {formatTime(event.starts_at)} {event.title}
    </button>
  );

  const occPill = (occ: TrainingOccurrence) => (
    <button
      key={`t${occ.group_id}-${occ.date}`}
      type="button"
      className={`event-calendar__pill event-type--training${occ.canceled ? " is-canceled" : ""}`}
      onClick={(e) => {
        e.stopPropagation();
        onSelectOccurrence(occ);
      }}
      title={`${occ.name} ${occ.start_time.slice(0, 5)}`}
    >
      {occ.start_time.slice(0, 5)} {occ.name}
    </button>
  );

  return (
    <section className="event-calendar">
      <div className="event-calendar__toolbar">
        <div className="event-calendar__viewtoggle">
          {(["month", "week", "day"] as CalView[]).map((v) => (
            <button
              key={v}
              type="button"
              className={view === v ? "is-active" : ""}
              onClick={() => onViewChange(v)}
            >
              {v === "month" ? "Měsíc" : v === "week" ? "Týden" : "Den"}
            </button>
          ))}
        </div>
        <div className="event-calendar__nav">
          <button type="button" className="event-calendar__arrow" onClick={() => step(-1)} aria-label="Předchozí">
            ‹
          </button>
          <button type="button" className="event-calendar__today" onClick={() => onAnchorChange(startOfDay(new Date()))}>
            Dnes
          </button>
          <button type="button" className="event-calendar__arrow" onClick={() => step(1)} aria-label="Další">
            ›
          </button>
        </div>
        {view === "day" ? (
          <input
            type="date"
            className="event-calendar__jump"
            value={toDateInputValue(anchor)}
            onChange={(e) => {
              if (!e.target.value) return;
              const [y, m, d] = e.target.value.split("-").map(Number);
              onAnchorChange(startOfDay(new Date(y, m - 1, d)));
            }}
          />
        ) : (
          <input
            type="month"
            className="event-calendar__jump"
            value={`${anchor.getFullYear()}-${String(anchor.getMonth() + 1).padStart(2, "0")}`}
            onChange={(e) => {
              if (!e.target.value) return;
              const [y, m] = e.target.value.split("-").map(Number);
              onAnchorChange(startOfDay(new Date(y, m - 1, 1)));
            }}
          />
        )}
      </div>

      <div className="event-calendar__title">{title}</div>

      {view === "month" && (
        <>
          <div className="event-calendar__weekdays">
            {["Po", "Út", "St", "Čt", "Pá", "So", "Ne"].map((d) => (
              <span key={d}>{d}</span>
            ))}
          </div>
          <div className="event-calendar__grid">
            {visibleDays.map((day) => {
              const key = day.toDateString();
              const dayEvents = byDay.get(key) ?? [];
              const dayOccurrences = occByDay.get(key) ?? [];
              const isOtherMonth = day.getMonth() !== anchor.getMonth();
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
                    {dayEvents.map(pill)}
                    {dayOccurrences.map(occPill)}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {view !== "month" && (
        <div className={`event-calendar__agenda event-calendar__agenda--${view}`}>
          {visibleDays.map((day) => {
            const key = day.toDateString();
            const dayEvents = byDay.get(key) ?? [];
            const dayOccurrences = occByDay.get(key) ?? [];
            const empty = dayEvents.length === 0 && dayOccurrences.length === 0;
            return (
              <div
                key={key}
                className={`event-calendar__agenda-day${key === today ? " is-today" : ""}${onSelectDay ? " is-clickable" : ""}`}
                onClick={onSelectDay ? () => onSelectDay(new Date(day)) : undefined}
                role={onSelectDay ? "button" : undefined}
              >
                <div className="event-calendar__agenda-head">
                  <span className="event-calendar__agenda-weekday">
                    {day.toLocaleDateString("cs-CZ", { weekday: "short" })}
                  </span>
                  <span className="event-calendar__agenda-date">
                    {day.toLocaleDateString("cs-CZ", { day: "numeric", month: "numeric" })}
                  </span>
                </div>
                <div className="event-calendar__events">
                  {dayEvents.map(pill)}
                  {dayOccurrences.map(occPill)}
                  {empty && <span className="event-calendar__agenda-empty">—</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

function TrainingOccurrencePanel({
  occurrence,
  role,
  onClose,
  onChanged,
}: {
  occurrence: TrainingOccurrence;
  role: Role;
  onClose: () => void;
  onChanged: () => void;
}) {
  const queryClient = useQueryClient();
  const [sessionId, setSessionId] = useState<number | null>(occurrence.session_id);
  const [savingIds, setSavingIds] = useState<Set<number>>(new Set());
  const [editing, setEditing] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const openSession = useMutation({
    mutationFn: () => api.openGroupSession(occurrence.group_id, occurrence.date),
    onSuccess: (session) => {
      setSessionId(session.id);
      onChanged();
    },
  });

  const deleteSeries = useMutation({
    mutationFn: () => api.deleteTrainingGroup(occurrence.group_id),
    onSuccess: () => {
      onChanged();
      onClose();
    },
  });

  const deleteTerm = useMutation({
    mutationFn: async () => {
      let sid = sessionId;
      if (sid == null) {
        const created = await api.openGroupSession(occurrence.group_id, occurrence.date);
        sid = created.id;
      }
      await api.cancelOccurrence(sid, true);
    },
    onSuccess: () => {
      onChanged();
      onClose();
    },
  });

  const detailQuery = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => api.session(sessionId as number),
    enabled: sessionId != null && role === "trainer",
  });

  const cancelMutation = useMutation({
    mutationFn: (canceled: boolean) =>
      api.cancelOccurrence(sessionId as number, canceled),
    onSuccess: () => {
      onChanged();
      if (sessionId != null) queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
    },
  });

  const setStatus = async (studentId: number, status: AttendanceStatus, attendanceId?: number) => {
    if (sessionId == null) return;
    setSavingIds((cur) => new Set(cur).add(studentId));
    try {
      await api.setAttendance(sessionId, studentId, status, attendanceId);
      queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
      onChanged();
    } finally {
      setSavingIds((cur) => {
        const next = new Set(cur);
        next.delete(studentId);
        return next;
      });
    }
  };

  const dateLabel = new Date(occurrenceDateKey(occurrence.date)).toLocaleDateString("cs-CZ", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  if (editing) {
    return (
      <TrainingEditForm
        groupId={occurrence.group_id}
        onCancel={() => setEditing(false)}
        onSaved={() => {
          setEditing(false);
          onChanged();
          onClose();
        }}
      />
    );
  }

  if (confirmingDelete) {
    return (
      <div className="event-detail">
        <p className="event-rsvp__pending">Co chceš smazat?</p>
        <div className="occurrence-delete-choice">
          <button
            type="button"
            className="occurrence-delete-choice__btn"
            disabled={deleteTerm.isPending}
            onClick={() => deleteTerm.mutate()}
          >
            <strong>Jen tento termín</strong>
            <small>{dateLabel} — ostatní termíny zůstanou</small>
          </button>
          <button
            type="button"
            className="occurrence-delete-choice__btn occurrence-delete-choice__btn--danger"
            disabled={deleteSeries.isPending}
            onClick={() => {
              if (
                window.confirm(
                  `Smazat celou sérii „${occurrence.name}"? Smažou se všechny termíny i zaznamenaná docházka.`,
                )
              ) {
                deleteSeries.mutate();
              }
            }}
          >
            <strong>Celou sérii</strong>
            <small>Všechny termíny + docházka</small>
          </button>
        </div>
        <div className="notification-compose__actions notification-compose__actions--single">
          <button type="button" className="btn btn--ghost" onClick={() => setConfirmingDelete(false)}>
            Zpět
          </button>
        </div>
        {(deleteTerm.isError || deleteSeries.isError) && (
          <div className="error-box">{String(deleteTerm.error ?? deleteSeries.error)}</div>
        )}
      </div>
    );
  }

  return (
    <div className="event-detail event-detail--occurrence">
      {role === "trainer" && (
        <div className="events-toolbar__actions">
          <button type="button" className="btn btn--ghost" onClick={() => setEditing(true)}>
            Upravit trénink
          </button>
          <button type="button" className="notification-delete" onClick={() => setConfirmingDelete(true)}>
            Smazat
          </button>
        </div>
      )}

      <dl className="event-detail__facts">
        <div>
          <dt>Kdy</dt>
          <dd>{dateLabel} · {occurrence.start_time.slice(0, 5)}–{occurrence.end_time.slice(0, 5)}</dd>
        </div>
        <div>
          <dt>Zapsáno</dt>
          <dd>{occurrence.roster_count} dětí</dd>
        </div>
      </dl>

      {role !== "trainer" ? (
        <p className="event-rsvp__label">Docházku zaznamenává trenér na místě.</p>
      ) : sessionId == null ? (
        <div className="event-rsvp">
          <button
            type="button"
            className="btn btn--primary"
            disabled={openSession.isPending}
            onClick={() => openSession.mutate()}
          >
            {openSession.isPending ? "Otevírám…" : "Otevřít docházku"}
          </button>
          {openSession.isError && <div className="error-box">{String(openSession.error)}</div>}
        </div>
      ) : detailQuery.isLoading ? (
        <div className="loading">Načítám…</div>
      ) : detailQuery.data ? (
        <>
          {detailQuery.data.canceled && <p className="event-rsvp__pending">Tento termín je zrušený.</p>}
          <AttendanceOverview
            students={detailQuery.data.students}
            onStatus={setStatus}
            isSaving={(id) => savingIds.has(id)}
          />
          <div className="event-detail__owner-actions">
            <button
              type="button"
              className="btn btn--ghost"
              disabled={cancelMutation.isPending}
              onClick={() => cancelMutation.mutate(!detailQuery.data?.canceled)}
            >
              {detailQuery.data.canceled ? "Obnovit termín" : "Zrušit tento termín"}
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}

function TrainingEditForm({
  groupId,
  onCancel,
  onSaved,
}: {
  groupId: number;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const groupQuery = useQuery({ queryKey: ["training-group", groupId], queryFn: () => api.trainingGroup(groupId) });
  if (groupQuery.isLoading) return <div className="loading">Načítám…</div>;
  if (groupQuery.isError || !groupQuery.data) {
    return <div className="error-box">{String(groupQuery.error)}</div>;
  }
  return <TrainingEditFields group={groupQuery.data} onCancel={onCancel} onSaved={onSaved} />;
}

function TrainingEditFields({
  group,
  onCancel,
  onSaved,
}: {
  group: import("../api/types").TrainingGroup;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(group.name);
  const [startTime, setStartTime] = useState(group.start_time.slice(0, 5));
  const [endTime, setEndTime] = useState(group.end_time.slice(0, 5));
  const [weekdays, setWeekdays] = useState<Set<number>>(() => new Set(group.weekdays ?? []));
  const [activeFrom, setActiveFrom] = useState(group.active_from ?? "");
  const [activeUntil, setActiveUntil] = useState(group.active_until ?? "");
  const [studentIds, setStudentIds] = useState<Set<number>>(() => new Set(group.students.map((s) => s.id)));

  const studentsQuery = useQuery({ queryKey: ["students"], queryFn: () => api.students() });
  const students = studentsQuery.data ?? [];
  const eligible = useMemo(
    () => students.filter((s) => s.branches.some((b) => b.id === group.branch_id)),
    [students, group.branch_id],
  );

  const save = useMutation({
    mutationFn: async () => {
      await api.updateTrainingGroup(group.id, {
        name,
        start_time: startTime,
        end_time: endTime,
        weekdays: [...weekdays].sort((a, b) => a - b),
        active_from: activeFrom || null,
        active_until: activeUntil || null,
      });
      await api.replaceGroupStudents(group.id, [...studentIds]);
    },
    onSuccess: onSaved,
  });

  const missing: string[] = [];
  if (!name.trim()) missing.push("název");
  if (weekdays.size === 0) missing.push("alespoň jeden den");
  if (endTime <= startTime) missing.push("konec po začátku");
  if (activeFrom && activeUntil && activeUntil < activeFrom) missing.push("konec po začátku opakování");
  const canSave = missing.length === 0;

  const toggleWeekday = (d: number) =>
    setWeekdays((cur) => {
      const next = new Set(cur);
      if (next.has(d)) next.delete(d);
      else next.add(d);
      return next;
    });
  const toggleStudent = (id: number) =>
    setStudentIds((cur) => {
      const next = new Set(cur);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <>
      <div className="events-compose__row">
        <label className="notification-field">
          Název tréninku
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
      </div>
      <div className="events-compose__row">
        <label className="notification-field">
          Začátek
          <TimeField value={startTime} onChange={setStartTime} />
        </label>
        <label className="notification-field">
          Konec
          <TimeField value={endTime} onChange={setEndTime} />
        </label>
      </div>

      <div className="notification-section">
        <h3 className="notification-section__title">Opakování (týdně)</h3>
        <div className="training-weekdays">
          {WEEKDAYS.map((w) => (
            <button
              key={w.value}
              type="button"
              className={`training-weekday${weekdays.has(w.value) ? " is-active" : ""}`}
              onClick={() => toggleWeekday(w.value)}
            >
              {w.label}
            </button>
          ))}
        </div>
        <div className="events-compose__row">
          <label className="notification-field">
            Opakovat od
            <DateField value={activeFrom} onChange={setActiveFrom} />
          </label>
          <label className="notification-field">
            Opakovat do
            <DateField value={activeUntil} onChange={setActiveUntil} />
          </label>
        </div>
      </div>

      <div className="notification-section">
        <h3 className="notification-section__title">Zapsané děti</h3>
        {eligible.length === 0 && <p className="event-attachments__empty">Na této pobočce nejsou žádné děti.</p>}
        <div className="training-roster">
          {eligible.map((s) => (
            <label key={s.id} className={`training-roster__item${studentIds.has(s.id) ? " is-active" : ""}`}>
              <input type="checkbox" checked={studentIds.has(s.id)} onChange={() => toggleStudent(s.id)} />
              <span>{s.first_name} {s.last_name}</span>
              <small>{s.age_group}</small>
            </label>
          ))}
        </div>
      </div>

      <div className="notification-compose__actions">
        <button type="button" className="btn btn--ghost" onClick={onCancel}>Zrušit</button>
        <button
          type="button"
          className="btn btn--primary"
          disabled={!canSave || save.isPending}
          onClick={() => save.mutate()}
        >
          {save.isPending ? "Ukládám…" : "Uložit změny"}
        </button>
      </div>
      {!canSave && <p className="notification-compose__missing">Ještě chybí: {missing.join(", ")}.</p>}
      {save.isError && <div className="error-box">{String(save.error)}</div>}
    </>
  );
}

