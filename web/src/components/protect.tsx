"use client";

import { useEffect, useState } from "react";

/**
 * Makes task content harder to copy out of the page. A browser cannot stop a screenshot outright, so this is a
 * deterrent, not a lock: no selecting, copying, dragging or right-click, the content is covered whenever the page
 * is not in front or a capture key is pressed, and a faint mark of the signed-in wallet makes any capture traceable.
 */
export function Protect({ children, mark }: { children: React.ReactNode; mark?: string | null }) {
  const [covered, setCovered] = useState(false);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const cover = (ms?: number) => {
      setCovered(true);
      if (timer) clearTimeout(timer);
      if (ms) timer = setTimeout(() => setCovered(false), ms);
    };
    const show = () => {
      if (timer) clearTimeout(timer);
      if (!document.hidden && document.hasFocus()) setCovered(false);
    };
    const onVisibility = () => (document.hidden ? cover() : show());
    const onBlur = () => cover();
    const onKey = (e: KeyboardEvent) => {
      const k = e.key.toLowerCase();
      const capture = k === "printscreen" || (e.metaKey && e.shiftKey && ["3", "4", "5", "s"].includes(k)) || (e.ctrlKey && e.shiftKey && k === "s");
      const copy = (e.metaKey || e.ctrlKey) && ["c", "x", "p", "s", "a"].includes(k) && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement);
      if (capture) {
        cover(2500);
        navigator.clipboard?.writeText("").catch(() => {});
      }
      if (copy) e.preventDefault();
    };
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("blur", onBlur);
    window.addEventListener("focus", show);
    window.addEventListener("keydown", onKey, true);
    window.addEventListener("keyup", onKey, true);
    return () => {
      if (timer) clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("blur", onBlur);
      window.removeEventListener("focus", show);
      window.removeEventListener("keydown", onKey, true);
      window.removeEventListener("keyup", onKey, true);
    };
  }, []);

  const stop = (e: React.SyntheticEvent) => {
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
    e.preventDefault();
  };

  return (
    <div className="protect relative select-none" onCopy={stop} onCut={stop} onContextMenu={stop} onDragStart={stop} style={{ WebkitTouchCallout: "none" }}>
      <div className={covered ? "pointer-events-none blur-[18px] transition duration-100" : "transition duration-200"}>{children}</div>
      {mark && (
        <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden rounded-[18px] opacity-[0.07]">
          <div className="absolute -inset-[40%] flex rotate-[-24deg] flex-wrap content-center justify-center gap-x-10 gap-y-8 font-mono text-[12px] text-white">
            {Array.from({ length: 80 }, (_, i) => <span key={i}>{mark}</span>)}
          </div>
        </div>
      )}
      {covered && (
        <div className="absolute inset-0 flex items-center justify-center rounded-[18px] bg-[#0a0a0f]/70 p-6 text-center font-serif text-[15px] text-white/80">
          Task content is hidden while this page is not in front. Click here to continue.
        </div>
      )}
    </div>
  );
}
