"use client";

import { motion } from "framer-motion";
import { LANGS, useLang } from "@/lib/i18n";

/** EN / 中文 in the navigation. The chosen one carries a sliding highlight. */
export function LanguageSwitch({ className = "" }: { className?: string }) {
  const { lang, setLang, t } = useLang();
  return (
    <div role="group" aria-label={t("nav.language")} className={`relative inline-flex h-[36px] items-center rounded-full border border-white/15 bg-white/[0.04] p-0.5 font-sans text-[12px] font-semibold ${className}`}>
      {LANGS.map((l) => (
        <button key={l.code} onClick={() => setLang(l.code)} aria-pressed={lang === l.code} className={`relative z-10 rounded-full px-3 py-1.5 transition-colors ${lang === l.code ? "text-[#0a0a0f]" : "text-white/65 hover:text-white"}`}>
          {lang === l.code && <motion.span layoutId="lang-pill" transition={{ type: "spring", stiffness: 420, damping: 32, mass: 0.7 }} className="absolute inset-0 -z-10 rounded-full bg-white" />}
          {l.label}
        </button>
      ))}
    </div>
  );
}
