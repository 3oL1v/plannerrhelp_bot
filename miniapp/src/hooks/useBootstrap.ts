import { useEffect, useState } from "react";

import { setAuthToken } from "../api/client";
import { bootstrapTelegram } from "../api/planner";
import type { BootstrapResponse } from "../api/types";
import { getBootstrapPayload } from "../lib/telegram";

export function useBootstrap() {
  const [data, setData] = useState<BootstrapResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    getBootstrapPayload()
      .then((payload) => bootstrapTelegram(payload))
      .then((response) => {
        if (!active) return;
        setAuthToken(response.token);
        setData(response);
      })
      .catch((err: Error) => {
        if (!active) return;
        setError(err.message);
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  return { data, loading, error };
}
