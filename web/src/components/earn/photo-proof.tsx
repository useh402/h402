"use client";

import { Camera, Check, X } from "lucide-react";
import { useRef, useState } from "react";
import { API_URL, getToken } from "@/lib/api";

type Shot = { id: string; preview: string; distanceM: number | null };

/**
 * Proof photos for a task: taken with the camera now, with the capture code on paper in the shot. Each photo is shrunk
 * in the browser and sent straight away, with the phone's location when the task has a place to be.
 */
export function PhotoProof({ taskId, code, needsLocation, onChange, note, onNote, write = null }: { taskId: string; code: string | null; needsLocation: boolean; onChange: (ids: string[]) => void; note: string; onNote: (s: string) => void; write?: string | null }) {
  const [shots, setShots] = useState<Shot[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const locate = () =>
    new Promise<GeolocationPosition | null>((resolve) => {
      if (!needsLocation || !navigator.geolocation) return resolve(null);
      navigator.geolocation.getCurrentPosition(resolve, () => resolve(null), { enableHighAccuracy: true, timeout: 15_000, maximumAge: 30_000 });
    });

  const onFile = async (file: File | undefined) => {
    if (input.current) input.current.value = "";
    if (!file) return;
    setError(null);
    setBusy(true);
    try {
      const [blob, pos] = await Promise.all([shrink(file), locate()]);
      if (needsLocation && !pos) throw new Error("Allow location access in your browser and try again. The photo must be taken at the place.");
      const headers: Record<string, string> = { Authorization: `Bearer ${getToken() ?? ""}`, "Content-Type": blob.type };
      if (pos) {
        headers["x-photo-lat"] = String(pos.coords.latitude);
        headers["x-photo-lng"] = String(pos.coords.longitude);
        headers["x-photo-accuracy"] = String(Math.round(pos.coords.accuracy));
      }
      const r = await fetch(`${API_URL}/v1/tasks/${taskId}/photos`, { method: "POST", headers, body: blob });
      const j = await r.json();
      if (!r.ok) throw new Error(j.message || j.error || `upload failed (${r.status})`);
      const shot = { id: j.photoId as string, preview: URL.createObjectURL(blob), distanceM: j.distanceM as number | null };
      const next = [...shots, shot];
      setShots(next);
      onChange(next.map((s) => s.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const remove = (id: string) => {
    const next = shots.filter((s) => s.id !== id);
    setShots(next);
    onChange(next.map((s) => s.id));
  };

  return (
    <div className="space-y-4">
      {code && (
        <div className="flex flex-wrap items-center gap-4 rounded-[14px] border border-[#3b6cff]/40 bg-[#3b6cff]/10 p-4">
          <div className="font-mono text-[34px] font-semibold tracking-[0.25em] text-white">{code}</div>
          <div className="min-w-[200px] flex-1 font-serif text-[14px] leading-[1.4] text-white/80">
            Write this code on a piece of paper and keep it in every photo. It proves the photos were taken now, for this task.
          </div>
        </div>
      )}
      <div className="rounded-[12px] border border-dashed border-white/20 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="font-serif text-[14px] text-white/70">
            Photos taken now <span className="text-white/45">· {shots.length} of 3</span>
            {needsLocation && <span className="ml-2 text-white/45">· your location is sent with each photo</span>}
          </div>
          <label className={`inline-flex h-[42px] cursor-pointer items-center gap-2 rounded-full border px-4 font-serif text-[14px] ${shots.length >= 3 || busy ? "border-white/10 text-white/35" : "border-white/30 text-white hover:bg-white/[0.06]"}`}>
            <Camera className="h-4 w-4" strokeWidth={1.8} />
            {busy ? "Sending…" : shots.length === 0 ? "Open the camera" : "Add another"}
            <input ref={input} type="file" accept="image/*" capture="environment" disabled={shots.length >= 3 || busy} onChange={(e) => onFile(e.target.files?.[0])} className="hidden" />
          </label>
        </div>
        {shots.length > 0 && (
          <div className="mt-3 grid grid-cols-3 gap-2">
            {shots.map((s) => (
              <div key={s.id} className="group relative overflow-hidden rounded-[10px] border border-white/10">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={s.preview} alt="" className="aspect-square w-full object-cover" />
                <span className="absolute left-2 top-2 inline-flex items-center gap-1 rounded-full bg-black/60 px-2 py-0.5 font-serif text-[11px] text-[#9be36b]"><Check className="h-3 w-3" strokeWidth={3} />sent{s.distanceM != null ? ` · ${s.distanceM} m away` : ""}</span>
                <button type="button" onClick={() => remove(s.id)} aria-label="Remove" className="absolute right-2 top-2 rounded-full bg-black/60 p-1 text-white/80 hover:text-white"><X className="h-3.5 w-3.5" /></button>
              </div>
            ))}
          </div>
        )}
        {error && <p className="mt-3 font-serif text-[13px] text-red-300">{error}</p>}
        <p className="mt-3 font-serif text-[12px] text-white/40">The camera opens directly. Pictures from your gallery, screenshots and photos of a screen are not accepted.</p>
      </div>
      {write ? (
        <label className="block">
          <span className="font-serif text-[14px] text-white/80">Type it out as well <span className="text-white/45">· required</span></span>
          <span className="mt-1 block font-serif text-[14px] text-white/60">{write}</span>
          <textarea value={note} onChange={(e) => onNote(e.target.value)} rows={3} placeholder="What the photo shows, in your own words" className={`mt-2 w-full rounded-[12px] border bg-black/30 px-4 py-3 font-serif text-[15px] text-white outline-none placeholder:text-white/35 ${note.trim().length >= 5 ? "border-white/10" : "border-[#3b6cff]/40"}`} />
        </label>
      ) : (
        <textarea value={note} onChange={(e) => onNote(e.target.value)} rows={2} placeholder="One line on what you saw (optional)" className="w-full rounded-[12px] border border-white/10 bg-black/30 px-4 py-3 font-serif text-[15px] text-white outline-none placeholder:text-white/35" />
      )}
    </div>
  );
}

/** Shrinks a photo in the browser to at most 1600px on the long side, JPEG. Keeps uploads small on a phone connection. */
async function shrink(file: File): Promise<Blob> {
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const i = new Image();
      i.onload = () => resolve(i);
      i.onerror = () => reject(new Error("That file is not a photo this browser can read."));
      i.src = url;
    });
    const scale = Math.min(1, 1600 / Math.max(img.width, img.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(img.width * scale);
    canvas.height = Math.round(img.height * scale);
    canvas.getContext("2d")!.drawImage(img, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.85));
    if (!blob) throw new Error("Could not prepare the photo.");
    return blob;
  } finally {
    URL.revokeObjectURL(url);
  }
}
