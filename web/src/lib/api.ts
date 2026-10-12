"use client";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8400";
const TOKEN_KEY = "humanapi.worker.token";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

/** Fired on `window` whenever the worker session token is set or cleared, so other parts of the page can re-check who is signed in. */
export const SESSION_EVENT = "h402:session";

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {}
  try {
    window.dispatchEvent(new Event(SESSION_EVENT));
  } catch {}
}

export async function api<T = unknown>(path: string, init: { method?: string; body?: unknown; auth?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (init.auth !== false) {
    const t = getToken();
    if (t) headers.Authorization = `Bearer ${t}`;
  }
  const r = await fetch(`${API_URL}${path}`, { method: init.method ?? (init.body ? "POST" : "GET"), headers, body: init.body ? JSON.stringify(init.body) : undefined });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiError(r.status, data.error ?? "error", data.message ?? r.statusText);
  return data as T;
}

export const money = (atomic: number) => `$${(atomic / 1e6).toFixed(2)}`;

export const RAILS = {
  robinhood: { network: process.env.NEXT_PUBLIC_ROBINHOOD_NETWORK ?? "eip155:46630", label: "Robinhood Chain", asset: "USDG" },
  solana: { network: process.env.NEXT_PUBLIC_SOLANA_NETWORK ?? "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1", label: "Solana", asset: "USDC" },
} as const;
export type Rail = keyof typeof RAILS;

export type Worker = { id: string; rail: Rail; wallet: string; reputation: number; tier: string; languages: string[]; qualifiedTypes: string[]; termsAccepted: boolean; answered: number; agreed: number; paused?: boolean; pausedReason?: string | null };
export type Card = { taskId: string; type: string; category?: string | null; categoryLabel?: string | null; price: number; timeLeft: number; deadline: number; workers: number; preview: string; captureCode?: string | null; held: boolean; holdExpiresAt: number | null; payload?: Record<string, unknown> };
