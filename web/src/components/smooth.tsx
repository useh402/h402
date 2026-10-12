"use client";

import { cancelFrame, frame, motion, useScroll, useSpring, type FrameData } from "framer-motion";
import { ReactLenis, useLenis } from "lenis/react";
import { useEffect, type ReactNode } from "react";

/**
 * Inertia scrolling for the whole site. Lenis moves the page toward the wheel
 * position a little each frame, so scrolling glides instead of stepping. It is
 * ticked from Framer Motion's frame loop, so scroll, scroll-linked values and
 * every animation share one requestAnimationFrame. Reduced-motion users get
 * plain native scrolling.
 */
const LENIS = {
  autoRaf: false,
  lerp: 0.085,
  wheelMultiplier: 0.9,
  smoothWheel: true,
  syncTouch: false,
  anchors: { offset: -96 },
  stopInertiaOnNavigate: true,
} as const;

export function SmoothScroll({ children }: { children: ReactNode }) {
  return (
    <ReactLenis root options={LENIS}>
      <Tick />
      {children}
    </ReactLenis>
  );
}

function Tick() {
  const lenis = useLenis();
  useEffect(() => {
    if (!lenis) return;
    const update = ({ timestamp }: FrameData) => lenis.raf(timestamp);
    frame.update(update, true);
    return () => cancelFrame(update);
  }, [lenis]);
  return null;
}

/** Stops the page behind a modal from scrolling while `locked` is true. */
export function useScrollLock(locked: boolean) {
  const lenis = useLenis();
  useEffect(() => {
    if (!lenis) return;
    if (locked) lenis.stop();
    else lenis.start();
    return () => lenis.start();
  }, [lenis, locked]);
}

/** A hairline across the top of the screen showing how far down the page the reader is. */
export function ScrollProgress() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 180, damping: 36, mass: 0.4, restDelta: 0.001 });
  return (
    <motion.div
      aria-hidden
      style={{ scaleX, transformOrigin: "0% 50%" }}
      className="pointer-events-none fixed inset-x-0 top-0 z-[70] h-[2px] bg-gradient-to-r from-[#3b6cff] via-[#8fa8ff] to-white/80"
    />
  );
}

/** Each page fades in as it mounts. Opacity only: a transform here would break the fixed navigation inside the page. */
export function PageFade({ children }: { children: ReactNode }) {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }} className="flex min-h-full flex-1 flex-col">
      {children}
    </motion.div>
  );
}
