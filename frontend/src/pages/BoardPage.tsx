import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { NotificationAudience, NotificationDurationUnit, NotificationTargetCreate } from "../api/types";
import { TrainerSwitcher } from "../components/TrainerSwitcher";
import { useTrainer } from "../context/TrainerContext";

type SelectedPerson = {
  key: string;
  label: string;
  target: NotificationTargetCreate;
};

function normalize(value: string) {
  return value.trim().toLocaleLowerCase("cs-CZ");
}

function formatDate(value: string) {
  return new Date(value).toLocaleString("cs-CZ", {
    day: "numeric",
    month: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function audienceLabel(audience: NotificationAudience) {
  return audience === "trainer" ? "Trenéři" : "Rodiče";
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
  const { trainer, trainers, isAuthenticated, isLoading } = useTrainer();
  const [composeOpen, setComposeOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [trainerAudience, setTrainerAudience] = useState(false);
  const [parentAudience, setParentAudience] = useState(false);
  const [allAudience, setAllAudience] = useState(false);
  const [search, setSearch] = useState("");
  const [selectedPeople, setSelectedPeople] = useState<SelectedPerson[]>([]);
  const [expiryMode, setExpiryMode] = useState<"duration" | "exact">("duration");
  const [durationAmount, setDurationAmount] = useState(7);
  const [durationUnit, setDurationUnit] = useState<NotificationDurationUnit>("days");
  const [visibleUntil, setVisibleUntil] = useState(() => toDatetimeLocalValue(new Date(Date.now() + 7 * 24 * 60 * 60 * 1000)));

  const parentsQuery = useQuery({
    queryKey: ["parents"],
    queryFn: () => api.parents(),
    enabled: isAuthenticated,
  });
  const notificationsQuery = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api.notifications(),
    enabled: isAuthenticated,
  });

  const parents = parentsQuery.data ?? [];
  const people = useMemo<SelectedPerson[]>(() => {
    const trainerPeople = trainers.map((row) => ({
      key: `trainer:${row.id}`,
      label: `${row.first_name} ${row.last_name} · trenér`,
      target: { audience: "trainer" as const, trainer_id: row.id },
    }));
    const parentPeople = parents.map((row) => ({
      key: `parent:${row.id}`,
      label: `${row.first_name} ${row.last_name} · rodič · ${row.email}`,
      target: { audience: "parent" as const, parent_id: row.id },
    }));
    return [...trainerPeople, ...parentPeople];
  }, [parents, trainers]);

  const searchResults = useMemo(() => {
    const term = normalize(search);
    if (!term) return [];
    const selected = new Set(selectedPeople.map((person) => person.key));
    return people
      .filter((person) => !selected.has(person.key) && normalize(person.label).includes(term))
      .slice(0, 6);
  }, [people, search, selectedPeople]);

  const createNotification = useMutation({
    mutationFn: () => {
      const audiences: NotificationAudience[] = [];
      if (allAudience || trainerAudience) audiences.push("trainer");
      if (allAudience || parentAudience) audiences.push("parent");
      return api.createNotification({
        title,
        body,
        audiences,
        targets: selectedPeople.map((person) => person.target),
        ...(expiryMode === "duration"
          ? { duration_amount: durationAmount, duration_unit: durationUnit }
          : { visible_until: new Date(visibleUntil).toISOString() }),
      });
    },
    onSuccess: () => {
      setComposeOpen(false);
      setTitle("");
      setBody("");
      setTrainerAudience(false);
      setParentAudience(false);
      setAllAudience(false);
      setSearch("");
      setSelectedPeople([]);
      setExpiryMode("duration");
      setDurationAmount(7);
      setDurationUnit("days");
      setVisibleUntil(toDatetimeLocalValue(new Date(Date.now() + 7 * 24 * 60 * 60 * 1000)));
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

  const hasTarget =
    allAudience || trainerAudience || parentAudience || selectedPeople.length > 0;
  const hasValidExpiry =
    expiryMode === "duration" ? durationAmount >= 1 : Boolean(visibleUntil);

  return (
    <div className="app-shell notification-board">
      <header className="page-header">
        <div className="page-header__row">
          <div>
            <p className="page-header__eyebrow">Board</p>
            <h1 className="page-header__title">Notifications</h1>
            <p className="page-header__sub">Zprávy pro trenéry a rodiče</p>
          </div>
          <Link className="board-link" to="/">Menu</Link>
        </div>
      </header>

      <TrainerSwitcher variant="bar" />

      <div className="notification-actions">
        <button type="button" className="btn btn--primary" onClick={() => setComposeOpen(true)}>
          Nová notification
        </button>
      </div>

      {composeOpen && (
        <section className="notification-compose">
          <h2>Nová notification</h2>
          <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Název" />
          <textarea value={body} onChange={(event) => setBody(event.target.value)} placeholder="Text zprávy" rows={4} />

          <div className="notification-checks">
            <label>
              <input
                type="checkbox"
                checked={trainerAudience}
                disabled={allAudience}
                onChange={(event) => setTrainerAudience(event.target.checked)}
              />
              Trenéři
            </label>
            <label>
              <input
                type="checkbox"
                checked={parentAudience}
                disabled={allAudience}
                onChange={(event) => setParentAudience(event.target.checked)}
              />
              Rodiče
            </label>
            <label>
              <input
                type="checkbox"
                checked={allAudience}
                onChange={(event) => setAllAudience(event.target.checked)}
              />
              Všichni
            </label>
          </div>

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

          <div className="notification-search">
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Začni psát jméno trenéra nebo rodiče"
            />
            {searchResults.length > 0 && (
              <div className="notification-search__results">
                {searchResults.map((person) => (
                  <button
                    key={person.key}
                    type="button"
                    onClick={() => {
                      setSelectedPeople((current) => [...current, person]);
                      setSearch("");
                    }}
                  >
                    {person.label}
                  </button>
                ))}
              </div>
            )}
          </div>

          {selectedPeople.length > 0 && (
            <div className="notification-chips">
              {selectedPeople.map((person) => (
                <button
                  key={person.key}
                  type="button"
                  onClick={() => setSelectedPeople((current) => current.filter((row) => row.key !== person.key))}
                >
                  {person.label} ×
                </button>
              ))}
            </div>
          )}

          <div className="notification-compose__actions">
            <button
              className="btn btn--ghost"
              type="button"
              onClick={() => setComposeOpen(false)}
            >
              Zrušit
            </button>
            <button
              className="btn btn--primary"
              type="button"
              disabled={!title.trim() || !body.trim() || !hasTarget || !hasValidExpiry || createNotification.isPending}
              onClick={() => createNotification.mutate()}
            >
              {createNotification.isPending ? "Publikuji…" : "Publikovat"}
            </button>
          </div>
          {createNotification.isError && <div className="error-box">{String(createNotification.error)}</div>}
        </section>
      )}

      <section className="notification-list">
        <h2>Existing notifications</h2>
        {notificationsQuery.isLoading && <div className="loading">Načítám…</div>}
        {notificationsQuery.isError && <div className="error-box">{String(notificationsQuery.error)}</div>}
        {(notificationsQuery.data ?? []).map((notification) => {
          const broadcastTargets = notification.targets.filter((target) => target.trainer_id == null && target.parent_id == null);
          return (
            <article
              className={`notification-card${notification.visibility_state === "expired" ? " notification-card--expired" : ""}`}
              key={notification.id}
            >
              <div>
                <span className="notification-card__meta">
                  {formatDate(notification.created_at)}
                  {notification.author_trainer ? ` · ${notification.author_trainer.first_name} ${notification.author_trainer.last_name}` : ""}
                </span>
                <h3>{notification.title}</h3>
                <p>{notification.body}</p>
                <small>
                  {broadcastTargets.map((target) => audienceLabel(target.audience)).join(", ") || "Jednotlivci"}
                  {" · "}
                  {notification.visibility_state === "expired" ? "expired" : `visible do ${formatDate(notification.visible_until)}`}
                </small>
              </div>
              {notification.can_delete && (
                <button
                  type="button"
                  className="notification-delete"
                  disabled={deleteNotification.isPending}
                  onClick={() => deleteNotification.mutate(notification.id)}
                >
                  Smazat
                </button>
              )}
            </article>
          );
        })}
        {!notificationsQuery.isLoading && (notificationsQuery.data ?? []).length === 0 && (
          <div className="loading">Zatím tu nejsou žádné notifications.</div>
        )}
      </section>
    </div>
  );
}
