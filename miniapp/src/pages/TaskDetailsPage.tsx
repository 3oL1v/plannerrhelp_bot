import { FormEvent, useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { completeTask, deleteTask, getTask, updateTask } from "../api/planner";
import type { Task } from "../api/types";
import { ErrorState, LoadingState } from "../components/States";

export function TaskDetailsPage() {
  const { taskId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [task, setTask] = useState<Task | null>(null);
  const [title, setTitle] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [dueTime, setDueTime] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const notice = typeof (location.state as { notice?: string } | null)?.notice === "string"
    ? (location.state as { notice?: string }).notice
    : null;

  useEffect(() => {
    if (!taskId) return;
    getTask(Number(taskId))
      .then((data) => {
        setTask(data);
        setTitle(data.title);
        setDueDate(data.due_date ?? "");
        setDueTime(data.due_time ? data.due_time.slice(0, 5) : "");
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [taskId]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!taskId || !task) return;
    setSaving(true);
    try {
      const updated = await updateTask(Number(taskId), {
        title: title.trim() || task.title,
        due_date: dueDate || null,
        due_time: dueTime ? `${dueTime}:00` : null,
      });
      setTask(updated);
      setTitle(updated.title);
      setDueDate(updated.due_date ?? "");
      setDueTime(updated.due_time ? updated.due_time.slice(0, 5) : "");
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;
  if (!task) return null;

  const readOnly = task.status === "completed";

  return (
    <div className="stack">
      <section className="card accent">
        <p className="eyebrow">Task</p>
        <h2>{task.title}</h2>
        <p>Статус: {task.status}</p>
      </section>
      {notice ? <section className="card muted">{notice}</section> : null}
      {readOnly ? <section className="card muted">Выполненная задача доступна только для просмотра.</section> : null}
      <section className="card">
        <form className="stack compact" onSubmit={submit}>
          <label>
            Название
            <input type="text" value={title} onChange={(event) => setTitle(event.target.value)} disabled={readOnly} />
          </label>
          <label>
            Дата
            <input type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} disabled={readOnly} />
          </label>
          <label>
            Время
            <input type="time" value={dueTime} onChange={(event) => setDueTime(event.target.value)} disabled={readOnly} />
          </label>
          <div className="actions">
            <button type="submit" disabled={readOnly || saving}>Применить</button>
            <button type="button" className="ghost" disabled={readOnly || saving} onClick={() => setDueTime("")}>Без времени</button>
            <button type="button" className="ghost" onClick={() => navigate(-1)}>Назад</button>
          </div>
        </form>
      </section>
      {!readOnly ? (
        <section className="actions">
          <button onClick={() => completeTask(task.id).then((data) => setTask(data))}>Выполнить</button>
          <button className="ghost" onClick={() => deleteTask(task.id).then(() => navigate("/"))}>
            Удалить
          </button>
        </section>
      ) : null}
    </div>
  );
}
