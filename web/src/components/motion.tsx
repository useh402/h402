"use client";

import { animate, motion, useInView, useMotionValue, useScroll, useTransform, type MotionValue, type Variants } from "framer-motion";
import { useEffect, useRef, type ReactNode } from "react";

/** The one easing curve used for every reveal on the site: fast out, long soft settle. */
export const EASE = [0.22, 1, 0.36, 1] as const;

/** Fade and rise into view once. */
export function Reveal({ children, delay = 0, y = 20, className }: { children: ReactNode; delay?: number; y?: number; className?: string }) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-12% 0px -12% 0px" }}
      transition={{ duration: 0.9, delay, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}

/**
 * A group whose children appear one after another. Wrap the children in
 * `Item` (or give them `variants={item}`); the gap between them is `gap`.
 */
export function Stagger({ children, gap = 0.06, delay = 0, className }: { children: ReactNode; gap?: number; delay?: number; className?: string }) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-8% 0px" }}
      variants={{ hidden: {}, show: { transition: { staggerChildren: gap, delayChildren: delay } } }}
    >
      {children}
    </motion.div>
  );
}

export const item: Variants = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.75, ease: EASE } },
};

export function Item({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div variants={item} className={className}>
      {children}
    </motion.div>
  );
}

/** The small square and caption above a section: "■ Introduction". */
export function Label({ children, light = false }: { children: ReactNode; light?: boolean }) {
  return (
    <Reveal>
      <div className={`flex items-center gap-2.5 text-[14px] ${light ? "text-white/70" : "text-[#8c8c8c]"}`}>
        <span className="h-[5px] w-[5px] bg-[#3b6cff]" />
        {children}
      </div>
    </Reveal>
  );
}

/**
 * A paragraph whose words brighten one by one as the reader scrolls it into
 * the middle of the screen. Words start at `dim` opacity and end fully bright.
 * Opacity rather than colour: the compositor can tween it without repainting
 * the text every frame.
 */
export function ScrollWords({ text, className, dim = 0.22 }: { text: string; className?: string; dim?: number }) {
  const ref = useRef<HTMLParagraphElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 0.85", "end 0.45"] });
  // Text with spaces brightens word by word; text without them (Chinese) brightens a few characters at a time.
  const spaced = /\s/.test(text);
  const words = spaced ? text.split(" ") : (text.match(/.{1,2}/gu) ?? [text]);
  return (
    <p ref={ref} className={className}>
      {words.map((word, i) => (
        <Word key={`${i}-${word}`} progress={scrollYProgress} range={[i / words.length, (i + 1) / words.length]} dim={dim} space={spaced}>
          {word}
        </Word>
      ))}
    </p>
  );
}

function Word({ children, progress, range, dim, space }: { children: string; progress: MotionValue<number>; range: [number, number]; dim: number; space: boolean }) {
  const opacity = useTransform(progress, range, [dim, 1]);
  return (
    <motion.span style={{ opacity, willChange: "opacity" }} className="inline-block whitespace-pre">
      {children}{space ? " " : ""}
    </motion.span>
  );
}

/**
 * Counts from 0 to `to` the first time it is seen. The number is written
 * straight to the text node each frame; React is not involved while it runs.
 */
export function CountUp({ to, duration = 2.2, className }: { to: number; duration?: number; className?: string }) {
  return <LiveCount value={to} duration={duration} className={className} />;
}

/** A number that counts up when first seen and glides to each new value after that. */
export function LiveCount({ value, format = (n: number) => String(Math.round(n)), duration = 1.8, className }: { value: number; format?: (n: number) => string; duration?: number; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-15% 0px" });
  const count = useMotionValue(0);
  // `format` is a display detail; a new function on each render must not restart the count.
  const fmt = useRef(format);
  useEffect(() => {
    fmt.current = format;
  }, [format]);
  const text = useTransform(count, (n) => fmt.current(n));
  useEffect(() => {
    if (!inView) return;
    const controls = animate(count, value, { duration, ease: EASE });
    return () => controls.stop();
  }, [inView, value, duration, count]);
  return (
    <motion.span ref={ref} className={className}>
      {text}
    </motion.span>
  );
}
