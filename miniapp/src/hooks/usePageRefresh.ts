import { useEffect } from "react";

export function usePageRefresh(refresh: () => void | Promise<void>, delayMs = 5000) {
  useEffect(() => {
    let active = true;

    const runRefresh = () => {
      if (!active || document.visibilityState !== "visible") {
        return;
      }
      void refresh();
    };

    const intervalId = window.setInterval(runRefresh, delayMs);
    const handleVisibility = () => runRefresh();
    const handleFocus = () => runRefresh();

    document.addEventListener("visibilitychange", handleVisibility);
    window.addEventListener("focus", handleFocus);

    return () => {
      active = false;
      window.clearInterval(intervalId);
      document.removeEventListener("visibilitychange", handleVisibility);
      window.removeEventListener("focus", handleFocus);
    };
  }, [delayMs, refresh]);
}
