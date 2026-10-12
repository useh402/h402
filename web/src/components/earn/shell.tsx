"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import { api, ApiError, getToken, type Worker } from "@/lib/api";
import { short, signOut } from "@/lib/wallet";
import { Mark } from "@/components/nav";
import { SignOut } from "@/components/sign-in";

const WorkerContext = createContext<{ worker: Worker | null; refresh: () => Promise<void> }>({ worker: null, refresh: async () => {} });
export const useWorker = () => useContext(WorkerContext);

export function EarnShell({ children }: { children: React.ReactNode }) {
  const [worker, setWorker] = useState<Worker | null>(null);
  const [paused, setPaused] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const router = useRouter();
  const path = usePathname();

  const refresh = async () => {
    if (!getToken()) {
      setWorker(null);
      return;
    }
    try {
      setWorker(await api<Worker>("/v1/workers/me"));
      setPaused(null);
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        setPaused(e.message);
        return;
      }
      signOut();
      setWorker(null);
    }
  };

  useEffect(() => {
    const t = setTimeout(() => {
      refresh().finally(() => setReady(true));
    }, 0);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    if (!ready || paused) return;
    if (!worker && path !== "/earn") router.replace("/earn");
    if (worker && path === "/earn") router.replace(worker.qualifiedTypes.length ? "/tasks" : "/earn/qualify/verify");
  }, [ready, paused, worker, path, router]);

  useEffect(() => {
    if (!worker) return;
    const id = setInterval(() => api("/v1/workers/heartbeat", { body: {} }).catch(() => {}), 30_000);
    return () => clearInterval(id);
  }, [worker]);

  const links = [
    { href: "/tasks", label: "Open tasks" },
    { href: "/earn/tasks", label: "My list" },
    { href: "/earn/qualify/verify", label: "Types of work" },
    { href: "/earn/earnings", label: "Earnings" },
  ];

  return (
    <WorkerContext.Provider value={{ worker, refresh }}>
      <div className="min-h-screen bg-[#080808] text-white">
        <header className="sticky top-0 z-40 border-b border-white/[0.08] bg-[#0a0a0f]/80 backdrop-blur-xl">
          <div className="mx-auto flex min-h-[64px] max-w-[1200px] flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-2 sm:px-8 md:flex-nowrap md:py-0">
            <Link href="/" className="flex shrink-0 items-center gap-2 text-[17px] font-semibold text-white sm:gap-2.5 sm:text-[18px]">
              <Mark className="h-7 w-7" />
              <span className="font-sans">H402</span>
              <span className="ml-2 rounded-full border border-white/15 px-2.5 py-0.5 font-serif text-[12px] font-light text-white/70">Earn</span>
            </Link>
            {worker && (
              <nav className="order-last flex w-full items-center gap-5 overflow-x-auto whitespace-nowrap pb-1 font-serif text-[15px] font-light md:order-none md:w-auto md:gap-7 md:pb-0 md:text-[16px]">
                {links.map((l) => (
                  <Link key={l.href} href={l.href} className={path.startsWith(l.href.replace("/verify", "")) ? "text-white" : "text-white/60 hover:text-white"}>
                    {l.label}
                  </Link>
                ))}
              </nav>
            )}
            <div className="flex shrink-0 items-center gap-3 whitespace-nowrap font-serif text-[13px] text-white/70 sm:text-[14px]">
              {worker ? (
                <>
                  <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5">
                    <span className="mr-2 inline-block h-1.5 w-1.5 rounded-full bg-[#9be36b]" />
                    <span className="hidden sm:inline">{worker.rail === "robinhood" ? "Robinhood" : "Solana"} · </span>{short(worker.wallet)}
                  </span>
                  <SignOut
                    className="text-white/50 hover:text-white"
                    onDone={() => {
                      signOut();
                      setWorker(null);
                      router.replace("/earn");
                    }}
                  />
                </>
              ) : (
                <span>Not signed in</span>
              )}
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-[1200px] px-4 py-6 sm:px-8 sm:py-10">
          {paused ? (
            <section className="rounded-[18px] border border-red-400/30 bg-red-400/5 p-7">
              <h2 className="font-serif text-[22px] font-light">Your account is paused</h2>
              <p className="mt-3 font-serif text-[16px] font-light text-white/75">{paused}</p>
              <p className="mt-3 font-serif text-[14px] text-white/45">Pending earnings are kept. Write to support with your wallet address if you think this is a mistake.</p>
              <button onClick={() => { signOut(); setPaused(null); router.replace("/earn"); }} className="mt-5 font-serif text-[14px] text-white/60 underline">Sign out</button>
            </section>
          ) : ready ? children : null}
        </main>
      </div>
    </WorkerContext.Provider>
  );
}

export function Panel({ title, children, aside }: { title?: string; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <section className="rounded-[18px] border border-white/[0.08] bg-white/[0.025] p-7">
      {(title || aside) && (
        <div className="mb-5 flex items-center justify-between">
          {title && <h2 className="font-serif text-[22px] font-light">{title}</h2>}
          {aside}
        </div>
      )}
      {children}
    </section>
  );
}

export function Button({ children, onClick, disabled, kind = "primary", type = "button" }: { children: React.ReactNode; onClick?: () => void; disabled?: boolean; kind?: "primary" | "ghost" | "danger"; type?: "button" | "submit" }) {
  const base = "inline-flex h-[44px] items-center justify-center rounded-full px-6 font-serif text-[15px] font-semibold transition disabled:cursor-not-allowed disabled:opacity-40";
  const styles = {
    primary: "bg-white text-[#0a0a0f] hover:bg-[#e6ecff]",
    ghost: "border border-white/30 text-white hover:bg-white/10",
    danger: "border border-red-400/40 text-red-200 hover:bg-red-400/10",
  }[kind];
  return (
    <button type={type} onClick={onClick} disabled={disabled} className={`${base} ${styles}`}>
      {children}
    </button>
  );
}
