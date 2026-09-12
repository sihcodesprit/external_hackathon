import { useEffect, useRef, useState } from "react";
import type { JobPoll } from "../types";

export function usePolling<T>(
  fn: () => Promise<T>,
  isDone: (value: T) => boolean,
  intervalMs = 700,
) {
  const [value, setValue] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const doneRef = useRef(isDone);
  const fnRef = useRef(fn);
  doneRef.current = isDone;
  fnRef.current = fn;

  useEffect(() => {
    let stopped = false;
    let timer: number | undefined;
    const poll = async () => {
      try {
        const result = await fnRef.current();
        if (stopped) return;
        setValue(result);
        setError(null);
        if (!doneRef.current(result)) {
          timer = window.setTimeout(poll, intervalMs);
        } else {
          setLoading(false);
        }
      } catch (e) {
        if (stopped) return;
        setError(e instanceof Error ? e.message : String(e));
        timer = window.setTimeout(poll, intervalMs);
      }
    };
    poll();
    return () => {
      stopped = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [intervalMs]);

  return { value, loading, error };
}

export function pollJobDone(poll: JobPoll): boolean {
  return poll.status === "done" || poll.status === "error";
}