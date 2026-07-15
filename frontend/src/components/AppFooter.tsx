import { Link } from "react-router-dom";

export function AppFooter() {
  const year = new Date().getFullYear();
  return (
    <footer className="app-footer">
      <span>Judo klub Orlová {year}</span>
      <span className="app-footer__sep" aria-hidden="true">
        ·
      </span>
      <Link to="/privacy" className="app-footer__link">
        Ochrana osobních údajů
      </Link>
    </footer>
  );
}
