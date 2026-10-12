"use client";

import { motion } from "framer-motion";
import { ArrowUpRight, Check, Copy } from "lucide-react";
import { useEffect, useState } from "react";
import { useLang } from "@/lib/i18n";
import { GlCanvas, SMOKE } from "./gl";
import { PillButton } from "./nav";

/** The H402 token on Robinhood Chain: its contract address and where to trade it. */
export const TOKEN_ADDRESS = "0x949700985645e346b8ee23535e747853fbbfd3b1";
export const TOKEN_TRADE_URL = "https://axiom.trade/token/0x949700985645e346b8ee23535e747853fbbfd3b1?chain=robinhood&chains=robinhood&pulseChains=robinhood&trackerChains=sol,robinhood,bnb,eth&discoverChains=robinhood";

/** The token's contract address with a copy button and a link to the trade page. */
function TokenPill() {
  const { t } = useLang();
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const t = setTimeout(() => setCopied(false), 1600);
    return () => clearTimeout(t);
  }, [copied]);
  const copy = () => {
    navigator.clipboard?.writeText(TOKEN_ADDRESS).then(() => setCopied(true)).catch(() => {});
  };
  return (
    <div className="inline-flex max-w-full flex-wrap items-center justify-center gap-x-1 gap-y-2 rounded-full border border-white/15 bg-white/[0.05] py-1.5 pl-4 pr-1.5 backdrop-blur-xl">
      <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-white/50">CA</span>
      <button onClick={copy} title={t("hero.copy")} className="group ml-2 inline-flex items-center gap-2 rounded-full px-2 py-1 font-mono text-[13px] text-white/85 transition-colors hover:bg-white/[0.07] hover:text-white">
        <span className="hidden sm:inline">{TOKEN_ADDRESS}</span>
        <span className="sm:hidden">{TOKEN_ADDRESS.slice(0, 8)}…{TOKEN_ADDRESS.slice(-6)}</span>
        {copied ? <Check className="h-3.5 w-3.5 text-[#9be36b]" strokeWidth={2.2} /> : <Copy className="h-3.5 w-3.5 text-white/50 transition-colors group-hover:text-white" strokeWidth={2} />}
      </button>
      <motion.a
        href={TOKEN_TRADE_URL}
        target="_blank"
        rel="noreferrer noopener"
        whileHover={{ scale: 1.03 }}
        whileTap={{ scale: 0.97 }}
        transition={{ type: "spring", stiffness: 420, damping: 24, mass: 0.6 }}
        className="inline-flex h-[34px] items-center gap-1.5 rounded-full bg-white px-3.5 font-serif text-[13px] font-semibold text-[#0a0a0f] hover:bg-[#e6ecff]"
      >
        {t("hero.trade")}
        <ArrowUpRight className="h-3.5 w-3.5" strokeWidth={2.2} />
      </motion.a>
    </div>
  );
}

export function Hero() {
  const { t, lang } = useLang();
  return (
    <section id="top" className="relative h-[100svh] min-h-[720px] w-full overflow-hidden bg-[#080808]">
      <GlCanvas fragment={SMOKE} className="absolute inset-0 h-full w-full" />
      <div aria-hidden className="pointer-events-none absolute inset-x-0 bottom-0 h-[38%] bg-gradient-to-b from-transparent to-[#080808]" />

      <div className="relative mx-auto flex h-full max-w-[1600px] flex-col items-center justify-center px-6 text-center">
        <motion.h1
          initial={{ opacity: 0, y: 24, filter: "blur(10px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={{ duration: 1.4, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
          className={`font-serif text-[56px] font-light leading-[1.15] text-white sm:text-[84px] lg:text-[120px] lg:leading-[1.3] ${lang === "zh" ? "tracking-[0.02em]" : "tracking-[-0.04em] lg:tracking-[-6px]"}`}
        >
          {t("hero.title.a")}<em className="italic">{t("hero.title.em")}</em>{t("hero.title.b")}
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1.1, delay: 0.55, ease: [0.22, 1, 0.36, 1] }}
          className="mt-4 max-w-[1100px] font-serif text-[15px] font-light leading-[1.4] tracking-[0.01em] text-white/85 sm:text-[16px]"
        >
          {t("hero.sub")}
        </motion.p>
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1.1, delay: 0.75, ease: [0.22, 1, 0.36, 1] }}
          className="mt-8"
        >
          <PillButton href="/tasks">{t("hero.cta")}</PillButton>
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1.1, delay: 0.95, ease: [0.22, 1, 0.36, 1] }}
          className="mt-5 flex max-w-full justify-center px-2"
        >
          <TokenPill />
        </motion.div>
      </div>
    </section>
  );
}
