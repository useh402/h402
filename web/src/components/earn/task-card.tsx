"use client";

import { useEffect, useState } from "react";
import { PhotoProof } from "./photo-proof";
import { Button } from "./shell";
import { money, type Card } from "@/lib/api";
import { labelOf } from "@/lib/types";

/** `long` is for how long a task stays on the board ("12h 36m"); the default is a running clock for the time to answer. */
export function Countdown({ until, long = false }: { until: number; long?: boolean }) {
  const [now, setNow] = useState(0);
  useEffect(() => {
    const tick = () => setNow(Math.floor(Date.now() / 1000));
    const first = setTimeout(tick, 0);
    const id = setInterval(tick, 1000);
    return () => {
      clearTimeout(first);
      clearInterval(id);
    };
  }, []);
  if (!now) return <span className="font-mono text-[13px] text-white/40">--:--</span>;
  const left = Math.max(0, until - now);
  if (long && left >= 3600) {
    const h = Math.floor(left / 3600);
    return <span className="font-mono text-[13px] text-white/60">{h >= 24 ? `${Math.floor(h / 24)}d ${h % 24}h` : `${h}h ${Math.floor((left % 3600) / 60)}m`}</span>;
  }
  const m = Math.floor(left / 60);
  const s = left % 60;
  return <span className={`font-mono text-[13px] ${left < 20 ? "text-red-300" : "text-white/60"}`}>{m}:{s.toString().padStart(2, "0")}</span>;
}

type Props = { card: Card; onSubmit: (answer: unknown, note: string, confidence?: number) => Promise<void>; onRelease: () => void; onReport?: (reason: string) => void; busy: boolean; practice?: boolean };

