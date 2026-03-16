import { FormEvent, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { completeTask, deleteTask, getTask, rescheduleTask } from "../api/planner";
import type { Task } from "../api/types";
import { ErrorState, LoadingState } from "../components/States";

export function TaskDetailsPage() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const [task, setTask] = useState<Task | null>(null);
  const [schedule, setSchedule] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!taskId) return;
    getTask(Number(taskId))
      .then((data) => {
        setTask(data);
        setSchedule(data.due_date && data.due_time ? `${data.due_date}T${data.due_time.slice(0, 5)}` : "");
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [taskId]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!taskId) return;
    const [dueDate, dueTime] = schedule ? schedule.split("T") : [null, null];
    const updated = await rescheduleTask(Number(taskId), dueDate, dueTime ? `${dueTime}:00` : null);
    setTask(updated);
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
      <section className="card">
        <form className="stack compact" onSubmit={submit}>
          <label>
            Новый срок
            <input type="datetime-local" value={schedule} onChange={(event) => setSchedule(event.target.value)} />
          </label>
          <button type="submit">Перенести</button>
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
