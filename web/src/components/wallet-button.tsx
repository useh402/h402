"use client";

import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, LogOut } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { usePrivy, useWallets } from "@privy-io/react-auth";
import { api, getToken, setToken, type Worker } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { short } from "@/lib/wallet";
import { PRIVY_ON } from "./providers";
import { session } from "./sign-in";

const PILL = "relative inline-flex whitespace-nowrap h-[42px] items-center justify-center gap-1.5 rounded-full bg-white px-4 font-serif text-[14px] font-semibold sm:h-[50px] sm:gap-2 sm:px-[24px] sm:text-[16px] text-[#0a0a0f] shadow-[0_0_18px_rgba(255,255,255,0.35)] transition hover:bg-[#e6ecff] disabled:opacity-60";

/** The button at the end of the navigation bar: connects a wallet, then becomes the signed-in menu. */
export function WalletButton() {
  const { t } = useLang();
  return PRIVY_ON ? <PrivyWalletButton /> : <Link href="/earn" className={PILL}>{t("nav.connect")}</Link>;
}

function PrivyWalletButton() {
  const { t } = useLang();
  const { ready, authenticated, login, logout } = usePrivy();
  const { wallets, ready: walletsReady } = useWallets();
  const router = useRouter();
  const [worker, setWorker] = useState<Worker | null>(null);
  const [checked, setChecked] = useState(false);
  const [wanted, setWanted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const running = useRef(false);
  const box = useRef<HTMLDivElement>(null);

  // Already signed in from an earlier visit?
  useEffect(() => {
    let live = true;
    (async () => {
      let me: Worker | null = null;
      if (getToken()) me = await api<Worker>("/v1/workers/me").catch(() => null);
      if (live) {
        setWorker(me);
        setChecked(true);
      }
    })();
    return () => {
      live = false;
    };
  }, []);

  // After the wallet connects, sign the site's own sign-in message.
  useEffect(() => {
    if (!wanted || !authenticated || !walletsReady || running.current) return;
    const wallet = wallets[0];
    if (!wallet) return;
    running.current = true;
    (async () => {
      setBusy(true);
      try {
        const provider = await wallet.getEthereumProvider();
        const me = (await session("worker", wallet.address, async (message) => (await provider.request({ method: "personal_sign", params: [message, wallet.address] })) as string)) as Worker;
        setWorker(me);
        if (!me.termsAccepted || !me.qualifiedTypes?.length) router.push("/earn/qualify/verify");
      } catch {
        // The person closed the wallet window; the button simply stays as it was.
      } finally {
        setBusy(false);
        setWanted(false);
        running.current = false;
      }
    })();
  }, [wanted, authenticated, walletsReady, wallets, router]);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  if (!worker) {
    return (
      <button
        onClick={() => {
          setWanted(true);
          if (!authenticated) login();
        }}
        disabled={!ready || !checked || busy}
        className={PILL}
      >
        {busy ? t("nav.connecting") : t("nav.connect")}
      </button>
    );
  }

  const disconnect = () => {
    setToken(null);
    setWorker(null);
    setOpen(false);
    logout().catch(() => {});
  };

  return (
    <div ref={box} className="relative">
      <button onClick={() => setOpen((v) => !v)} aria-expanded={open} className={PILL}>
        <span className="h-2 w-2 rounded-full bg-[#3fbf6b]" />
        <span className="font-mono text-[12px] font-medium sm:text-[14px]">{short(worker.wallet)}</span>
        <ChevronDown className={`h-4 w-4 transition ${open ? "rotate-180" : ""}`} strokeWidth={2} />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.97, transition: { duration: 0.14, ease: "easeIn" } }}
            transition={{ type: "spring", stiffness: 520, damping: 40, mass: 0.7 }}
            style={{ transformOrigin: "top right" }}
            className="absolute right-0 top-[52px] z-50 w-[250px] max-w-[calc(100vw-24px)] sm:top-[60px] overflow-hidden rounded-[18px] border border-white/12 bg-[#0c0c12]/95 p-2 shadow-[0_24px_60px_-20px_rgba(0,0,0,0.8)] backdrop-blur-2xl"
          >
            <div className="px-3 pb-2 pt-2">
              <div className="font-serif text-[12px] text-white/45">Connected wallet</div>
              <button onClick={() => navigator.clipboard?.writeText(worker.wallet)} title="Copy address" className="mt-0.5 font-mono text-[13px] text-white/90 hover:text-white">
                {short(worker.wallet)}
              </button>
            </div>
            <div className="my-1 h-px bg-white/10" />
            {[
              { href: "/tasks", label: "Open tasks" },
              { href: "/earn/tasks", label: "My tasks" },
              { href: "/earn/earnings", label: "Earnings" },
            ].map((l) => (
              <Link key={l.href} href={l.href} onClick={() => setOpen(false)} className="block rounded-[10px] px-3 py-2.5 font-serif text-[15px] text-white/80 hover:bg-white/[0.07] hover:text-white">
                {l.label}
              </Link>
            ))}
            <div className="my-1 h-px bg-white/10" />
            <button onClick={disconnect} className="flex w-full items-center gap-2 rounded-[10px] px-3 py-2.5 text-left font-serif text-[15px] text-red-300/90 hover:bg-red-400/10">
              <LogOut className="h-4 w-4" strokeWidth={1.8} />
              Disconnect
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
