import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getWeekDashboard } from "../api/planner";
import type { WeekDashboard } from "../api/types";
import { ErrorState, LoadingState } from "../components/States";
import { usePageRefresh } from "../hooks/usePageRefresh";

export function WeekPage() {
  const [data, setData] = useState<WeekDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (withLoading = false) => {
    if (withLoading) {
      setLoading(true);
    }
    try {
      setData(await getWeekDashboard());
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      if (withLoading) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void load(true);
  }, [load]);

  usePageRefresh(() => load(false), 7000);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;
  if (!data) return null;

  return (
    <div className="stack">
      <section className="card accent">
        <p className="eyebrow">Неделя</p>
        <h2>
          {data.week_start} - {data.week_end}
        </h2>
      </section>
      {data.days.map((day) => (
        <section key={day.date} className="card">
          <div className="section-head">
            <h3>{day.date}</h3>
            <span>{day.tasks.length + day.events.length} элементов</span>
          </div>
          {day.events.map((event) => (
            <Link key={`e-${event.id}`} to={`/events/${event.id}`} className="list-row">
              <strong>{event.title}</strong>
              <span className="list-meta">{event.start_time.slice(0, 5)}</span>
            </Link>
          ))}
          {day.tasks.map((task) => (
            <Link key={`t-${task.id}`} to={`/tasks/${task.id}`} className="list-row">
              <strong>{task.title}</strong>
              <span className="list-meta">{task.due_time ? task.due_time.slice(0, 5) : "\u00A0"}</span>
            </Link>
          ))}
        </section>
      ))}
    </div>
  );
}
