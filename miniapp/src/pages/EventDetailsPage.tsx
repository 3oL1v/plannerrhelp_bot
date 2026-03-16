import { FormEvent, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { deleteEvent, getEvent, rescheduleEvent } from "../api/planner";
import type { EventItem } from "../api/types";
import { ErrorState, LoadingState } from "../components/States";

export function EventDetailsPage() {
  const { eventId } = useParams();
  const navigate = useNavigate();
  const [eventItem, setEventItem] = useState<EventItem | null>(null);
  const [schedule, setSchedule] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!eventId) return;
    getEvent(Number(eventId))
      .then((data) => {
        setEventItem(data);
        setSchedule(`${data.event_date}T${data.start_time.slice(0, 5)}`);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [eventId]);

  async function submit(formEvent: FormEvent) {
    formEvent.preventDefault();
    if (!eventId) return;
    const [eventDate, startTime] = schedule.split("T");
    const updated = await rescheduleEvent(Number(eventId), eventDate, `${startTime}:00`);
    setEventItem(updated);
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
      <section className="card">
        <form className="stack compact" onSubmit={submit}>
          <label>
            Новый слот
            <input type="datetime-local" value={schedule} onChange={(event) => setSchedule(event.target.value)} />
          </label>
          <button type="submit">Перенести</button>
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
