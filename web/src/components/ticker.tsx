"use client";

import { useReducedMotion } from "framer-motion";
import Link from "next/link";
import { money } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { useRewards } from "@/lib/live";
import { short } from "@/lib/wallet";

/** A strip of the latest real payments, moving slowly from right to left. It pauses under the cursor. */
export function Ticker() {
  const { t } = useLang();
  const r = useRewards();
  const still = useReducedMotion();
  const rows = r?.recent ?? [];
  if (rows.length === 0) return null;
  // Enough copies to fill a wide screen, then the whole run twice so the loop has no seam.
  const copies = Math.max(1, Math.ceil(12 / rows.length));
  const run = Array.from({ length: copies }, () => rows).flat();
  const seconds = Math.max(40, run.length * 5);

  const item = (p: (typeof rows)[number], i: number) => (
    <Link key={i} href={p.taskId ? `/tasks/${p.taskId}` : "/rewards"} className="group flex shrink-0 items-center gap-3 whitespace-nowrap px-6 font-serif text-[14px] text-white/65 hover:text-white">
      <span className="h-1.5 w-1.5 rounded-full bg-[#9be36b]" />
      <span className="font-mono text-[#9be36b]">{money(p.amount)}</span>
      <span>{t("ticker.paidTo")}</span>
      <span className="font-mono text-[13px] text-white/80">{short(p.wallet)}</span>
      {p.team && <span className="rounded-full border border-white/15 px-2 py-0.5 text-[11px] text-white/50">{t("ticker.team")}</span>}
      <span className="max-w-[260px] truncate text-white/45">{t("ticker.for", { title: p.title })}</span>
    </Link>
  );

  return (
    <div className="relative border-y border-white/[0.08] bg-[#0a0a0f]">
      <div className="mx-auto flex max-w-[1800px] items-stretch">
        <Link href="/rewards" className="z-10 flex shrink-0 items-center gap-2 border-r border-white/[0.08] bg-[#0a0a0f] px-4 font-mono text-[11px] uppercase tracking-[0.08em] text-white/60 hover:text-white sm:px-6">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#9be36b] opacity-70" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-[#9be36b]" />
          </span>
          <span className="hidden sm:inline">{t("ticker.paid")}</span>
          <span className="sm:hidden">{t("ticker.paidShort")}</span>
        </Link>
        <div className="ticker-mask relative min-w-0 flex-1 overflow-hidden py-3.5">
          {still ? (
            <div className="flex overflow-x-auto">{rows.map(item)}</div>
          ) : (
            <div className="ticker-track flex w-max" style={{ animationDuration: `${seconds}s` }}>
              {run.map(item)}
              {run.map((p, i) => item(p, i + run.length))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
