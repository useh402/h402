"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Nav } from "@/components/nav";
import { Footer } from "@/components/footer";
import { TaskArt, artFor } from "@/components/board/art";
import { RequesterMark, requesterFor } from "@/components/board/requester";
import { TaskCard } from "@/components/earn/task-card";
import { Button } from "@/components/earn/shell";
import { api, API_URL, getToken, money, type Card, type Worker } from "@/lib/api";
import { SignIn } from "@/components/sign-in";
import { Protect } from "@/components/protect";
import { TYPE_BY_KEY, labelOf } from "@/lib/types";

type Listing = {
  taskId: string; title: string; type: string; state: string; category: string | null; categoryLabel: string | null; categoryNeed: string | null; location: string; difficulty: string; effortMinutes: number; price: number; workers: number; slotsLeft: number;
  deadline: number; postedAt: number; timeLimitSeconds: number; requester: string | null; image: string | null; payload: Record<string, unknown>; acceptance: string | null; minReputation: number;
  requirements: { qualification: string; consensus: string; proof: string | null; paidWhen: string; holdSeconds: number; location: string }; open: boolean; place?: { lat: number; lng: number; exact: boolean } | null; mapsUrl?: string | null;
  review?: { verdict: string; reason: string } | null;
};
type Comment = { id: string; author: string; tier: string; mine: boolean; response: unknown; note: string; confidence: number | null; at: number; seconds: number | null; outcome: string; wallet?: string | null; reward?: number; rewardPaid?: boolean; rewardTransaction?: string | null; rewardExplorer?: string | null; team?: boolean; claimable?: boolean; canClaim?: boolean };
type Comments = { decided: boolean; total: number; hidden: number; comments: Comment[] };

