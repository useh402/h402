"use client";

import { motion, useMotionTemplate, useMotionValue, useReducedMotion, useSpring, useTransform } from "framer-motion";
import { ArrowLeft, ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Nav, PillButton } from "@/components/nav";
import { Pixel404 } from "@/components/pixel-404";
import { useLang } from "@/lib/i18n";

const EASE = [0.22, 1, 0.36, 1] as const;

/**
 * The page for an address that goes nowhere. "404" is drawn in pixels that
 * assemble, shimmer and answer the cursor; a status line types itself out
 * under them, then the message and the ways back. The page itself stays quiet:
 * near-black, a faint glow from the top, and a soft light under the cursor.
 */
export default function NotFound() {
  const still = useReducedMotion();
  const { t } = useLang();
  const LINE = t("nf.status");
  const px = useMotionValue(0.5);
  const py = useMotionValue(0.25);
  const sx = useSpring(px, { stiffness: 60, damping: 20, mass: 0.8 });
  const sy = useSpring(py, { stiffness: 60, damping: 20, mass: 0.8 });
  const lx = useTransform(sx, (v) => `${v * 100}%`);
  const ly = useTransform(sy, (v) => `${v * 100}%`);
  const spotlight = useMotionTemplate`radial-gradient(560px circle at ${lx} ${ly}, rgba(88,124,255,0.13), transparent 65%)`;

  useEffect(() => {
    if (still) return;
    const onMove = (e: PointerEvent) => {
      px.set(e.clientX / window.innerWidth);
      py.set(e.clientY / window.innerHeight);
    };
    window.addEventListener("pointermove", onMove);
    return () => window.removeEventListener("pointermove", onMove);
  }, [still, px, py]);

  // The status line types itself out once the pixels have assembled.
  const [typed, setTyped] = useState(still ? LINE.length : 0);
  useEffect(() => {
    let id: ReturnType<typeof setInterval>;
    const reset = setTimeout(() => setTyped(still ? LINE.length : 0), 0);
    const wait = setTimeout(() => {
      if (still) return;
      id = setInterval(() => setTyped((n) => (n >= LINE.length ? (clearInterval(id), n) : n + 1)), 38);
    }, 1300);
    return () => {
      clearTimeout(reset);
      clearTimeout(wait);
      clearInterval(id);
    };
  }, [still, LINE]);

  const rise = (delay: number) => ({ initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 }, transition: { duration: 1, delay, ease: EASE } });

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#060608] text-white">
      <Nav />
      <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-[70vh] bg-[radial-gradient(60%_100%_at_50%_0%,rgba(70,100,255,0.14),transparent_70%)]" />
      <motion.div aria-hidden style={{ background: spotlight }} className="pointer-events-none absolute inset-0" />
      <div aria-hidden className="noise-card pointer-events-none absolute inset-0" />

      <main className="relative mx-auto flex min-h-screen max-w-[1100px] flex-col items-center justify-center px-5 pb-14 pt-[104px] text-center">
        <Pixel404 className="w-[min(94vw,92vh,860px)]" />

        <div className="mt-2 flex items-center gap-4 font-mono text-[11px] uppercase tracking-[0.16em] text-white/55 sm:text-[12px]">
          <span aria-hidden className="hidden h-px w-14 bg-gradient-to-r from-transparent to-white/30 sm:block" />
          <span aria-label={LINE}>
            <span aria-hidden>{LINE.slice(0, typed)}</span>
            <motion.span aria-hidden animate={still ? undefined : { opacity: [1, 1, 0, 0] }} transition={{ duration: 1, times: [0, 0.5, 0.5, 1], repeat: Infinity }} className="ml-0.5 inline-block h-[1em] w-[0.55em] translate-y-[0.15em] bg-[#8fa8ff]" />
          </span>
          <span aria-hidden className="hidden h-px w-14 bg-gradient-to-l from-transparent to-white/30 sm:block" />
        </div>

        <motion.h1 {...rise(1.5)} className="mt-6 font-serif text-[32px] font-light leading-[1.06] tracking-[-0.5px] sm:text-[50px] sm:tracking-[-1px]">
          {t("nf.title.a")}<em className="italic">{t("nf.title.em")}</em>{t("nf.title.b")}
        </motion.h1>
        <motion.p {...rise(1.6)} className="mt-4 max-w-[470px] font-serif text-[17px] font-light leading-[1.5] text-white/60">
          {t("nf.sub")}
        </motion.p>

        <motion.div {...rise(1.7)} className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <PillButton href="/tasks">{t("nf.cta")}</PillButton>
          <motion.span whileHover={{ x: -3 }} whileTap={{ scale: 0.97 }} transition={{ type: "spring", stiffness: 420, damping: 24, mass: 0.6 }} className="inline-flex">
            <Link href="/" className="inline-flex h-[50px] items-center gap-2 rounded-full border border-white/25 px-6 font-serif text-[16px] font-semibold text-white transition-colors hover:border-white hover:bg-white/[0.06]">
              <ArrowLeft className="h-4 w-4" strokeWidth={2} />
              {t("nf.home")}
            </Link>
          </motion.span>
        </motion.div>

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 1.2, delay: 2 }} className="mt-10 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 font-mono text-[11px] uppercase tracking-[0.12em] text-white/40">
          {[["nf.docs", "/docs"], ["nf.rewards", "/rewards"], ["nf.map", "/map"], ["nf.contact", "/contact"]].map(([key, href]) => (
            <Link key={href} href={href} className="group inline-flex items-center gap-1 transition-colors hover:text-white">
              {t(key)}
              <ArrowUpRight className="h-3 w-3 opacity-0 transition-opacity group-hover:opacity-100" strokeWidth={2} />
            </Link>
          ))}
        </motion.div>
      </main>
    </div>
  );
}
