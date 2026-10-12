"use client";

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { ChevronDown, Grid2X2, Grid3X3, LayoutList, Search, SlidersHorizontal } from "lucide-react";
import { Nav } from "@/components/nav";
import { Footer } from "@/components/footer";
import { GlCanvas, SMOKE } from "@/components/gl";
import { Mark } from "@/components/nav";
import { TaskArt, artFor } from "@/components/board/art";
import { requesterFor } from "@/components/board/requester";
import { API_URL, money } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { TYPES, labelOf } from "@/lib/types";

type Card = { taskId: string; title: string; type: string; category: string | null; categoryLabel: string | null; location: string; difficulty: string; effortMinutes: number; price: number; workers: number; slotsLeft: number; deadline: number; postedAt: number; image?: string | null; proof?: string | null; requester?: string | null };
type Board = { tasks: Card[]; count: number; openValue: number };
type Stats = { open: number; openValue: number; lowestPrice: number; highestPrice: number; paid24h: number; paidTotal: number; done24h: number; doneTotal: number; workersOnline: number; online?: number; workersTotal: number; catalogueSize: number; feeBps: number };
type Cat = Record<string, { label: string; need: string }>;
type Activity = { taskId: string; title: string; type: string; categoryLabel: string | null; location: string; price: number; workers: number; state: string; agreement: number | null; completedAt: number; method: string | null; teamRun?: boolean; requester?: string | null; settlement?: string | null; settlementExplorer?: string | null; paid?: number }[];

const SORTS = ["newest", "price_desc", "price_asc", "ending"] as const;

