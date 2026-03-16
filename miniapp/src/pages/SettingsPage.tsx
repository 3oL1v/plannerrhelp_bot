import { FormEvent, useEffect, useState } from "react";

import { getSettings, updateSettings } from "../api/planner";
import type { UserSettings } from "../api/types";
import { ErrorState, LoadingState } from "../components/States";

export function SettingsPage() {
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSettings()
      .then(setSettings)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!settings) return;
    const updated = await updateSettings(settings);
    setSettings(updated);
  }

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;
  if (!settings) return null;

  return (
    <form className="stack" onSubmit={onSubmit}>
      <section className="card accent">
        <p className="eyebrow">Settings</p>
        <h2>Настройки</h2>
      </section>
      <section className="card stack compact">
        <label>
          Часовой пояс
          <input value={settings.timezone} onChange={(event) => setSettings({ ...settings, timezone: event.target.value })} />
        </label>
        <label className="toggle">
          <span>Утренняя сводка</span>
          <input
            type="checkbox"
            checked={settings.morning_digest_enabled}
            onChange={(event) => setSettings({ ...settings, morning_digest_enabled: event.target.checked })}
          />
        </label>
        <label className="toggle">
          <span>Напоминания</span>
          <input
            type="checkbox"
            checked={settings.notifications_enabled}
            onChange={(event) => setSettings({ ...settings, notifications_enabled: event.target.checked })}
          />
        </label>
        <label>
          Время сводки
          <input
            type="time"
            value={settings.morning_digest_time.slice(0, 5)}
            onChange={(event) => setSettings({ ...settings, morning_digest_time: `${event.target.value}:00` })}
          />
        </label>
        <label>
          Напоминание по умолчанию, мин
          <input
            type="number"
            value={settings.default_reminder_minutes}
            onChange={(event) => setSettings({ ...settings, default_reminder_minutes: Number(event.target.value) })}
          />
        </label>
        <button type="submit">Сохранить</button>
      </section>
    </form>
  );
}
