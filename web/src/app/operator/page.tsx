"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Nav } from "@/components/nav";
import { API_URL, money } from "@/lib/api";
import { labelOf } from "@/lib/types";

const KEY = "humanapi.operator.key";
type Dispute = { disputeId: string; taskId: string; reason: string; createdAt: number; task: { title: string; type: string; price: number; state: string } };
type Photo = { photoId: string; url: string | null; expired?: boolean; distanceM?: number | null; accuracyM?: number | null; takenAt?: number };
type Response = {
  taskId: string; title: string; type: string; category: string | null; categoryLabel: string | null; location: string; price: number; state: string; proofKind: string | null; awaitingOperator: boolean;
  instructions: string; write: string | null; acceptance: string; worker: { id: string; wallet: string; reputation: number | null; team: boolean }; answerId: string; submittedAt: number; seconds: number | null;
  value: unknown; text: string | null; screenshot: string | null; photos: Photo[]; code: string | null; note: string; confidence: number | null; review: { verdict: string; reason: string; model?: string } | null;
  decision: "waiting" | "disputed" | "approved" | "not_paid" | "refused" | "open"; paid: boolean; dispute: { disputeId: string; reason: string } | null;
};
type Filter = "waiting" | "approved" | "refused" | "all";
type Review = { taskId: string; title: string; type: string; price: number; moderationReason: string | null; payload: Record<string, unknown> };
type Report = { reportId: string; taskId: string; workerId: string; reason: string; createdAt: number };
type Proposal = { id: string; requester: string; title: string; type: string; location: string | null; price: number; why: string; status: string; reason: string | null };
type Escrow = { contract: string; operator: string; balance: number; allocated: number; feesAccrued: number; operatorGasWei: number; tasks: { pending: number; open: number; closed: number } };
type House = { enabled: boolean; houseBalance: number; openHouseTasks: number; spentToday: number; dailyBudget: number };

