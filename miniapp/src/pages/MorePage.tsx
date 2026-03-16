import { Link } from "react-router-dom";

export function MorePage() {
  return (
    <div className="stack">
      <section className="card accent">
        <p className="eyebrow">More</p>
        <h2>Дополнительно</h2>
        <p>Здесь собраны быстрые переходы к настройкам и детальным карточкам.</p>
      </section>
      <Link className="card list-row" to="/settings">
        <strong>Настройки</strong>
        <span>Часовой пояс, сводка, напоминания</span>
      </Link>
      <div className="card">
        <p>Для задач и событий используй карточки деталей через Today и Week.</p>
      </div>
    </div>
  );
}
