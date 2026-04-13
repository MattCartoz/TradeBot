"use client";

import { useEffect, useRef, useState } from "react";
import { WS_URL } from "@/lib/utils";
import type { AgentEvent } from "@/lib/types";

function createSocket(
  url: string,
  onOpen: () => void,
  onClose: () => void,
  onMessage: (data: AgentEvent) => void,
): WebSocket {
  const ws = new WebSocket(url);
  ws.onopen = onOpen;
  ws.onmessage = (event) => {
    try {
      onMessage(JSON.parse(event.data) as AgentEvent);
    } catch {
      /* ignore malformed */
    }
  };
  ws.onclose = onClose;
  ws.onerror = () => ws.close();
  return ws;
}

export function useAgentFeed() {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const connect = () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);

      const ws = createSocket(
        `${WS_URL}/ws/agent-feed`,
        () => setConnected(true),
        () => {
          setConnected(false);
          reconnectTimer.current = setTimeout(connect, 3000);
        },
        (data) => setEvents((prev) => [...prev.slice(-199), data]),
      );
      wsRef.current = ws;
    };

    connect();

    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, []);

  return { events, connected };
}

export function useMarketData() {
  const [tickers, setTickers] = useState<Record<string, { last: number; volume: number }>>({});
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const connect = () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);

      const ws = createSocket(
        `${WS_URL}/ws/market-data`,
        () => {},
        () => {
          reconnectTimer.current = setTimeout(connect, 5000);
        },
        (data: Record<string, unknown>) => {
          if (data.type === "ticker") {
            const d = data as { symbol: string; last: number; volume: number };
            setTickers((prev) => ({
              ...prev,
              [d.symbol]: { last: d.last, volume: d.volume },
            }));
          }
        },
      );
      wsRef.current = ws;
    };

    connect();

    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, []);

  return tickers;
}
