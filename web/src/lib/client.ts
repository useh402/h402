"use client";

import { API_URL, ApiError, RAILS, type Rail } from "./api";

const TOKEN_KEY = "humanapi.client.token";

export function getClientToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}
export function setClientToken(t: string | null) {
  try {
    if (t) localStorage.setItem(TOKEN_KEY, t);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {}
}

export async function capi<T = unknown>(path: string, init: { method?: string; body?: unknown; headers?: Record<string, string>; raw?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...(init.headers ?? {}) };
  const t = getClientToken();
  if (t) headers.Authorization = `Bearer ${t}`;
  const r = await fetch(`${API_URL}${path}`, { method: init.method ?? (init.body ? "POST" : "GET"), headers, body: init.body ? JSON.stringify(init.body) : undefined });
  const data = await r.json().catch(() => ({}));
  if (init.raw) return { status: r.status, data, headers: r.headers } as unknown as T;
  if (!r.ok) throw new ApiError(r.status, data.error ?? "error", data.message ?? r.statusText);
  return data as T;
}

export type Client = { id: string; rail: Rail; wallet: string; name: string; tasksPaid: number; blocked: boolean };

export async function clientSignIn(rail: Rail): Promise<Client> {
  const { connectWallet, signMessage } = await import("./wallet");
  const network = RAILS[rail].network;
  const wallet = await connectWallet(rail);
  const nonce = await capi<{ nonce: string; message: string; wallet: string }>("/v1/clients/nonce", { body: { wallet, network } });
  const signature = await signMessage(rail, wallet, nonce.message);
  const s = await capi<{ token: string; client: Client }>("/v1/clients/session", { body: { wallet: nonce.wallet, network, nonce: nonce.nonce, signature } });
  setClientToken(s.token);
  return s.client;
}

export async function clientDevSignIn(rail: Rail, wallet: string): Promise<Client> {
  const s = await capi<{ token: string; client: Client }>("/v1/clients/dev-session", { body: { wallet, network: RAILS[rail].network } });
  setClientToken(s.token);
  return s.client;
}

export type ClientTask = {
  taskId: string; type: string; title: string; location: string; state: string; difficulty: string; effortMinutes: number; templateId?: string | null; reference?: string | null;
  workers: { wanted: number; answered: number }; cost: { pricePerWorker: number; fee: number; total: number }; deadline: number; createdAt: number; completedAt: number | null;
  payment?: { network: string; transaction: string; explorer: string }; result?: Record<string, unknown>; agreement?: number; proof?: { value: Record<string, unknown> | string; note: string; submittedAt: number }; acceptBy?: number; awaitingOperator?: boolean;
  refund?: number; moderation?: { status: string; reason: string }; verification?: { method: string; outcome: string; checks: { name: string; passed: boolean; detail: string }[]; decidedAt: number; by: string };
  buyerToken?: string; payload?: Record<string, unknown>; acceptance?: string; receipt?: { payouts: unknown[]; refunds: unknown[]; ledger: { at: number; debit: string; credit: string; amount: number; memo: string }[]; timeline: { at: number; from: string | null; to: string; reason: string }[] };
};
