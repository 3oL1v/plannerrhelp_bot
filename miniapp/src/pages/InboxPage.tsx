import { FormEvent, useCallback, useEffect, useState } from "react";

import { addInbox, convertInboxToEvent, convertInboxToTask, deleteInbox, getInbox } from "../api/planner";
import type { InboxItem } from "../api/types";
import { EmptyState, ErrorState, LoadingState } from "../components/States";
import { usePageRefresh } from "../hooks/usePageRefresh";

export function InboxPage() {
  const [items, setItems] = useState<InboxItem[]>([]);
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
              <button onClick={() => convertInboxToTask(item.id).then(() => load(false))}>В задачу</button>
              <button onClick={() => convertInboxToEvent(item.id).then(() => load(false))}>В событие</button>
              <button className="ghost" onClick={() => deleteInbox(item.id).then(() => load(false))}>
                Удалить
              </button>
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}
