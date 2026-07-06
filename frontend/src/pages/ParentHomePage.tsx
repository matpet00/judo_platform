import { Navigate, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { countUnreadBoard, countUnreadPlanner } from "../lib/notificationNavigation";
import { parentNotificationsKey } from "../api/queryKeys";
import { useParent } from "../context/ParentContext";

export function ParentHomePage() {
  const navigate = useNavigate();
  const { parent, isAuthenticated, isLoading, clearParent } = useParent();

  const notificationsQuery = useQuery({
    queryKey: parentNotificationsKey(parent?.id),
    queryFn: () => api.notifications("parent"),
    enabled: isAuthenticated && !!parent,
    refetchInterval: 5_000,
    refetchOnWindowFocus: true,
  });
  const notifs = notificationsQuery.data ?? [];
  const unreadBoard = countUnreadBoard(notifs);
  const unreadEvents = countUnreadPlanner(notifs);

  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  if (isLoading || !parent) {
    return (
      <div className="boot-screen">
        <div className="boot-screen__logo">JUDO</div>
        <p className="page-header__sub">Načítám profil…</p>
      </div>
    );
  }

  const logout = () => {
    clearParent();
    navigate("/", { replace: true });
  };

  return (
    <div className="boot-screen app-shell">
      <div className="hub-card">
        <p className="page-header__eyebrow">Rodič</p>
        <h1 className="trainer-picker__title">
          {parent.first_name} {parent.last_name}
        </h1>
        <p className="trainer-picker__sub">Moje děti</p>

        <ul className="parent-children">
          {parent.children.length === 0 && (
            <li className="parent-children__empty">Zatím nemáš přiřazené žádné dítě.</li>
          )}
          {parent.children.map((child) => (
            <li key={child.id} className="parent-child">
              <span className="parent-child__name">
                {child.first_name} {child.last_name}
              </span>
              <span className="parent-child__meta">
                <span className="parent-child__age">{child.age_group}</span>
                {child.branches.map((b) => (
                  <span key={b.id} className="parent-child__branch">
                    {b.name}
                  </span>
                ))}
              </span>
            </li>
          ))}
        </ul>

        <button type="button" className="btn btn--primary auth-back" onClick={() => navigate("/parent/board")}>
          Nástěnka
          {unreadBoard > 0 && <span className="trainer-card__badge">{unreadBoard}</span>}
        </button>
        <button type="button" className="btn btn--primary auth-back" onClick={() => navigate("/parent/chat")}>
          Chat
        </button>
        <button type="button" className="btn btn--primary auth-back" onClick={() => navigate("/parent/events")}>
          Akce
          {unreadEvents > 0 && <span className="trainer-card__badge">{unreadEvents}</span>}
        </button>
        <button type="button" className="btn btn--ghost auth-back" onClick={logout}>
          Odhlásit
        </button>
      </div>
    </div>
  );
}
