"use client";

import { AnimatePresence, motion, useMotionTemplate, useScroll, useSpring, useTransform } from "framer-motion";
import { ArrowUpRight, Menu, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useLang } from "@/lib/i18n";
import { LanguageSwitch } from "./language-switch";
import { LivePill } from "./live-pill";
import { WalletButton } from "./wallet-button";

const LINKS = [
  { href: "/tasks", key: "nav.tasks" },
  { href: "/map", key: "nav.map" },
  { href: "/docs", key: "nav.docs" },
  { href: "/rewards", key: "nav.rewards" },
  { href: "/scouts", key: "nav.sources" },
  { href: "/#introduction", key: "nav.how" },
];

export function Nav() {
  const { t } = useLang();
  const { scrollY } = useScroll();
  const progress = useSpring(useTransform(scrollY, [0, 160], [0, 1]), { stiffness: 120, damping: 24, restDelta: 0.001 });
  const bgAlpha = useTransform(progress, [0, 1], [0.04, 0.55]);
  const background = useMotionTemplate`rgba(10, 10, 16, ${bgAlpha})`;
  const borderAlpha = useTransform(progress, [0, 1], [0.1, 0.18]);
  const border = useMotionTemplate`rgba(255, 255, 255, ${borderAlpha})`;
  // Only a small lift, never a scale: scaling a blurred bar makes the browser redo the blur every frame.
  const y = useTransform(progress, [0, 1], [0, -4]);
  const [hovered, setHovered] = useState<string | null>(null);
  const [menu, setMenu] = useState(false);

  return (
    <motion.header
      initial={{ opacity: 0, y: -18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 1, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
      className="fixed inset-x-0 top-3 z-50 flex justify-center px-3 sm:top-5 sm:px-6"
    >
      <motion.nav
        style={{ background, borderColor: border, y }}
        className="relative flex h-[56px] w-full max-w-[1180px] items-center gap-1 rounded-full border pl-1.5 pr-1.5 shadow-[0_20px_60px_-30px_rgba(60,100,255,0.45)] backdrop-blur-2xl sm:h-[66px] sm:gap-2 sm:pl-3 sm:pr-3"
      >
        <span aria-hidden className="pointer-events-none absolute inset-x-10 -bottom-px h-px bg-gradient-to-r from-transparent via-white/40 to-transparent" />
        <span aria-hidden className="pointer-events-none absolute inset-x-16 top-0 h-px bg-gradient-to-r from-transparent via-white/25 to-transparent" />

        <Link href="/" className="group flex shrink-0 items-center gap-2 rounded-full py-2 pl-2 pr-2 text-[17px] font-semibold tracking-tight text-white sm:gap-2.5 sm:pr-4 sm:text-[20px]">
          <motion.span whileHover={{ rotate: 90 }} transition={{ type: "spring", stiffness: 200, damping: 14 }} className="inline-flex">
            <Mark />
          </motion.span>
          <span className="hidden font-sans min-[370px]:inline">H402</span>
        </Link>

        <div className="relative ml-2 hidden items-center lg:flex" onMouseLeave={() => setHovered(null)}>
          {LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              onMouseEnter={() => setHovered(link.href)}
              className="relative whitespace-nowrap rounded-full px-4 py-2 font-serif text-[17px] font-light text-white/75 transition-colors duration-300 hover:text-white"
            >
              <AnimatePresence>
                {hovered === link.href && (
                  <motion.span
                    layoutId="nav-hover"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ type: "spring", stiffness: 380, damping: 32, mass: 0.7 }}
                    className="absolute inset-0 rounded-full bg-white/[0.08]"
                  />
                )}
              </AnimatePresence>
              <span className="relative">{t(link.key)}</span>
            </a>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-1.5 sm:gap-2.5">
          <LivePill />
          <LanguageSwitch className="hidden md:inline-flex" />
          <span className="hidden md:inline-flex">
            <GhostButton href="/tasks">{t("nav.board")}</GhostButton>
          </span>
          <WalletButton />
          <button onClick={() => setMenu((v) => !v)} aria-label={t("nav.menu")} aria-expanded={menu} className="flex h-[42px] w-[42px] items-center justify-center rounded-full border border-white/20 text-white lg:hidden">
            {menu ? <X className="h-5 w-5" strokeWidth={1.8} /> : <Menu className="h-5 w-5" strokeWidth={1.8} />}
          </button>
        </div>

        <AnimatePresence>
          {menu && (
            <motion.div
              initial={{ opacity: 0, y: -10, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -10, scale: 0.98, transition: { duration: 0.16, ease: "easeIn" } }}
              transition={{ type: "spring", stiffness: 520, damping: 40, mass: 0.7 }}
              className="absolute inset-x-0 top-[calc(100%+10px)] origin-top rounded-[22px] border border-white/12 bg-[#0c0c12]/95 p-2 shadow-[0_24px_60px_-20px_rgba(0,0,0,0.8)] backdrop-blur-2xl lg:hidden"
            >
              {LINKS.map((link) => (
                <a key={link.href} href={link.href} onClick={() => setMenu(false)} className="block rounded-[14px] px-4 py-3.5 font-serif text-[18px] text-white/85 hover:bg-white/[0.07]">
                  {t(link.key)}
                </a>
              ))}
              <a href="/earn" onClick={() => setMenu(false)} className="block rounded-[14px] px-4 py-3.5 font-serif text-[18px] text-white/85 hover:bg-white/[0.07]">{t("nav.earn")}</a>
              <div className="flex items-center justify-between px-4 py-3.5">
                <span className="font-serif text-[15px] text-white/55">{t("nav.language")}</span>
                <LanguageSwitch />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.nav>
    </motion.header>
  );
}

/** White pill with a soft glow, like the original's Glow / Stroke / Fill layers. */
export function PillButton({ href, children, className = "" }: { href: string; children: React.ReactNode; className?: string }) {
  return (
    <motion.a
      href={href}
      whileHover="hover"
      whileTap={{ scale: 0.97 }}
      transition={{ type: "spring", stiffness: 420, damping: 24, mass: 0.6 }}
      className={`group relative inline-flex h-[50px] items-center justify-center gap-2 rounded-full px-[26px] font-serif text-[16px] font-semibold text-[#0a0a0f] ${className}`}
    >
      <motion.span aria-hidden variants={{ hover: { opacity: 1, scale: 1.08 } }} initial={{ opacity: 0.55, scale: 1 }} className="absolute inset-0 rounded-full bg-white/70 blur-[8px]" />
      <span aria-hidden className="absolute inset-0 rounded-full bg-gradient-to-b from-white to-[#cfdcff]" />
      <span aria-hidden className="absolute inset-[2px] rounded-full bg-white" />
      <span className="relative">{children}</span>
      <motion.span variants={{ hover: { x: 2, y: -2 } }} className="relative">
        <ArrowUpRight className="h-4 w-4" strokeWidth={2} />
      </motion.span>
    </motion.a>
  );
}

/** Outlined pill that fills on hover. */
export function GhostButton({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <motion.a
      href={href}
      whileHover="hover"
      whileTap={{ scale: 0.97 }}
      transition={{ type: "spring", stiffness: 420, damping: 24, mass: 0.6 }}
      className="group relative inline-flex h-[50px] items-center justify-center whitespace-nowrap rounded-full border border-white/40 px-[22px] font-serif text-[16px] font-semibold text-white"
    >
      <motion.span aria-hidden variants={{ hover: { opacity: 1 } }} initial={{ opacity: 0 }} transition={{ duration: 0.25 }} className="absolute inset-0 rounded-full bg-white/10" />
      <span className="relative">{children}</span>
    </motion.a>
  );
}

export function Mark({ className = "h-7 w-7 sm:h-8 sm:w-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <circle cx="16" cy="16" r="15" fill="none" stroke="white" strokeWidth="1.4" />
      <path d="M16 4c-3 4-4 8-4 12s1 8 4 12c3-4 4-8 4-12s-1-8-4-12z" fill="none" stroke="white" strokeWidth="1.3" />
      <path d="M4 16c4-3 8-4 12-4s8 1 12 4c-4 3-8 4-12 4s-8-1-12-4z" fill="none" stroke="white" strokeWidth="1.3" />
      <circle cx="16" cy="16" r="2.4" fill="white" />
    </svg>
  );
}
