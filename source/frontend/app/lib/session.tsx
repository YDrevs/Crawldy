"use client";

/**
 * Хто зараз у застосунку.
 *
 * Один запит `/v1/auth/me` на завантаження, далі стан живе в контексті.
 * Компоненти не питають бекенд «а хто я» самі: інакше кожен екран додає
 * власний спінер до однієї й тієї ж відповіді.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { getMe } from "./api";
import type { Me } from "./contracts";

interface SessionState {
  me: Me | null;
  /** Поки не знаємо — не показуємо ні застосунок, ні форму входу. */
  loading: boolean;
  refresh: () => Promise<void>;
  clear: () => void;
}

const Context = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setMe(await getMe());
    } catch {
      // 401 тут — не помилка, а відповідь: людина не увійшла.
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo<SessionState>(
    () => ({ me, loading, refresh, clear: () => setMe(null) }),
    [me, loading, refresh],
  );

  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useSession(): SessionState {
  const value = useContext(Context);
  if (value === null) {
    throw new Error("useSession викликано поза SessionProvider");
  }
  return value;
}
