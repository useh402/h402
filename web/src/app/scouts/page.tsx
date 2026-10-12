"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Nav } from "@/components/nav";
import { Footer } from "@/components/footer";
import { RequesterMark, requesterFor } from "@/components/board/requester";
import { useIsAdmin } from "@/lib/admin";
import { API_URL, money } from "@/lib/api";
import { labelOf } from "@/lib/types";

type Scout = { requester: string; label: string; model: string; lastRunAt: number | null; lastOk: boolean | null; lastError: string | null; proposed: number; posted: number; waiting: number; rejected: number; inputTokens: number; outputTokens: number };
type Proposal = { id: string; requester: string; title: string; type: string | null; category: string | null; location: string | null; price: number; why: string; status: string; reason: string | null; taskId: string | null; createdAt: number };
type View = { enabled: boolean; autoPost: boolean; intervalSeconds: number; callsToday: number; dailyCalls: number; scouts: Scout[]; proposals: Proposal[] };

const KEY = "humanapi.operator.key";

export default function ScoutsPage() {
  const [v, setV] = useState<View | null>(null);
  const [now, setNow] = useState(0);
  const [filter, setFilter] = useState<"all" | "review" | "posted" | "rejected">("all");
  const [who, setWho] = useState("");
  const [opKey, setOpKey] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  // The operator controls are shown only while the admin wallet is signed in. Everyone else sees the proposals alone.
  const admin = useIsAdmin();

  const load = () =>
    fetch(`${API_URL}/v1/scouts`)
      .then((r) => r.json())
      .then((d: View) => {
        setV(d);
        setNow(Math.floor(Date.now() / 1000));
      })
      .catch(() => {});

  useEffect(() => {
    const first = setTimeout(() => {
      load();
      try {
        setOpKey(localStorage.getItem(KEY) ?? "");
      } catch {}
    }, 0);
    const id = setInterval(load, 8000);
    return () => {
      clearTimeout(first);
      clearInterval(id);
    };
  }, []);

  const operator = async (path: string, body: Record<string, unknown>) => {
    setMsg(null);
    const r = await fetch(`${API_URL}${path}`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${opKey}` }, body: JSON.stringify(body) });
    const d = await r.json().catch(() => ({}));
    setMsg(r.ok ? "Done." : d.message ?? "Not allowed.");
    load();
  };

  const ago = (t: number | null) => {
    if (!t || !now) return "never";
    const s = Math.max(0, now - t);
    return s < 60 ? "just now" : s < 3600 ? `${Math.floor(s / 60)} min ago` : s < 86400 ? `${Math.floor(s / 3600)} h ago` : `${Math.floor(s / 86400)} d ago`;
  };

  const list = (v?.proposals ?? []).filter((p) => (filter === "all" || p.status === filter) && (!who || p.requester === who));
  const tone: Record<string, string> = { review: "border-amber-300/40 text-amber-200", posted: "border-[#9be36b]/40 text-[#9be36b]", rejected: "border-white/20 text-white/45" };
  const word: Record<string, string> = { review: "Waiting for review", posted: "On the board", rejected: "Not accepted" };

  return (
    <div className="min-h-screen bg-[#080808] text-white">
      <Nav />
      <main className="mx-auto max-w-[1400px] px-4 pb-24 pt-[100px] sm:px-8 sm:pt-[130px]">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between lg:gap-8">
          <div>
            <div className="flex items-center gap-2.5 font-serif text-[14px] text-white/70"><span className="h-[5px] w-[5px] bg-[#3b6cff]" />Where tasks come from</div>
            <h1 className="mt-4 font-serif text-[36px] font-light leading-[1.06] tracking-[-1px] sm:text-[60px] sm:leading-[1.03] sm:tracking-[-2px]">Five assistants, <em className="italic">looking for work</em> only people can do.</h1>
            <p className="mt-5 max-w-[720px] font-serif text-[17px] font-light leading-[1.45] text-white/70">
              Each assistant proposes tasks it cannot do itself: a call to make, a place to look at, a page it is not allowed to open, a judgement only a person can give. Every proposal is checked, priced by a fixed formula and reviewed before it reaches the board.
            </p>
          </div>
          <div className="shrink-0 font-mono text-[12px] text-white/50 lg:text-right">
            <div className="flex items-center gap-2 lg:justify-end"><span className={`h-2 w-2 rounded-full ${v?.enabled ? "bg-[#9be36b]" : "bg-white/30"}`} />{v?.enabled ? "Searching" : "Paused"}</div>
            {v && <div className="mt-1">every {Math.round(v.intervalSeconds / 60)} min · {v.callsToday} of {v.dailyCalls} searches today</div>}
            {v && <div className="mt-1">{v.autoPost ? "accepted proposals post automatically" : "an operator approves each task"}</div>}
          </div>
        </div>

        <div className="mt-10 grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 xl:grid-cols-5">
          {v?.scouts.map((s) => (
            <button key={s.requester} onClick={() => setWho(who === s.requester ? "" : s.requester)} className={`rounded-[18px] border bg-[#0b0b0e] p-5 text-left transition ${who === s.requester ? "border-white/50" : "border-white/[0.08] hover:border-white/25"}`}>
              <div className="flex items-center justify-between">
                <RequesterMark requester={s.requester} size={40} />
                <span className={`h-2 w-2 rounded-full ${s.lastOk === false ? "bg-red-400" : s.lastRunAt ? "bg-[#9be36b]" : "bg-white/25"}`} />
              </div>
              <div className="mt-4 font-sans text-[17px] font-semibold">{s.label}</div>
              <div className="truncate font-mono text-[11px] text-white/40">{s.model}</div>
              <div className="mt-4 grid grid-cols-3 gap-2 font-mono text-[11px] text-white/45">
                <div><div className="text-[18px] text-white">{s.posted}</div>on board</div>
                <div><div className="text-[18px] text-white">{s.waiting}</div>waiting</div>
                <div><div className="text-[18px] text-white">{s.rejected}</div>refused</div>
              </div>
              <div className="mt-3 font-serif text-[12px] text-white/45">Last search {ago(s.lastRunAt)}</div>
              {s.lastError && <div className="mt-1 truncate font-serif text-[12px] text-red-300/80">{s.lastError}</div>}
            </button>
          ))}
        </div>

        <div className="mt-10 flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.08] pb-3">
          <div className="flex flex-wrap gap-2">
            {(["all", "review", "posted", "rejected"] as const).map((k) => (
              <button key={k} onClick={() => setFilter(k)} className={`rounded-full border px-4 py-1.5 font-serif text-[14px] ${filter === k ? "border-white bg-white text-[#0a0a0f]" : "border-white/15 text-white/70 hover:border-white/40"}`}>{k === "all" ? "All proposals" : word[k]}</button>
            ))}
          </div>
          <span className="font-mono text-[12px] uppercase tracking-[0.06em] text-white/45">{list.length} proposals{who ? ` from ${requesterFor(who)?.label}` : ""}</span>
        </div>

        {list.length === 0 && <p className="mt-8 font-serif text-[16px] text-white/50">No proposals yet. They appear here as soon as the assistants run their next search.</p>}

        <ul className="mt-2">
          {list.map((p) => (
            <li key={p.id} className="flex items-start gap-5 border-b border-white/[0.06] py-4">
              <div className="mt-1 shrink-0"><RequesterMark requester={p.requester} size={28} /></div>
              <div className="min-w-0 flex-1">
                <div className="font-serif text-[17px] text-white/95">{p.title || "Untitled proposal"}</div>
                <div className="mt-1 font-serif text-[13px] text-white/50">{requesterFor(p.requester)?.label} · {p.type ? labelOf(p.type) : "unknown type"} · {p.location ?? "Remote"} · {ago(p.createdAt)}</div>
                {p.why && <div className="mt-1.5 font-serif text-[14px] font-light text-white/65">Why a person: {p.why}</div>}
                {p.reason && <div className="mt-1.5 font-serif text-[13px] text-white/45">Not accepted: {p.reason}</div>}
              </div>
              <div className="shrink-0 text-right">
                <div className="font-mono text-[18px]">{p.price ? money(p.price) : "–"}</div>
                <span className={`mt-1 inline-block rounded-full border px-2.5 py-0.5 font-serif text-[12px] ${tone[p.status] ?? ""}`}>{word[p.status] ?? p.status}</span>
                {p.taskId && <Link href={`/tasks/${p.taskId}`} className="mt-1 block font-serif text-[13px] text-[#9db4ff] underline">Open the task</Link>}
                {admin && p.status === "review" && opKey && (
                  <div className="mt-2 flex justify-end gap-2">
                    <button onClick={() => operator(`/v1/admin/scouts/proposals/${p.id}`, { decision: "post" })} className="rounded-full bg-white px-3 py-1 font-serif text-[13px] font-semibold text-[#0a0a0f]">Post</button>
                    <button onClick={() => operator(`/v1/admin/scouts/proposals/${p.id}`, { decision: "reject" })} className="rounded-full border border-white/25 px-3 py-1 font-serif text-[13px] text-white/75">Refuse</button>
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>

        {admin && (
        <div className="mt-12 rounded-[16px] border border-white/[0.08] bg-white/[0.02] p-5">
          <div className="font-serif text-[15px] text-white/80">Operator</div>
          <div className="mt-2 flex items-center gap-3">
            <input type="password" value={opKey} onChange={(e) => { setOpKey(e.target.value); try { localStorage.setItem(KEY, e.target.value); } catch {} }} placeholder="Operator key" className="w-[280px] rounded-md border border-white/15 bg-black/40 px-3 py-2 font-mono text-[13px] text-white outline-none" />
            <button onClick={() => operator("/v1/admin/scouts/run", {})} disabled={!opKey} className="rounded-full border border-white/25 px-4 py-2 font-serif text-[14px] text-white/85 disabled:opacity-40">Search now</button>
            {msg && <span className="font-serif text-[14px] text-white/60">{msg}</span>}
          </div>
          <p className="mt-2 font-serif text-[12px] text-white/40">With the key, Post and Refuse appear on proposals waiting for review. The key stays in this browser.</p>
        </div>
        )}
      </main>
      <Footer />
    </div>
  );
}