export default function OperatorPage() {
  const [key, setKey] = useState("");
  const [tab, setTab] = useState<"responses" | "disputes" | "proposals" | "review" | "reports" | "money">("responses");
  const [filter, setFilter] = useState<Filter>("waiting");
  const [responses, setResponses] = useState<Response[]>([]);
  const [waiting, setWaiting] = useState(0);
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [review, setReview] = useState<Review[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [escrow, setEscrow] = useState<Escrow | null>(null);
  const [house, setHouse] = useState<House | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const [denied, setDenied] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => {
      try {
        setKey(localStorage.getItem(KEY) ?? "");
      } catch {}
    }, 0);
    return () => clearTimeout(t);
  }, []);

  const call = useCallback(
    async <T,>(path: string, body?: unknown): Promise<T> => {
      const r = await fetch(`${API_URL}${path}`, { method: body === undefined ? "GET" : "POST", headers: { Authorization: `Bearer ${key}`, "content-type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
      if (r.status === 401 || r.status === 403) {
        setDenied(true);
        throw new Error("That operator key is not accepted.");
      }
      const j = await r.json();
      if (!r.ok) throw new Error(j.message || j.error || `request failed (${r.status})`);
      return j as T;
    },
    [key],
  );

  const load = useCallback(() => {
    if (!key) return;
    setDenied(false);
    call<{ responses: Response[]; waiting: number | null }>(`/v1/admin/responses?status=${filter}&limit=150`)
      .then((d) => {
        setResponses(d.responses);
        if (d.waiting != null) setWaiting(d.waiting);
      })
      .catch(() => {});
    call<{ disputes: Dispute[] }>("/v1/admin/disputes").then((d) => setDisputes(d.disputes)).catch(() => {});
    call<{ tasks?: Review[]; review?: Review[] } | Review[]>("/v1/admin/review").then((d) => setReview(Array.isArray(d) ? d : (d.tasks ?? d.review ?? []))).catch(() => {});
    call<{ reports: Report[] }>("/v1/admin/reports").then((d) => setReports(d.reports)).catch(() => {});
    call<Escrow>("/v1/admin/escrow").then(setEscrow).catch(() => {});
    call<House>("/v1/admin/house").then(setHouse).catch(() => {});
    fetch(`${API_URL}/v1/scouts`).then((r) => r.json()).then((d: { proposals: Proposal[] }) => setProposals(d.proposals.filter((p) => p.status === "review"))).catch(() => {});
  }, [call, key, filter]);

  useEffect(() => {
    const t = setTimeout(load, 0);
    const id = setInterval(load, 30_000);
    return () => {
      clearTimeout(t);
      clearInterval(id);
    };
  }, [load]);

  const act = async (label: string, path: string, body: unknown) => {
    setMsg(null);
    try {
      await call(path, body);
      setMsg(label);
      load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  };
  const note = (id: string) => notes[id] ?? "";
  const setNote = (id: string, v: string) => setNotes((n) => ({ ...n, [id]: v }));

  const counts = { responses: waiting, disputes: disputes.length, proposals: proposals.length, review: review.length, reports: reports.length, money: 0 };

  return (
    <div className="min-h-screen bg-[#080808] text-white">
      <Nav />
      <main className="mx-auto max-w-[1200px] px-4 pb-24 pt-[100px] sm:px-8 sm:pt-[130px]">
        <div className="flex items-center gap-2.5 font-serif text-[14px] text-white/70"><span className="h-[5px] w-[5px] bg-[#3b6cff]" />Operator</div>
        <h1 className="mt-4 font-serif text-[36px] font-light leading-[1.06] tracking-[-1px] sm:text-[56px] sm:tracking-[-2px]">Decisions that need <em className="italic">a person</em>.</h1>
        <p className="mt-4 max-w-[640px] font-serif text-[15px] leading-[1.5] text-white/55">This page is for the operator only. It is not linked from the site, and nothing on it loads without the operator key.</p>

        <div className="mt-8 flex flex-wrap items-center gap-3">
          <input
            type="password"
            value={key}
            onChange={(e) => {
              setKey(e.target.value);
              try {
                localStorage.setItem(KEY, e.target.value);
              } catch {}
            }}
            placeholder="Operator key"
            className="h-[44px] w-full max-w-[360px] rounded-full border border-white/15 bg-black/30 px-5 font-mono text-[14px] text-white outline-none placeholder:text-white/35"
          />
          <button onClick={load} className="h-[44px] rounded-full border border-white/25 px-5 font-serif text-[14px] text-white hover:bg-white/[0.06]">Refresh</button>
          {denied && <span className="font-serif text-[14px] text-red-300">That key is not accepted.</span>}
          {msg && !denied && <span className="font-serif text-[14px] text-[#9be36b]">{msg}</span>}
        </div>

        <div className="mt-8 flex gap-6 overflow-x-auto whitespace-nowrap border-b border-white/[0.08] font-serif text-[15px]">
          {([["responses", "Responses"], ["disputes", "Disputes"], ["proposals", "Proposals"], ["review", "Held for review"], ["reports", "Reports"], ["money", "Money"]] as const).map(([k, label]) => (
            <button key={k} onClick={() => setTab(k)} className={`-mb-px border-b-2 pb-3 ${tab === k ? "border-white text-white" : "border-transparent text-white/55 hover:text-white"}`}>
              {label}
              {counts[k] > 0 && <span className="ml-2 rounded-full bg-white/10 px-2 py-0.5 font-mono text-[11px] text-white/80">{counts[k]}</span>}
            </button>
          ))}
        </div>

        {tab === "responses" && (
          <section className="mt-6 space-y-4">
            <p className="font-serif text-[14px] leading-[1.5] text-white/55">
              Everything people sent back, newest first. Only this page shows it; nobody else sees another person&apos;s photos or answers. Photos and screenshots are never paid until you approve them here. Approve pays the person; refuse returns the money and nobody is paid.
            </p>
            <div className="flex flex-wrap gap-2">
              {([["waiting", "Waiting for you"], ["approved", "Approved"], ["refused", "Refused"], ["all", "Everything"]] as const).map(([k, label]) => (
                <button key={k} onClick={() => setFilter(k)} className={`h-[36px] rounded-full border px-4 font-serif text-[14px] ${filter === k ? "border-white bg-white text-[#0a0a0f]" : "border-white/20 text-white/70 hover:text-white"}`}>
                  {label}
                  {k === "waiting" && waiting > 0 && <span className={`ml-2 font-mono text-[11px] ${filter === k ? "text-[#0a0a0f]/60" : "text-white/50"}`}>{waiting}</span>}
                </button>
              ))}
            </div>
            {!key && <Empty>Enter the operator key to see what people have sent.</Empty>}
            {key && responses.length === 0 && <Empty>{filter === "waiting" ? "Nothing waiting. New photos and answers appear here as soon as they are sent." : "Nothing here yet."}</Empty>}
            {responses.map((r) => (
              <Card key={r.answerId}>
                <Head title={r.title} meta={`${labelOf(r.type)}${r.categoryLabel ? ` · ${r.categoryLabel}` : ""} · ${r.location} · ${money(r.price)} · ${ago(r.submittedAt)}`} href={`/tasks/${r.taskId}`} />
                <div className="mt-2 flex flex-wrap items-center gap-2 font-serif text-[13px]">
                  <Badge decision={r.decision} />
                  {r.proofKind && r.proofKind !== "text" && <span className="rounded-full bg-[#3b6cff]/20 px-2.5 py-0.5 text-[#9db4ff]">{r.proofKind === "photos" ? "camera photos" : r.proofKind === "both" ? "text and screenshot" : "screenshot"}</span>}
                  <span className="text-white/45">by {r.worker.wallet ? `${r.worker.wallet.slice(0, 6)}…${r.worker.wallet.slice(-4)}` : r.worker.id.slice(0, 10)}{r.worker.team ? " (team)" : ""}{r.seconds != null ? ` · took ${Math.round(r.seconds / 60)} min` : ""}</span>
                  {r.review && <span className={r.review.verdict === "right" ? "text-[#9be36b]" : r.review.verdict === "wrong" ? "text-red-300" : "text-amber-200"}>assistant says {r.review.verdict}{r.review.reason ? `: ${r.review.reason}` : ""}</span>}
                </div>
                <details className="mt-3">
                  <summary className="cursor-pointer font-serif text-[13px] text-white/50 hover:text-white/80">What was asked</summary>
                  <p className="mt-2 whitespace-pre-line font-serif text-[14px] leading-[1.5] text-white/70">{r.instructions}</p>
                  {r.write && <p className="mt-2 font-serif text-[13px] text-white/55">To type: {r.write}</p>}
                  {r.acceptance && <p className="mt-1 font-serif text-[13px] text-white/45">Accepted when: {r.acceptance}</p>}
                </details>
                <div className="mt-4 rounded-[12px] border border-white/[0.08] bg-black/30 p-4">
                  <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-white/45">What they sent</div>
                  {r.text ? <p className="mt-2 whitespace-pre-line font-serif text-[16px] leading-[1.5] text-white">{r.text}</p> : typeof r.value === "string" || typeof r.value === "number" ? <p className="mt-2 font-serif text-[16px] text-white">{String(r.value)}</p> : Array.isArray(r.value) ? <p className="mt-2 font-serif text-[16px] text-white">{r.value.join(", ")}</p> : null}
                  {r.note && <p className="mt-2 font-serif text-[14px] text-white/60">Note: {r.note}</p>}
                  {r.confidence != null && <p className="mt-1 font-serif text-[13px] text-white/45">Confidence {Math.round(r.confidence * 100)}%</p>}
                  {r.code && <p className="mt-2 font-serif text-[13px] text-white/60">Capture code to look for in every photo: <span className="font-mono text-[15px] tracking-[0.2em] text-white">{r.code}</span></p>}
                  {r.photos.length > 0 && (
                    <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
                      {r.photos.map((ph) => (
                        <ProofPhoto key={ph.photoId} photo={ph} token={key} />
                      ))}
                    </div>
                  )}
                  {r.screenshot && (
                    <a href={r.screenshot} target="_blank" rel="noreferrer noopener" className="mt-3 block">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={r.screenshot} alt="screenshot sent as proof" className="max-h-[420px] rounded-[10px] border border-white/10" />
                    </a>
                  )}
                </div>
                {r.dispute && <p className="mt-3 font-serif text-[14px] text-amber-200">Disputed: {r.dispute.reason}</p>}
                {(r.decision === "waiting" || r.decision === "disputed") && (
                  <Actions
                    note={note(r.taskId)}
                    onNote={(v) => setNote(r.taskId, v)}
                    buttons={[
                      ["Refuse: not paid", "danger", () => act("Refused. The money goes back; nobody is paid.", `/v1/admin/responses/${r.taskId}`, { decision: "refuse", note: note(r.taskId) })],
                      ["Approve and pay", "primary", () => act(`Approved. ${money(r.price)} goes to the person.`, `/v1/admin/responses/${r.taskId}`, { decision: "approve", note: note(r.taskId) })],
                    ]}
                  />
                )}
              </Card>
            ))}
          </section>
        )}

        {tab === "disputes" && (
          <section className="mt-6 space-y-4">
            {disputes.length === 0 && <Empty>No open disputes. Responses the verifier could not accept appear here.</Empty>}
            {disputes.map((d) => (
              <Card key={d.disputeId}>
                <Head title={d.task.title} meta={`${labelOf(d.task.type)} · ${money(d.task.price)} · ${ago(d.createdAt)}`} href={`/tasks/${d.taskId}`} />
                <p className="mt-3 font-serif text-[15px] leading-[1.45] text-white/80">{d.reason}</p>
                <p className="mt-2 font-serif text-[13px] text-white/45">The worker&apos;s response and any photos are on the task page when you are signed in as operator. Upheld means the work was not acceptable: the reward returns to the pool. Rejected means the work stands and the worker is paid.</p>
                <Actions
                  note={note(d.disputeId)}
                  onNote={(v) => setNote(d.disputeId, v)}
                  buttons={[
                    ["Uphold: not acceptable", "danger", () => act("Dispute upheld.", `/v1/admin/disputes/${d.disputeId}`, { outcome: "upheld", note: note(d.disputeId) })],
                    ["Reject: the work stands", "primary", () => act("Dispute rejected; the worker is paid.", `/v1/admin/disputes/${d.disputeId}`, { outcome: "rejected", note: note(d.disputeId) })],
                  ]}
                />
              </Card>
            ))}
          </section>
        )}

        {tab === "proposals" && (
          <section className="mt-6 space-y-4">
            {proposals.length === 0 && <Empty>No proposals waiting. The assistants&apos; next search adds more.</Empty>}
            {proposals.map((p) => (
              <Card key={p.id}>
                <Head title={p.title} meta={`${p.requester} · ${labelOf(p.type)} · ${p.location ?? "Remote"} · ${money(p.price)}`} />
                <p className="mt-3 font-serif text-[14px] text-white/60">Why a person: {p.why}</p>
                <Actions
                  buttons={[
                    ["Refuse", "quiet", () => act("Proposal refused.", `/v1/admin/scouts/proposals/${p.id}`, { decision: "reject" })],
                    ["Post it", "primary", () => act("Posted to the board.", `/v1/admin/scouts/proposals/${p.id}`, { decision: "post" })],
                  ]}
                />
              </Card>
            ))}
          </section>
        )}

        {tab === "review" && (
          <section className="mt-6 space-y-4">
            {review.length === 0 && <Empty>Nothing held. Paid tasks that tripped a moderation rule wait here.</Empty>}
            {review.map((t) => (
              <Card key={t.taskId}>
                <Head title={t.title} meta={`${labelOf(t.type)} · ${money(t.price)}`} href={`/tasks/${t.taskId}`} />
                {t.moderationReason && <p className="mt-2 font-serif text-[14px] text-amber-200">{t.moderationReason}</p>}
                <pre className="mt-3 max-h-[220px] overflow-auto rounded-[10px] bg-black/40 p-3 font-mono text-[12px] text-white/70">{JSON.stringify(t.payload, null, 2)}</pre>
                <Actions
                  note={note(t.taskId)}
                  onNote={(v) => setNote(t.taskId, v)}
                  buttons={[
                    ["Reject and refund", "danger", () => act("Task rejected and refunded.", `/v1/admin/review/${t.taskId}`, { decision: "reject", note: note(t.taskId) })],
                    ["Approve", "primary", () => act("Task approved.", `/v1/admin/review/${t.taskId}`, { decision: "approve", note: note(t.taskId) })],
                  ]}
                />
              </Card>
            ))}
          </section>
        )}

        {tab === "reports" && (
          <section className="mt-6 space-y-4">
            {reports.length === 0 && <Empty>No open reports from workers.</Empty>}
            {reports.map((r) => (
              <Card key={r.reportId}>
                <Head title={`Report on task ${r.taskId}`} meta={`by worker ${r.workerId.slice(0, 10)} · ${ago(r.createdAt)}`} href={`/tasks/${r.taskId}`} />
                <p className="mt-3 font-serif text-[15px] text-white/80">{r.reason}</p>
              </Card>
            ))}
          </section>
        )}

        {tab === "money" && (
          <section className="mt-6 grid gap-4 md:grid-cols-2">
            <Card>
              <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-white/45">Contract</div>
              {escrow ? (
                <dl className="mt-3 grid grid-cols-[150px_1fr] gap-y-2 font-serif text-[14px]">
                  <dt className="text-white/50">Holds</dt><dd className="font-mono">{money(escrow.balance)}</dd>
                  <dt className="text-white/50">Locked for tasks</dt><dd className="font-mono">{money(escrow.allocated)}</dd>
                  <dt className="text-white/50">Fees waiting</dt><dd className="font-mono">{money(escrow.feesAccrued)}</dd>
                  <dt className="text-white/50">Operator gas</dt><dd className="font-mono">{(escrow.operatorGasWei / 1e18).toFixed(5)} ETH</dd>
                  <dt className="text-white/50">Tasks on chain</dt><dd className="font-mono">{escrow.tasks.open} open · {escrow.tasks.pending} pending · {escrow.tasks.closed} closed</dd>
                </dl>
              ) : (
                <p className="mt-3 font-serif text-[14px] text-white/50">Not loaded.</p>
              )}
              <button onClick={() => act("Settlement run started.", "/v1/admin/escrow/run", {})} className="mt-4 h-[40px] rounded-full border border-white/25 px-4 font-serif text-[14px] hover:bg-white/[0.06]">Run settlement now</button>
            </Card>
            <Card>
              <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-white/45">Pool for platform tasks</div>
              {house ? (
                <dl className="mt-3 grid grid-cols-[150px_1fr] gap-y-2 font-serif text-[14px]">
                  <dt className="text-white/50">Available</dt><dd className="font-mono">{money(house.houseBalance)}</dd>
                  <dt className="text-white/50">Open tasks</dt><dd className="font-mono">{house.openHouseTasks}</dd>
                  <dt className="text-white/50">Spent today</dt><dd className="font-mono">{money(house.spentToday)} of {money(house.dailyBudget)}</dd>
                  <dt className="text-white/50">Automatic posting</dt><dd>{house.enabled ? "on" : "off"}</dd>
                </dl>
              ) : (
                <p className="mt-3 font-serif text-[14px] text-white/50">Not loaded.</p>
              )}
              <div className="mt-5 border-t border-white/[0.08] pt-4">
                <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-white/45">Close a task now</div>
                <p className="mt-1 font-serif text-[13px] text-white/50">Decides a task with the answers it already has, instead of waiting for more people or the deadline. Paste the task id from its page address.</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <input value={note("close")} onChange={(e) => setNote("close", e.target.value.trim())} placeholder="task_…" className="h-[40px] min-w-[260px] flex-1 rounded-full border border-white/10 bg-black/30 px-4 font-mono text-[13px] text-white outline-none placeholder:text-white/35" />
                  <button onClick={() => note("close") && act("Task decided with the answers it had.", `/v1/admin/tasks/${note("close")}/close`, {})} className="h-[40px] rounded-full bg-white px-4 font-serif text-[14px] font-semibold text-[#0a0a0f] hover:bg-[#e6ecff]">Close now</button>
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-3">
                <button onClick={() => act("Posted a batch.", "/v1/admin/house/post", {})} className="h-[40px] rounded-full border border-white/25 px-4 font-serif text-[14px] hover:bg-white/[0.06]">Post a batch of tasks</button>
                <button onClick={() => act("Verifier run started.", "/v1/admin/verifier/run", {})} className="h-[40px] rounded-full border border-white/25 px-4 font-serif text-[14px] hover:bg-white/[0.06]">Run the verifier</button>
              </div>
            </Card>
          </section>
        )}
      </main>
    </div>
  );
}

const ago = (t: number) => {
  const s = Math.max(0, Math.floor(Date.now() / 1000) - t);
  return s < 3600 ? `${Math.floor(s / 60)} min ago` : s < 86400 ? `${Math.floor(s / 3600)} h ago` : `${Math.floor(s / 86400)} d ago`;
};

function Badge({ decision }: { decision: Response["decision"] }) {
  const look: Record<Response["decision"], [string, string]> = {
    waiting: ["Waiting for you", "bg-amber-300/15 text-amber-200"],
    disputed: ["Disputed, waiting for you", "bg-amber-300/15 text-amber-200"],
    approved: ["Approved and paid", "bg-[#9be36b]/15 text-[#9be36b]"],
    not_paid: ["Done, this answer not paid", "bg-white/10 text-white/60"],
    refused: ["Refused", "bg-red-400/15 text-red-200"],
    open: ["Still collecting answers", "bg-white/10 text-white/60"],
  };
  const [label, cls] = look[decision];
  return <span className={`rounded-full px-2.5 py-0.5 ${cls}`}>{label}</span>;
}

/** A proof photo fetched with the operator key in the header, so the key never appears in a link. */
function ProofPhoto({ photo, token }: { photo: Photo; token: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!photo.url || !token) return;
    let url: string | null = null;
    let gone = false;
    fetch(photo.url, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.blob() : Promise.reject(new Error(String(r.status)))))
      .then((b) => {
        url = URL.createObjectURL(b);
        if (!gone) setSrc(url);
      })
      .catch(() => {
        if (!gone) setFailed(true);
      });
    return () => {
      gone = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [photo.url, token]);
  const meta = [photo.distanceM != null ? `${photo.distanceM} m from the place` : null, photo.accuracyM != null ? `±${photo.accuracyM} m` : null].filter(Boolean).join(" · ");
  return (
    <div className="overflow-hidden rounded-[10px] border border-white/10 bg-black/40">
      {src ? (
        <a href={src} target="_blank" rel="noreferrer noopener">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={src} alt="proof photo" className="aspect-square w-full object-cover" />
        </a>
      ) : (
        <div className="flex aspect-square items-center justify-center font-serif text-[13px] text-white/40">{photo.expired || failed ? "Photo no longer available" : "Loading…"}</div>
      )}
      {meta && <div className="px-2 py-1 font-serif text-[11px] text-white/50">{meta}</div>}
    </div>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return <div className="rounded-[16px] border border-white/[0.1] bg-[#0b0b0e] p-5 sm:p-6">{children}</div>;
}
function Empty({ children }: { children: React.ReactNode }) {
  return <p className="rounded-[16px] border border-dashed border-white/10 p-6 font-serif text-[15px] text-white/50">{children}</p>;
}
function Head({ title, meta, href }: { title: string; meta: string; href?: string }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-2">
      {href ? <Link href={href} className="font-serif text-[18px] text-white hover:underline">{title}</Link> : <span className="font-serif text-[18px] text-white">{title}</span>}
      <span className="font-serif text-[13px] text-white/45">{meta}</span>
    </div>
  );
}
function Actions({ note, onNote, buttons }: { note?: string; onNote?: (v: string) => void; buttons: [string, "primary" | "danger" | "quiet", () => void][] }) {
  const tone = { primary: "bg-white text-[#0a0a0f] hover:bg-[#e6ecff]", danger: "border border-red-300/40 text-red-200 hover:bg-red-400/10", quiet: "border border-white/25 text-white hover:bg-white/[0.06]" };
  return (
    <div className="mt-4 flex flex-wrap items-center gap-3">
      {onNote && <input value={note} onChange={(e) => onNote(e.target.value)} placeholder="Note for the record (optional)" className="h-[40px] min-w-[220px] flex-1 rounded-full border border-white/10 bg-black/30 px-4 font-serif text-[14px] text-white outline-none placeholder:text-white/35" />}
      {buttons.map(([label, t, fn]) => (
        <button key={label} onClick={fn} className={`h-[40px] rounded-full px-4 font-serif text-[14px] font-semibold ${tone[t]}`}>{label}</button>
      ))}
    </div>
  );
}
