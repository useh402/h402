"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Panel, useWorker } from "@/components/earn/shell";
import { Countdown, TaskCard } from "@/components/earn/task-card";
import { api, money, type Card } from "@/lib/api";
import { labelOf } from "@/lib/types";
import { short } from "@/lib/wallet";
import { Protect } from "@/components/protect";

export default function TasksPage() {
  const { worker } = useWorker();
  const [feed, setFeed] = useState<Card[]>([]);
  const [active, setActive] = useState<Card | null>(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await api<{ tasks: Card[] }>("/v1/workers/tasks");
      setFeed(r.tasks);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    const first = setTimeout(load, 0);
    const id = setInterval(load, 4000);
    return () => {
      clearTimeout(first);
      clearInterval(id);
    };
  }, [load]);

  const claim = async (card: Card) => {
    setBusy(true);
    try {
      setActive(await api<Card>(`/v1/tasks/${card.taskId}/claim`, { body: {} }));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      load();
    } finally {
      setBusy(false);
    }
  };

  const submit = async (answer: unknown, note: string, confidence?: number) => {
    if (!active) return;
    setBusy(true);
    try {
      const r = await api<{ state: string; agreed?: boolean }>(`/v1/tasks/${active.taskId}/answer`, { body: { answer, note, confidence } });
      setToast(r.state === "done" ? (r.agreed ? `Accepted. ${money(active.price)} added to your pending balance.` : "Submitted. The other answers did not match yours this time.") : active.type === "do" ? (["photos", "both", "screenshot"].includes(String(active.payload?.proof ?? "text")) ? "Proof submitted. The operator looks at your photos and what you typed, and approves them by hand." : "Proof submitted. The client has up to an hour to accept it; after that it is accepted automatically.") : "Submitted. You are paid once the other answers are in and match.");
      setActive(null);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const report = async (reason: string) => {
    if (!active) return;
    setBusy(true);
    try {
      await api(`/v1/tasks/${active.taskId}/report`, { body: { reason } });
      setToast("Reported. Thank you; the task is under review and your time is credited.");
      setActive(null);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const release = async () => {
    if (!active) return;
    await api(`/v1/tasks/${active.taskId}/release`, { body: {} }).catch(() => {});
    setActive(null);
    load();
  };

  if (worker && worker.qualifiedTypes.length === 0) {
    return (
      <Panel title="One step first">
        <p className="font-serif text-[16px] font-light text-white/70">
          Complete a qualification to see tasks.{" "}
          <Link href="/earn/qualify/verify" className="text-white underline">
            Start with Check →
          </Link>
        </p>
      </Panel>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[380px_1fr] lg:gap-8">
      <Panel title="Open tasks" aside={<span className="font-serif text-[13px] text-white/50">{feed.length} available</span>}>
        {error && <p className="mb-3 font-serif text-[13px] text-red-300">{error}</p>}
        {feed.length === 0 && <p className="font-serif text-[15px] font-light text-white/50">Nothing right now. New tasks appear here as soon as clients post them.</p>}
        <ul className="space-y-2">
          {feed.map((c, idx) => (
            <li key={c.taskId}>
              {(idx === 0 || feed[idx - 1].categoryLabel !== c.categoryLabel) && (
                <div className="mb-1.5 mt-3 font-serif text-[12px] uppercase tracking-[0.08em] text-white/40 first:mt-0">{c.categoryLabel ?? "Other"}</div>
              )}
              <button
                onClick={() => (c.held ? setActive(c) : claim(c))}
                disabled={busy}
                className={`w-full rounded-[12px] border px-4 py-3 text-left transition ${active?.taskId === c.taskId ? "border-white/60 bg-white/[0.08]" : "border-white/10 bg-white/[0.02] hover:border-white/30"}`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-serif text-[14px] text-[#9db4ff]">{labelOf(c.type)}</span>
                  <span className="font-serif text-[14px]">{money(c.price)}</span>
                </div>
                <div className="mt-1 truncate font-serif text-[14px] font-light text-white/70">{c.preview || "image task"}</div>
                <div className="mt-1 flex items-center justify-between font-serif text-[12px] text-white/40">
                  <span>{c.workers} workers</span>
                  <span>closes in <Countdown until={c.deadline} long /></span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      </Panel>
      <div>
        {toast && (
          <div className="mb-4 rounded-[12px] border border-[#9be36b]/30 bg-[#9be36b]/10 px-4 py-3 font-serif text-[15px] text-[#d6f5bd]">
            {toast}
            <button className="ml-4 text-white/50" onClick={() => setToast(null)}>
              dismiss
            </button>
          </div>
        )}
        {active ? (
          <Protect mark={worker ? short(worker.wallet) : null}>
            <TaskCard key={active.taskId} card={active} onSubmit={submit} onRelease={release} onReport={active.taskId.startsWith("gold_") ? undefined : report} busy={busy} />
          </Protect>
        ) : (
          <Panel>
            <p className="font-serif text-[18px] font-light text-white/60">Pick a task on the left. Taking it holds your place and shows the full task. Short tasks hold for two minutes, action tasks for their whole time limit.</p>
            <p className="mt-3 font-serif text-[14px] font-light text-white/40">
              {worker?.tier} tier · reputation {worker?.reputation.toFixed(2)} · {worker?.agreed} of {worker?.answered} answers agreed · qualified for {worker?.qualifiedTypes.map(labelOf).join(", ")}
            </p>
          </Panel>
        )}
      </div>
    </div>
  );
}
