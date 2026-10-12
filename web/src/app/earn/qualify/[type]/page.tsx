"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Button, Panel, useWorker } from "@/components/earn/shell";
import { TaskCard } from "@/components/earn/task-card";
import { api, type Card } from "@/lib/api";
import { TYPES, TYPE_BY_KEY, labelOf } from "@/lib/types";

type Result = { correct: number; passed: boolean; results: boolean[]; explanations: string[] };

export default function QualifyPage() {
  const { type } = useParams<{ type: string }>();
  const info = TYPE_BY_KEY[type] ?? TYPES[0];
  const { worker, refresh } = useWorker();
  const router = useRouter();
  const returnTo = useSearchParams().get("next");
  const [samples, setSamples] = useState<Card[]>([]);
  const [stage, setStage] = useState<"intro" | "questions" | "result">("intro");
  const [i, setI] = useState(0);
  const [answers, setAnswers] = useState<unknown[]>([]);
  const [result, setResult] = useState<Result | null>(null);
  const [terms, setTerms] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<{ samples: { index: number; type: string; payload: Record<string, unknown> }[] }>(`/v1/workers/qualification/${type}`)
      .then((r) => {
        setStage("intro");
        setI(0);
        setAnswers([]);
        setResult(null);
        setSamples(r.samples.map((s) => ({ taskId: `q${s.index}`, type: s.type, price: 0, timeLeft: 0, deadline: 0, workers: 1, preview: "", held: true, holdExpiresAt: null, payload: s.payload })));
      })
      .catch((e) => setError(e.message));
  }, [type]);

  const unlocked = worker?.qualifiedTypes ?? [];
  const done = unlocked.includes(type);
  const next = TYPES.find((t) => !unlocked.includes(t.key) && t.key !== type);

  const acceptTerms = async () => {
    await api("/v1/workers/profile", { body: { acceptTerms: true, languages: ["en"] } });
    await refresh();
  };

  const submit = async (answer: unknown) => {
    // Answers are kept by question number, so going back and answering again replaces the earlier answer.
    const nextAnswers = [...answers.slice(0, i), answer];
    setAnswers(nextAnswers);
    setError(null);
    if (nextAnswers.length < 3) {
      setI(nextAnswers.length);
      return;
    }
    try {
      const r = await api<Result>(`/v1/workers/qualification/${type}`, { body: { answers: nextAnswers } });
      setResult(r);
      setStage("result");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const restart = () => {
    setI(0);
    setAnswers([]);
    setResult(null);
    setStage("questions");
  };

  if (worker && !worker.termsAccepted) {
    return (
      <div className="mx-auto max-w-[760px]">
        <Eyebrow>Before your first task</Eyebrow>
        <h1 className="mt-3 font-serif text-[40px] font-light leading-[1.1]">How working here works</h1>
        <Panel>
          <ol className="space-y-4 font-serif text-[17px] font-light leading-[1.45] text-white/80">
            {[
              ["You do the work yourself.", "One person, one account. Automated or shared accounts are removed and not paid."],
              ["You are paid when the work is accepted.", "For most tasks that means your answer matches the other people who did the same task. For action tasks the client accepts your proof."],
              ["Nobody knows who you are.", "You never see who posted a task. Clients never see who did it. Anything that asks for passwords, codes, money or private people is against the rules: report it with one tap and you are still paid."],
              ["Money goes to your wallet.", "Accepted work is paid in batches every ten minutes to the wallet you signed in with, on that wallet's chain."],
              ["You work for yourself.", "You are an independent contractor. Taxes on what you earn are yours to handle."],
            ].map(([head, body]) => (
              <li key={head} className="flex gap-4">
                <span className="mt-1 h-[6px] w-[6px] shrink-0 rounded-full bg-[#3b6cff]" />
                <span>
                  <span className="text-white">{head}</span> {body}
                </span>
              </li>
            ))}
          </ol>
          <label className="mt-7 flex items-center gap-3 font-serif text-[15px]">
            <input type="checkbox" checked={terms} onChange={(e) => setTerms(e.target.checked)} /> I have read this and I agree
          </label>
          <div className="mt-5">
            <Button onClick={acceptTerms} disabled={!terms}>
              Continue
            </Button>
          </div>
        </Panel>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-[300px_1fr] gap-8">
      <aside className="rounded-[18px] border border-white/[0.08] bg-white/[0.025] p-6">
        <div className="flex items-baseline justify-between">
          <h2 className="font-serif text-[20px] font-light">Types of work</h2>
          <span className="font-serif text-[13px] text-white/50">
            {unlocked.length} of {TYPES.length} unlocked
          </span>
        </div>
        <div className="mt-3 h-[3px] w-full rounded-full bg-white/10">
          <div className="h-full rounded-full bg-[#3b6cff] transition-all" style={{ width: `${(unlocked.length / TYPES.length) * 100}%` }} />
        </div>
        <ul className="mt-5 space-y-1">
          {TYPES.map((t) => {
            const isDone = unlocked.includes(t.key);
            const active = t.key === type;
            return (
              <li key={t.key}>
                <Link href={`/earn/qualify/${t.key}`} className={`flex items-center justify-between rounded-[12px] px-3 py-2.5 ${active ? "bg-white/[0.08]" : "hover:bg-white/[0.04]"}`}>
                  <span>
                    <span className={`block font-serif text-[16px] ${active ? "text-white" : "text-white/80"}`}>{t.label}</span>
                    <span className="block font-serif text-[12px] text-white/45">
                      {t.pay} · {t.short}
                    </span>
                  </span>
                  <span className={`font-serif text-[12px] ${isDone ? "text-[#9be36b]" : "text-white/35"}`}>{isDone ? "Unlocked" : "Locked"}</span>
                </Link>
              </li>
            );
          })}
        </ul>
        <p className="mt-5 font-serif text-[13px] font-light leading-[1.4] text-white/45">Each type has three practice questions. Two right unlocks paid tasks of that type. You can retry any time.</p>
      </aside>

      <div>
        {error && <p className="mb-3 font-serif text-[14px] text-red-300">{error}</p>}

        {stage === "intro" && (
          <div>
            <Eyebrow>{done ? "Unlocked" : "Qualification"}</Eyebrow>
            <h1 className="mt-3 font-serif text-[44px] font-light leading-[1.05] tracking-[-1px]">{info.label}</h1>
            <p className="mt-4 max-w-[640px] font-serif text-[18px] font-light leading-[1.45] text-white/75">{info.what}</p>
            <div className="mt-7 grid grid-cols-3 gap-4">
              {[
                ["Pays", info.pay],
                ["Takes", info.time],
                ["Accepted when", info.proof],
              ].map(([k, v]) => (
                <div key={k} className="rounded-[14px] border border-white/[0.08] bg-white/[0.025] p-5">
                  <div className="font-serif text-[12px] uppercase tracking-[0.08em] text-white/45">{k}</div>
                  <div className="mt-2 font-serif text-[16px] leading-[1.35] text-white/90">{v}</div>
                </div>
              ))}
            </div>
            <div className="mt-7 rounded-[14px] border border-white/[0.08] bg-white/[0.025] p-6">
              <div className="font-serif text-[12px] uppercase tracking-[0.08em] text-white/45">How to do it well</div>
              <ul className="mt-3 space-y-2 font-serif text-[16px] font-light leading-[1.45] text-white/80">
                {info.rules.map((r) => (
                  <li key={r} className="flex gap-3">
                    <span className="mt-[9px] h-[5px] w-[5px] shrink-0 bg-[#3b6cff]" />
                    {r}
                  </li>
                ))}
              </ul>
            </div>
            <div className="mt-8 flex items-center gap-4">
              {done ? (
                <>
                  <Button onClick={() => router.push(returnTo || "/tasks")}>{returnTo ? "Back to the task" : "Go to tasks"}</Button>
                  <Button kind="ghost" onClick={() => setStage("questions")}>
                    Practice again
                  </Button>
                </>
              ) : (
                <Button onClick={() => setStage("questions")} disabled={samples.length === 0}>
                  Start the three questions
                </Button>
              )}
              <span className="font-serif text-[14px] text-white/45">About a minute. No pay for practice, nothing lost if you miss.</span>
            </div>
          </div>
        )}

        {stage === "questions" && samples[i] && (
          <div>
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-3 font-serif text-[14px] text-white/60">
                <span>Practice · {info.label}</span>
                <Steps total={3} current={i} />
              </div>
              <span className="flex items-center gap-4">
                {i > 0 && (
                  <button onClick={() => { setError(null); setI(i - 1); }} className="font-serif text-[14px] text-white/70 hover:text-white">
                    ← Previous question
                  </button>
                )}
                <button onClick={() => setStage("intro")} className="font-serif text-[14px] text-white/45 hover:text-white">
                  Back to overview
                </button>
              </span>
            </div>
            <TaskCard key={`${type}-${i}`} card={samples[i]} practice onSubmit={async (a) => submit(a)} onRelease={() => setStage("intro")} busy={false} />
          </div>
        )}

        {stage === "result" && result && (
          <div>
            <Eyebrow>{result.passed ? "Unlocked" : "Not yet"}</Eyebrow>
            <h1 className="mt-3 font-serif text-[44px] font-light leading-[1.05] tracking-[-1px]">
              {result.passed ? `You can take ${info.label} tasks.` : "Two right are needed."}
            </h1>
            <p className="mt-3 font-serif text-[17px] font-light text-white/70">
              {result.correct} of 3 correct.{" "}
              {result.passed ? "Paid tasks of this type will show in your list from now on." : "Read the notes below and try again; it takes a minute."}
            </p>
            <ol className="mt-6 space-y-3">
              {result.results.map((ok, n) => (
                <li key={n} className={`flex gap-4 rounded-[14px] border p-4 ${ok ? "border-[#9be36b]/25 bg-[#9be36b]/5" : "border-red-400/25 bg-red-400/5"}`}>
                  <span className={`font-serif text-[14px] ${ok ? "text-[#9be36b]" : "text-red-300"}`}>{ok ? "Right" : "Missed"}</span>
                  <span className="font-serif text-[15px] font-light text-white/80">{result.explanations[n]}</span>
                </li>
              ))}
            </ol>
            <div className="mt-8 flex items-center gap-3">
              {result.passed ? (
                <>
                  <Button onClick={() => router.push(returnTo || "/tasks")}>{returnTo ? "Back to the task" : "Go to tasks"}</Button>
                  {next && (
                    <Button kind="ghost" onClick={() => router.push(`/earn/qualify/${next.key}`)}>
                      Next: {labelOf(next.key)}
                    </Button>
                  )}
                </>
              ) : (
                <>
                  <Button onClick={restart}>Try again</Button>
                  <Button kind="ghost" onClick={() => setStage("intro")}>
                    Read the overview
                  </Button>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2.5 font-serif text-[14px] text-white/70">
      <span className="h-[5px] w-[5px] bg-[#3b6cff]" />
      {children}
    </div>
  );
}

function Steps({ total, current }: { total: number; current: number }) {
  return (
    <span className="flex items-center gap-1.5">
      {Array.from({ length: total }).map((_, n) => (
        <span key={n} className={`h-[6px] rounded-full transition-all ${n < current ? "w-5 bg-[#9be36b]" : n === current ? "w-7 bg-white" : "w-5 bg-white/20"}`} />
      ))}
    </span>
  );
}
