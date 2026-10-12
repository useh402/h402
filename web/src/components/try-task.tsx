"use client";

import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Check, Loader2, Minus } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useLang } from "@/lib/i18n";
import { Label, Reveal } from "./motion";

type Practice = { kind: string; reward: string; text: string; question: string; right: "yes" | "no"; why: string };

const PRACTICE: Practice[] = [
  { kind: "Check", reward: "$2.00", text: "A listing says “Open house Sunday, 1 pm to 3 pm.” The sign in the yard, photographed this morning, says “Sold.”", question: "Is this open house still likely to happen?", right: "no", why: "A sold sign means the listing is out of date." },
  { kind: "Check", reward: "$2.00", text: "The store's website says “Open until 9 pm.” A photo of the door, taken today, shows a handwritten note: “Closing at 5 today.”", question: "Should a customer trust the website tonight?", right: "no", why: "The note on the door is newer than the website." },
  { kind: "Check", reward: "$2.00", text: "A reply to an upset customer reads: “We hear you. A full refund is on its way and you can keep the item.”", question: "Would most customers feel looked after by this reply?", right: "yes", why: "It apologises in effect, fixes the problem and adds something extra." },
];

type Stage = "idle" | "checking" | "accepted" | "paid" | "missed";
type RowState = "waiting" | "working" | "done" | "none";

