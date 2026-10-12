"use client";

import { AnimatePresence, motion } from "framer-motion";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useLang } from "@/lib/i18n";
import { Mark } from "./nav";
import { useScrollLock } from "./smooth";

const KEY = "humanapi.notice.v1";

/** Shown once, before anything else, the first time someone opens the site. Says plainly what happens to their responses. */
export function Announcement() {
  const { t } = useLang();
  const [show, setShow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => {
      try {
        if (!localStorage.getItem(KEY)) setShow(true);
      } catch {
        setShow(true);
      }
    }, 0);
    return () => clearTimeout(t);
  }, []);
  useScrollLock(show);
  const accept = () => {
    try {
      localStorage.setItem(KEY, String(Date.now()));
    } catch {}
    setShow(false);
  };
  return (
    <AnimatePresence>
      {show && (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, transition: { duration: 0.3, ease: "easeOut" } }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="fixed inset-0 z-[100] flex items-end justify-center bg-[#080808]/90 p-4 backdrop-blur-md sm:items-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="notice-title"
    >
      <motion.div
        data-lenis-prevent
        initial={{ opacity: 0, y: 28, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 16, scale: 0.98, transition: { duration: 0.22, ease: "easeIn" } }}
        transition={{ type: "spring", stiffness: 260, damping: 30, mass: 0.9, delay: 0.05 }}
        className="max-h-[calc(100dvh-32px)] w-full max-w-[640px] overflow-y-auto rounded-[22px] border border-white/[0.12] bg-[#0b0b0e] p-6 shadow-[0_40px_120px_-40px_rgba(60,100,255,0.5)] sm:p-9"
      >
        <div className="flex items-center gap-3">
          <Mark className="h-8 w-8" />
          <span className="font-sans text-[18px] font-semibold">H402</span>
        </div>
        <h1 id="notice-title" className="mt-6 font-serif text-[28px] font-light leading-[1.1] tracking-[-0.5px] sm:text-[34px]">{t("notice.title")}</h1>
        <ol className="mt-6 space-y-4 font-serif text-[15px] font-light leading-[1.5] text-white/80">
          {([1, 2, 3] as const).map((n) => (
            <li key={n} className="flex gap-3">
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-white/25 font-mono text-[11px] text-white/70">{n}</span>
              <span>
                <strong className="font-normal text-white">{t(`notice.${n}.strong`)}</strong>
                {t(`notice.${n}.body`)}
              </span>
            </li>
          ))}
        </ol>
        <p className="mt-5 font-serif text-[13px] text-white/50">
          {t("notice.terms.a")}<Link href="/terms" className="text-white underline">{t("notice.terms.link")}</Link>{t("notice.terms.and")}<Link href="/privacy" className="text-white underline">{t("notice.privacy.link")}</Link>{t("notice.terms.b")}
        </p>
        <div className="mt-6 flex flex-wrap items-center justify-end gap-3">
          <a href="https://www.google.com" className="font-serif text-[14px] text-white/55 hover:text-white">{t("notice.leave")}</a>
          <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }} transition={{ type: "spring", stiffness: 420, damping: 24, mass: 0.6 }} onClick={accept} className="h-[48px] rounded-full bg-white px-6 font-serif text-[15px] font-semibold text-[#0a0a0f] hover:bg-[#e6ecff]">
            {t("notice.accept")}
          </motion.button>
        </div>
      </motion.div>
    </motion.div>
      )}
    </AnimatePresence>
  );
}
