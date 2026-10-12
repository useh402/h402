"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Panel } from "@/components/earn/shell";
import { StateBadge } from "@/components/client/shell";
import { money } from "@/lib/api";
import { capi, type ClientTask } from "@/lib/client";
import { labelOf } from "@/lib/types";

type Listing = { tasks: ClientTask[]; counts: Record<string, number>; spent: number; refundsDue: number };

export default function ClientTasks() {
  const [data, setData] = useState<Listing | null>(null);
  const [filter, setFilter] = useState<string>("");
  useEffect(() => {
    const load = () => capi<Listing>(`/v1/clients/tasks${filter ? `?state=${filter}` : ""}`).then(setData).catch(() => {});
    const first = setTimeout(load, 0);
    const id = setInterval(load, 5000);
    return () => {
      clearTimeout(first);
      clearInterval(id);
    };
  }, [filter]);
  if (!data) return null;
  const c = data.counts;
  const stats: [string, string | number, string][] = [
    ["Open", c.open + c.claimed + c.submitted, "waiting or in progress"],
    ["Done", c.done, "answered and paid"],
    ["Refunded", c.expired + c.rejected + c.cancelled, "expired, refused or cancelled"],
    ["Spent", money(data.spent), `refunds due ${money(data.refundsDue)}`],
  ];
  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="font-serif text-[40px] font-light leading-[1.05]">My tasks</h1>
          <p className="mt-2 font-serif text-[15px] text-white/55">Refreshes every few seconds. Open a task to see the answer, the proof and the receipt.</p>
        </div>
        <Link href="/client/docs" className="inline-flex h-[44px] items-center rounded-full border border-white/30 px-6 font-serif text-[15px] text-white hover:bg-white/10">How your software posts tasks</Link>
      </div>
      <div className="grid grid-cols-4 gap-4">
        {stats.map(([k, v, hint]) => (
          <div key={k} className="rounded-[16px] border border-white/[0.08] bg-white/[0.025] p-6">
            <div className="font-serif text-[13px] text-white/50">{k}</div>
            <div className="mt-2 font-serif text-[36px] font-light leading-none">{v}</div>
            <div className="mt-2 font-serif text-[12px] text-white/40">{hint}</div>
          </div>
        ))}
      </div>
      <Panel
        title="Tasks"
        aside={
          <select value={filter} onChange={(e) => setFilter(e.target.value)} className="rounded-md border border-white/15 bg-black/40 px-3 py-1.5 font-serif text-[13px] text-white">
            <option value="">All states</option>
            {["open", "claimed", "submitted", "disputed", "done", "expired", "rejected", "cancelled"].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        }
      >
        {data.tasks.length === 0 ? (
          <p className="font-serif text-[15px] font-light text-white/50">No tasks from this wallet yet. Tasks are posted by software through the API; see Connect your software.</p>
        ) : (
          <div className="overflow-x-auto"><table className="w-full min-w-[560px] font-serif text-[14px]">
            <thead className="text-left text-white/45">
              <tr><th className="pb-2 font-normal">Task</th><th className="pb-2 font-normal">Type</th><th className="pb-2 font-normal">Where</th><th className="pb-2 font-normal">Price</th><th className="pb-2 font-normal">State</th><th className="pb-2 font-normal">Posted</th></tr>
            </thead>
            <tbody>
              {data.tasks.map((t) => (
                <tr key={t.taskId} className="border-t border-white/[0.06]">
                  <td className="py-2.5 pr-4"><Link href={`/client/tasks/${t.taskId}`} className="text-white hover:underline">{t.title || t.taskId}</Link></td>
                  <td className="py-2.5 text-white/70">{labelOf(t.type)}</td>
                  <td className="py-2.5 text-white/70">{t.location}</td>
                  <td className="py-2.5">{money(t.cost.total)}</td>
                  <td className="py-2.5"><StateBadge state={t.state} /></td>
                  <td className="py-2.5 text-white/50">{new Date(t.createdAt * 1000).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </Panel>
    </div>
  );
}
