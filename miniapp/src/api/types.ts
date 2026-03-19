export interface User {
  id: number;
  telegram_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
}

export interface UserSettings {
  timezone: string;
  morning_digest_enabled: boolean;
  morning_digest_time: string;
  notifications_enabled: boolean;
  default_reminder_minutes: number;
  week_starts_on: string;
  last_morning_digest_at: string | null;
}

export interface InboxItem {
  id: number;
  text: string;
  status: string;
  created_at: string;
  processed_at: string | null;
  deleted_at: string | null;
}

export interface Task {
  id: number;
  source_inbox_item_id: number | null;
  category_id: number | null;
  title: string;
  description: string | null;
  status: string;
  priority: string;
  due_date: string | null;
  due_time: string | null;
  completed_at: string | null;
}

export interface EventItem {
  id: number;
  source_inbox_item_id: number | null;
  category_id: number | null;
  title: string;
  description: string | null;
  event_date: string;
  start_time: string;
  end_time: string | null;
  duration_minutes: number | null;
  location: string | null;
  status: string;
}

export interface TodayDashboard {
  date: string;
  next_event: EventItem | null;
  events: EventItem[];
  tasks: Task[];
  completed_tasks: Task[];
  overdue_tasks: Task[];
  inbox_preview: InboxItem[];
}

export interface WeekDaySummary {
  date: string;
  tasks: Task[];
  events: EventItem[];
}

export interface WeekDashboard {
  week_start: string;
  week_end: string;
  days: WeekDaySummary[];
}

export interface BootstrapResponse {
  token: string;
  user: User;
  settings: UserSettings;
}
