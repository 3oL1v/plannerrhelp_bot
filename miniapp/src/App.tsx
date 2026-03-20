import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { ErrorState, LoadingState } from "./components/States";
import { useBootstrap } from "./hooks/useBootstrap";
import { EventDetailsPage } from "./pages/EventDetailsPage";
import { InboxPage } from "./pages/InboxPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TaskDetailsPage } from "./pages/TaskDetailsPage";
import { TodayPage } from "./pages/TodayPage";
import { WeekPage } from "./pages/WeekPage";

export default function App() {
  const { loading, error } = useBootstrap();

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;

  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<TodayPage />} />
        <Route path="/week" element={<WeekPage />} />
        <Route path="/inbox" element={<InboxPage />} />
        <Route path="/tasks/:taskId" element={<TaskDetailsPage />} />
        <Route path="/events/:eventId" element={<EventDetailsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
