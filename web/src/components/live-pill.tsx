"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { useLang } from "@/lib/i18n";

/** The small pill in the navigation: how many people are on the platform right now, from the task service. */
export function LivePill() {
  const { t } = useLang();
  const [n, setN] = useState<number | null>(null);
  useEffect(() => {
    let live = true;
    // This browser's own presence id lives for the session; it carries no personal data.
    let pid = "";
    try {
      pid = sessionStorage.getItem("h402.presence") || "";
      if (!pid) {
        pid = Array.from(crypto.getRandomValues(new Uint8Array(12)), (b) => b.toString(16).padStart(2, "0")).join("");
        sessionStorage.setItem("h402.presence", pid);
      }
    } catch {
      pid = Math.random().toString(16).slice(2) + Date.now().toString(16);
    }
    const load = () =>
      fetch(`${API_URL}/v1/presence`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ id: pid }) })
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
        .then((d: { online: number }) => live && setN(d.online))
        .catch(() => {});
    const t = setTimeout(load, 0);
    const id = setInterval(load, 30_000);
    return () => {
      live = false;
      clearTimeout(t);
      clearInterval(id);
    };
  }, []);
  return (
    <span className="hidden items-center gap-2 whitespace-nowrap rounded-full border border-white/10 bg-white/[0.04] px-3.5 py-2 font-serif text-[14px] text-white/75 xl:inline-flex" title={t("live.title")}>
      <span className="relative flex h-1.5 w-1.5">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#9be36b] opacity-70" />
        <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[#9be36b]" />
      </span>
      {n === null ? t("live.live") : n === 1 ? t("live.one") : t("live.many", { n })}
    </span>
  );
}
