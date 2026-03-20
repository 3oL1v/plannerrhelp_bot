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

export function clearTodayCompletedList() {
  return apiRequest<void>("/api/v1/dashboard/today/completed/clear", {
    method: "POST"
  });
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

export function convertInboxToTask(id: number, payload: { title?: string; due_date?: string | null; due_time?: string | null } = {}) {
  return apiRequest<Task>(`/api/v1/inbox/${id}/convert-to-task`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function convertInboxToEvent(
  id: number,
  payload: { title?: string; event_date: string; start_time: string; duration_minutes?: number | null },
) {
  return apiRequest<EventItem>(`/api/v1/inbox/${id}/convert-to-event`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getTask(id: number) {
  return apiRequest<Task>(`/api/v1/tasks/${id}`);
}

export function createTask(payload: { title: string; due_date?: string | null; due_time?: string | null }) {
  return apiRequest<Task>("/api/v1/tasks", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateTask(id: number, payload: { title?: string; due_date?: string | null; due_time?: string | null; status?: string | null }) {
  return apiRequest<Task>(`/api/v1/tasks/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function completeTask(id: number) {
  return apiRequest<Task>(`/api/v1/tasks/${id}/complete`, { method: "POST" });
}

export function deleteTask(id: number) {
  return apiRequest<void>(`/api/v1/tasks/${id}`, { method: "DELETE" });
}

export function getEvent(id: number) {
  return apiRequest<EventItem>(`/api/v1/events/${id}`);
}

export function createEvent(payload: { title: string; event_date: string; start_time: string }) {
  return apiRequest<EventItem>("/api/v1/events", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateEvent(id: number, payload: { title?: string; event_date?: string; start_time?: string }) {
  return apiRequest<EventItem>(`/api/v1/events/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
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
