"use client";

import { api, RAILS, setToken, type Rail, type Worker } from "./api";

const ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
function base58(bytes: Uint8Array): string {
  const digits = [0];
  for (const b of bytes) {
    let carry = b;
    for (let i = 0; i < digits.length; i++) {
      carry += digits[i] << 8;
      digits[i] = carry % 58;
      carry = (carry / 58) | 0;
    }
    while (carry > 0) {
      digits.push(carry % 58);
      carry = (carry / 58) | 0;
    }
  }
  let out = "";
  for (const b of bytes) {
    if (b !== 0) break;
    out += "1";
  }
  for (let i = digits.length - 1; i >= 0; i--) out += ALPHABET[digits[i]];
  return out;
}

type Eip1193 = { request: (args: { method: string; params?: unknown[] }) => Promise<unknown> };
type SolanaProvider = { connect: () => Promise<{ publicKey: { toString(): string } }>; signMessage: (m: Uint8Array, enc: "utf8") => Promise<{ signature: Uint8Array }>; publicKey?: { toString(): string } };

declare global {
  interface Window {
    ethereum?: Eip1193;
    solana?: SolanaProvider;
  }
}

export function hasWallet(rail: Rail): boolean {
  if (typeof window === "undefined") return false;
  return rail === "robinhood" ? !!window.ethereum : !!window.solana;
}

export async function connectWallet(rail: Rail): Promise<string> {
  if (rail === "robinhood") {
    if (!window.ethereum) throw new Error("No EVM wallet found. Install MetaMask or Rabby.");
    const accounts = (await window.ethereum.request({ method: "eth_requestAccounts" })) as string[];
    if (!accounts?.[0]) throw new Error("No account selected.");
    return accounts[0];
  }
  if (!window.solana) throw new Error("No Solana wallet found. Install Phantom or Solflare.");
  const res = await window.solana.connect();
  return res.publicKey.toString();
}

export async function signMessage(rail: Rail, wallet: string, message: string): Promise<string> {
  if (rail === "robinhood") {
    return (await window.ethereum!.request({ method: "personal_sign", params: [message, wallet] })) as string;
  }
  const { signature } = await window.solana!.signMessage(new TextEncoder().encode(message), "utf8");
  return base58(signature);
}

export async function signIn(rail: Rail): Promise<Worker> {
  const network = RAILS[rail].network;
  const wallet = await connectWallet(rail);
  const nonce = await api<{ nonce: string; message: string; wallet: string }>("/v1/workers/nonce", { body: { wallet, network }, auth: false });
  const signature = await signMessage(rail, wallet, nonce.message);
  const session = await api<{ token: string; worker: Worker }>("/v1/workers/session", { body: { wallet: nonce.wallet, network, nonce: nonce.nonce, signature }, auth: false });
  setToken(session.token);
  return session.worker;
}

/** Local development only: the API refuses this outside HA_ENV=local with HA_DEV_LOGIN=true. */
export async function devSignIn(rail: Rail, wallet: string): Promise<Worker> {
  const session = await api<{ token: string; worker: Worker }>("/v1/workers/dev-session", { body: { wallet, network: RAILS[rail].network }, auth: false });
  setToken(session.token);
  return session.worker;
}

export function signOut() {
  setToken(null);
}

export const short = (w: string) => (w.length > 12 ? `${w.slice(0, 6)}…${w.slice(-4)}` : w);
