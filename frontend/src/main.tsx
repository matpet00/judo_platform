import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes, useParams } from "react-router-dom";
import { TrainerProvider } from "./context/TrainerContext";
import { BootPage } from "./pages/BootPage";
import { TodayPage } from "./pages/TodayPage";
import { SessionSwipePage } from "./pages/SessionSwipePage";
import "./index.css";
import "./components/StudentSwipeDeck.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 10_000 },
  },
});

function SessionRoute() {
  const { id } = useParams();
  const sessionId = Number(id);
  if (!sessionId) return <div className="error-box app-shell">Neplatné ID session</div>;
  return <SessionSwipePage sessionId={sessionId} />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <TrainerProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<BootPage />} />
            <Route path="/today" element={<TodayPage />} />
            <Route path="/session/:id" element={<SessionRoute />} />
          </Routes>
        </BrowserRouter>
      </TrainerProvider>
    </QueryClientProvider>
  </StrictMode>,
);
