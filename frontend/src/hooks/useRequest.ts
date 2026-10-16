import { useCallback, useEffect, useRef, useState } from "react";
export function useRequest<T>() {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const reset = useCallback(() => {
    generation.current++;
    controller.current?.abort();
    setData(null);
    setError(null);
    setLoading(false);
  }, []);
  useEffect(
    () => () => {
      generation.current++;
      controller.current?.abort();
    },
    [],
  );
  const run = useCallback(
    async (operation: (signal: AbortSignal) => Promise<T>) => {
      controller.current?.abort();
      const current = ++generation.current;
      const active = new AbortController();
      controller.current = active;
      setLoading(true);
      setData(null);
      setError(null);
      try {
        const result = await operation(active.signal);
        if (current !== generation.current) return;
        setData(result);
        return result;
      } catch (err) {
        if (current === generation.current && !active.signal.aborted)
          setError(
            err instanceof Error
              ? err.message
              : "Something went wrong. Please try again.",
          );
      } finally {
        if (current === generation.current) setLoading(false);
      }
    },
    [],
  );
  return { data, error, loading, run, reset };
}
