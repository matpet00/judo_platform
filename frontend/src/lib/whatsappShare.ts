import QRCode from "qrcode";

/** Origin for QR / WhatsApp links. On localhost always use http (https://localhost breaks Safari). */
export function absoluteShareUrl(path: string): string {
  const url = new URL(window.location.origin);
  if (url.hostname === "localhost" || url.hostname === "127.0.0.1") {
    url.protocol = "http:";
  }
  const base = url.origin;
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

export function eventSharePath(token: string): string {
  return `/e/${token}`;
}

export function trainingSharePath(token: string): string {
  return `/t/${token}`;
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

export async function qrDataUrl(text: string, size = 220): Promise<string> {
  return QRCode.toDataURL(text, {
    width: size,
    margin: 2,
    errorCorrectionLevel: "M",
  });
}

function clip(text: string, max = 280): string {
  const t = text.trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max - 1).trimEnd()}…`;
}

/** WhatsApp ignores HTML; it uses *bold* _italic_ ~strike~ ```mono```. */
function waSafe(text: string): string {
  return text.replace(/[*_~`]/g, "").trim();
}

function waBold(text: string): string {
  const t = waSafe(text);
  return t ? `*${t}*` : "";
}

const WA_RULE = "────────────";

export function buildEventWhatsAppMessage(opts: {
  title: string;
  whenLabel: string;
  location?: string;
  description?: string;
  shareUrl: string;
}): string {
  const lines = [
    waBold("Nová akce"),
    WA_RULE,
    waBold(opts.title),
    "",
    `*Kdy:* ${waSafe(opts.whenLabel)}`,
  ];
  if (opts.location?.trim()) {
    lines.push(`*Kde:* ${waSafe(opts.location)}`);
  }
  if (opts.description?.trim()) {
    lines.push("");
    lines.push(waSafe(clip(opts.description)));
  }
  lines.push(WA_RULE);
  lines.push(opts.shareUrl);
  return lines.filter((line, i, arr) => !(line === "" && arr[i - 1] === "")).join("\n");
}

export function buildTrainingWhatsAppMessage(opts: {
  name: string;
  branchName: string;
  scheduleLabel: string;
  shareUrl: string;
}): string {
  const lines = [
    waBold("Nový trénink"),
    WA_RULE,
    waBold(opts.name),
    "",
  ];
  if (opts.branchName.trim()) {
    lines.push(`*Pobočka:* ${waSafe(opts.branchName)}`);
  }
  lines.push(`*Rozvrh:* ${waSafe(opts.scheduleLabel)}`);
  lines.push(WA_RULE);
  lines.push(opts.shareUrl);
  return lines.filter((line, i, arr) => !(line === "" && arr[i - 1] === "")).join("\n");
}

/**
 * Open WhatsApp with prefilled text and contact/group picker.
 * Must stay synchronous (user click) — use a real <a href> or this helper.
 */
export function whatsAppShareHref(message: string): string {
  return `https://wa.me/?text=${encodeURIComponent(message)}`;
}

export function openWhatsAppShare(message: string): void {
  const href = whatsAppShareHref(message);
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.target = "_blank";
  anchor.rel = "noopener noreferrer";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}
