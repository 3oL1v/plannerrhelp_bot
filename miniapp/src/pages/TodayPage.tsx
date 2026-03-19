import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getTasks, getTodayDashboard } from "../api/planner";
import type { Task, TodayDashboard } from "../api/types";
import { EmptyState, ErrorState, LoadingState } from "../components/States";
import { usePageRefresh } from "../hooks/usePageRefresh";

export function TodayPage() {
  const [data, setData] = useState<TodayDashboard | null>(null);
  const [completedTasks, setCompletedTasks] = useState<Task[]>([]);
  const [taskTab, setTaskTab] = useState<"active" | "completed">("active");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (withLoading = false) => {
    if (withLoading) {
      setLoading(true);
    }
    try {
      const [dashboard, tasks] = await Promise.all([getTodayDashboard(), getTasks()]);
      setData(dashboard);
      setCompletedTasks(
        tasks
          .filter((task) => task.status === "completed")
          .sort((left, right) => (right.completed_at ?? "").localeCompare(left.completed_at ?? "")),
      );
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

  usePageRefresh(() => load(false), 5000);

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
              <span className="list-meta">{event.start_time.slice(0, 5)}</span>
            </Link>
          ))
        )}
      </section>

      <section className="card">
        <div className="section-head">
          <h3>Задачи</h3>
          <span>{taskTab === "active" ? data.tasks.length : completedTasks.length}</span>
        </div>
        <div className="segment">
          <button type="button" className={taskTab === "active" ? "active" : ""} onClick={() => setTaskTab("active")}>
            На сегодня
          </button>
          <button type="button" className={taskTab === "completed" ? "active" : ""} onClick={() => setTaskTab("completed")}>
            Выполненные
          </button>
        </div>
        {taskTab === "active" ? (
          data.tasks.length === 0 ? (
            <EmptyState>На сегодня задач нет.</EmptyState>
          ) : (
            data.tasks.map((task) => (
              <Link key={`task-${task.id}`} to={`/tasks/${task.id}`} className="list-row">
                <strong>{task.title}</strong>
                <span className="list-meta">{task.due_time ? task.due_time.slice(0, 5) : "\u00A0"}</span>
              </Link>
            ))
          )
        ) : completedTasks.length === 0 ? (
          <EmptyState>Выполненных задач пока нет.</EmptyState>
        ) : (
          completedTasks.map((task) => (
            <Link key={`completed-${task.id}`} to={`/tasks/${task.id}`} className="list-row">
              <strong>{task.title}</strong>
              <span className="list-meta">{task.completed_at ? task.completed_at.slice(0, 10) : "\u00A0"}</span>
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
              <span className="list-meta">{task.due_date}</span>
            </Link>
          ))
        )}
      </section>
    </div>
  );
}
