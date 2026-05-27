import { useOnlineStatus } from "../hooks/useOnlineStatus";

export function OfflineBanner() {
  const online = useOnlineStatus();
  if (online) return null;
  return <div className="offline-banner">Offline — uložení dočasně vypnuto</div>;
}
