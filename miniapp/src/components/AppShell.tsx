import { NavLink, Outlet } from "react-router-dom";

export function AppShell() {
  return (
    <div className="shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Planner Help</p>
          <h1>Личный планировщик в Telegram</h1>
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
      <nav className="bottom-nav">
        <NavLink to="/">Today</NavLink>
        <NavLink to="/week">Week</NavLink>
        <NavLink to="/inbox">Inbox</NavLink>
        <NavLink to="/more">More</NavLink>
      </nav>
    </div>
  );
}