export default function TaskBoard() {
  const { t } = useLang();
  // A type's name in the chosen language; the English label when there is no translation.
  const typeName = (k: string) => (t(`type.${k}`) === `type.${k}` ? labelOf(k) : t(`type.${k}`));
  const place = (s: string) => (s === "Remote" ? t("board.remote") : s);
  const [board, setBoard] = useState<Board | null>(null);
  const [down, setDown] = useState(false);
  const [stats, setStats] = useState<Stats | null>(null);
  const [cats, setCats] = useState<Cat>({});
  const [activity, setActivity] = useState<Activity>([]);
  const [tab, setTab] = useState<"items" | "completed" | "activity" | "how">("items");
  const [now, setNow] = useState(0);
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<(typeof SORTS)[number]>("newest");
  const [status, setStatus] = useState<"all" | "slots" | "action">("all");
  const [types, setTypes] = useState<Set<string>>(new Set());
  const [cat, setCat] = useState<string>("");
  const [maxPrice, setMaxPrice] = useState<number>(0);
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [density, setDensity] = useState<3 | 4 | 1>(4);
  const [filtersOpen, setFiltersOpen] = useState<boolean | null>(null);

  useEffect(() => {
    // Each part loads on its own and keeps its last good data, so one failed request never blanks the board.
    const get = <T,>(path: string, apply: (d: T) => void) =>
      fetch(`${API_URL}${path}`)
        .then((r) => (r.ok ? (r.json() as Promise<T>) : Promise.reject(new Error(String(r.status)))))
        .then((d) => {
          apply(d);
          setDown(false);
        })
        .catch(() => setDown(true));
    const load = () => {
      get<Board>("/v1/tasks/open?limit=200", (b) => {
        setBoard(b);
        setNow(Math.floor(Date.now() / 1000));
      });
      get<Stats>("/v1/stats", setStats);
      get<{ activity: Activity }>("/v1/activity", (a) => setActivity(a.activity));
    };
    const first = setTimeout(load, 0);
    const id = setInterval(load, 20000);
    fetch(`${API_URL}/v1/catalogue`).then((r) => r.json()).then((c: { categories: Cat }) => setCats(c.categories)).catch(() => {});
    return () => {
      clearTimeout(first);
      clearInterval(id);
    };
  }, []);

  const counts = useMemo(() => {
    const byCat: Record<string, number> = {};
    const byType: Record<string, number> = {};
    for (const t of board?.tasks ?? []) {
      if (t.category) byCat[t.category] = (byCat[t.category] ?? 0) + 1;
      byType[t.type] = (byType[t.type] ?? 0) + 1;
    }
    return { byCat, byType };
  }, [board]);

  const items = useMemo(() => {
    let list = board?.tasks ?? [];
    if (q.trim()) list = list.filter((t) => (t.title + " " + (t.categoryLabel ?? "") + " " + t.location).toLowerCase().includes(q.toLowerCase()));
    if (status === "slots") list = list.filter((t) => t.slotsLeft > 0);
    if (status === "action") list = list.filter((t) => t.type === "do");
    if (types.size) list = list.filter((t) => types.has(t.type));
    if (cat) list = list.filter((t) => t.category === cat);
    if (maxPrice > 0) list = list.filter((t) => t.price <= maxPrice);
    if (remoteOnly) list = list.filter((t) => t.location === "Remote");
    const s = [...list];
    if (sort === "price_desc") s.sort((a, b) => b.price - a.price);
    if (sort === "price_asc") s.sort((a, b) => a.price - b.price);
    if (sort === "ending") s.sort((a, b) => a.deadline - b.deadline);
    if (sort === "newest") s.sort((a, b) => b.postedAt - a.postedAt);
    return s;
  }, [board, q, status, types, cat, maxPrice, remoteOnly, sort]);

  const tr = t;
  const ago = (t: number) => {
    const s = Math.max(0, now - t);
    if (s < 60) return tr("ago.now");
    if (s < 3600) return tr("ago.m", { n: Math.floor(s / 60) });
    if (s < 86400) return tr("ago.h", { n: Math.floor(s / 3600) });
    return tr("ago.d", { n: Math.floor(s / 86400) });
  };

  const statCells: [string, string, string?][] = stats
    ? [
        [t("board.stat.lowest"), money(stats.lowestPrice)],
        [t("board.stat.highest"), money(stats.highestPrice)],
        [t("board.stat.paid24"), money(stats.paid24h), stats.done24h ? t("board.stat.tasks", { n: stats.done24h }) : undefined],
        [t("board.stat.paidTotal"), money(stats.paidTotal), t("board.stat.tasks", { n: stats.doneTotal })],
        [t("board.stat.openNow"), String(stats.open), money(stats.openValue)],
        [t("board.stat.online"), String(stats.workersOnline), t("board.stat.joined", { n: stats.workersTotal })],
      ]
    : [];

  const gridCols = density === 3 ? "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3" : density === 4 ? "grid-cols-2 md:grid-cols-3 xl:grid-cols-4" : "grid-cols-1";

  return (
    <div className="min-h-screen bg-[#080808] text-white">
      <Nav />

      {/* Banner */}
      <div className="relative h-[260px] w-full overflow-hidden sm:h-[380px]">
        <GlCanvas fragment={SMOKE} className="absolute inset-0 h-full w-full" speed={0.6} mouseStrength={0.4} />
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-[#080808]" />
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="flex items-center gap-3 px-5 pt-10 sm:gap-5 sm:pt-0">
            <Mark className="h-11 w-11 shrink-0 sm:h-20 sm:w-20" />
            <div>
              <div className="font-serif text-[38px] font-light leading-none tracking-[-1px] sm:text-[64px] sm:tracking-[-2px]">{t("board.title")}</div>
              <div className="mt-2 font-serif text-[13px] text-white/70 sm:text-[16px]">{t("board.sub")}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Collection header */}
      <div className="mx-auto max-w-[1480px] px-4 sm:px-8">
        <div className="relative z-10 -mt-10 flex items-end justify-between gap-8">
          <div className="flex min-w-0 items-end gap-3 sm:gap-5">
            <div className="flex h-[64px] w-[64px] shrink-0 items-center justify-center rounded-[16px] sm:h-[92px] sm:w-[92px] sm:rounded-[20px] border border-white/15 bg-[#0d0d14] shadow-[0_10px_40px_-10px_rgba(60,100,255,0.5)]">
              <Mark className="h-9 w-9 sm:h-12 sm:w-12" />
            </div>
            <div className="pb-1">
              <div className="flex items-center gap-2">
                <h1 className="font-serif text-[24px] font-light leading-none sm:text-[34px]">{t("board.h1")}</h1>
                <span className="rounded-full bg-[#3b6cff] px-2 py-0.5 font-sans text-[11px] font-semibold text-white">{t("board.verified")}</span>
              </div>
              <div className="mt-3 hidden flex-wrap gap-2 font-mono text-[11px] uppercase tracking-[0.06em] text-white/60 sm:flex">
                {[t("board.badge.us"), "USDG", t("board.badge.kinds", { n: stats?.catalogueSize ?? 112 }), t("board.badge.new"), t("board.badge.fee", { fee: stats ? stats.feeBps / 100 : 20 })].map((b) => (
                  <span key={b} className="rounded-md border border-white/12 bg-white/[0.04] px-2 py-1">{b}</span>
                ))}
              </div>
            </div>
          </div>
          <div className="hidden gap-7 pb-2 pt-12 lg:flex">
            {statCells.map(([k, v, sub]) => (
              <div key={k} className="text-right">
                <div className="whitespace-nowrap font-mono text-[10px] uppercase tracking-[0.08em] text-white/45">{k}</div>
                <div className="mt-1 font-mono text-[18px] text-white">{v}</div>
                {sub && <div className="font-mono text-[11px] text-white/45">{sub}</div>}
              </div>
            ))}
          </div>
        </div>

        {/* Numbers, on small screens */}
        <div className="mt-6 grid grid-cols-3 gap-x-3 gap-y-4 lg:hidden">
          {statCells.map(([k, v]) => (
            <div key={k}>
              <div className="font-mono text-[9px] uppercase tracking-[0.06em] text-white/45">{k}</div>
              <div className="mt-0.5 font-mono text-[16px] text-white">{v}</div>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div className="mt-8 flex gap-6 overflow-x-auto whitespace-nowrap border-b border-white/[0.08] font-serif text-[15px] sm:gap-7">
          {([["items", "board.tab.tasks"], ["completed", "board.tab.completed"], ["activity", "board.tab.activity"], ["how", "board.tab.how"]] as const).map(([k, key]) => (
            <button key={k} onClick={() => setTab(k)} className={`-mb-px border-b-2 pb-3 ${tab === k ? "border-white text-white" : "border-transparent text-white/55 hover:text-white"}`}>
              {t(key)}
            </button>
          ))}
        </div>

        {/* The chosen tab's content fades up as it is switched to. */}
        <motion.div key={tab} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}>
        {tab === "items" && (
          <div className="flex flex-col gap-6 py-6 lg:flex-row">
            {/* Filters: open by default on wide screens, closed on phones until asked for */}
            {filtersOpen !== false && (
              <aside className={`w-full shrink-0 space-y-6 lg:w-[260px] ${filtersOpen === null ? "hidden lg:block" : ""}`}>
                <Section title={t("board.status")}>
                  <div className="flex flex-wrap gap-2">
                    {([["all", "board.all"], ["slots", "board.slots"], ["action", "board.action"]] as const).map(([k, l]) => (
                      <Chip key={k} active={status === k} onClick={() => setStatus(k)}>{t(l)}</Chip>
                    ))}
                  </div>
                </Section>
                <Section title={t("board.type")}>
                  <ul className="space-y-1.5">
                    {TYPES.map((t) => (
                      <li key={t.key}>
                        <label className="flex cursor-pointer items-center justify-between font-serif text-[14px] text-white/75 hover:text-white">
                          <span className="flex items-center gap-2.5">
                            <input type="checkbox" checked={types.has(t.key)} onChange={(e) => { const n = new Set(types); if (e.target.checked) n.add(t.key); else n.delete(t.key); setTypes(n); }} className="accent-[#3b6cff]" />
                            {typeName(t.key)}
                          </span>
                          <span className="font-mono text-[12px] text-white/40">{counts.byType[t.key] ?? 0}</span>
                        </label>
                      </li>
                    ))}
                  </ul>
                </Section>
                <Section title={t("board.price")}>
                  <div className="flex flex-wrap gap-2">
                    {([[0, t("board.any")], [1_000_000, "≤ $1"], [5_000_000, "≤ $5"], [10_000_000, "≤ $10"], [20_000_000, "≤ $20"]] as const).map(([v, l]) => (
                      <Chip key={v} active={maxPrice === v} onClick={() => setMaxPrice(v)}>{l}</Chip>
                    ))}
                  </div>
                </Section>
                <Section title={t("board.where")}>
                  <div className="flex gap-2">
                    <Chip active={!remoteOnly} onClick={() => setRemoteOnly(false)}>{t("board.anywhere")}</Chip>
                    <Chip active={remoteOnly} onClick={() => setRemoteOnly(true)}>{t("board.remoteOnly")}</Chip>
                  </div>
                </Section>
                <Section title={t("board.category")}>
                  <ul className="space-y-1">
                    <li><button onClick={() => setCat("")} className={`flex w-full items-center justify-between rounded-md px-2 py-1.5 font-serif text-[14px] ${!cat ? "bg-white/[0.08] text-white" : "text-white/70 hover:text-white"}`}><span>{t("board.all")}</span><span className="font-mono text-[12px] text-white/40">{board?.count ?? 0}</span></button></li>
                    {Object.entries(cats).map(([k, v]) => (
                      <li key={k}>
                        <button onClick={() => setCat(cat === k ? "" : k)} className={`flex w-full items-center justify-between rounded-md px-2 py-1.5 font-serif text-[14px] ${cat === k ? "bg-white/[0.08] text-white" : "text-white/70 hover:text-white"}`}>
                          <span className="flex items-center gap-2"><span className="inline-block h-2 w-2 rounded-full" style={{ background: artFor(k).accent }} />{v.label}</span>
                          <span className="font-mono text-[12px] text-white/40">{counts.byCat[k] ?? 0}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </Section>
              </aside>
            )}

            {/* Items */}
            <div className="order-first min-w-0 flex-1 lg:order-none">
              <div className="flex flex-wrap items-center gap-2 sm:gap-3">
                <button onClick={() => setFiltersOpen(filtersOpen === null ? !window.matchMedia("(min-width: 1024px)").matches : !filtersOpen)} className="flex h-[42px] items-center gap-2 rounded-full border border-white/15 px-4 font-serif text-[14px] text-white/80 hover:bg-white/[0.06]"><SlidersHorizontal className="h-4 w-4" />{t("board.filters")}</button>
                <label className="order-first flex h-[42px] w-full items-center gap-2 rounded-full border border-white/15 bg-white/[0.03] px-4 sm:order-none sm:w-auto sm:flex-1">
                  <Search className="h-4 w-4 text-white/40" />
                  <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("board.search")} className="w-full bg-transparent font-serif text-[14px] text-white outline-none placeholder:text-white/35" />
                </label>
                <div className="relative">
                  <select value={sort} onChange={(e) => setSort(e.target.value as typeof sort)} className="h-[42px] appearance-none rounded-full border border-white/15 bg-[#0d0d14] pl-4 pr-9 font-serif text-[14px] text-white/85">
                    {SORTS.map((k) => <option key={k} value={k}>{t(`board.sort.${k}`)}</option>)}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/50" />
                </div>
                <div className="ml-auto hidden h-[42px] items-center rounded-full border border-white/15 p-1 sm:flex">
                  {([[4, Grid3X3], [3, Grid2X2], [1, LayoutList]] as const).map(([d, Icon]) => (
                    <button key={d} onClick={() => setDensity(d)} className={`rounded-full p-2 ${density === d ? "bg-white/[0.12] text-white" : "text-white/50 hover:text-white"}`}><Icon className="h-4 w-4" /></button>
                  ))}
                </div>
              </div>

              <div className="mt-4 flex items-center justify-between font-mono text-[12px] uppercase tracking-[0.06em] text-white/45">
                <span>{board && items.length !== board.count ? t("board.countOf", { n: items.length, total: board.count }) : t("board.count", { n: items.length })}</span>
                <span>{t("board.updated")}</span>
              </div>

              {down && board === null && <p className="mt-10 rounded-[14px] border border-amber-300/30 bg-amber-300/5 p-5 font-serif text-[15px] text-amber-100/90">{t("board.down")}</p>}
              {items.length === 0 && !(down && board === null) && <p className="mt-10 font-serif text-[16px] text-white/50">{t("board.empty")}</p>}

              <div className={`mt-4 grid ${gridCols} gap-3 sm:gap-4`}>
                {items.map((t, i) => {
                  const a = artFor(t.category);
                  // New cards rise in with a short cascade; a card that is already on screen glides to its new place when the filter changes.
                  const card = (children: React.ReactNode) => (
                    <motion.div key={t.taskId} layout="position" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ layout: { type: "spring", stiffness: 380, damping: 36, mass: 0.8 }, opacity: { duration: 0.5, delay: Math.min(i, 11) * 0.035 }, y: { duration: 0.6, delay: Math.min(i, 11) * 0.035, ease: [0.22, 1, 0.36, 1] } }} className="min-w-0">
                      {children}
                    </motion.div>
                  );
                  return card(density === 1 ? (
                    <Link href={`/tasks/${t.taskId}`} className="group flex items-center gap-3 rounded-[14px] border border-white/[0.08] bg-white/[0.02] p-3 transition hover:border-white/25 hover:bg-white/[0.05] sm:gap-5">
                      <div className="w-[56px] shrink-0 sm:w-[72px] overflow-hidden rounded-[10px]"><TaskArt category={t.category} image={t.image} seed={t.taskId} requester={t.requester} /></div>
                      <div className="min-w-0 flex-1">
                        <div className="truncate font-serif text-[16px]">{t.title}</div>
                        <div className="mt-1 truncate font-serif text-[13px] text-white/50">{typeName(t.type)} · {t.categoryLabel ?? tr("board.task")} · {place(t.location)} · {tr("board.slotsOf", { left: t.slotsLeft, total: t.workers })}</div>
                      </div>
                      <div className="shrink-0 text-right"><div className="font-mono text-[16px]">{money(t.price)}</div><div className="font-mono text-[11px] text-white/45">{tr("board.about", { n: t.effortMinutes })}</div></div>
                    </Link>
                  ) : (
                    <Link href={`/tasks/${t.taskId}`} className="group relative block overflow-hidden rounded-[16px] border border-white/[0.08] bg-[#0d0d14] transition duration-300 hover:-translate-y-1 hover:border-white/25 hover:shadow-[0_24px_60px_-24px_rgba(60,100,255,0.6)]">
                      <TaskArt category={t.category} image={t.image} seed={t.taskId} requester={t.requester} />
                      <div className="absolute left-3 top-3 rounded-full border border-white/15 bg-black/50 px-2.5 py-1 font-mono text-[11px] text-white/85 backdrop-blur">{typeName(t.type)}</div>
                      <div className="absolute right-3 top-3 rounded-full bg-black/50 px-2.5 py-1 font-mono text-[11px] text-white/85 backdrop-blur">{tr("board.of", { left: t.slotsLeft, total: t.workers })}</div>
                      <div className="p-3 sm:p-4">
                        <div className="line-clamp-2 min-h-[40px] font-serif text-[14px] leading-[1.3] text-white/95 sm:min-h-[44px] sm:text-[15.5px]">{t.title}</div>
                        <div className="mt-2 flex items-center gap-2 font-serif text-[12px] text-white/50">
                          <span className="inline-block h-2 w-2 rounded-full" style={{ background: a.accent }} />
                          <span className="truncate">{t.categoryLabel ?? tr("board.task")} · {place(t.location)}{requesterFor(t.requester) ? ` · ${tr("board.for", { name: requesterFor(t.requester)!.label })}` : ""}</span>
                        </div>
                        <div className="mt-3 flex items-end justify-between">
                          <div>
                            <div className="font-mono text-[11px] uppercase tracking-[0.06em] text-white/45">{tr("board.pays")}</div>
                            <div className="font-mono text-[18px]">{money(t.price)}</div>
                          </div>
                          <div className="hidden text-right font-mono text-[11px] text-white/45 min-[420px]:block">
                            <div>{tr("board.about", { n: t.effortMinutes })}</div>
                            <div>{tr("board.openOf", { left: t.slotsLeft, total: t.workers })}</div>
                          </div>
                        </div>
                      </div>
                      <div className="absolute inset-x-0 bottom-0 translate-y-full bg-[#3b6cff] py-2.5 text-center font-serif text-[14px] font-semibold text-white transition duration-300 group-hover:translate-y-0">{tr("board.view")}</div>
                    </Link>
                  ));
                })}
              </div>
            </div>
          </div>
        )}

        {tab === "completed" && (
          <div className="py-6">
            {activity.filter((a) => a.state === "done").length === 0 && <p className="py-6 font-serif text-[14px] text-white/50">{t("board.noneCompleted")}</p>}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {activity.filter((a) => a.state === "done").map((a) => (
                <div key={a.taskId} className="group overflow-hidden rounded-[16px] border border-white/[0.08] bg-white/[0.025]">
                  <Link href={`/tasks/${a.taskId}`} className="block">
                    <TaskArt requester={a.requester} />
                  </Link>
                  <div className="p-4">
                    <div className="flex items-center justify-between font-mono text-[11px] uppercase tracking-[0.06em] text-white/45">
                      <span>{typeName(a.type)}</span>
                      <span>{now ? ago(a.completedAt) : ""}</span>
                    </div>
                    <Link href={`/tasks/${a.taskId}`} className="mt-1.5 block font-serif text-[16px] leading-[1.3] text-white/95 hover:text-white">{a.title}</Link>
                    <div className="mt-3 flex items-end justify-between">
                      <div>
                        <div className="font-mono text-[11px] uppercase tracking-[0.06em] text-white/40">{t("board.paid")}</div>
                        <div className="font-mono text-[18px] text-[#9be36b]">{money(a.paid ?? 0)}</div>
                      </div>
                      <div className="text-right font-serif text-[12px] text-white/50">{t("board.each", { amount: money(a.price) })}{a.agreement != null ? ` · ${t("board.agreed", { pct: Math.round(a.agreement * 100) })}` : ""}</div>
                    </div>
                    <div className="mt-3 flex items-center justify-between border-t border-white/[0.06] pt-3 font-serif text-[12px]">
                      {a.settlementExplorer ? <a href={a.settlementExplorer} target="_blank" rel="noreferrer" className="text-[#9db4ff] underline">{t("board.onChain")}</a> : <span className="text-white/40">{t("board.batch")}</span>}
                      {a.teamRun && <span className="rounded-full border border-white/15 px-2 py-0.5 text-white/60" title={t("board.teamTitle")}>{t("board.team")}</span>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === "activity" && (
          <div className="overflow-x-auto py-6">
            <table className="w-full min-w-[720px] font-serif text-[14px]">
              <thead className="text-left font-mono text-[11px] uppercase tracking-[0.06em] text-white/45">
                <tr>{(["task", "type", "where", "paidPer", "decidedBy", "result", "when"] as const).map((c) => <th key={c} className="pb-3 font-normal">{t(`board.col.${c}`)}</th>)}</tr>
              </thead>
              <tbody>
                {activity.length === 0 && <tr><td colSpan={7} className="py-6 text-white/50">{t("board.noneActivity")}</td></tr>}
                {activity.map((a) => (
                  <tr key={a.taskId} className="border-t border-white/[0.06]">
                    <td className="py-3 pr-4 text-white/90">{a.title}</td>
                    <td className="py-3 text-white/60">{typeName(a.type)}</td>
                    <td className="py-3 text-white/60">{place(a.location)}</td>
                    <td className="py-3 font-mono">{money(a.price)}</td>
                    <td className="py-3 text-white/60">{a.method ?? "–"}</td>
                    <td className="py-3">{a.state === "done" ? <span className="text-[#9be36b]">{t("board.accepted")}{a.agreement != null ? ` · ${t("board.agreed", { pct: Math.round(a.agreement * 100) })}` : ""}</span> : <span className="text-white/45">{t("board.expired")}</span>}</td>
                    <td className="py-3 font-mono text-[12px] text-white/45">{now ? ago(a.completedAt) : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {tab === "how" && (
          <div className="grid grid-cols-1 gap-4 py-8 md:grid-cols-3 md:gap-5">
            {[1, 2, 3].map((n) => [t(`board.how.${n}.h`), t(`board.how.${n}.b`)]).map(([h, b]) => (
              <div key={h} className="rounded-[18px] border border-white/[0.08] bg-white/[0.025] p-7">
                <div className="font-serif text-[22px] font-light">{h}</div>
                <p className="mt-3 font-serif text-[15px] font-light leading-[1.45] text-white/70">{b}</p>
              </div>
            ))}
          </div>
        )}
        </motion.div>
      </div>

      {/* Sticky action bar */}
      <div className="sticky bottom-0 z-30 border-t border-white/[0.08] bg-[#0a0a0f]/85 backdrop-blur-xl">
        <div className="mx-auto flex h-[60px] max-w-[1480px] items-center justify-between gap-3 px-4 sm:h-[64px] sm:px-8">
          <div className="flex min-w-0 items-center gap-3 whitespace-nowrap font-mono text-[11px] text-white/60 sm:gap-6 sm:text-[12px]">
            <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-[#9be36b]" />{t("board.live")}</span>
            <span>{t("board.openN", { n: board?.count ?? 0 })}</span>
            <span className="hidden min-[420px]:inline">{t("board.toEarn", { amount: money(board?.openValue ?? 0) })}</span>
            {stats && <span className="hidden sm:inline">{t("board.onlineN", { n: stats.online ?? stats.workersOnline })}</span>}
          </div>
          <div className="flex shrink-0 items-center gap-3">
            <Link href="/client/docs" className="hidden font-serif text-[14px] text-white/60 hover:text-white md:inline">{t("board.post")}</Link>
            <Link href="/earn" className="inline-flex h-[40px] items-center whitespace-nowrap rounded-full bg-[#3b6cff] px-5 font-serif text-[14px] font-semibold text-white hover:bg-[#5b86ff] sm:px-6 sm:text-[15px]">{t("board.earn")}</Link>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border-b border-white/[0.08] pb-5">
      <div className="mb-3 font-serif text-[15px] text-white/90">{title}</div>
      {children}
    </div>
  );
}

function Chip({ children, active, onClick }: { children: React.ReactNode; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} className={`rounded-full border px-3 py-1.5 font-serif text-[13px] transition ${active ? "border-white bg-white text-[#0a0a0f]" : "border-white/15 text-white/70 hover:border-white/40 hover:text-white"}`}>
      {children}
    </button>
  );
}
