"use client";
import { useEffect, useRef, useState } from "react";
import type { StreamPayload } from "@/app/lib/types";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export function useSSE() {
  const [data, setData] = useState<StreamPayload | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource(`${BACKEND_URL}/stream`);
    esRef.current = es;

    es.onopen = () => {
      setConnected(true);
      setError(null);
    };

    es.onmessage = (event) => {
      try {
        const payload: StreamPayload = JSON.parse(event.data);
        if (payload.error) {
          setError(payload.error as unknown as string);
        } else {
          setData(payload);
        }
      } catch {
        setError("Failed to parse stream data");
      }
    };

    es.onerror = () => {
      setConnected(false);
      setError("Connection lost — retrying...");
    };

    return () => {
      es.close();
      setConnected(false);
    };
  }, []);

  return { data, connected, error };
}
