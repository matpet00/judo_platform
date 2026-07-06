import { CLUB_NAME } from "../lib/clubBrand";
import "./ClubLogo.css";

type ClubLogoProps = {
  variant?: "splash" | "header" | "inline";
  showName?: boolean;
  className?: string;
};

export function ClubLogo({ variant = "header", showName = true, className = "" }: ClubLogoProps) {
  const rootClass = ["club-brand", `club-brand--${variant}`, className].filter(Boolean).join(" ");

  return (
    <div className={rootClass} aria-label={CLUB_NAME}>
      <div className="club-brand__mark">
        <img className="club-brand__image" src="/logo.png" alt="" aria-hidden="true" />
      </div>

      {showName && <p className="club-brand__name">{CLUB_NAME}</p>}
    </div>
  );
}
