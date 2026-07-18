import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes, useParams } from "react-router-dom";
import { TrainerProvider, useTrainer } from "./context/TrainerContext";
import { ParentProvider, useParent } from "./context/ParentContext";
import { AdminProvider } from "./context/AdminContext";
import { AttendanceBootPage, BootPage } from "./pages/BootPage";
import { AdminPage } from "./pages/AdminPage";
import { BoardPage } from "./pages/BoardPage";
import { TodayPage } from "./pages/TodayPage";
import { SessionSwipePage } from "./pages/SessionSwipePage";
import { ParentHomePage } from "./pages/ParentHomePage";
import { ParentAttendancePage } from "./pages/ParentAttendancePage";
import { RegisterPage } from "./pages/RegisterPage";
import { PrivacyPolicyPage } from "./pages/PrivacyPolicyPage";
import { ParentBoardPage } from "./pages/ParentBoardPage";
import { ChatPage } from "./pages/ChatPage";
import { EventsPage } from "./pages/EventsPage";
import { TrainerStudentsPage } from "./pages/TrainerStudentsPage";
import { TrainerPayAttendancePage } from "./pages/TrainerPayAttendancePage";
import { TrainerPinSecurityGate } from "./components/TrainerPinSecurityGate";
import { NotificationBell } from "./components/NotificationBell";
import { AppFooter } from "./components/AppFooter";
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
  return (
    <TrainerPinSecurityGate>
      <TrainerChatPage />
    </TrainerPinSecurityGate>
  );
}

function TrainerChatPage() {
  const { trainer } = useTrainer();
  if (!trainer) return null;
  return <ChatPage role="trainer" selfId={trainer.id} homePath="/" />;
}

function ParentChatRoute() {
  const { parent, isAuthenticated } = useParent();
  if (!isAuthenticated || !parent) return <Navigate to="/" replace />;
  return <ChatPage role="parent" selfId={parent.id} homePath="/parent" />;
}

function TrainerEventsRoute() {
  return (
    <TrainerPinSecurityGate>
      <TrainerEventsPage />
    </TrainerPinSecurityGate>
  );
}

function TrainerEventsPage() {
  const { trainer } = useTrainer();
  if (!trainer) return null;
  return <EventsPage role="trainer" selfId={trainer.id} homePath="/" />;
}

function TrainerStudentsRoute() {
  return (
    <TrainerPinSecurityGate>
      <TrainerStudentsPage />
    </TrainerPinSecurityGate>
  );
}

function ParentEventsRoute() {
  const { parent, isAuthenticated } = useParent();
  if (!isAuthenticated || !parent) return <Navigate to="/" replace />;
  return <EventsPage role="parent" selfId={parent.id} homePath="/parent" />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <TrainerProvider>
        <ParentProvider>
          <AdminProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<BootPage />} />
              <Route path="/admin" element={<AdminPage />} />
              <Route path="/board" element={<TrainerPinSecurityGate><BoardPage /></TrainerPinSecurityGate>} />
              <Route path="/today" element={<TrainerPinSecurityGate><TodayPage /></TrainerPinSecurityGate>} />
              <Route path="/session/:id" element={<TrainerPinSecurityGate><SessionRoute /></TrainerPinSecurityGate>} />
              <Route path="/attendance" element={<AttendanceBootPage />} />
              <Route path="/chat" element={<TrainerChatRoute />} />
              <Route path="/events" element={<TrainerEventsRoute />} />
              <Route path="/students" element={<TrainerStudentsRoute />} />
              <Route
                path="/trainer/pay-attendance"
                element={
                  <TrainerPinSecurityGate>
                    <TrainerPayAttendancePage />
                  </TrainerPinSecurityGate>
                }
              />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/privacy" element={<PrivacyPolicyPage />} />
              <Route path="/parent" element={<ParentHomePage />} />
              <Route path="/parent/attendance" element={<ParentAttendancePage />} />
              <Route path="/parent/board" element={<ParentBoardPage />} />
              <Route path="/parent/chat" element={<ParentChatRoute />} />
              <Route path="/parent/events" element={<ParentEventsRoute />} />
            </Routes>
            <NotificationBell />
            <AppFooter />
          </BrowserRouter>
          </AdminProvider>
        </ParentProvider>
      </TrainerProvider>
    </QueryClientProvider>
  </StrictMode>,
);
