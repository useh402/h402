"use client";

import { AnimatePresence, motion } from "framer-motion";
import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { useLang } from "@/lib/i18n";
import { Label, Reveal } from "./motion";

export function Faq() {
  const { t } = useLang();
  const FAQ = [1, 2, 3, 4, 5, 6, 7, 8].map((n) => [t(`faq.${n}.q`), t(`faq.${n}.a`)] as const);
  const [open, setOpen] = useState<number | null>(null);
  return (
    <section id="faq" className="bg-[#080808] px-6 py-[120px] sm:px-12 lg:px-[55px]">
      <div className="mx-auto grid max-w-[1600px] gap-16 lg:grid-cols-2 lg:gap-24">
        <div>
          <Label>{t("faq.label")}</Label>
          <Reveal>
            <h2 className="mt-6 font-serif text-[36px] font-light leading-[1.05] tracking-[-0.01em] text-white sm:text-[44px] lg:text-[56px]">
              {t("faq.title.1")}
              <br />
              {t("faq.title.2")}
            </h2>
          </Reveal>
        </div>
        <div>
          {FAQ.map(([question, answer], i) => (
            <motion.div
              key={question}
              initial={{ opacity: 0, x: 40 * (i + 1) * 0.35, y: 20 }}
              whileInView={{ opacity: 1, x: 0, y: 0 }}
              viewport={{ once: true, margin: "-10% 0px" }}
              transition={{ duration: 0.9, delay: i * 0.07, ease: [0.22, 1, 0.36, 1] }}
              className="border-b border-white/[0.12]"
            >
              <button onClick={() => setOpen(open === i ? null : i)} className="flex w-full items-start gap-5 py-7 text-left">
                <span className="mt-0.5 w-5 shrink-0 font-serif text-[12px] text-[#3b6cff]">{String(i + 1).padStart(2, "0")}</span>
                <span className="flex-1 font-serif text-[19px] font-light leading-[1.25] text-white/90 transition group-hover:text-white sm:text-[22px] lg:text-[24px]">{question}</span>
                <motion.span animate={{ rotate: open === i ? 90 : 0 }} transition={{ type: "spring", stiffness: 400, damping: 28 }} className="mt-1 text-white/60">
                  <ChevronRight className="h-5 w-5" strokeWidth={1.5} />
                </motion.span>
              </button>
              <AnimatePresence initial={false}>
                {open === i && (
                  <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ height: { duration: 0.45, ease: [0.22, 1, 0.36, 1] }, opacity: { duration: 0.3, ease: "easeOut" } }} className="overflow-hidden">
                    <p className="max-w-[560px] pb-7 pl-8 sm:pl-10 font-serif text-[16px] font-light leading-[1.45] text-[#a2a2a2]">{answer}</p>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
