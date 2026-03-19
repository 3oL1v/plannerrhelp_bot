import { FormEvent, useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { addInbox, convertInboxToEvent, convertInboxToTask, deleteInbox, getInbox } from "../api/planner";
import type { InboxItem } from "../api/types";
import { EmptyState, ErrorState, LoadingState } from "../components/States";
import { usePageRefresh } from "../hooks/usePageRefresh";

export function InboxPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<InboxItem[]>([]);
  const [text, setText] = useState("");
  const [eventDraftFor, setEventDraftFor] = useState<number | null>(null);
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

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!text.trim()) return;
    await addInbox(text.trim());
    setText("");
    await load(false);
  }

  async function onConvertToTask(item: InboxItem) {
    setActionError(null);
    setBusyId(item.id);
    try {
      const task = await convertInboxToTask(item.id, { title: item.text });
      navigate(`/tasks/${task.id}`, {
        state: {
          notice: "Задача создана из Inbox. Если нужно, добавь срок и время на карточке."
        }
      });
    } catch (err) {
      setActionError((err as Error).message);
    } finally {
      setBusyId(null);
    }
  }

  function openEventDraft(itemId: number) {
    setActionError(null);
    setEventDraftFor(itemId);
    setEventDate("");
    setEventTime("");
  }

  async function onConvertToEvent(item: InboxItem) {
    if (!eventDate || !eventTime) {
      setActionError("Для события сначала выбери дату и время.");
      return;
    }
    setActionError(null);
    setBusyId(item.id);
    try {
      const eventItem = await convertInboxToEvent(item.id, {
        title: item.text,
        event_date: eventDate,
        start_time: `${eventTime}:00`
      });
      setEventDraftFor(null);
      navigate(`/events/${eventItem.id}`, {
        state: {
          notice: "Событие создано из Inbox. При необходимости поправь слот на карточке."
        }
      });
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
            <div className="actions">
              <button type="button" disabled={busyId === item.id} onClick={() => void onConvertToTask(item)}>
                В задачу
              </button>
              <button type="button" disabled={busyId === item.id} onClick={() => openEventDraft(item.id)}>
                В событие
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
            {eventDraftFor === item.id ? (
              <form
                className="stack compact convert-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  void onConvertToEvent(item);
                }}
              >
                <p className="muted-text">Сначала задай дату и время, потом создавай событие.</p>
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
                    Создать событие
                  </button>
                  <button
                    type="button"
                    className="ghost"
                    onClick={() => {
                      setEventDraftFor(null);
                      setEventDate("");
                      setEventTime("");
                    }}
                  >
                    Отмена
                  </button>
                </div>
              </form>
            ) : null}
          </article>
        ))}
      </section>
    </div>
  );
}
