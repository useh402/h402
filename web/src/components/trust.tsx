"use client";

import { motion } from "framer-motion";
import { useLang } from "@/lib/i18n";
import { Reveal, ScrollWords } from "./motion";

export function Trust() {
  const { t } = useLang();
  return (
    <section id="trust" className="bg-[#080808] px-6 pb-[140px] pt-[80px] sm:px-12 lg:px-[55px]">
      <div className="relative mx-auto max-w-[1600px]">
        <motion.div
          aria-hidden
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 1.4 }}
          className="pointer-events-none select-none text-center font-serif text-[120px] font-light italic leading-none tracking-[-0.05em] text-white/[0.07] lg:text-[200px]"
        >
          Trust
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-10% 0px" }}
          transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }}
          className="noise-card relative -mt-10 overflow-hidden rounded-[18px] px-7 pb-20 pt-12 sm:px-11 lg:-mt-16 lg:px-11 lg:pt-12"
        >
          <div aria-hidden className="absolute inset-0 bg-[radial-gradient(120%_90%_at_12%_0%,#dfe8ff_0%,#4f7df0_22%,#163a9d_48%,#0a1e5a_68%,#050a1f_100%)]" />
          <div aria-hidden className="absolute inset-0 bg-[radial-gradient(60%_80%_at_100%_100%,rgba(30,70,200,0.55),transparent_70%)]" />
          <div className="relative">
            <div className="flex items-center gap-2.5 font-serif text-[14px] text-white/80">
              <span className="h-[5px] w-[5px] bg-white/80" />
              {t("trust.label")}
            </div>
            <ScrollWords
              text={t("trust.big")}
              dim={0.35}
              className="mt-6 max-w-[1240px] font-serif text-[28px] font-light leading-[1.22] tracking-[-0.01em] text-white sm:text-[38px] lg:text-[48px] lg:leading-[1.2]"
            />
            <div className="mt-[180px] grid items-end gap-10 lg:grid-cols-[1fr_auto]">
              <Reveal>
                <p className="max-w-[760px] font-serif text-[20px] font-light leading-[1.3] text-white/85 lg:text-[24px]">{t("trust.p")}</p>
              </Reveal>
              <Reveal delay={0.15}>
                <div className="flex flex-wrap gap-3">
                  {[
                    { mark: "/brands/x402.svg", name: "x402", line: t("trust.x402"), wide: true },
                    { mark: "/brands/robinhood.svg", name: "Robinhood Chain", line: t("trust.rh") },
                  ].map((b) => (
                    <div key={b.name} className="flex items-center gap-3 rounded-full border border-white/35 bg-white/10 py-2 pl-2 pr-5 backdrop-blur">
                      <span className={`flex h-11 items-center justify-center rounded-full bg-white/15 ${"wide" in b && b.wide ? "min-w-11 px-3" : "w-11"}`}>
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={b.mark} alt="" className={"wide" in b && b.wide ? "h-[13px] w-auto" : "h-6 w-6 object-contain"} />
                      </span>
                      <span>
                        <span className="block font-sans text-[14px] font-semibold text-white">{b.name}</span>
                        <span className="block font-serif text-[12px] text-white/70">{b.line}</span>
                      </span>
                    </div>
                  ))}
                </div>
              </Reveal>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
