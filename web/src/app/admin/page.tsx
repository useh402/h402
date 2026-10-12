"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL, money } from "@/lib/api";

/**
 * The admin page: sign in with an id and a password, see every response waiting for a person (photo,
 * screenshot and written proofs, and written answers), approve or refuse each one. Nothing else.
 */

const TOKEN = "humanapi.admin.token";
type Photo = { photoId: string; url: string | null; expired?: boolean; distanceM?: number | null };
type Unclaimed = { taskId: string; title: string; type: string; amount: number; workers: number; approvedAt: number; chainState: string | null; locked: boolean };
type Row = { taskId: string; answerId: string; title: string; type: string; price: number; location: string; proofKind: string | null; options?: string[] | null; value?: unknown; submittedAt: number; instructions: string; write: string | null; text: string | null; note: string; code: string | null; photos: Photo[]; screenshot: string | null; worker: { wallet: string; id: string }; decision: string };

export default function AdminPage() {
  const [token, setToken] = useState("");
  const [user, setUser] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [rows, setRows] = useState<Row[] | null>(null);
  const [unclaimed, setUnclaimed] = useState<Unclaimed[]>([]);
  const [sure, setSure] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [done, setDone] = useState<Record<string, string>>({});

  useEffect(() => {
    const t = setTimeout(() => {
      try {
        setToken(localStorage.getItem(TOKEN) ?? "");
      } catch {}
    }, 0);
    return () => clearTimeout(t);
  }, []);

  const load = useCallback(async () => {
    if (!token) return;
    const r = await fetch(`${API_URL}/v1/admin/responses?status=waiting&limit=200`, { headers: { Authorization: `Bearer ${token}` } });
    if (r.status === 401 || r.status === 403 || r.status === 404) {
      setToken("");
      try {
        localStorage.removeItem(TOKEN);
      } catch {}
      setError("Signed out. Sign in again.");
      return;
    }
    const j = (await r.json()) as { responses: Row[] };
    // Every response waiting for a person: proofs of every kind, written answers, and consensus answers when the operator decides everything.
    setRows(j.responses);
    const u = await fetch(`${API_URL}/v1/admin/unclaimed`, { headers: { Authorization: `Bearer ${token}` } });
    if (u.ok) setUnclaimed(((await u.json()) as { tasks: Unclaimed[] }).tasks);
  }, [token]);

  const voidReward = async (t: Unclaimed) => {
    setBusy(t.taskId);
    setError(null);
    try {
      const r = await fetch(`${API_URL}/v1/admin/tasks/${t.taskId}/void-reward`, { method: "POST", headers: { Authorization: `Bearer ${token}`, "content-type": "application/json" }, body: JSON.stringify({ reason: "not claimed; returned to the pool" }) });
      const j = await r.json();
      if (!r.ok) throw new Error(j.message || j.error || `failed (${r.status})`);
      setDone((d) => ({ ...d, [t.taskId]: `Reward of ${money(j.amount)} withdrawn and returned to the pool${j.transaction ? ` (${String(j.transaction).slice(0, 12)}…)` : ""}` }));
      setUnclaimed((u) => u.filter((x) => x.taskId !== t.taskId));
      setSure(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  useEffect(() => {
    const t = setTimeout(() => load().catch((e) => setError(String(e))), 0);
    const id = setInterval(() => load().catch(() => {}), 30_000);
    return () => {
      clearTimeout(t);
      clearInterval(id);
    };
  }, [load]);

  const signIn = async () => {
    setError(null);
    try {
      const r = await fetch(`${API_URL}/v1/admin/login`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ user, password }) });
      const j = await r.json();
      if (!r.ok) throw new Error(j.message || "wrong id or password");
      try {
        localStorage.setItem(TOKEN, j.token);
      } catch {}
      setPassword("");
      setToken(j.token);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const decide = async (row: Row, decision: "approve" | "refuse") => {
    setBusy(row.taskId);
    setError(null);
    try {
      const r = await fetch(`${API_URL}/v1/admin/responses/${row.taskId}`, { method: "POST", headers: { Authorization: `Bearer ${token}`, "content-type": "application/json" }, body: JSON.stringify({ decision }) });
      const j = await r.json();
      if (!r.ok) throw new Error(j.message || j.error || `failed (${r.status})`);
      setDone((d) => ({ ...d, [row.taskId]: decision === "approve" ? `Approved, ${money(row.price)} paid` : "Refused, not paid" }));
      setRows((rs) => (rs ?? []).filter((x) => x.taskId !== row.taskId));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const signOut = () => {
    try {
      localStorage.removeItem(TOKEN);
    } catch {}
    setToken("");
    setRows(null);
  };

  if (!token) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#080808] px-4 text-white">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            signIn();
          }}
          className="w-full max-w-[360px] rounded-[16px] border border-white/10 bg-[#0b0b0e] p-6"
        >
          <h1 className="font-serif text-[26px] font-light">Admin</h1>
          <label className="mt-5 block font-serif text-[13px] text-white/60">
            Id
            <input value={user} onChange={(e) => setUser(e.target.value)} autoComplete="username" className="mt-1 h-[44px] w-full rounded-[10px] border border-white/15 bg-black/30 px-4 font-mono text-[14px] text-white outline-none" />
          </label>
          <label className="mt-4 block font-serif text-[13px] text-white/60">
            Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" className="mt-1 h-[44px] w-full rounded-[10px] border border-white/15 bg-black/30 px-4 font-mono text-[14px] text-white outline-none" />
          </label>
          {error && <p className="mt-3 font-serif text-[13px] text-red-300">{error}</p>}
          <button type="submit" className="mt-5 h-[44px] w-full rounded-full bg-white font-serif text-[15px] font-semibold text-[#0a0a0f] hover:bg-[#e6ecff]">Sign in</button>
        </form>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#080808] px-4 pb-24 pt-8 text-white sm:px-8">
      <div className="mx-auto max-w-[900px]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="font-serif text-[28px] font-light">
            Responses to approve <span className="font-mono text-[16px] text-white/50">{rows ? rows.length : "…"}</span>
          </h1>
          <div className="flex gap-2">
            <button onClick={() => load().catch(() => {})} className="h-[38px] rounded-full border border-white/25 px-4 font-serif text-[14px] hover:bg-white/[0.06]">Refresh</button>
            <button onClick={signOut} className="h-[38px] rounded-full border border-white/15 px-4 font-serif text-[14px] text-white/60 hover:text-white">Sign out</button>
          </div>
        </div>
        {error && <p className="mt-3 font-serif text-[14px] text-red-300">{error}</p>}
        {Object.entries(done).map(([id, msg]) => (
          <p key={id} className="mt-2 font-serif text-[13px] text-[#9be36b]">{msg}</p>
        ))}
        {rows && rows.length === 0 && <p className="mt-8 rounded-[14px] border border-dashed border-white/10 p-6 font-serif text-[15px] text-white/50">Nothing waiting. Responses show up here as soon as someone sends them.</p>}
        <div className="mt-6 space-y-5">
          {(rows ?? []).map((r) => (
            <div key={r.answerId} className="rounded-[16px] border border-white/10 bg-[#0b0b0e] p-5">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <a href={`/tasks/${r.taskId}`} target="_blank" rel="noreferrer" className="font-serif text-[18px] hover:underline">{r.title}</a>
                <span className="font-serif text-[13px] text-white/45">{money(r.price)} · {r.location} · {ago(r.submittedAt)} · {r.worker.wallet ? `${r.worker.wallet.slice(0, 6)}…${r.worker.wallet.slice(-4)}` : r.worker.id.slice(0, 10)}</span>
              </div>
              <p className="mt-2 font-serif text-[13px] leading-[1.5] text-white/50">{r.instructions}</p>
              {r.code && (
                <p className="mt-3 font-serif text-[13px] text-white/60">
                  Code that must be in every photo: <span className="font-mono text-[16px] tracking-[0.2em] text-white">{r.code}</span>
                </p>
              )}
              {r.photos.length > 0 && (
                <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {r.photos.map((ph) => (
                    <ProofPhoto key={ph.photoId} photo={ph} token={token} />
                  ))}
                </div>
              )}
              {r.screenshot && (
                <a href={r.screenshot} target="_blank" rel="noreferrer noopener" className="mt-3 block">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={r.screenshot} alt="screenshot" className="max-h-[360px] rounded-[10px] border border-white/10" />
                </a>
              )}
              {r.text && (
                <div className="mt-3 rounded-[10px] bg-black/30 p-3">
                  {r.write && <div className="font-serif text-[12px] text-white/45">Asked to type: {r.write}</div>}
                  <p className="whitespace-pre-line font-serif text-[15px] text-white">{r.text}</p>
                </div>
              )}
              {!r.text && r.value != null && typeof r.value !== "object" && (
                <div className="mt-3 rounded-[10px] bg-black/30 p-3">
                  <div className="font-serif text-[12px] text-white/45">Answered</div>
                  <p className="font-serif text-[15px] text-white">{r.options && typeof r.value === "number" ? `${r.value + 1}. ${r.options[r.value] ?? r.value}` : String(r.value)}</p>
                </div>
              )}
              {!r.text && Array.isArray(r.value) && (
                <div className="mt-3 rounded-[10px] bg-black/30 p-3">
                  <div className="font-serif text-[12px] text-white/45">Answered</div>
                  <p className="font-serif text-[15px] text-white">{(r.value as unknown[]).map(String).join(", ")}</p>
                </div>
              )}
              {r.note && <p className="mt-2 font-serif text-[13px] text-white/55">Note: {r.note}</p>}
              <div className="mt-4 flex gap-3">
                <button disabled={busy === r.taskId} onClick={() => decide(r, "approve")} className="h-[42px] rounded-full bg-white px-5 font-serif text-[15px] font-semibold text-[#0a0a0f] hover:bg-[#e6ecff] disabled:opacity-50">Approve and pay</button>
                <button disabled={busy === r.taskId} onClick={() => decide(r, "refuse")} className="h-[42px] rounded-full border border-red-300/40 px-5 font-serif text-[15px] text-red-200 hover:bg-red-400/10 disabled:opacity-50">Refuse</button>
              </div>
            </div>
          ))}
        </div>

        {unclaimed.length > 0 && (
          <div className="mt-12">
            <h2 className="font-serif text-[22px] font-light">
              Approved, not yet claimed <span className="font-mono text-[14px] text-white/50">{unclaimed.length}</span>
            </h2>
            <p className="mt-2 font-serif text-[13px] leading-[1.5] text-white/50">
              Rewards you approved that the worker has not collected. Withdrawing one returns the money to the pool, releases it from the contract if it is locked there, and tells the worker on their earnings page. This takes back pay you approved: use it only for rewards left unclaimed for a long time.
            </p>
            <div className="mt-4 space-y-3">
              {unclaimed.map((t) => (
                <div key={t.taskId} className="flex flex-col gap-3 rounded-[14px] border border-white/10 bg-[#0b0b0e] p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <a href={`/tasks/${t.taskId}`} target="_blank" rel="noreferrer" className="font-serif text-[16px] hover:underline">{t.title}</a>
                    <div className="mt-1 font-serif text-[13px] text-white/45">
                      {money(t.amount)} · {t.workers} worker{t.workers === 1 ? "" : "s"} · approved {ago(t.approvedAt)}{t.locked ? " · locked in the contract" : ""}
                    </div>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    {sure === t.taskId ? (
                      <>
                        <button disabled={busy === t.taskId} onClick={() => voidReward(t)} className="h-[38px] rounded-full bg-red-400/90 px-4 font-serif text-[14px] font-semibold text-[#0a0a0f] hover:bg-red-300 disabled:opacity-50">Yes, withdraw {money(t.amount)}</button>
                        <button onClick={() => setSure(null)} className="h-[38px] rounded-full border border-white/20 px-4 font-serif text-[14px] text-white/70 hover:text-white">Keep</button>
                      </>
                    ) : (
                      <button onClick={() => setSure(t.taskId)} className="h-[38px] rounded-full border border-red-300/40 px-4 font-serif text-[14px] text-red-200 hover:bg-red-400/10">Withdraw reward</button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

const ago = (t: number) => {
  const s = Math.max(0, Math.floor(Date.now() / 1000) - t);
  return s < 3600 ? `${Math.floor(s / 60)} min ago` : s < 86400 ? `${Math.floor(s / 3600)} h ago` : `${Math.floor(s / 86400)} d ago`;
};

/** A proof photo fetched with the token in a header, so it never appears in a link. */
function ProofPhoto({ photo, token }: { photo: Photo; token: string }) {
  const [src, setSrc] = useState<string | null>(null);
  // "gone" only when the API says the photo no longer exists; any other failure can be retried.
  const [failed, setFailed] = useState<"gone" | "error" | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!photo.url || !token) return;
    let url: string | null = null;
    let left = false;
    let retry: ReturnType<typeof setTimeout> | null = null;
    const load = (tries: number) =>
      fetch(photo.url!, { headers: { Authorization: `Bearer ${token}` } })
        .then((r) => {
          if (r.ok) return r.blob();
          throw new Error(String(r.status));
        })
        .then((b) => {
          url = URL.createObjectURL(b);
          if (!left) setSrc(url);
        })
        .catch((e: Error) => {
          if (left) return;
          if (e.message === "404") setFailed("gone");
          else if (tries > 0) retry = setTimeout(() => load(tries - 1), 1500); // a blip on the network or a slow store: try again
          else setFailed("error");
        });
    load(2);
    return () => {
      left = true;
      if (retry) clearTimeout(retry);
      if (url) URL.revokeObjectURL(url);
    };
  }, [photo.url, token, attempt]);
  return (
    <div className="overflow-hidden rounded-[10px] border border-white/10 bg-black/40">
      {src ? (
        <a href={src} target="_blank" rel="noreferrer noopener">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={src} alt="proof photo" className="aspect-square w-full object-cover" />
        </a>
      ) : (
        <div className="flex aspect-square flex-col items-center justify-center gap-2 font-serif text-[13px] text-white/40">
          {photo.expired || failed === "gone" ? (
            "Photo gone"
          ) : failed === "error" ? (
            <>
              <span>Could not load the photo.</span>
              <button onClick={() => { setFailed(null); setAttempt((n) => n + 1); }} className="rounded-full border border-white/20 px-3 py-1 text-white/80 hover:border-white hover:text-white">Retry</button>
            </>
          ) : (
            "Loading…"
          )}
        </div>
      )}
      {photo.distanceM != null && <div className="px-2 py-1 font-serif text-[11px] text-white/50">{photo.distanceM} m from the place</div>}
    </div>
  );
}
