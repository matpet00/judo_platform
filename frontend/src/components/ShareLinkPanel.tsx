import { useEffect, useState } from "react";
import {
  absoluteShareUrl,
  copyText,
  qrDataUrl,
  shareToWhatsApp,
} from "../lib/whatsappShare";

type Props = {
  path: string;
  whatsappMessage: string;
  /** Shown next to the collapsed share control after create. */
  successText?: string;
  onDone?: () => void;
  doneLabel?: string;
  defaultOpen?: boolean;
};

export function ShareLinkPanel({
  path,
  whatsappMessage,
  successText,
  onDone,
  doneLabel = "Hotovo",
  defaultOpen = false,
}: Props) {
  const shareUrl = absoluteShareUrl(path);
  const [open, setOpen] = useState(defaultOpen);
  const [qr, setQr] = useState<string | null>(null);
  const [copied, setCopied] = useState<"link" | "text" | null>(null);
  const [waHint, setWaHint] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    void qrDataUrl(shareUrl).then((data) => {
      if (!cancelled) setQr(data);
    });
    return () => {
      cancelled = true;
    };
  }, [open, shareUrl]);

  const flashCopied = (kind: "link" | "text") => {
    setCopied(kind);
    window.setTimeout(() => setCopied(null), 2000);
  };

  const onWhatsApp = async () => {
    setWaHint(null);
    const result = await shareToWhatsApp(whatsappMessage);
    if (result === "copied") {
      setWaHint("Celý text je ve schránce — ve WhatsAppu ho vlož (dlouhým stiskem).");
    }
  };

  return (
    <section className={`share-link-panel${open ? " is-open" : ""}`}>
      {(successText || onDone) && (
        <div className="share-link-panel__bar">
          {successText && <p className="share-link-panel__success">{successText}</p>}
          <div className="share-link-panel__bar-actions">
            <button
              type="button"
              className={`btn share-link-panel__toggle${open ? " is-active" : ""}`}
              aria-expanded={open}
              onClick={() => setOpen((v) => !v)}
            >
              {open ? "Skrýt sdílení" : "Sdílet"}
            </button>
            {onDone && (
              <button type="button" className="btn btn--ghost" onClick={onDone}>
                {doneLabel}
              </button>
            )}
          </div>
        </div>
      )}

      {!successText && !onDone && (
        <button
          type="button"
          className={`btn share-link-panel__toggle${open ? " is-active" : ""}`}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "Skrýt sdílení" : "Sdílet"}
        </button>
      )}

      {open && (
        <div className="share-link-panel__body">
          <div className="share-link-panel__qr-wrap">
            {qr ? (
              <img className="share-link-panel__qr" src={qr} alt="QR kód s odkazem na akci" />
            ) : (
              <p className="page-header__sub">Připravuji QR…</p>
            )}
          </div>

          <p className="share-link-panel__url">{shareUrl}</p>

          <pre className="share-link-panel__preview">{whatsappMessage}</pre>

          <div className="share-link-panel__actions">
            <button type="button" className="btn btn--primary" onClick={() => void onWhatsApp()}>
              WhatsApp
            </button>
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => {
                void copyText(whatsappMessage).then((ok) => {
                  if (ok) flashCopied("text");
                });
              }}
            >
              {copied === "text" ? "Text zkopírován" : "Kopírovat text"}
            </button>
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => {
                void copyText(shareUrl).then((ok) => {
                  if (ok) flashCopied("link");
                });
              }}
            >
              {copied === "link" ? "Odkaz zkopírován" : "Kopírovat odkaz"}
            </button>
          </div>
          {waHint && <p className="share-link-panel__hint">{waHint}</p>}
        </div>
      )}
    </section>
  );
}
