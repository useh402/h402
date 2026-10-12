"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Nav } from "@/components/nav";
import { Item, Stagger } from "@/components/motion";
import { API_URL, money } from "@/lib/api";
import { short } from "@/lib/wallet";

type Rewards = {
  rewardsPaid: number; rewardsPaidToWorkers: number; rewardsPaidTeamRuns: number; payments: number; peoplePaid: number;
  tasks: { total: number; open: number; completed: number; expired: number };
  openRewards: number; poolAvailable: number; feesEarned: number; feeBps: number; asset: string; network: string;
  contract: { address: string; balance: number | null; locked: number | null; explorer: string } | null;
  recent: { amount: number; taskId: string | null; title: string; wallet: string; team: boolean; at: number; transaction: string | null; explorer: string | null }[];
};

const ago = (t: number, now: number) => {
  const s = Math.max(0, now - t);
  return s < 60 ? "just now" : s < 3600 ? `${Math.floor(s / 60)} min ago` : s < 86400 ? `${Math.floor(s / 3600)} h ago` : `${Math.floor(s / 86400)} d ago`;
};

function Stat({ label, value, note, big = false }: { label: string; value: string; note?: string; big?: boolean }) {
  return (
    <div className="rounded-[18px] border border-white/[0.08] bg-[#0b0b0e] p-5 sm:p-6">
      <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-white/45">{label}</div>
      <div className={`mt-2 font-mono ${big ? "text-[38px] text-[#9be36b] sm:text-[44px]" : "text-[28px] text-white sm:text-[30px]"} leading-none`}>{value}</div>
      {note && <div className="mt-3 font-serif text-[13px] leading-[1.4] text-white/50">{note}</div>}
    </div>
  );
}

export default function RewardsPage() {
  const [r, setR] = useState<Rewards | null>(null);
  const [now, setNow] = useState(0);

  useEffect(() => {
    const load = () =>
      fetch(`${API_URL}/v1/rewards`)
        .then((x) => (x.ok ? x.json() : Promise.reject(new Error(String(x.status)))))
        .then((d: Rewards) => {
          setR(d);
          setNow(Math.floor(Date.now() / 1000));
        })
        .catch(() => {});
    const first = setTimeout(load, 0);
    const id = setInterval(load, 30000);
    return () => {
      clearTimeout(first);
      clearInterval(id);
    };
  }, []);

  const dash = "…";
  return (
    <div className="min-h-screen bg-[#080808] text-white">
      <Nav />
      <main className="mx-auto max-w-[1400px] px-4 pb-24 pt-[100px] sm:px-8 sm:pt-[130px]">
        <div className="flex items-center gap-2.5 font-serif text-[14px] text-white/70"><span className="h-[5px] w-[5px] bg-[#3b6cff]" />Rewards</div>
        <h1 className="mt-4 font-serif text-[36px] font-light leading-[1.06] tracking-[-1px] sm:text-[60px] sm:leading-[1.03] sm:tracking-[-2px]">Every reward, <em className="italic">paid on chain</em>.</h1>
        <p className="mt-5 max-w-[760px] font-serif text-[17px] font-light leading-[1.45] text-white/70">
          Rewards are held by a contract on Robinhood Chain and paid in {r?.asset ?? "USDG"} the moment a task is accepted. Every payment below links to its transaction, so anyone can check it.
        </p>

        <Stagger className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          <Item><Stat big label="Total rewards paid" value={r ? money(r.rewardsPaid) : dash} note={r ? `${r.payments} payments to ${r.peoplePaid} wallets` : undefined} /></Item>
          <Item><Stat label="Live pool" value={r ? money(r.openRewards) : dash} note={r ? `Rewards on offer across ${r.tasks.open} open tasks` : undefined} /></Item>
          <Item><Stat label="Tasks, all time" value={r ? String(r.tasks.total) : dash} note={r ? `${r.tasks.completed} completed · ${r.tasks.open} open · ${r.tasks.expired} expired and refunded` : undefined} /></Item>
        </Stagger>

        {r && (
          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="rounded-[18px] border border-white/[0.08] bg-[#0b0b0e] p-6 lg:col-span-2">
              <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-white/45">Where the paid rewards went</div>
              <div className="mt-4 space-y-3 font-serif text-[15px]">
                <div className="flex items-center justify-between"><span className="text-white/80">Paid to workers</span><span className="font-mono">{money(r.rewardsPaidToWorkers)}</span></div>
                <div className="flex items-center justify-between gap-4"><span className="text-white/80">Paid in H402 team test runs <span className="text-white/45">(our own wallets, while testing payments)</span></span><span className="font-mono text-white/70">{money(r.rewardsPaidTeamRuns)}</span></div>
                <div className="flex items-center justify-between border-t border-white/[0.08] pt-3"><span className="text-white/80">Service fee earned ({r.feeBps / 100}% on top of each reward)</span><span className="font-mono text-white/70">{money(r.feesEarned)}</span></div>
              </div>
            </div>
            <div className="rounded-[18px] border border-white/[0.08] bg-[#0b0b0e] p-6">
              <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-white/45">The contract</div>
              {r.contract ? (
                <>
                  <a href={r.contract.explorer} target="_blank" rel="noreferrer" className="mt-3 block break-all font-mono text-[13px] text-[#9db4ff] underline">{r.contract.address}</a>
                  <div className="mt-3 font-serif text-[14px] text-white/60">Robinhood Chain, {r.asset}.</div>
                </>
              ) : (
                <div className="mt-3 font-serif text-[14px] text-white/50">Not connected.</div>
              )}
              <Link href="/tasks" className="mt-4 inline-block font-serif text-[14px] text-white underline">See open tasks</Link>
            </div>
          </div>
        )}

        <h2 className="mt-14 font-serif text-[28px] font-light">Latest payments</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[640px] font-serif text-[14px]">
            <thead className="text-left font-mono text-[11px] uppercase tracking-[0.06em] text-white/45">
              <tr><th className="pb-3 font-normal">Task</th><th className="pb-3 font-normal">Paid to</th><th className="pb-3 font-normal">Reward</th><th className="pb-3 font-normal">When</th><th className="pb-3 font-normal">Transaction</th></tr>
            </thead>
            <tbody>
              {r && r.recent.length === 0 && <tr><td colSpan={5} className="py-6 text-white/50">No payments yet. The first accepted task will show here.</td></tr>}
              {r?.recent.map((p, i) => (
                <tr key={i} className="border-t border-white/[0.06]">
                  <td className="py-3 pr-4">{p.taskId ? <Link href={`/tasks/${p.taskId}`} className="text-white/90 hover:text-white">{p.title}</Link> : <span className="text-white/70">{p.title}</span>}</td>
                  <td className="py-3 font-mono text-[13px] text-white/70">{short(p.wallet)}{p.team && <span className="ml-2 rounded-full border border-white/15 px-2 py-0.5 font-serif text-[11px] text-white/55">H402 team</span>}</td>
                  <td className="py-3 font-mono text-[#9be36b]">{money(p.amount)}</td>
                  <td className="py-3 font-mono text-[12px] text-white/45">{now ? ago(p.at, now) : ""}</td>
                  <td className="py-3">{p.explorer ? <a href={p.explorer} target="_blank" rel="noreferrer" className="font-mono text-[13px] text-[#9db4ff] underline">{p.transaction?.slice(0, 12)}… ↗</a> : <span className="text-white/40">in a batch</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
