import { FormEvent, useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { deleteEvent, getEvent, updateEvent } from "../api/planner";
import type { EventItem } from "../api/types";
import { ErrorState, LoadingState } from "../components/States";

export function EventDetailsPage() {
  const { eventId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [eventItem, setEventItem] = useState<EventItem | null>(null);
  const [title, setTitle] = useState("");
  const [eventDate, setEventDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const notice = typeof (location.state as { notice?: string } | null)?.notice === "string"
    ? (location.state as { notice?: string }).notice
    : null;

  useEffect(() => {
    if (!eventId) return;
    getEvent(Number(eventId))
      .then((data) => {
        setEventItem(data);
        setTitle(data.title);
        setEventDate(data.event_date);
        setStartTime(data.start_time.slice(0, 5));
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [eventId]);

  async function submit(formEvent: FormEvent) {
    formEvent.preventDefault();
    if (!eventId || !eventItem) return;
    setSaving(true);
    try {
      const updated = await updateEvent(Number(eventId), {
        title: title.trim() || eventItem.title,
        event_date: eventDate,
        start_time: `${startTime}:00`,
      });
      setEventItem(updated);
      setTitle(updated.title);
      setEventDate(updated.event_date);
      setStartTime(updated.start_time.slice(0, 5));
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;
  if (!eventItem) return null;

  return (
    <div className="stack">
      <section className="card accent">
        <p className="eyebrow">Event</p>
        <h2>{eventItem.title}</h2>
        <p>Дата: {eventItem.event_date}</p>
      </section>
      {notice ? <section className="card muted">{notice}</section> : null}
      <section className="card">
        <form className="stack compact" onSubmit={submit}>
          <label>
            Название
            <input type="text" value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>
          <label>
            Дата
            <input type="date" value={eventDate} onChange={(event) => setEventDate(event.target.value)} />
          </label>
          <label>
            Время
            <input type="time" value={startTime} onChange={(event) => setStartTime(event.target.value)} />
          </label>
          <div className="actions">
            <button type="submit" disabled={saving}>Применить</button>
            <button type="button" className="ghost" onClick={() => navigate(-1)}>Назад</button>
          </div>
        </form>
      </section>
      <section className="actions">
        <button className="ghost" onClick={() => deleteEvent(eventItem.id).then(() => navigate("/week"))}>
          Удалить
        </button>
      </section>
    </div>
  );
}
