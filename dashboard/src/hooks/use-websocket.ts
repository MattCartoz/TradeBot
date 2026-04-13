"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { WS_URL } from "@/lib/utils";
import type { AgentEvent } from "@/lib/types";

export function useAgentFeed() {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(`${WS_URL}/ws/agent-feed`);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => {
      setConnected(false);
      // Reconnect after 3 seconds
      setTimeout(() => {
        wsRef.current = new WebSocket(`${WS_URL}/ws/agent-feed`);
      }, 3000);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as AgentEvent;
        setEvents((prev) => [...prev.slice(-199), data]);
      } catch {
        // ignore malformed messages
      }
    };

    return () => {
      ws.close();
    };
  }, []);

  return { events, connected };
}

export function useMarketData() {
  const [tickers, setTickers] = useState<Record<string, { last: number; volume: number }>>({});

  useEffect(() => {
    const ws = new WebSocket(`${WS_URL}/ws/market-data`);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "ticker") {
          setTickers((prev) => ({
            ...prev,
            [data.symbol]: { last: data.last, volume: data.volume },
          }));
        }
      } catch {
        // ignore
      }
    };

    return () => ws.close();
  }, []);

  return tickers;
}
