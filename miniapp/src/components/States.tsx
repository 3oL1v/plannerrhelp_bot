import type { PropsWithChildren } from "react";

export function LoadingState() {
  return <div className="card muted">Загрузка...</div>;
}

export function ErrorState({ message }: { message: string }) {
  return <div className="card danger">{message}</div>;
}

export function EmptyState({ children }: PropsWithChildren) {
  return <div className="card muted">{children}</div>;
}