export default function TaskListing() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [t, setT] = useState<Listing | null>(null);
  const [worker, setWorker] = useState<Worker | null>(null);
  const [card, setCard] = useState<Card | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [showSignIn, setShowSignIn] = useState(false);
  const [now, setNow] = useState(0);
  const [comments, setComments] = useState<Comments | null>(null);

  useEffect(() => {
    const load = () =>
      fetch(`${API_URL}/v1/tasks/open/${id}`)
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error("This task is no longer listed."))))
        .then((d: Listing) => {
          setT(d);
          setNow(Math.floor(Date.now() / 1000));
        })
        .catch((e) => setMsg(e.message))
        .then(() => fetch(`${API_URL}/v1/tasks/${id}/comments`, { headers: getToken() ? { Authorization: `Bearer ${getToken()}` } : {} }))
        .then((r) => (r && r.ok ? r.json() : null))
        .then((c: Comments | null) => c && setComments(c))
        .catch(() => {});
    const first = setTimeout(() => {
      load();
      if (getToken()) api<Worker>("/v1/workers/me").then(setWorker).catch(() => setWorker(null));
    }, 0);
    const i = setInterval(load, 10000);
    return () => {
      clearTimeout(first);
      clearInterval(i);
    };
  }, [id]);

  const take = async () => {
    if (!t) return;
    if (!worker) return setShowSignIn(true);
    if (!worker.termsAccepted || !worker.qualifiedTypes.includes(t.type)) return router.push(`/earn/qualify/${t.type}?next=/tasks/${id}`);
    setBusy(true);
    setMsg(null);
    try {
      setCard(await api<Card>(`/v1/tasks/${t.taskId}/claim`, { body: {} }));
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const claimReward = async () => {
    if (!t) return;
    setBusy(true);
    try {
      const r = await api<{ amount: number; transaction: string; explorer: string }>(`/v1/tasks/${t.taskId}/claim-reward`, { body: {} });
      setMsg(`${money(r.amount)} sent to your wallet.`);
      const c = await fetch(`${API_URL}/v1/tasks/${t.taskId}/comments`, { headers: getToken() ? { Authorization: `Bearer ${getToken()}` } : {} });
      if (c.ok) setComments(await c.json());
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const submit = async (answer: unknown, note: string, confidence?: number) => {
    if (!t) return;
    setBusy(true);
    try {
      const r = await api<{ state: string; agreed?: boolean }>(`/v1/tasks/${t.taskId}/answer`, { body: { answer, note, confidence } });
      setCard(null);
      setMsg(r.state === "done" ? (r.agreed ? `Accepted. ${money(t.price)} added to your pending balance.` : "Submitted. The other answers did not match yours this time.") : t.type === "do" || t.type === "answer" ? "Submitted. Your response is being reviewed now; clear ones are approved within a minute, anything unclear is looked at by a person." : "Submitted. You are paid once the other answers are in and match.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const release = async () => {
    if (!t) return;
    await api(`/v1/tasks/${t.taskId}/release`, { body: {} }).catch(() => {});
    setCard(null);
  };

  if (!t) {
    return (
      <div className="min-h-screen bg-[#080808] text-white">
        <Nav />
        <main className="mx-auto max-w-[1200px] px-4 pt-[110px] font-serif text-white/60 sm:px-8 sm:pt-[140px]">{msg ?? "Loading…"}</main>
      </div>
    );
  }
  const info = TYPE_BY_KEY[t.type];
  const r = requesterFor(t.requester);
  const p = t.payload;
  const left = Math.max(0, t.deadline - now);
  const qualified = !!worker && worker.termsAccepted && worker.qualifiedTypes.includes(t.type);

  return (
    <div className="min-h-screen bg-[#080808] text-white">
      <Nav />
      <main className="mx-auto max-w-[1280px] px-4 pb-24 pt-[90px] sm:px-8 sm:pt-[110px]">
        <Link href="/tasks" className="font-serif text-[13px] text-white/45 hover:text-white">← All open tasks</Link>
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-[460px_1fr] lg:gap-10">
          {/* Left: artwork and facts. On a phone the task itself comes first and the artwork is left out. */}
          <div className="order-2 space-y-4 lg:order-none">
            <div className="group hidden overflow-hidden rounded-[22px] border border-white/[0.1] lg:block">
              <TaskArt category={t.category} image={t.image} seed={t.taskId} requester={t.requester} big />
            </div>
            <div className="rounded-[18px] border border-white/[0.08] bg-white/[0.025] p-5">
              <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-white/45">Details</div>
              <dl className="mt-3 grid grid-cols-[120px_1fr] gap-y-2 font-serif text-[14px] sm:grid-cols-[140px_1fr]">
                <dt className="text-white/50">Type of work</dt><dd>{labelOf(t.type)}</dd>
                <dt className="text-white/50">Category</dt><dd>{t.categoryLabel ?? "Task"}</dd>
                <dt className="text-white/50">Where</dt><dd>{t.location}{t.mapsUrl && <a href={t.mapsUrl} target="_blank" rel="noreferrer" className="ml-2 text-[#9db4ff] underline">Open in Maps ↗</a>}</dd>
                <dt className="text-white/50">Difficulty</dt><dd className="capitalize">{t.difficulty}</dd>
                <dt className="text-white/50">Takes about</dt><dd>{t.effortMinutes} min</dd>
                <dt className="text-white/50">Time limit</dt><dd>{Math.round(t.timeLimitSeconds / 60)} min once taken</dd>
                <dt className="text-white/50">People wanted</dt><dd>{t.workers} · {t.slotsLeft} slot{t.slotsLeft === 1 ? "" : "s"} open</dd>
                <dt className="text-white/50">Listed</dt><dd>{now ? (now - t.postedAt >= 3600 ? `${Math.floor((now - t.postedAt) / 3600)} h ago` : `${Math.max(1, Math.floor((now - t.postedAt) / 60))} min ago`) : ""}</dd>
                <dt className="hidden">Ends in</dt><dd className="hidden font-mono">{now ? (left >= 3600 ? `${Math.floor(left / 3600)}h ${Math.floor((left % 3600) / 60)}m` : `${Math.floor(left / 60)}m ${left % 60}s`) : ""}</dd>
                {r && (<><dt className="text-white/50">For</dt><dd className="flex items-center gap-2"><RequesterMark requester={t.requester} size={16} />{r.label}</dd></>)}
              </dl>
            </div>
          </div>

          {/* Right: title, price, requirements, action */}
          <div className="order-1 min-w-0 lg:order-none">
            <div className="flex items-center gap-2 font-serif text-[14px] text-white/60">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: artFor(t.category).accent }} />
              {t.categoryLabel ?? "Task"} · {labelOf(t.type)}
            </div>
            <h1 className="mt-3 font-serif text-[30px] font-light leading-[1.1] tracking-[-0.5px] sm:text-[44px] sm:leading-[1.08] sm:tracking-[-1px]">{t.title}</h1>
            {t.categoryNeed && <p className="mt-3 font-serif text-[15px] font-light text-white/55">{t.categoryNeed}</p>}

            <div className="mt-6 flex flex-col gap-4 rounded-[18px] border border-white/[0.1] bg-[#0d0d14] p-5 sm:flex-row sm:items-end sm:justify-between sm:p-6">
              <div>
                <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-white/45">Pays, per person</div>
                <div className="mt-1 font-mono text-[34px] leading-none sm:text-[40px]">{money(t.price)}</div>
                <div className="mt-2 font-serif text-[13px] text-white/50">Paid when {t.requirements.paidWhen}. Payouts go to your wallet every ten minutes.</div>
              </div>
              <div className="sm:text-right">
                {card ? (
                  <span className="font-serif text-[14px] text-[#9be36b]">You hold this task</span>
                ) : t.open ? (
                  <Button onClick={take} disabled={busy}>{busy ? "Working…" : worker ? (qualified ? "Take this task" : `Qualify for ${labelOf(t.type)} first`) : "Sign in to take it"}</Button>
                ) : (
                  <span className="font-serif text-[14px] text-white/50">No longer open</span>
                )}
                {worker && <div className="mt-2 font-serif text-[12px] text-white/45">Signed in as {worker.wallet.slice(0, 6)}…{worker.wallet.slice(-4)}</div>}
              </div>
            </div>

            {msg && <div className="mt-4 rounded-[12px] border border-white/15 bg-white/[0.04] px-4 py-3 font-serif text-[14px]">{msg}</div>}

            {showSignIn && !worker && (
              <div className="mt-4 rounded-[18px] border border-white/[0.1] bg-white/[0.03] p-5">
                <div className="mb-3 font-serif text-[16px]">Sign in to take this task</div>
                <SignIn
                  role="worker"
                  onDone={(w) => {
                    const me = w as Worker;
                    setWorker(me);
                    setShowSignIn(false);
                    if (!me.termsAccepted || !me.qualifiedTypes.includes(t.type)) router.push(`/earn/qualify/${t.type}?next=/tasks/${id}`);
                  }}
                />
              </div>
            )}

            {card && (
              <div className="mt-6">
                <Protect mark={worker ? `${worker.wallet.slice(0, 6)}…${worker.wallet.slice(-4)}` : null}>
                  <TaskCard key={card.taskId} card={card} onSubmit={submit} onRelease={release} busy={busy} />
                </Protect>
              </div>
            )}

            {!card && (
              <>
                <section className="mt-8">
                  <h2 className="font-serif text-[22px] font-light">What you will do</h2>
                  <Protect>
                  <div className="mt-3 space-y-3 font-serif text-[16px] font-light leading-[1.5] text-white/85">
                    {typeof p.instructions === "string" && <p className="whitespace-pre-line">{p.instructions}</p>}
                    {typeof p.question === "string" && <p>{p.question}</p>}
                    {typeof p.text === "string" && <blockquote className="rounded-[12px] border border-white/10 bg-white/[0.03] p-4">{p.text}</blockquote>}
                    {typeof p.item === "string" && <blockquote className="rounded-[12px] border border-white/10 bg-white/[0.03] p-4">{p.item}</blockquote>}
                    {typeof p.rubric === "string" && <p className="text-white/60">Scale: {p.rubric}</p>}
                    {Array.isArray(p.options) && <ol className="list-decimal space-y-1 pl-5">{(p.options as string[]).map((o, i) => <li key={i}>{/^https?:\/\//.test(o) ? <a href={o} target="_blank" rel="noreferrer" className="text-[#9db4ff] underline">option image {i + 1}</a> : o}</li>)}</ol>}
                    {Array.isArray(p.labels) && <p className="text-white/60">Labels to choose from: {(p.labels as string[]).join(", ")}</p>}
                    {typeof p.url === "string" && <a href={p.url} target="_blank" rel="noreferrer noopener" className="inline-block rounded-full border border-white/30 px-4 py-2 text-[14px] text-white hover:bg-white/10">Open the page ↗</a>}
                  </div>
                  </Protect>
                </section>

                <section className="mt-8">
                  <h2 className="font-serif text-[22px] font-light">Requirements</h2>
                  <ul className="mt-3 space-y-2 font-serif text-[15px] font-light leading-[1.45] text-white/80">
                    <li className="flex gap-3"><Dot />Qualification: {labelOf(t.requirements.qualification)} (three practice questions, two right). {qualified ? <span className="text-[#9be36b]">You have it.</span> : worker ? <Link href={`/earn/qualify/${t.type}?next=/tasks/${id}`} className="text-[#9db4ff] underline">Take it now</Link> : null}</li>
                    {t.requirements.proof && <li className="flex gap-3"><Dot />Proof: {t.requirements.proof === "photos" ? "one to three photos taken now with your phone's camera, each showing the capture code you are given when you take the task" : t.requirements.proof === "both" ? "a written note and a photo or screenshot" : t.requirements.proof === "screenshot" ? "a photo or screenshot" : "a written note, and a screenshot if you can so it can be checked"}</li>}
                    {t.acceptance && <li className="flex gap-3"><Dot />Accepted when: {t.acceptance}</li>}
                    <li className="flex gap-3"><Dot />Paid when {t.requirements.paidWhen}.</li>
                    <li className="flex gap-3"><Dot />{t.location === "Remote" ? "Can be done from anywhere in the United States." : t.place?.exact ? <span>You need to be at the exact spot in {t.location}. {t.mapsUrl && <a href={t.mapsUrl} target="_blank" rel="noreferrer" className="text-[#9db4ff] underline">Open it in Maps ↗</a>} Your photos are checked against that location.</span> : <span>You need to be in {t.location}. {t.mapsUrl && <a href={t.mapsUrl} target="_blank" rel="noreferrer" className="text-[#9db4ff] underline">Open in Maps ↗</a>}</span>}</li>
                    <li className="flex gap-3"><Dot />Once taken, you have {Math.round(t.requirements.holdSeconds / 60)} minutes to finish.</li>
                    {t.minReputation > 0 && <li className="flex gap-3"><Dot />Reputation of at least {t.minReputation.toFixed(1)}.</li>}
                    {info?.rules.map((rule) => <li key={rule} className="flex gap-3"><Dot />{rule}</li>)}
                  </ul>
                </section>
              </>
            )}
          </div>
        </div>
        <section className="mt-14 border-t border-white/[0.08] pt-8">
          <div className="flex items-baseline justify-between">
            <h2 className="font-serif text-[26px] font-light">Responses</h2>
            <span className="font-mono text-[12px] uppercase tracking-[0.06em] text-white/45">{comments?.total ?? 0} saved</span>
          </div>
          {comments && comments.hidden > 0 && (
            <p className="mt-3 font-serif text-[14px] text-white/50">
              {comments.hidden} response{comments.hidden === 1 ? " is" : "s are"} saved and hidden until this task is decided, so that everyone answers on their own.
            </p>
          )}
          {comments && comments.total === 0 && <p className="mt-3 font-serif text-[14px] text-white/50">No responses yet. Every response to this task is kept here.</p>}
          <ul className="mt-4 space-y-3">
            {comments?.comments.map((c) => {
              const v = c.response as { text?: string; screenshot?: string } | string | number | string[] | null;
              const obj = v && typeof v === "object" && !Array.isArray(v) ? v : null;
              return (
                <li key={c.id} className="rounded-[14px] border border-white/[0.08] bg-white/[0.025] p-5">
                  <div className="flex items-center justify-between font-serif text-[13px] text-white/55">
                    <span><span className="text-white/90">{c.author}</span>{c.wallet && <span className="ml-2 font-mono text-[12px] text-[#9be36b]" title="The wallet this reward is paid to">{c.wallet.slice(0, 6)}…{c.wallet.slice(-4)}</span>}{c.team && <span className="ml-2 rounded-full border border-white/15 px-2 py-0.5 text-[11px] text-white/60" title="A wallet run by the H402 team while testing payments.">H402 team</span>} · {c.tier} tier · {new Date(c.at * 1000).toLocaleString()}{c.seconds ? ` · took ${Math.round(c.seconds)}s` : ""}</span>
                    <span className={c.outcome === "accepted" ? "text-[#9be36b]" : c.outcome === "waiting" ? "text-amber-200" : "text-white/45"}>{c.outcome}</span>
                  </div>
                  <div className="mt-2 whitespace-pre-line font-serif text-[16px] font-light text-white/90">
                    {obj ? obj.text : Array.isArray(v) ? v.join(", ") : v === null ? "Removed after 30 days." : String(v)}
                  </div>
                  {obj?.screenshot && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={obj.screenshot} alt="proof" className="mt-3 max-h-[360px] rounded-[10px] border border-white/10" />
                  )}
                  {c.note && <div className="mt-2 font-serif text-[14px] text-white/60">{c.note}</div>}
                  {c.outcome === "accepted" && (c.reward ?? 0) > 0 && (
                    <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-white/[0.06] pt-3 font-serif text-[13px]">
                      <span className="font-mono text-[#9be36b]">{money(c.reward ?? 0)}</span>
                      {c.rewardExplorer ? (
                        <a href={c.rewardExplorer} target="_blank" rel="noreferrer" className="text-[#9db4ff] underline">Reward paid · view transaction ↗</a>
                      ) : c.canClaim ? (
                        <button onClick={() => claimReward()} disabled={busy} className="h-[36px] rounded-full bg-[#9be36b] px-4 font-serif text-[14px] font-semibold text-[#0a0a0f] hover:bg-[#b4f08a] disabled:opacity-60">
                          {busy ? "Sending…" : "Claim reward"}
                        </button>
                      ) : c.claimable ? (
                        <span className="text-white/50">Reward ready to claim</span>
                      ) : (
                        <span className="text-white/50">{c.rewardPaid ? "Reward paid" : "Reward on its way"}</span>
                      )}
                    </div>
                  )}
                  {c.outcome === "not accepted" && (
                    <div className="mt-3 border-t border-white/[0.06] pt-3 font-serif text-[13px] text-white/45">
                      {t.review?.verdict === "wrong" ? `No reward: the review found this answer wrong. ${t.review.reason}` : t.type === "do" || t.type === "answer" ? "No reward: this response was refused after review." : "No reward: this response did not match the accepted answer."}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      </main>
      <Footer />
    </div>
  );
}

function Dot() {
  return <span className="mt-[10px] h-[5px] w-[5px] shrink-0 bg-[#3b6cff]" />;
}
