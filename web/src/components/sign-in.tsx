"use client";

import { useEffect, useRef, useState } from "react";
import { usePrivy, useWallets } from "@privy-io/react-auth";
import { PRIVY_ON } from "./providers";
import { api, RAILS, setToken, type Rail, type Worker } from "@/lib/api";
import { capi, setClientToken, type Client } from "@/lib/client";
import { devSignIn, hasWallet, signIn } from "@/lib/wallet";
import { clientDevSignIn, clientSignIn } from "@/lib/client";

const DEV = process.env.NEXT_PUBLIC_DEV_LOGIN === "1";
type Role = "worker" | "client";
type Done = (who: Worker | Client) => void;

/** One sign-in for the whole site. With Privy: MetaMask or Phantom. Without it: a browser wallet. */
export function SignIn({ role, onDone, label = "Connect wallet" }: { role: Role; onDone: Done; label?: string }) {
  return PRIVY_ON ? <PrivySignIn role={role} onDone={onDone} label={label} /> : <WalletSignIn role={role} onDone={onDone} />;
}

export async function session(role: Role, wallet: string, sign: (message: string) => Promise<string>): Promise<Worker | Client> {
  const network = RAILS.robinhood.network;
  const base = role === "worker" ? "/v1/workers" : "/v1/clients";
  const call = role === "worker" ? api : capi;
  const nonce = await call<{ nonce: string; message: string; wallet: string }>(`${base}/nonce`, { body: { wallet, network }, ...(role === "worker" ? { auth: false } : {}) });
  const signature = await sign(nonce.message);
  const s = await call<{ token: string; worker?: Worker; client?: Client }>(`${base}/session`, { body: { wallet: nonce.wallet, network, nonce: nonce.nonce, signature }, ...(role === "worker" ? { auth: false } : {}) });
  if (role === "worker") setToken(s.token);
  else setClientToken(s.token);
  return (s.worker ?? s.client)!;
}

function PrivySignIn({ role, onDone, label }: { role: Role; onDone: Done; label: string }) {
  const { ready, authenticated, login, logout } = usePrivy();
  const { wallets, ready: walletsReady } = useWallets();
  const [busy, setBusy] = useState(false);
  const [wanted, setWanted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [devWallet, setDevWallet] = useState("");
  const running = useRef(false);

  useEffect(() => {
    if (!wanted || !authenticated || !walletsReady || running.current) return;
    const wallet = wallets[0];
    if (!wallet) return; // the wallet is still connecting
    running.current = true;
    (async () => {
      setBusy(true);
      setError(null);
      try {
        const provider = await wallet.getEthereumProvider();
        const who = await session(role, wallet.address, async (message) => (await provider.request({ method: "personal_sign", params: [message, wallet.address] })) as string);
        onDone(who);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setBusy(false);
        setWanted(false);
        running.current = false;
      }
    })();
  }, [wanted, authenticated, walletsReady, wallets, role, onDone]);

  const start = () => {
    setError(null);
    setWanted(true);
    if (!authenticated) login();
  };

  const dev = async () => {
    try {
      onDone(role === "worker" ? await devSignIn("robinhood", devWallet) : await clientDevSignIn("robinhood", devWallet));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="space-y-3">
      <button onClick={start} disabled={!ready || busy} className="flex h-[52px] w-full items-center justify-center rounded-full bg-white font-serif text-[16px] font-semibold text-[#0a0a0f] transition hover:bg-[#e6ecff] disabled:opacity-50">
        {busy ? "Signing you in…" : !ready ? "Loading…" : label}
      </button>
      <p className="font-serif text-[13px] font-light text-white/50">MetaMask or Phantom. Your installed wallet is found automatically, and your rewards are paid to it.</p>
      {authenticated && !busy && (
        <button onClick={() => logout()} className="font-serif text-[13px] text-white/45 underline hover:text-white">Use a different wallet</button>
      )}
      {DEV && (
        <div className="rounded-[12px] border border-dashed border-amber-300/30 p-3 font-serif text-[13px] text-amber-100/80">
          <div className="mb-2">Local sign-in without an account</div>
          <div className="flex gap-2">
            <input value={devWallet} onChange={(e) => setDevWallet(e.target.value)} placeholder="0x…" className="w-full rounded-md border border-white/10 bg-black/40 px-3 py-2 font-mono text-[13px] text-white outline-none" />
            <button onClick={dev} disabled={!devWallet} className="shrink-0 rounded-md border border-white/20 px-3 text-white/80 disabled:opacity-40">Go</button>
          </div>
        </div>
      )}
      {error && <p className="font-serif text-[14px] text-red-300">{error}</p>}
    </div>
  );
}

function WalletSignIn({ role, onDone }: { role: Role; onDone: Done }) {
  const [busy, setBusy] = useState<Rail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const go = async (rail: Rail) => {
    setBusy(rail);
    setError(null);
    try {
      onDone(role === "worker" ? await signIn(rail) : await clientSignIn(rail));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };
  return (
    <div className="space-y-3">
      {(Object.keys(RAILS) as Rail[]).map((rail) => (
        <button key={rail} onClick={() => go(rail)} disabled={busy !== null} className="flex w-full items-center justify-between rounded-[14px] border border-white/10 bg-white/[0.03] px-5 py-4 text-left hover:border-white/30 disabled:opacity-50">
          <span className="font-serif text-[18px]">{RAILS[rail].label}</span>
          <span className="font-serif text-[14px] text-white/60">{busy === rail ? "Signing…" : hasWallet(rail) ? "Connect →" : "No wallet found"}</span>
        </button>
      ))}
      {error && <p className="font-serif text-[14px] text-red-300">{error}</p>}
    </div>
  );
}

/** Signs out of the site and, when Privy is on, of the Privy account too. */
export function SignOut({ onDone, className = "" }: { onDone: () => void; className?: string }) {
  return PRIVY_ON ? <PrivySignOut onDone={onDone} className={className} /> : <button onClick={onDone} className={className}>Sign out</button>;
}

function PrivySignOut({ onDone, className }: { onDone: () => void; className: string }) {
  const { logout } = usePrivy();
  return (
    <button
      onClick={() => {
        logout().catch(() => {});
        onDone();
      }}
      className={className}
    >
      Sign out
    </button>
  );
}

/** For accounts whose wallet was created here: lets the person take their key with them. */
export function ExportWallet() {
  return PRIVY_ON ? <PrivyExport /> : null;
}

function PrivyExport() {
  const { exportWallet, authenticated, user } = usePrivy();
  if (!authenticated || !user?.wallet || user.wallet.walletClientType !== "privy") return null;
  return (
    <button onClick={() => exportWallet().catch(() => {})} className="font-serif text-[13px] text-white/55 underline hover:text-white">
      Export this wallet&apos;s key
    </button>
  );
}
