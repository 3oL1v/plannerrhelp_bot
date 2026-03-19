import { FormEvent, useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { completeTask, deleteTask, getTask, rescheduleTask } from "../api/planner";
import type { Task } from "../api/types";
import { ErrorState, LoadingState } from "../components/States";

export function TaskDetailsPage() {
  const { taskId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [task, setTask] = useState<Task | null>(null);
  const [dueDate, setDueDate] = useState("");
  const [dueTime, setDueTime] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const notice = typeof (location.state as { notice?: string } | null)?.notice === "string"
    ? (location.state as { notice?: string }).notice
    : null;

  useEffect(() => {
    if (!taskId) return;
    getTask(Number(taskId))
      .then((data) => {
        setTask(data);
        setDueDate(data.due_date ?? "");
        setDueTime(data.due_time ? data.due_time.slice(0, 5) : "");
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [taskId]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!taskId) return;
    const updated = await rescheduleTask(Number(taskId), dueDate || null, dueTime ? `${dueTime}:00` : null);
    setTask(updated);
    setDueDate(updated.due_date ?? "");
    setDueTime(updated.due_time ? updated.due_time.slice(0, 5) : "");
  }

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;
  if (!task) return null;

  return (
    <div className="stack">
      <section className="card accent">
        <p className="eyebrow">Task</p>
        <h2>{task.title}</h2>
        <p>Статус: {task.status}</p>
      </section>
      {notice ? <section className="card muted">{notice}</section> : null}
      <section className="card">
        <form className="stack compact" onSubmit={submit}>
          <label>
            Дата
            <input type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} />
          </label>
          <label>
            Время
            <input type="time" value={dueTime} onChange={(event) => setDueTime(event.target.value)} />
          </label>
          <div className="actions">
            <button type="submit">Перенести</button>
            <button type="button" className="ghost" onClick={() => setDueTime("")}>
              Без времени
            </button>
          </div>
        </form>
      </section>
      <section className="actions">
        <button onClick={() => completeTask(task.id).then((data) => setTask(data))}>Выполнить</button>
        <button className="ghost" onClick={() => deleteTask(task.id).then(() => navigate("/"))}>
          Удалить
        </button>
      </section>
    </div>
  );
}
