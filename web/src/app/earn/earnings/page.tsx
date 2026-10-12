"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Panel } from "@/components/earn/shell";
import { api, money } from "@/lib/api";
import { ExportWallet } from "@/components/sign-in";
import { Withdraw } from "@/components/earn/withdraw";

type Earnings = { rail: string; wallet: string; pending: number; today: number; thisWeek: number; allTime: number; paid: number; answered: number; agreed: number; reputation: number; tier: string; gold: { total: number; correct: number }; payouts: { amount: number; status: string; taskId: string; transaction: string | null; at: number; explorer: string | null }[]; refused?: { taskId: string; title: string; amount: number; at: number; reason: string }[] };

export default function EarningsPage() {
  const [e, setE] = useState<Earnings | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string; url?: string } | null>(null);
  useEffect(() => {
    const load = () => api<Earnings>("/v1/workers/earnings").then(setE).catch(() => {});
    load();
    const id = setInterval(load, 10_000);
    return () => clearInterval(id);
  }, []);
  if (!e) return null;
  const claimable = e.payouts.filter((p) => p.status === "claimable");
  const claimableTotal = claimable.reduce((a, p) => a + p.amount, 0);
  const claim = async (taskId: string) => {
    setBusy(taskId);
    setMsg(null);
    try {
      const r = await api<{ amount: number; transaction: string; explorer: string }>(`/v1/tasks/${taskId}/claim-reward`, { body: {} });
      setMsg({ ok: true, text: `${money(r.amount)} sent to your wallet.`, url: r.explorer });
      api<Earnings>("/v1/workers/earnings").then(setE).catch(() => {});
    } catch (err) {
      setMsg({ ok: false, text: err instanceof Error ? err.message : String(err) });
    } finally {
      setBusy(null);
    }
  };
  const stats = [
    ["Ready to claim", money(claimableTotal), claimable.length ? `${claimable.length} reward${claimable.length === 1 ? "" : "s"} waiting` : "accepted work appears here"],
    ["Today", money(e.today), "accepted work"],
    ["This week", money(e.thisWeek), ""],
    ["Paid out", money(e.paid), "all time"],
  ];
  return (
    <div className="space-y-8">
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        {stats.map(([k, v, hint]) => (
          <div key={k} className="rounded-[16px] border border-white/[0.08] bg-white/[0.025] p-6">
            <div className="font-serif text-[13px] text-white/50">{k}</div>
            <div className="mt-2 font-serif text-[30px] font-light leading-none sm:text-[40px]">{v}</div>
            {hint && <div className="mt-2 font-serif text-[12px] text-white/40">{hint}</div>}
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between rounded-[16px] border border-white/[0.08] bg-white/[0.025] px-6 py-4">
        <div className="font-serif text-[14px] text-white/60">
          Rewards are paid to <span className="font-mono text-[13px] text-white/90">{e.wallet}</span>
          <button onClick={() => navigator.clipboard?.writeText(e.wallet)} className="ml-3 text-white/55 underline hover:text-white">Copy</button>
        </div>
        <ExportWallet />
      </div>
      {claimable.length > 0 && (
        <div className="rounded-[16px] border border-[#9be36b]/30 bg-[#9be36b]/5 p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <h2 className="font-serif text-[20px] font-light">Rewards ready to claim</h2>
            <span className="font-mono text-[16px] text-[#9be36b]">{money(claimableTotal)}</span>
          </div>
          <p className="mt-1 font-serif text-[14px] font-light text-white/55">Each claim sends the reward from the platform wallet to yours, on chain, straight away.</p>
          <ul className="mt-4 space-y-2">
            {claimable.map((p) => (
              <li key={p.taskId + String(p.at)} className="flex flex-wrap items-center justify-between gap-3 rounded-[12px] border border-white/[0.08] bg-black/20 px-4 py-3">
                <span className="font-serif text-[14px] text-white/80">Task <span className="font-mono text-[12px]">{p.taskId}</span></span>
                <span className="flex items-center gap-3">
                  <span className="font-mono text-[15px] text-[#9be36b]">{money(p.amount)}</span>
                  <button onClick={() => claim(p.taskId)} disabled={busy !== null} className="h-[36px] rounded-full bg-[#9be36b] px-4 font-serif text-[14px] font-semibold text-[#0a0a0f] hover:bg-[#b4f08a] disabled:opacity-60">
                    {busy === p.taskId ? "Sending…" : "Claim"}
                  </button>
                </span>
              </li>
            ))}
          </ul>
          {msg && (
            <p className={`mt-3 font-serif text-[14px] ${msg.ok ? "text-[#9be36b]" : "text-red-300"}`}>
              {msg.text}
              {msg.url && <a href={msg.url} target="_blank" rel="noreferrer" className="ml-2 text-[#9db4ff] underline">view transaction ↗</a>}
            </p>
          )}
        </div>
      )}
      <Withdraw wallet={e.wallet} rail={e.rail} />
      <Panel title="Payouts" aside={<span className="font-serif text-[13px] text-white/50">{e.tier} tier · {e.agreed} of {e.answered} tasks accepted · reputation {e.reputation.toFixed(2)} · checks {e.gold.correct}/{e.gold.total}</span>}>
        {e.payouts.length === 0 ? (
          <p className="font-serif text-[15px] font-light text-white/50">No payouts yet. Accepted work accumulates as pending and goes out in one transfer per batch.</p>
        ) : (
          <div className="overflow-x-auto"><table className="w-full min-w-[560px] font-serif text-[14px]">
            <thead className="text-left text-white/45">
              <tr>
                <th className="pb-2 font-normal">When</th>
                <th className="pb-2 font-normal">Task</th>
                <th className="pb-2 font-normal">Amount</th>
                <th className="pb-2 font-normal">Status</th>
                <th className="pb-2 font-normal">Transaction</th>
              </tr>
            </thead>
            <tbody>
              {e.payouts.map((p, i) => (
                <tr key={i} className="border-t border-white/[0.06]">
                  <td className="py-2 text-white/70">{new Date(p.at * 1000).toLocaleString()}</td>
                  <td className="py-2 font-mono text-[12px] text-white/60">{p.taskId}</td>
                  <td className="py-2">{money(p.amount)}</td>
                  <td className="py-2 capitalize text-white/70">{p.status}</td>
                  <td className="py-2">{p.explorer ? <a href={p.explorer} target="_blank" rel="noreferrer" className="text-[#9db4ff] underline">{p.transaction?.slice(0, 14)}…</a> : <span className="text-white/40">{p.transaction ? p.transaction.slice(0, 14) + "…" : "—"}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </Panel>
      {(e.refused?.length ?? 0) > 0 && (
        <Panel title="Not paid" aside={<span className="font-serif text-[13px] text-white/50">answers the review found wrong</span>}>
          <ul className="space-y-3">
            {e.refused!.map((r) => (
              <li key={`${r.taskId}-${r.at}`} className="flex flex-col gap-1 rounded-[12px] border border-white/[0.08] bg-white/[0.02] p-4 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
                <div className="min-w-0">
                  <Link href={`/tasks/${r.taskId}`} className="font-serif text-[15px] text-white/90 underline decoration-white/25 underline-offset-4 hover:decoration-white">{r.title}</Link>
                  <div className="mt-1 font-serif text-[13px] leading-[1.45] text-white/55">{r.reason}</div>
                  <div className="mt-1 font-serif text-[12px] text-white/40">{new Date(r.at * 1000).toLocaleString()}</div>
                </div>
                <div className="shrink-0 font-mono text-[14px] text-white/45 line-through">{money(r.amount)}</div>
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}
