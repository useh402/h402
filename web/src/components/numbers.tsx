"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { useLang } from "@/lib/i18n";
import { useRewards } from "@/lib/live";
import { Label, LiveCount, Reveal } from "./motion";

export function Numbers() {
  const { t } = useLang();
  const r = useRewards();
  const dollars = (n: number) => Math.round(n).toLocaleString("en-US");
  const stats = [
    {
      prefix: "$", value: (r?.rewardsPaid ?? 0) / 1e6, format: dollars, title: t("numbers.paid.title"),
      body: r ? t("numbers.paid.body", { payments: r.payments, people: r.peoplePaid, team: dollars(r.rewardsPaidTeamRuns / 1e6) }) : t("numbers.paid.fallback"),
      href: "/rewards", link: t("numbers.paid.link"),
    },
    {
      prefix: "", value: r?.tasks.open ?? 0, format: (n: number) => String(Math.round(n)), title: t("numbers.open.title"),
      body: t("numbers.open.body"),
      href: "/tasks", link: t("numbers.open.link"),
    },
    {
      prefix: "$", value: (r?.openRewards ?? 0) / 1e6, format: dollars, title: t("numbers.waiting.title"),
      body: t("numbers.waiting.body"),
      href: "/tasks", link: t("numbers.waiting.link"),
    },
  ];
  return (
    <section className="relative overflow-hidden bg-[#080808] px-6 py-[90px] sm:px-12 sm:py-[120px] lg:px-[55px]">
      <DotGrid />
      <div className="relative mx-auto max-w-[1600px]">
        <div className="flex items-center gap-3">
          <Label>{t("numbers.label")}</Label>
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#9be36b] opacity-70" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-[#9be36b]" />
          </span>
        </div>
        <div className="mt-[60px] grid gap-14 sm:mt-[90px] lg:grid-cols-3 lg:gap-0">
          {stats.map((stat, i) => (
            <Reveal key={stat.title} delay={i * 0.12} className={`lg:px-10 ${i > 0 ? "lg:border-l lg:border-white/[0.12]" : "lg:pl-0"}`}>
              <div className="flex items-start font-serif font-light leading-none text-white">
                {stat.prefix && <span className="mt-3 text-[40px] text-white/70 sm:text-[52px] lg:mt-5 lg:text-[64px]">{stat.prefix}</span>}
                <LiveCount value={stat.value} format={stat.format} className="text-[104px] tracking-[-0.06em] tabular-nums sm:text-[150px] xl:text-[190px]" />
              </div>
              <h3 className="mt-8 font-serif text-[24px] font-light text-white sm:mt-10">{stat.title}</h3>
              <p className="mt-3 max-w-[360px] font-serif text-[16px] font-light leading-[1.45] text-[#a2a2a2]">{stat.body}</p>
              <Link href={stat.href} className="mt-4 inline-block font-serif text-[15px] text-white underline decoration-white/30 underline-offset-4 hover:decoration-white">{stat.link}</Link>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/** Dots on a grid that light up toward the centre of the section. */
function DotGrid() {
  return (
    <motion.div
      aria-hidden
      initial={{ opacity: 0 }}
      whileInView={{ opacity: 1 }}
      viewport={{ once: true }}
      transition={{ duration: 1.6 }}
      className="pointer-events-none absolute inset-0"
      style={{
        backgroundImage: "radial-gradient(circle, rgba(140,160,255,0.55) 1px, transparent 1.6px)",
        backgroundSize: "26px 26px",
        maskImage: "radial-gradient(ellipse 38% 55% at 50% 40%, black 10%, rgba(0,0,0,0.35) 45%, transparent 75%)",
        WebkitMaskImage: "radial-gradient(ellipse 38% 55% at 50% 40%, black 10%, rgba(0,0,0,0.35) 45%, transparent 75%)",
      }}
    />
  );
}
