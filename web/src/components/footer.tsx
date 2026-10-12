"use client";

import { useSyncExternalStore } from "react";
import { useLang } from "@/lib/i18n";
import { Mark } from "./nav";

const subscribe = (callback: () => void) => {
  const id = setInterval(callback, 1000);
  return () => clearInterval(id);
};

function Clock() {
  // Seconds since the epoch; 0 on the server so the markup matches on first paint.
  const seconds = useSyncExternalStore(subscribe, () => Math.floor(Date.now() / 1000), () => 0);
  if (!seconds) return null;
  const now = new Date(seconds * 1000);
  const time = now.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", second: "2-digit" });
  const date = now.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });
  return (
    <>
      <span className="font-semibold text-white/80">{time}</span> {date}
    </>
  );
}

export function Footer() {
  const { t } = useLang();
  return (
    <footer id="earn" className="bg-[#0d0d0d] px-6 pb-10 pt-16 sm:px-12 lg:px-[55px]">
      <div className="mx-auto max-w-[1600px]">
        <div className="flex flex-col justify-between gap-10 lg:flex-row">
          <div>
            <div className="flex items-center gap-2.5 text-[22px] font-semibold text-white">
              <Mark />
              <span className="font-sans">H402</span>
            </div>
            <p className="mt-6 max-w-[260px] font-serif text-[16px] font-light leading-[1.4] text-[#8c8c8c]">{t("footer.tagline")}</p>
          </div>
          <nav className="flex flex-wrap gap-x-[60px] gap-y-3">
            {[["footer.open", "/tasks"], ["footer.docs", "/docs"], ["footer.earn", "/earn"], ["footer.connect", "/client/docs"], ["footer.contact", "/contact"]].map(([key, href]) => (
              <a key={key} href={href} className="font-serif text-[16px] font-light text-[#8c8c8c] transition hover:text-white">
                {t(key)}
              </a>
            ))}
          </nav>
        </div>
        <div className="mt-[120px] h-px w-full bg-white/[0.12]" />
        <div className="mt-10 flex flex-col justify-between gap-4 font-serif text-[16px] font-light text-[#8c8c8c] lg:flex-row">
          <div>
            @ 2026 H402 — <Clock />
          </div>
          <div className="flex gap-4">
            <a href="/privacy" className="transition hover:text-white">{t("footer.privacy")}</a>
            <span className="text-white/20">|</span>
            <a href="/terms" className="transition hover:text-white">{t("footer.terms")}</a>
          </div>
        </div>
      </div>
    </footer>
  );
}