export function TaskCard({ card, onSubmit, onRelease, onReport, busy, practice = false }: Props) {
  const [reporting, setReporting] = useState(false);
  const [reportReason, setReportReason] = useState("");
  const p = (card.payload ?? {}) as Record<string, unknown>;
  const [value, setValue] = useState<unknown>(null);
  const [note, setNote] = useState("");
  const [confidence, setConfidence] = useState(0.8);
  const [labels, setLabels] = useState<string[]>([]);
  const [text, setText] = useState("");
  const [shot, setShot] = useState<string | null>(null);
  const [shotError, setShotError] = useState<string | null>(null);

  const onFile = async (file: File | undefined) => {
    setShotError(null);
    if (!file) return setShot(null);
    try {
      setShot(await shrinkImage(file));
    } catch {
      setShotError("Could not read that image. Use a PNG or JPG.");
    }
  };
  const proofKind = String(p.proof ?? "text");
  const write = typeof p.write === "string" ? p.write : null;
  const [photos, setPhotos] = useState<string[]>([]);

  const answer = card.type === "label" ? labels : card.type === "read" || card.type === "answer" ? text : card.type === "do" ? (proofKind === "photos" ? { text: text.trim() || undefined, photos } : { text: text.trim() || undefined, screenshot: shot ?? undefined }) : value;
  const ready =
    card.type === "label"
      ? labels.length > 0
      : card.type === "read" || card.type === "answer"
        ? text.trim().length > 0
        : card.type === "do"
          ? proofKind === "photos"
            ? photos.length > 0 && (!write || text.trim().length >= 5)
            : (proofKind === "screenshot" || text.trim().length >= 5) && (proofKind === "text" || !!shot)
          : value !== null;

  return (
    <div className="rounded-[18px] border border-white/[0.12] bg-[#0d0d14] p-4 sm:p-7">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="rounded-full bg-[#3b6cff]/20 px-3 py-1 font-serif text-[13px] text-[#9db4ff]">{labelOf(card.type)}</span>
          {card.categoryLabel && <span className="font-serif text-[13px] text-white/50">{card.categoryLabel}</span>}
          {practice ? (
            <span className="font-serif text-[15px] text-white/60">Practice question, not paid</span>
          ) : (
            <span className="font-serif text-[15px] text-white/80">{money(card.price)} when accepted</span>
          )}
        </div>
        {!practice && (
          <div className="flex items-center gap-3">
            <span className="font-serif text-[13px] text-white/50" title="The task is held for you until this runs out. After that it goes back on the board.">{card.holdExpiresAt ? "Yours to answer for" : "Closes in"}</span>
            <Countdown until={card.holdExpiresAt ?? card.deadline} long={!card.holdExpiresAt} />
          </div>
        )}
      </div>

      {typeof p.image === "string" && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={p.image} alt="task" className="mt-5 max-h-[360px] w-full rounded-[12px] border border-white/10 object-contain" />
      )}
      {typeof p.text === "string" && <blockquote className="mt-5 rounded-[12px] border border-white/10 bg-white/[0.03] p-4 font-serif text-[17px] font-light">{p.text}</blockquote>}
      {typeof p.item === "string" && <blockquote className="mt-5 rounded-[12px] border border-white/10 bg-white/[0.03] p-4 font-serif text-[17px] font-light">{p.item}</blockquote>}
      {typeof p.question === "string" && <h3 className="mt-5 font-serif text-[20px] font-light leading-[1.25] sm:text-[24px]">{p.question}</h3>}
      {card.type === "do" && typeof p.instructions === "string" && (
        <div className="mt-5">
          <h3 className="font-serif text-[18px] font-light leading-[1.35] whitespace-pre-line sm:text-[22px] sm:leading-[1.3]">{p.instructions}</h3>
          <div className="mt-4 flex flex-wrap items-center gap-3 font-serif text-[14px] text-white/60">
            {typeof p.url === "string" && (
              <a href={p.url} target="_blank" rel="noreferrer noopener" className="rounded-full border border-white/30 px-4 py-2 text-white hover:bg-white/10">
                Open the page ↗
              </a>
            )}
            <span>Proof needed: {proofKind === "photos" ? (write ? "one to three photos taken now with your camera, and what they show typed out" : "one to three photos taken now with your camera") : proofKind === "both" ? "a written note and a photo or screenshot" : proofKind === "screenshot" ? "a photo or screenshot" : "a written note; add a screenshot if you can, so it can be checked"}</span>
            {proofKind !== "text" && <span className="text-white/45">· checked by the operator before it is paid</span>}
          </div>
        </div>
      )}
      {typeof p.rubric === "string" && <p className="mt-2 font-serif text-[14px] text-white/55">Rubric: {p.rubric}</p>}

      <div className="mt-6">
        {card.type === "verify" && (
          <div className="flex gap-3">
            {["yes", "no", "unsure"].map((v) => (
              <Choice key={v} active={value === v} onClick={() => setValue(v)}>
                {v}
              </Choice>
            ))}
          </div>
        )}
        {card.type === "choose" && Array.isArray(p.options) && (
          <div className="grid gap-2">
            {(p.options as string[]).map((o, i) => (
              <Choice key={i} active={value === i} onClick={() => setValue(i)} wide>
                <span className="mr-3 font-mono text-[12px] text-white/40">{i + 1}</span>
                {/^https?:\/\/.+\.(jpg|jpeg|png|webp)(\?.*)?$/i.test(o) || /images\.unsplash\.com/.test(o) ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={o} alt={`option ${i + 1}`} className="inline-block max-h-[160px] rounded-[8px] align-middle" />
                ) : (
                  o
                )}
              </Choice>
            ))}
          </div>
        )}
        {card.type === "rate" && (
          <div className="flex gap-3">
            {[1, 2, 3, 4, 5].map((n) => (
              <Choice key={n} active={value === n} onClick={() => setValue(n)}>
                {n}
              </Choice>
            ))}
          </div>
        )}
        {card.type === "label" && Array.isArray(p.labels) && (
          <div className="flex flex-wrap gap-2">
            {(p.labels as string[]).map((l) => (
              <Choice key={l} active={labels.includes(l)} onClick={() => setLabels(labels.includes(l) ? labels.filter((x) => x !== l) : [...labels, l])}>
                {l}
              </Choice>
            ))}
          </div>
        )}
        {(card.type === "read" || card.type === "answer") && (
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={card.type === "read" ? 4 : 6} placeholder={card.type === "read" ? "Type exactly what the image says" : "Your answer"} className="w-full rounded-[12px] border border-white/15 bg-black/40 p-4 font-serif text-[16px] text-white outline-none focus:border-white/40" />
        )}
        {card.type === "do" && proofKind === "photos" && !practice && (
          <PhotoProof taskId={card.taskId} code={card.captureCode ?? null} needsLocation={!!(p.geo as unknown)} onChange={setPhotos} note={text} onNote={setText} write={write} />
        )}
        {card.type === "do" && proofKind !== "photos" && (
          <div className="space-y-4">
            {proofKind !== "screenshot" && (
              <textarea value={text} onChange={(e) => setText(e.target.value)} rows={4} placeholder="What you did and what you found: who you spoke to, what they said, what the page showed" className="w-full rounded-[12px] border border-white/15 bg-black/40 p-4 font-serif text-[16px] text-white outline-none focus:border-white/40" />
            )}
            {/* Written tasks take a screenshot too, optional, so the answer can be checked against what the person saw. */}
            <div className="rounded-[12px] border border-dashed border-white/20 p-4">
              <label className="font-serif text-[14px] text-white/70">
                Photo or screenshot of the result{proofKind === "text" && <span className="text-white/45"> (optional, helps us verify your answer)</span>}
                <input type="file" accept="image/*" onChange={(e) => onFile(e.target.files?.[0])} className="mt-2 block font-sans text-[13px] text-white/60" />
              </label>
              {shot && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={shot} alt="your screenshot" className="mt-3 max-h-[240px] rounded-[8px] border border-white/10" />
              )}
              {shotError && <p className="mt-2 font-serif text-[13px] text-red-300">{shotError}</p>}
            </div>
          </div>
        )}
        {card.type === "answer" && (
          <label className="mt-3 flex items-center gap-3 font-serif text-[14px] text-white/60">
            Confidence {Math.round(confidence * 100)}%
            <input type="range" min={0} max={1} step={0.05} value={confidence} onChange={(e) => setConfidence(Number(e.target.value))} className="w-48" />
          </label>
        )}
        {card.type !== "read" && card.type !== "answer" && card.type !== "do" && (
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="One sentence why (optional)" className="mt-4 w-full rounded-[12px] border border-white/10 bg-black/30 px-4 py-3 font-serif text-[15px] text-white outline-none focus:border-white/30" />
        )}
      </div>

      {reporting && (
        <div className="mt-6 rounded-[12px] border border-red-400/30 bg-red-400/5 p-4">
          <p className="font-serif text-[14px] text-red-100/80">Report this task. It is taken out of the list for review and you are still paid for your time.</p>
          <input value={reportReason} onChange={(e) => setReportReason(e.target.value)} placeholder="What is wrong with it?" className="mt-3 w-full rounded-[10px] border border-white/10 bg-black/30 px-3 py-2 font-serif text-[14px] text-white outline-none" />
          <div className="mt-3 flex gap-2">
            <Button kind="danger" onClick={() => onReport?.(reportReason)} disabled={busy || reportReason.trim().length < 3}>
              Send report
            </Button>
            <Button kind="ghost" onClick={() => setReporting(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      <div className="mt-7 flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-2">
          <Button kind="ghost" onClick={onRelease} disabled={busy}>
            {practice ? "Leave" : "Skip"}
          </Button>
          {onReport && !reporting && (
            <button type="button" onClick={() => setReporting(true)} className="px-3 font-serif text-[14px] text-white/40 hover:text-red-200">
              Report
            </button>
          )}
        </div>
        <Button onClick={() => onSubmit(answer, note, card.type === "answer" ? confidence : undefined)} disabled={!ready || busy}>
          {busy ? "Sending…" : practice ? "Next" : card.type === "do" ? "Submit proof" : "Submit answer"}
        </Button>
      </div>
    </div>
  );
}

/** Resize a screenshot in the browser so the proof stays small (max 1280px, JPEG). */
async function shrinkImage(file: File): Promise<string> {
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const i = new Image();
      i.onload = () => resolve(i);
      i.onerror = reject;
      i.src = url;
    });
    const scale = Math.min(1, 1280 / Math.max(img.width, img.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(img.width * scale);
    canvas.height = Math.round(img.height * scale);
    canvas.getContext("2d")!.drawImage(img, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.82);
  } finally {
    URL.revokeObjectURL(url);
  }
}

function Choice({ children, active, onClick, wide }: { children: React.ReactNode; active: boolean; onClick: () => void; wide?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`${wide ? "w-full text-left" : ""} rounded-[12px] border px-5 py-3 font-serif text-[16px] capitalize transition ${active ? "border-white bg-white text-[#0a0a0f]" : "border-white/15 bg-white/[0.03] text-white hover:border-white/40"}`}
    >
      {children}
    </button>
  );
}
