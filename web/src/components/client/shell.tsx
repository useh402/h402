"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import { Mark } from "@/components/nav";
import { SignOut } from "@/components/sign-in";
import { capi, getClientToken, setClientToken, type Client } from "@/lib/client";
import { short } from "@/lib/wallet";

const Ctx = createContext<{ client: Client | null; refresh: () => Promise<void> }>({ client: null, refresh: async () => {} });
export const useClient = () => useContext(Ctx);

export function ClientShell({ children }: { children: React.ReactNode }) {
  const [client, setClient] = useState<Client | null>(null);
  const [ready, setReady] = useState(false);
  const router = useRouter();
  const path = usePathname();

  const refresh = async () => {
    if (!getClientToken()) return setClient(null);
    try {
      setClient(await capi<Client>("/v1/clients/me"));
    } catch {
      setClientToken(null);
      setClient(null);
    }
  };
  useEffect(() => {
    const t = setTimeout(() => refresh().finally(() => setReady(true)), 0);
    return () => clearTimeout(t);
  }, []);
  useEffect(() => {
    if (!ready) return;
    const open = path === "/client" || path.startsWith("/client/docs");
    if (!client && !open) router.replace("/client");
    if (client && path === "/client") router.replace("/client/tasks");
  }, [ready, client, path, router]);

  const links = [
    { href: "/client/tasks", label: "Tasks from your software" },
    { href: "/client/docs", label: "Connect your software" },
  ];
  return (
    <Ctx.Provider value={{ client, refresh }}>
      <div className="min-h-screen bg-[#080808] text-white">
        <header className="sticky top-0 z-40 border-b border-white/[0.08] bg-[#0a0a0f]/80 backdrop-blur-xl">
          <div className="mx-auto flex min-h-[64px] max-w-[1200px] flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-2 sm:px-8 md:flex-nowrap md:py-0">
            <Link href="/" className="flex shrink-0 items-center gap-2 text-[17px] font-semibold text-white sm:gap-2.5 sm:text-[18px]">
              <Mark className="h-7 w-7" />
              <span className="font-sans">H402</span>
              <span className="ml-2 rounded-full border border-white/15 px-2.5 py-0.5 font-serif text-[12px] font-light text-white/70">Clients</span>
            </Link>
            <nav className="order-last flex w-full items-center gap-5 overflow-x-auto whitespace-nowrap pb-1 font-serif text-[15px] font-light md:order-none md:w-auto md:gap-7 md:pb-0 md:text-[16px]">
              {links.map((l) => (
                <Link key={l.href} href={l.href} className={path.startsWith(l.href) ? "text-white" : "text-white/60 hover:text-white"}>
                  {l.label}
                </Link>
              ))}
            </nav>
            <div className="flex shrink-0 items-center gap-3 whitespace-nowrap font-serif text-[13px] text-white/70 sm:text-[14px]">
              {client ? (
                <>
                  <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5"><span className="hidden sm:inline">{client.name || (client.rail === "robinhood" ? "Robinhood" : "Solana")} · </span>{short(client.wallet)}</span>
                  <SignOut className="text-white/50 hover:text-white" onDone={() => { setClientToken(null); setClient(null); router.replace("/client"); }} />
                </>
              ) : (
                <Link href="/earn" className="text-white/50 hover:text-white">I want to earn instead</Link>
              )}
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-[1200px] px-4 py-6 sm:px-8 sm:py-10">{ready ? children : null}</main>
      </div>
    </Ctx.Provider>
  );
}

export function StateBadge({ state }: { state: string }) {
  const tone: Record<string, string> = {
    open: "border-[#9db4ff]/40 text-[#9db4ff]", claimed: "border-[#9db4ff]/40 text-[#9db4ff]", submitted: "border-amber-300/40 text-amber-200", done: "border-[#9be36b]/40 text-[#9be36b]",
    expired: "border-white/20 text-white/50", rejected: "border-red-400/40 text-red-300", cancelled: "border-white/20 text-white/50", disputed: "border-amber-300/40 text-amber-200",
  };
  const label: Record<string, string> = { open: "Waiting for workers", claimed: "Being worked on", submitted: "Proof in, your decision", done: "Done", expired: "Expired, refunded", rejected: "Refused, refunded", cancelled: "Cancelled, refunded", disputed: "In dispute" };
  return <span className={`rounded-full border px-2.5 py-0.5 font-serif text-[12px] ${tone[state] ?? "border-white/20 text-white/60"}`}>{label[state] ?? state}</span>;
}
