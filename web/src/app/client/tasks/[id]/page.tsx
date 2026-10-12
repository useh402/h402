"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Button, Panel } from "@/components/earn/shell";
import { StateBadge } from "@/components/client/shell";
import { money } from "@/lib/api";
import { capi, type ClientTask } from "@/lib/client";
import { labelOf } from "@/lib/types";

export default function ClientTaskPage() {
  const { id } = useParams<{ id: string }>();
  const [t, setT] = useState<ClientTask | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [mode, setMode] = useState<"none" | "reject" | "dispute" | "cancel">("none");
  const [now, setNow] = useState(0);

  const load = () =>
    capi<ClientTask>(`/v1/clients/tasks/${id}`)
      .then((task) => {
        setT(task);
        setNow(Math.floor(Date.now() / 1000));
      })
      .catch((e) => setMsg(e.message));
  useEffect(() => {
    const first = setTimeout(load, 0);
    const i = setInterval(load, 5000);
    return () => {
      clearTimeout(first);
      clearInterval(i);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const act = async (path: string, body: Record<string, unknown>, ok: string) => {
    setBusy(true);
    setMsg(null);
    try {
      await capi(`/v1/tasks/${id}/${path}`, { body });
      setMsg(ok);
      setMode("none");
      setReason("");
      await load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (!t) return msg ? <p className="font-serif text-red-300">{msg}</p> : null;
  const p = t.payload ?? {};
  const proofValue = t.proof?.value ?? (t.result as { proof?: unknown } | undefined)?.proof;
  const proof = typeof proofValue === "object" && proofValue ? (proofValue as { text?: string; screenshot?: string }) : null;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-6">
        <div>
          <Link href="/client/tasks" className="font-serif text-[13px] text-white/45 hover:text-white">← My tasks</Link>
          <h1 className="mt-2 font-serif text-[36px] font-light leading-[1.1]">{t.title}</h1>
          <div className="mt-3 flex flex-wrap items-center gap-3 font-serif text-[14px] text-white/60">
            <StateBadge state={t.state} />
            <span>{labelOf(t.type)}</span><span>·</span><span>{t.location}</span><span>·</span><span>{t.workers.wanted} worker{t.workers.wanted > 1 ? "s" : ""}</span><span>·</span><span>{money(t.cost.total)} total</span>
            {t.reference && <><span>·</span><span>ref {t.reference}</span></>}
          </div>
        </div>
        <div className="text-right font-serif text-[13px] text-white/50">
          <div>Posted {new Date(t.createdAt * 1000).toLocaleString()}</div>
          <div>Deadline {new Date(t.deadline * 1000).toLocaleString()}</div>
          {t.payment && <a href={t.payment.explorer} target="_blank" rel="noreferrer" className="text-[#9db4ff] underline">payment on chain ↗</a>}
        </div>
      </div>

      {msg && <div className="rounded-[12px] border border-white/15 bg-white/[0.04] px-4 py-3 font-serif text-[14px]">{msg}</div>}

      <div className="grid grid-cols-[1.2fr_0.8fr] gap-6">
        <div className="space-y-6">
          <Panel title="What you asked">
            {typeof p.image === "string" && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={p.image} alt="" className="mb-4 max-h-[300px] rounded-[10px] border border-white/10" />
            )}
            {typeof p.instructions === "string" && <p className="whitespace-pre-line font-serif text-[16px] font-light leading-[1.45] text-white/85">{p.instructions}</p>}
            {typeof p.question === "string" && <p className="font-serif text-[18px] font-light text-white/90">{p.question}</p>}
            {typeof p.text === "string" && <blockquote className="mt-3 rounded-[10px] border border-white/10 bg-white/[0.03] p-3 font-serif text-[15px] text-white/80">{p.text}</blockquote>}
            {typeof p.item === "string" && <blockquote className="mt-3 rounded-[10px] border border-white/10 bg-white/[0.03] p-3 font-serif text-[15px] text-white/80">{p.item}</blockquote>}
            {Array.isArray(p.options) && <ol className="mt-3 list-decimal space-y-1 pl-5 font-serif text-[15px] text-white/80">{(p.options as string[]).map((o, i) => <li key={i}>{o}</li>)}</ol>}
            {Array.isArray(p.labels) && <p className="mt-3 font-serif text-[14px] text-white/60">Labels: {(p.labels as string[]).join(", ")}</p>}
            {typeof p.url === "string" && <a href={p.url} target="_blank" rel="noreferrer" className="mt-3 inline-block font-serif text-[14px] text-[#9db4ff] underline">{p.url}</a>}
            {t.acceptance && <p className="mt-4 font-serif text-[14px] text-white/55">Accepted when: {t.acceptance}</p>}
          </Panel>

          {(t.state === "done" || t.proof) && (
            <Panel title={t.state === "done" ? "The answer" : "Proof submitted"}>
              {proof ? (
                <div className="space-y-3">
                  {proof.text && <p className="whitespace-pre-line font-serif text-[17px] font-light leading-[1.45]">{proof.text}</p>}
                  {proof.screenshot && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={proof.screenshot} alt="proof" className="max-h-[420px] rounded-[10px] border border-white/10" />
                  )}
                </div>
              ) : (
                <div className="font-serif text-[20px] font-light">
                  {String((t.result as { answer?: unknown } | undefined)?.answer ?? "")}
                  {(t.result as { note?: string } | undefined)?.note && <p className="mt-2 text-[14px] text-white/60">{(t.result as { note?: string }).note}</p>}
                  {t.agreement !== undefined && <p className="mt-2 text-[14px] text-white/60">{Math.round((t.agreement ?? 0) * 100)}% of the workers agreed</p>}
                </div>
              )}
              {t.state === "submitted" && (t.acceptBy || t.awaitingOperator) && (
                <div className="mt-5 rounded-[12px] border border-amber-300/30 bg-amber-300/5 p-4">
                  <p className="font-serif text-[14px] text-amber-100/85">
                    {t.acceptBy ? `Accept this proof or dispute it before ${new Date(t.acceptBy * 1000).toLocaleTimeString()}. After that it is accepted automatically.` : "The operator is looking at the pictures and will approve or refuse them. You can accept or dispute the proof yourself now."}
                  </p>
                  <div className="mt-3 flex gap-2">
                    <Button onClick={() => act("accept", {}, "Accepted. The worker is being paid.")} disabled={busy}>Accept</Button>
                    <Button kind="danger" onClick={() => setMode("reject")} disabled={busy}>Dispute</Button>
                  </div>
                </div>
              )}
            </Panel>
          )}

          {mode !== "none" && (
            <Panel title={mode === "cancel" ? "Cancel this task" : "Tell us what is wrong"}>
              <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3} placeholder={mode === "cancel" ? "Optional: why" : "At least ten characters. A person on our side reads this."} className="w-full rounded-[10px] border border-white/15 bg-black/40 p-3 font-serif text-[15px] text-white outline-none" />
              <div className="mt-3 flex gap-2">
                {mode === "reject" && <Button kind="danger" onClick={() => act("accept", { reject: true, reason }, "Sent. A person will look at it.")} disabled={busy || reason.trim().length < 10}>Send dispute</Button>}
                {mode === "dispute" && <Button kind="danger" onClick={() => act("dispute", { reason }, "Sent. A person will look at it.")} disabled={busy || reason.trim().length < 10}>Send dispute</Button>}
                {mode === "cancel" && <Button kind="danger" onClick={() => act("cancel", { reason }, "Cancelled. The money is on its way back.")} disabled={busy}>Cancel the task</Button>}
                <Button kind="ghost" onClick={() => setMode("none")}>Back</Button>
              </div>
            </Panel>
          )}

          {t.verification && (
            <Panel title="How it was decided">
              <p className="font-serif text-[14px] text-white/55">{t.verification.method} · {t.verification.outcome} · {new Date(t.verification.decidedAt * 1000).toLocaleString()}</p>
              <ul className="mt-3 space-y-2">
                {t.verification.checks.map((c, i) => (
                  <li key={i} className="flex gap-3 font-serif text-[15px]">
                    <span className={c.passed ? "text-[#9be36b]" : "text-red-300"}>{c.passed ? "✓" : "✗"}</span>
                    <span><span className="text-white">{c.name}</span> <span className="text-white/55">· {c.detail}</span></span>
                  </li>
                ))}
              </ul>
            </Panel>
          )}
        </div>

        <div className="space-y-6">
          <Panel title="Actions">
            <div className="flex flex-wrap gap-2">
              {["paid", "open", "claimed"].includes(t.state) && t.workers.answered === 0 && <Button kind="ghost" onClick={() => setMode("cancel")}>Cancel and refund</Button>}
              {t.state === "done" && t.completedAt && now - t.completedAt < 86400 && t.type !== "do" && <Button kind="ghost" onClick={() => setMode("dispute")}>Dispute the answer</Button>}
              <a href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8400"}/v1/receipts/${t.taskId}`} target="_blank" rel="noreferrer" className="inline-flex h-[44px] items-center rounded-full border border-white/30 px-6 font-serif text-[15px] text-white hover:bg-white/10">Public receipt ↗</a>
            </div>
            <p className="mt-4 font-serif text-[13px] text-white/45">Cancelling is possible until someone answers. Disputes on short tasks are open for 24 hours after completion.</p>
          </Panel>
          <Panel title="Money">
            <div className="overflow-x-auto"><table className="w-full min-w-[560px] font-serif text-[14px]">
              <tbody>
                <tr><td className="py-1 text-white/55">Per worker</td><td className="py-1 text-right">{money(t.cost.pricePerWorker)}</td></tr>
                <tr><td className="py-1 text-white/55">Workers</td><td className="py-1 text-right">{t.workers.wanted}</td></tr>
                <tr><td className="py-1 text-white/55">Service fee</td><td className="py-1 text-right">{money(t.cost.fee)}</td></tr>
                <tr className="border-t border-white/10"><td className="py-1 text-white">Paid</td><td className="py-1 text-right text-white">{money(t.cost.total)}</td></tr>
                {t.refund !== undefined && <tr><td className="py-1 text-[#9be36b]">Refund</td><td className="py-1 text-right text-[#9be36b]">{money(t.refund)}</td></tr>}
              </tbody>
            </table></div>
          </Panel>
          {t.receipt && (
            <Panel title="Timeline">
              <ul className="space-y-1.5 font-serif text-[13px] text-white/65">
                {t.receipt.timeline.map((e, i) => (
                  <li key={i}><span className="text-white/40">{new Date(e.at * 1000).toLocaleTimeString()}</span> · {e.to} <span className="text-white/40">· {e.reason}</span></li>
                ))}
              </ul>
            </Panel>
          )}
          <Panel title="For your software">
            <p className="font-serif text-[13px] text-white/55">Task id</p>
            <code className="block break-all font-mono text-[12px] text-white/80">{t.taskId}</code>
            <p className="mt-3 font-serif text-[13px] text-white/55">Buyer token (keeps the right to accept, dispute or cancel)</p>
            <code className="block break-all font-mono text-[12px] text-white/80">{t.buyerToken}</code>
          </Panel>
        </div>
      </div>
    </div>
  );
}
