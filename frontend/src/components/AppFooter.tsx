import { Link } from "react-router-dom";
import { CLUB_NAME } from "../lib/clubBrand";

export function AppFooter() {
  const year = new Date().getFullYear();
  return (
    <footer className="app-footer">
      <span>
        {CLUB_NAME} {year}
      </span>
      <span className="app-footer__sep" aria-hidden="true">
        ·
      </span>
      <Link to="/privacy" className="app-footer__link">
        Ochrana osobních údajů
      </Link>
    </footer>
  );
}
