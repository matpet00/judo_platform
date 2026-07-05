import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes, useParams } from "react-router-dom";
import { TrainerProvider, useTrainer } from "./context/TrainerContext";
import { ParentProvider, useParent } from "./context/ParentContext";
import { AttendanceBootPage, BootPage } from "./pages/BootPage";
import { BoardPage } from "./pages/BoardPage";
import { TodayPage } from "./pages/TodayPage";
import { SessionSwipePage } from "./pages/SessionSwipePage";
import { ParentHomePage } from "./pages/ParentHomePage";
import { ChatPage } from "./pages/ChatPage";
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

function TrainerChatRoute() {
  const { trainer, isAuthenticated } = useTrainer();
  if (!isAuthenticated || !trainer) return <Navigate to="/" replace />;
  return <ChatPage role="trainer" selfId={trainer.id} homePath="/" />;
}

function ParentChatRoute() {
  const { parent, isAuthenticated } = useParent();
  if (!isAuthenticated || !parent) return <Navigate to="/" replace />;
  return <ChatPage role="parent" selfId={parent.id} homePath="/parent" />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <TrainerProvider>
        <ParentProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<BootPage />} />
              <Route path="/attendance" element={<AttendanceBootPage />} />
              <Route path="/board" element={<BoardPage />} />
              <Route path="/today" element={<TodayPage />} />
              <Route path="/session/:id" element={<SessionRoute />} />
              <Route path="/chat" element={<TrainerChatRoute />} />
              <Route path="/parent" element={<ParentHomePage />} />
              <Route path="/parent/chat" element={<ParentChatRoute />} />
            </Routes>
          </BrowserRouter>
        </ParentProvider>
      </TrainerProvider>
    </QueryClientProvider>
  </StrictMode>,
);
