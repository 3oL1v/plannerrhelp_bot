import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getTodayDashboard } from "../api/planner";
import type { TodayDashboard } from "../api/types";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function TodayPage() {
  const [data, setData] = useState<TodayDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getTodayDashboard()
      .then(setData)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;
  if (!data) return <EmptyState>Нет данных.</EmptyState>;

  return (
    <div className="stack">
      <section className="card accent">
        <p className="eyebrow">Сегодня</p>
        <h2>{data.date}</h2>
        <p>{data.next_event ? `Следующее событие: ${data.next_event.title}` : "Свободное окно без ближайших событий."}</p>
      </section>

      <section className="card">
        <div className="section-head">
          <h3>События</h3>
          <span>{data.events.length}</span>
        </div>
        {data.events.length === 0 ? (
          <EmptyState>На сегодня событий нет.</EmptyState>
        ) : (
          data.events.map((event) => (
            <Link key={event.id} to={`/events/${event.id}`} className="list-row">
              <strong>{event.title}</strong>
              <span>{event.start_time.slice(0, 5)}</span>
            </Link>
          ))
        )}
      </section>

      <section className="card">
        <div className="section-head">
          <h3>Задачи</h3>
          <span>{data.tasks.length}</span>
        </div>
        {data.tasks.length === 0 ? (
          <EmptyState>На сегодня задач нет.</EmptyState>
        ) : (
          data.tasks.map((task) => (
            <Link key={task.id} to={`/tasks/${task.id}`} className="list-row">
              <strong>{task.title}</strong>
              <span>{task.due_time ? task.due_time.slice(0, 5) : "без времени"}</span>
            </Link>
          ))
        )}
      </section>

      <section className="card">
        <div className="section-head">
          <h3>Просрочено</h3>
          <span>{data.overdue_tasks.length}</span>
        </div>
        {data.overdue_tasks.length === 0 ? (
          <EmptyState>Просроченных задач нет.</EmptyState>
        ) : (
          data.overdue_tasks.map((task) => (
            <Link key={task.id} to={`/tasks/${task.id}`} className="list-row danger-row">
              <strong>{task.title}</strong>
              <span>{task.due_date}</span>
            </Link>
          ))
        )}
      </section>
    </div>
  );
}
