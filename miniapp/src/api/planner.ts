import { apiRequest } from "./client";
import type { BootstrapResponse, EventItem, InboxItem, Task, TodayDashboard, UserSettings, WeekDashboard } from "./types";

export function bootstrapTelegram(payload: Record<string, unknown>) {
  return apiRequest<BootstrapResponse>("/api/v1/auth/telegram/init", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getTodayDashboard() {
  return apiRequest<TodayDashboard>("/api/v1/dashboard/today");
}

export function getWeekDashboard() {
  return apiRequest<WeekDashboard>("/api/v1/dashboard/week");
}

export function getInbox() {
  return apiRequest<InboxItem[]>("/api/v1/inbox");
}

export function addInbox(text: string) {
  return apiRequest<InboxItem>("/api/v1/inbox", {
    method: "POST",
    body: JSON.stringify({ text })
  });
}

export function deleteInbox(id: number) {
  return apiRequest<void>(`/api/v1/inbox/${id}`, { method: "DELETE" });
}

export function convertInboxToTask(id: number) {
  return apiRequest<void>(`/api/v1/inbox/${id}/convert-to-task`, {
    method: "POST",
    body: JSON.stringify({})
  });
}

export function convertInboxToEvent(id: number) {
  return apiRequest<void>(`/api/v1/inbox/${id}/convert-to-event`, {
    method: "POST",
    body: JSON.stringify({})
  });
}

export function getTask(id: number) {
  return apiRequest<Task>(`/api/v1/tasks/${id}`);
}

export function getTasks() {
  return apiRequest<Task[]>("/api/v1/tasks");
}

export function completeTask(id: number) {
  return apiRequest<Task>(`/api/v1/tasks/${id}/complete`, { method: "POST" });
}

export function rescheduleTask(id: number, due_date: string | null, due_time: string | null) {
  return apiRequest<Task>(`/api/v1/tasks/${id}/reschedule`, {
    method: "POST",
    body: JSON.stringify({ due_date, due_time })
  });
}

export function deleteTask(id: number) {
  return apiRequest<void>(`/api/v1/tasks/${id}`, { method: "DELETE" });
}

export function getEvent(id: number) {
  return apiRequest<EventItem>(`/api/v1/events/${id}`);
}

export function rescheduleEvent(id: number, event_date: string, start_time: string) {
  return apiRequest<EventItem>(`/api/v1/events/${id}/reschedule`, {
    method: "POST",
    body: JSON.stringify({ event_date, start_time })
  });
}

export function deleteEvent(id: number) {
  return apiRequest<void>(`/api/v1/events/${id}`, { method: "DELETE" });
}

export function getSettings() {
  return apiRequest<UserSettings>("/api/v1/settings");
}

export function updateSettings(payload: Partial<UserSettings>) {
  return apiRequest<UserSettings>("/api/v1/settings", {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}
