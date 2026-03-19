import { FormEvent, useCallback, useEffect, useState } from "react";

import { addInbox, convertInboxToEvent, convertInboxToTask, deleteInbox, getInbox } from "../api/planner";
import type { InboxItem } from "../api/types";
import { EmptyState, ErrorState, LoadingState } from "../components/States";
import { usePageRefresh } from "../hooks/usePageRefresh";

function localDateInputValue() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 10);
}

export function InboxPage() {
  const [items, setItems] = useState<InboxItem[]>([]);
  const [text, setText] = useState("");

  const [taskDraftFor, setTaskDraftFor] = useState<number | null>(null);
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDate, setTaskDate] = useState(localDateInputValue());
  const [taskTime, setTaskTime] = useState("");

  const [eventDraftFor, setEventDraftFor] = useState<number | null>(null);
  const [eventTitle, setEventTitle] = useState("");
  const [eventDate, setEventDate] = useState("");
  const [eventTime, setEventTime] = useState("");

  const [busyId, setBusyId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async (withLoading = false) => {
    if (withLoading) {
      setLoading(true);
    }
    try {
      setItems(await getInbox());
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

  function closeTaskDraft() {
    setTaskDraftFor(null);
    setTaskTitle("");
    setTaskDate(localDateInputValue());
    setTaskTime("");
  }

  function closeEventDraft() {
    setEventDraftFor(null);
    setEventTitle("");
    setEventDate("");
    setEventTime("");
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!text.trim()) return;
    await addInbox(text.trim());
    setText("");
    await load(false);
  }

  function openTaskDraft(item: InboxItem) {
    setActionError(null);
    closeEventDraft();
    setTaskDraftFor(item.id);
    setTaskTitle(item.text);
    setTaskDate(localDateInputValue());
    setTaskTime("");
  }

  async function onConvertToTask(item: InboxItem) {
    if (!taskTitle.trim() || !taskDate) {
      setActionError("Для задачи сначала укажи название и дату.");
      return;
    }
    setActionError(null);
    setBusyId(item.id);
    try {
      await convertInboxToTask(item.id, {
        title: taskTitle.trim(),
        due_date: taskDate,
        due_time: taskTime ? `${taskTime}:00` : null,
      });
      closeTaskDraft();
      await load(false);
    } catch (err) {
      setActionError((err as Error).message);
    } finally {
      setBusyId(null);
    }
  }

  function openEventDraft(item: InboxItem) {
    setActionError(null);
    closeTaskDraft();
    setEventDraftFor(item.id);
    setEventTitle(item.text);
    setEventDate("");
    setEventTime("");
  }

  async function onConvertToEvent(item: InboxItem) {
    if (!eventTitle.trim() || !eventDate || !eventTime) {
      setActionError("Для события сначала укажи название, дату и время.");
      return;
    }
    setActionError(null);
    setBusyId(item.id);
    try {
      await convertInboxToEvent(item.id, {
        title: eventTitle.trim(),
        event_date: eventDate,
        start_time: `${eventTime}:00`,
      });
      closeEventDraft();
      await load(false);
    } catch (err) {
      setActionError((err as Error).message);
    } finally {
      setBusyId(null);
    }
  }

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;

  return (
    <div className="stack">
      <section className="card accent">
        <p className="eyebrow">Inbox</p>
        <form className="stack compact" onSubmit={onSubmit}>
          <textarea value={text} onChange={(event) => setText(event.target.value)} placeholder="Быстрая мысль, задача или событие" />
          <button type="submit">Сохранить</button>
        </form>
      </section>

      {actionError ? <ErrorState message={actionError} /> : null}

      <section className="stack">
        {items.length === 0 ? <EmptyState>Входящие пусты.</EmptyState> : null}
        {items.map((item) => (
          <article key={item.id} className="card">
            <p>{item.text}</p>

            {taskDraftFor === item.id ? (
              <form
                className="stack compact convert-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  void onConvertToTask(item);
                }}
              >
                <label>
                  Название
                  <input type="text" value={taskTitle} onChange={(event) => setTaskTitle(event.target.value)} required />
                </label>
                <div className="field-grid">
                  <label>
                    Дата
                    <input type="date" value={taskDate} onChange={(event) => setTaskDate(event.target.value)} required />
                  </label>
                  <label>
                    Время
                    <input type="time" value={taskTime} onChange={(event) => setTaskTime(event.target.value)} />
                  </label>
                </div>
                <div className="actions">
                  <button type="submit" disabled={busyId === item.id}>
                    Добавить задачу
                  </button>
                  <button type="button" className="ghost" onClick={closeTaskDraft}>
                    Назад
                  </button>
                </div>
              </form>
            ) : null}

            {eventDraftFor === item.id ? (
              <form
                className="stack compact convert-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  void onConvertToEvent(item);
                }}
              >
                <label>
                  Название
                  <input type="text" value={eventTitle} onChange={(event) => setEventTitle(event.target.value)} required />
                </label>
                <div className="field-grid">
                  <label>
                    Дата
                    <input type="date" value={eventDate} onChange={(event) => setEventDate(event.target.value)} required />
                  </label>
                  <label>
                    Время
                    <input type="time" value={eventTime} onChange={(event) => setEventTime(event.target.value)} required />
                  </label>
                </div>
                <div className="actions">
                  <button type="submit" disabled={busyId === item.id}>
                    Добавить событие
                  </button>
                  <button type="button" className="ghost" onClick={closeEventDraft}>
                    Назад
                  </button>
                </div>
              </form>
            ) : null}

            {taskDraftFor !== item.id && eventDraftFor !== item.id ? (
              <div className="actions">
                <button type="button" disabled={busyId === item.id} onClick={() => openTaskDraft(item)}>
                  Добавить задачу
                </button>
                <button type="button" disabled={busyId === item.id} onClick={() => openEventDraft(item)}>
                  Добавить событие
                </button>
                <button
                  type="button"
                  className="ghost"
                  disabled={busyId === item.id}
                  onClick={() => deleteInbox(item.id).then(() => load(false))}
                >
                  Удалить
                </button>
              </div>
            ) : null}
          </article>
        ))}
      </section>
    </div>
  );
}