export function TryTask() {
  const { t } = useLang();
  const word = (v: "yes" | "no") => t(v === "yes" ? "try.yes" : "try.no");
  const [n, setN] = useState(0);
  const [stage, setStage] = useState<Stage>("idle");
  const [pick, setPick] = useState<"yes" | "no" | null>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const task = PRACTICE[n % PRACTICE.length];

  useEffect(() => () => timers.current.forEach(clearTimeout), []);
  const later = (ms: number, f: () => void) => timers.current.push(setTimeout(f, ms));

  const answer = (v: "yes" | "no") => {
    if (stage !== "idle") return;
    setPick(v);
    setStage("checking");
    later(1600, () => {
      if (v === task.right) {
        setStage("accepted");
        later(1200, () => setStage("paid"));
      } else {
        setStage("missed");
      }
    });
  };
  const next = () => {
    setPick(null);
    setStage("idle");
    setN((x) => x + 1);
  };

  const finished = stage === "paid" || stage === "missed";
  const rows: { title: string; detail: string; state: RowState; value?: string }[] = [
    { title: t("try.row.answer"), detail: pick ? t("try.row.answer.picked", { pick: word(pick) }) : t("try.row.answer.idle"), state: pick ? "done" : "waiting" },
    {
      title: t("try.row.others"),
      detail: stage === "idle" ? t("try.row.others.idle") : stage === "checking" ? t("try.row.others.checking") : t("try.row.others.done", { right: word(task.right) }),
      state: stage === "idle" ? "waiting" : stage === "checking" ? "working" : "done",
    },
    {
      title: t("try.row.decision"),
      detail: stage === "missed" ? t("try.row.decision.missed", { why: task.why }) : stage === "accepted" || stage === "paid" ? t("try.row.decision.done", { why: task.why }) : t("try.row.decision.idle"),
      state: stage === "missed" ? "none" : stage === "accepted" || stage === "paid" ? "done" : "waiting",
    },
    {
      title: t("try.row.reward"),
      detail: stage === "paid" ? t("try.row.reward.paid") : stage === "missed" ? t("try.row.reward.missed") : stage === "accepted" ? t("try.row.reward.accepted") : t("try.row.reward.idle"),
      state: stage === "paid" ? "done" : stage === "accepted" ? "working" : stage === "missed" ? "none" : "waiting",
      value: stage === "paid" ? `+ ${task.reward}` : stage === "missed" ? "$0.00" : undefined,
    },
  ];

  return (
    <section className="bg-[#080808] px-6 py-[90px] sm:px-12 sm:py-[120px] lg:px-[55px]">
      <div className="mx-auto max-w-[1600px]">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Label>{t("try.label")}</Label>
            <Reveal>
              <h2 className="mt-6 font-serif text-[36px] font-light leading-[1.06] tracking-[-0.01em] text-white sm:text-[48px] lg:text-[56px]">
                {t("try.title.a")}<em className="italic">{t("try.title.em")}</em>
              </h2>
            </Reveal>
          </div>
          <Reveal delay={0.1}>
            <p className="max-w-[440px] font-serif text-[16px] font-light leading-[1.5] text-[#a2a2a2]">{t("try.desc")}</p>
          </Reveal>
        </div>

        <Reveal delay={0.12}>
          <div className="mt-12 overflow-hidden rounded-[20px] border border-white/[0.1] bg-[#0b0b0e]">
            {/* Panel header */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.08] px-5 py-4 sm:px-8">
              <div className="flex items-center gap-3 font-serif text-[14px] text-white/70">
                <span className="rounded-md border border-white/12 bg-white/[0.04] px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.06em] text-white/70">{task.kind}</span>
                {t("try.practice")}
              </div>
              <div className="font-serif text-[14px] text-white/55">
                {t("try.reward")} <span className="ml-2 font-mono text-[16px] text-white">{task.reward}</span>
              </div>
            </div>

            <div className="grid lg:grid-cols-[1.15fr_0.85fr]">
              {/* The task */}
              <div className="p-5 sm:p-8 lg:border-r lg:border-white/[0.08]">
                <AnimatePresence mode="wait">
                  <motion.div key={n} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.25 }}>
                    <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-white/40">{t("try.given")}</div>
                    <p className="mt-3 border-l-2 border-white/15 pl-4 font-serif text-[17px] font-light leading-[1.55] text-white/85">{task.text}</p>
                    <h3 className="mt-7 font-serif text-[24px] font-light leading-[1.25] text-white sm:text-[28px]">{task.question}</h3>
                  </motion.div>
                </AnimatePresence>
                <div className="mt-6 grid max-w-[420px] grid-cols-2 gap-3">
                  {(["yes", "no"] as const).map((v) => (
                    <button
                      key={v}
                      onClick={() => answer(v)}
                      disabled={stage !== "idle"}
                      className={`h-[52px] rounded-full border font-serif text-[16px] font-semibold capitalize transition ${pick === v ? "border-white bg-white text-[#0a0a0f]" : stage === "idle" ? "border-white/30 text-white hover:border-white hover:bg-white/[0.06]" : "border-white/10 text-white/30"}`}
                    >
                      {word(v)}
                    </button>
                  ))}
                </div>
                <div className="mt-5 min-h-[24px]">
                  {finished && (
                    <button onClick={next} className="font-serif text-[15px] text-white/70 underline decoration-white/30 underline-offset-4 hover:text-white">
                      {t("try.another")}
                    </button>
                  )}
                </div>
              </div>

              {/* What happens to it */}
              <div className="border-t border-white/[0.08] p-5 sm:p-8 lg:border-t-0">
                <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-white/40">{t("try.next")}</div>
                <ol className="mt-4">
                  {rows.map((row, i) => (
                    <li key={row.title} className="relative flex gap-4 pb-6 last:pb-0">
                      {i < rows.length - 1 && <span aria-hidden className={`absolute left-[11px] top-[26px] h-[calc(100%-26px)] w-px transition-colors duration-500 ${row.state === "done" ? "bg-[#9be36b]/50" : "bg-white/10"}`} />}
                      <span
                        className={`relative z-10 mt-0.5 flex h-[23px] w-[23px] shrink-0 items-center justify-center rounded-full border transition-colors duration-500 ${
                          row.state === "done" ? "border-[#9be36b] bg-[#9be36b] text-[#0a0a0f]" : row.state === "working" ? "border-white/60 text-white" : row.state === "none" ? "border-white/25 text-white/45" : "border-white/20 text-white/40"
                        }`}
                      >
                        {row.state === "done" ? <Check className="h-3.5 w-3.5" strokeWidth={3} /> : row.state === "working" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : row.state === "none" ? <Minus className="h-3.5 w-3.5" /> : <span className="font-mono text-[11px]">{i + 1}</span>}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-baseline justify-between gap-3">
                          <span className={`font-serif text-[16px] transition-colors duration-500 ${row.state === "waiting" ? "text-white/60" : "text-white"}`}>{row.title}</span>
                          {row.value && (
                            <motion.span initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className={`font-mono text-[15px] ${row.state === "done" ? "text-[#9be36b]" : "text-white/45"}`}>
                              {row.value}
                            </motion.span>
                          )}
                        </div>
                        <div className="mt-1 font-serif text-[14px] font-light leading-[1.45] text-white/50">{row.detail}</div>
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            </div>

            {/* Panel footer */}
            <div className="flex flex-wrap items-center justify-between gap-4 border-t border-white/[0.08] px-5 py-4 sm:px-8">
              <span className="font-serif text-[14px] text-white/50">{t("try.footer")}</span>
              <Link href="/tasks" className="inline-flex items-center gap-2 font-serif text-[15px] font-semibold text-white hover:text-[#cfdcff]">
                {t("try.open")} <ArrowRight className="h-4 w-4" strokeWidth={2} />
              </Link>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
