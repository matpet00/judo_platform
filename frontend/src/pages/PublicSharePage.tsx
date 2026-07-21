import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { EventType } from "../api/types";
import { ClubLogo } from "../components/ClubLogo";

const EVENT_TYPE_LABELS: Record<EventType, string> = {
  tournament: "Turnaj",
  meeting: "Schůzka",
  seminar: "Školení",
  training: "Trénink (akce)",
  other: "Jiné",
};

const WEEKDAY_LABELS = ["", "Po", "Út", "St", "Čt", "Pá", "So", "Ne"];

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("cs-CZ", {
    weekday: "short",
    day: "numeric",
    month: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatTime(value: string): string {
  return value.slice(0, 5);
}

export function PublicEventSharePage() {
  const { token = "" } = useParams();
  const query = useQuery({
    queryKey: ["public-event", token],
    queryFn: () => api.publicEventShare(token),
    enabled: Boolean(token),
  });

  return (
    <div className="boot-screen app-shell">
      <div className="auth-card share-public-card">
        <header className="trainer-picker__header">
          <ClubLogo variant="header" />
          <h1 className="trainer-picker__title">Akce klubu</h1>
        </header>

        {query.isLoading && <p className="page-header__sub">Načítám…</p>}
        {query.isError && <p className="error-box">{String(query.error)}</p>}
        {query.data && (
          <article className="share-public">
            <p className="share-public__eyebrow">{EVENT_TYPE_LABELS[query.data.event_type]}</p>
            <h2 className="share-public__title">{query.data.title}</h2>
            <dl className="share-public__meta">
              <div>
                <dt>Začátek</dt>
                <dd>{formatDateTime(query.data.starts_at)}</dd>
              </div>
              {query.data.ends_at && (
                <div>
                  <dt>Konec</dt>
                  <dd>{formatDateTime(query.data.ends_at)}</dd>
                </div>
              )}
              {query.data.location.trim() && (
                <div>
                  <dt>Místo</dt>
                  <dd>{query.data.location}</dd>
                </div>
              )}
              {query.data.audience_labels.length > 0 && (
                <div>
                  <dt>Určeno pro</dt>
                  <dd>{query.data.audience_labels.join("; ")}</dd>
                </div>
              )}
            </dl>
            {query.data.description.trim() && (
              <p className="share-public__body">{query.data.description}</p>
            )}

            {query.data.intended_for_you === false && (
              <p className="share-public__notice share-public__notice--warn">
                Tato akce není určena pro vaše děti (jiná věková kategorie / pobočka). V aplikaci ji
                neuvidíte a účast za ně potvrdit nelze.
              </p>
            )}
            {query.data.intended_for_you === true && (
              <p className="share-public__notice">
                Akce je pro vás — po otevření aplikace ji najdete v Kalendáři / Akcích a můžete potvrdit
                účast.
              </p>
            )}
            {query.data.intended_for_you == null && (
              <p className="share-public__cta-hint">
                Potvrzení účasti je v aplikaci po přihlášení. Akci uvidí jen rodiče z cílových skupin
                (např. U8).
              </p>
            )}
            <div className="confirm-card__actions">
              <Link to={query.data.intended_for_you === false ? "/" : "/parent/events"} className="btn btn--primary">
                {query.data.intended_for_you === false ? "Zpět na úvod" : "Otevřít v aplikaci"}
              </Link>
            </div>
          </article>
        )}
      </div>
    </div>
  );
}

export function PublicTrainingSharePage() {
  const { token = "" } = useParams();
  const query = useQuery({
    queryKey: ["public-training", token],
    queryFn: () => api.publicTrainingShare(token),
    enabled: Boolean(token),
  });

  const weekdays =
    query.data?.weekdays?.map((d) => WEEKDAY_LABELS[d] ?? String(d)).join(", ") ?? "—";

  return (
    <div className="boot-screen app-shell">
      <div className="auth-card share-public-card">
        <header className="trainer-picker__header">
          <ClubLogo variant="header" />
          <h1 className="trainer-picker__title">Tréninková série</h1>
        </header>

        {query.isLoading && <p className="page-header__sub">Načítám…</p>}
        {query.isError && <p className="error-box">{String(query.error)}</p>}
        {query.data && (
          <article className="share-public">
            <h2 className="share-public__title">{query.data.name}</h2>
            <dl className="share-public__meta">
              <div>
                <dt>Pobočka</dt>
                <dd>{query.data.branch_name}</dd>
              </div>
              <div>
                <dt>Čas</dt>
                <dd>
                  {formatTime(query.data.start_time)}–{formatTime(query.data.end_time)}
                </dd>
              </div>
              <div>
                <dt>Dny</dt>
                <dd>{weekdays}</dd>
              </div>
              {(query.data.active_from || query.data.active_until) && (
                <div>
                  <dt>Období</dt>
                  <dd>
                    {query.data.active_from ?? "…"} – {query.data.active_until ?? "…"}
                  </dd>
                </div>
              )}
            </dl>
            <p className="share-public__cta-hint">
              Informativní přehled série. Docházku a zápisy řeší trenér v aplikaci.
            </p>
            <div className="confirm-card__actions">
              <Link to="/" className="btn btn--primary">
                Otevřít aplikaci
              </Link>
            </div>
          </article>
        )}
      </div>
    </div>
  );
}
