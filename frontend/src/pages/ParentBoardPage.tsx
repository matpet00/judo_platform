import { Link, Navigate } from "react-router-dom";
import { useParent } from "../context/ParentContext";
import { ParentNotifications } from "../components/ParentNotifications";

export function ParentBoardPage() {
  const { parent, isAuthenticated, isLoading } = useParent();

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

  return (
    <div className="app-shell notification-board">
      <header className="page-header">
        <div className="page-header__row">
          <div>
            <p className="page-header__eyebrow">Nástěnka</p>
            <h1 className="page-header__title">Oznámení</h1>
            <p className="page-header__sub">Zprávy pro tvoje děti – můžeš reagovat ve vlákně</p>
          </div>
          <Link className="board-link" to="/parent">Zpět</Link>
        </div>
      </header>

      <div className="notification-board parent-board">
        <ParentNotifications parentId={parent.id} />
      </div>
    </div>
  );
}
