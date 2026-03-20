import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { clearTodayCompletedList, createEvent, createTask, getTodayDashboard } from "../api/planner";
import type { TodayDashboard } from "../api/types";
import { EmptyState, ErrorState, LoadingState } from "../components/States";
import { usePageRefresh } from "../hooks/usePageRefresh";

function localDateInputValue() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 10);
}

export function TodayPage() {
  const [data, setData] = useState<TodayDashboard | null>(null);
  const [taskTab, setTaskTab] = useState<"active" | "completed">("active");
  const [draftType, setDraftType] = useState<"task" | "event">("task");
  const [draftTitle, setDraftTitle] = useState("");
  const [draftDate, setDraftDate] = useState(localDateInputValue());
  const [draftTime, setDraftTime] = useState("");
  const [submittingDraft, setSubmittingDraft] = useState(false);
  const [clearingCompleted, setClearingCompleted] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (withLoading = false) => {
    if (withLoading) {
      setLoading(true);
    }
    try {
      const dashboard = await getTodayDashboard();
      setData(dashboard);
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

  function resetDraft() {
    setDraftTitle("");
    setDraftDate(localDateInputValue());
    setDraftTime("");
    setDraftType("task");
  }

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    const title = draftTitle.trim();
    if (!title) {
      setError("Добавь название.");
      return;
    }
    if (draftType === "event" && (!draftDate || !draftTime)) {
      setError("Для события нужны дата и время.");
      return;
    }

    setSubmittingDraft(true);
    try {
      if (draftType === "task") {
        await createTask({
          title,
          due_date: draftDate || null,
          due_time: draftTime ? `${draftTime}:00` : null,
        });
      } else {
        await createEvent({
          title,
          event_date: draftDate,
          start_time: `${draftTime}:00`,
        });
      }
      resetDraft();
      await load(false);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmittingDraft(false);
    }
  }

  async function onClearCompleted() {
    setClearingCompleted(true);
    try {
      await clearTodayCompletedList();
      await load(false);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setClearingCompleted(false);
    }
  }

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;
  if (!data) return <EmptyState>Нет данных.</EmptyState>;

  const completedCount = data.completed_tasks.length;

  return (
    <div className="stack">
      <section className="card accent">
        <p className="eyebrow">Сегодня</p>
        <h2>{data.date}</h2>
        <p>{data.next_event ? `Следующее событие: ${data.next_event.title}` : "Свободное окно без ближайших событий."}</p>
      </section>

      <section className="card">
        <div className="section-head">
          <h3>Быстро добавить</h3>
          <span>{draftType === "task" ? "Задача" : "Событие"}</span>
        </div>
        <div className="segment">
          <button type="button" className={draftType === "task" ? "active" : ""} onClick={() => setDraftType("task")}>
            Задача
          </button>
          <button type="button" className={draftType === "event" ? "active" : ""} onClick={() => setDraftType("event")}>
            Событие
          </button>
        </div>
        <form className="stack compact" onSubmit={onCreate}>
          <label>
            Название
            <input type="text" value={draftTitle} onChange={(event) => setDraftTitle(event.target.value)} placeholder="Что нужно сделать?" />
          </label>
          <div className="field-grid">
            <label>
              Дата
              <input type="date" value={draftDate} onChange={(event) => setDraftDate(event.target.value)} />
            </label>
            <label>
              Время
              <input type="time" value={draftTime} onChange={(event) => setDraftTime(event.target.value)} required={draftType === "event"} />
            </label>
          </div>
          {draftType === "task" ? <p className="muted-text">Время для задачи можно оставить пустым.</p> : null}
          <div className="actions">
            <button type="submit" disabled={submittingDraft}>
              {draftType === "task" ? "Добавить задачу" : "Добавить событие"}
            </button>
            <button type="button" className="ghost" disabled={submittingDraft} onClick={resetDraft}>
              Сбросить
            </button>
          </div>
        </form>
      </section>

      <section className="card">
        <div className="section-head">
          <h3>События</h3>
          <span>{data.events.length}</span>
        </div>
        {data.events.length === 0 ? (
          <EmptyState>На сегодня событий нет.</EmptyState>
        ) : (
          data.events.map((eventItem) => (
            <Link key={eventItem.id} to={`/events/${eventItem.id}`} className="list-row">
              <strong>{eventItem.title}</strong>
              <span className="list-meta">{eventItem.start_time.slice(0, 5)}</span>
            </Link>
          ))
        )}
      </section>

      <section className="card">
        <div className="section-head">
          <h3>Задачи</h3>
          <span>{taskTab === "active" ? data.tasks.length : completedCount}</span>
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
        ) : completedCount === 0 ? (
          <EmptyState>Выполненных задач пока нет.</EmptyState>
        ) : (
          <div className="stack compact">
            {data.completed_tasks.map((task) => (
              <div key={`completed-${task.id}`} className="list-row completed-row readonly-row">
                <strong>✅ {task.title}</strong>
              </div>
            ))}
            <div className="actions compact-actions completed-footer">
              <button type="button" className="ghost" disabled={clearingCompleted} onClick={() => void onClearCompleted()}>
                Очистить список выполненных
              </button>
            </div>
          </div>
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
