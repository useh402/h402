"use client";

import { useLang } from "@/lib/i18n";
import { Label, Reveal, ScrollWords } from "./motion";

export function Intro() {
  const { t } = useLang();
  return (
    <section id="introduction" className="bg-[#080808] px-6 pb-[120px] pt-[140px] sm:px-12 lg:px-[55px]">
      <div className="mx-auto max-w-[1600px]">
        <Label>{t("intro.label")}</Label>
        <ScrollWords
          text={t("intro.big")}
          className="mt-7 max-w-[1100px] font-serif text-[30px] font-light leading-[1.22] tracking-[-0.01em] sm:text-[40px] lg:text-[48px] lg:leading-[1.2]"
        />
        <div className="mt-[120px] h-px w-full bg-white/[0.12]" />
        <div className="mt-[64px] grid gap-10 lg:grid-cols-2 lg:gap-[250px]">
          <Reveal>
            <p className="max-w-[560px] font-serif text-[16px] font-light leading-[1.45] text-[#a2a2a2]">{t("intro.p1")}</p>
          </Reveal>
          <Reveal delay={0.1}>
            <p className="max-w-[420px] font-serif text-[16px] font-light leading-[1.45] text-[#a2a2a2]">{t("intro.p2")}</p>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
