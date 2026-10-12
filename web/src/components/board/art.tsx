"use client";

import { RequesterMark, requesterFor } from "./requester";

/** Colour per category, used for the small dot next to the category name. */
const ACCENT: Record<string, string> = {
  calls: "#7ea2ff", go_and_see: "#b89cff", blocked_sites: "#6fe3d6", forms_and_listings: "#f0c36b", real_and_current: "#8de39b", documents_and_receipts: "#f0a36b", judgement: "#d69cff",
  local_knowledge: "#6bc3f0", sorting_and_tagging: "#f06bb8", community_resources: "#6bf0c3", accessibility: "#9cc3ff", business_research: "#f0e06b", research_and_verification: "#dcdcdc", technical: "#6b9cf0", web3: "#a36bf0",
};

export function artFor(category: string | null | undefined) {
  return { accent: (category && ACCENT[category]) || "#7ea2ff" };
}

const GRAIN = "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)' opacity='0.5'/></svg>\")";

/** Square artwork: the task's photo when it has one, otherwise the official mark of the assistant the task is for, on a quiet dark plate. */
export function TaskArt({ image, requester, className = "", big = false }: { category?: string | null; image?: string | null; seed?: string; requester?: string | null; className?: string; big?: boolean }) {
  const r = requesterFor(requester);
  if (image) {
    return (
      <div className={`relative aspect-square w-full overflow-hidden ${className}`}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={image} alt="" className="h-full w-full object-cover transition duration-700 group-hover:scale-[1.04]" loading="lazy" />
        <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent" />
        {r && (
          <div className="absolute bottom-3 left-3 flex items-center gap-2 rounded-full border border-white/15 bg-black/60 py-1 pl-1.5 pr-3 backdrop-blur">
            <RequesterMark requester={requester} size={16} />
            <span className="font-sans text-[12px] font-medium text-white/90">{r.label}</span>
          </div>
        )}
      </div>
    );
  }
  return (
    <div className={`relative aspect-square w-full overflow-hidden bg-[#0b0b0e] ${className}`}>
      <div className="absolute inset-0" style={{ background: `radial-gradient(55% 55% at 50% 42%, ${r?.glow ?? "#3b6cff"}26, transparent 70%)` }} />
      <div className="absolute inset-0 opacity-[0.18] mix-blend-overlay" style={{ backgroundImage: GRAIN }} />
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/15 to-transparent" />
      <div className="absolute inset-0 flex items-center justify-center transition duration-700 group-hover:scale-[1.06]">
        <RequesterMark requester={requester} size={big ? 132 : 84} />
      </div>
      {r && <div className="absolute inset-x-0 bottom-4 text-center font-sans text-[13px] font-medium tracking-[0.02em] text-white/55">{r.label}</div>}
    </div>
  );
}
