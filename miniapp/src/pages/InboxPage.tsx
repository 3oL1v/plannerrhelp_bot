import { FormEvent, useEffect, useState } from "react";

import { addInbox, convertInboxToEvent, convertInboxToTask, deleteInbox, getInbox } from "../api/planner";
import type { InboxItem } from "../api/types";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function InboxPage() {
  const [items, setItems] = useState<InboxItem[]>([]);
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setItems(await getInbox());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!text.trim()) return;
    await addInbox(text.trim());
    setText("");
    await load();
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

      <section className="stack">
        {items.length === 0 ? <EmptyState>Входящие пусты.</EmptyState> : null}
        {items.map((item) => (
          <article key={item.id} className="card">
            <p>{item.text}</p>
            <div className="actions">
              <button onClick={() => convertInboxToTask(item.id).then(load)}>В задачу</button>
              <button onClick={() => convertInboxToEvent(item.id).then(load)}>В событие</button>
              <button className="ghost" onClick={() => deleteInbox(item.id).then(load)}>
                Удалить
              </button>
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}
