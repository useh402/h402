"use client";

import { useEffect } from "react";
import { API_URL } from "./api";
import { useLang, type Lang } from "./i18n";

/**
 * Translates everything on the page that the dictionary did not: task titles and
 * instructions from the API, long pages, labels in deep components. It walks the
 * rendered page for English text, asks the task service for translations (made
 * once and kept there), and swaps the text in place. A watcher keeps up with what
 * React adds or changes afterwards. Strings already in the chosen language are
 * left alone, so the dictionary's translations stay as they are.
 */

const SKIP_TAGS = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "CODE", "PRE", "TEXTAREA", "INPUT", "SELECT", "OPTION", "KBD", "SVG"]);
const ATTRS = ["placeholder", "title", "aria-label"];
const CACHE_KEY = "h402.tr.";
const MAX_CACHE = 4000;

const hasLetters = (s: string) => /[A-Za-z]{2,}/.test(s);
const isTranslated = (lang: Lang, s: string) => (lang === "zh" ? /[㐀-鿿]/.test(s) : true);
/** Mostly code, addresses or numbers: leave it. */
const looksLikeData = (s: string) => /^0x[0-9a-fA-F]{6,}/.test(s) || /^[\d\s$.,%:/-]+$/.test(s) || /^[A-Z0-9_]{2,}$/.test(s) || /^https?:\/\//.test(s);

class Translator {
  lang: Lang;
  cache = new Map<string, string>();
  pending = new Set<string>();
  waiting = new Map<string, (() => void)[]>();
  originals = new WeakMap<Text, string>();
  attrOriginals = new WeakMap<Element, Record<string, string>>();
  timer: ReturnType<typeof setTimeout> | null = null;
  observer: MutationObserver | null = null;
  applying = false;

  constructor(lang: Lang) {
    this.lang = lang;
    try {
      const raw = localStorage.getItem(CACHE_KEY + lang);
      if (raw) for (const [k, v] of Object.entries(JSON.parse(raw) as Record<string, string>)) this.cache.set(k, v);
    } catch {}
  }

  start(root: HTMLElement) {
    this.walk(root);
    this.observer = new MutationObserver((muts) => {
      if (this.applying) return;
      for (const m of muts) {
        if (m.type === "characterData" && m.target instanceof Text) this.node(m.target);
        for (const n of m.addedNodes) {
          if (n instanceof Text) this.node(n);
          else if (n instanceof HTMLElement) this.walk(n);
        }
      }
    });
    this.observer.observe(root, { subtree: true, childList: true, characterData: true });
  }

  stop() {
    this.observer?.disconnect();
    if (this.timer) clearTimeout(this.timer);
  }

  /** Puts every text back as React wrote it, for the switch back to English. */
  restore(root: HTMLElement) {
    this.applying = true;
    const it = document.createNodeIterator(root, NodeFilter.SHOW_TEXT);
    let n: Node | null;
    while ((n = it.nextNode())) {
      const o = this.originals.get(n as Text);
      if (o !== undefined && (n as Text).nodeValue !== o) (n as Text).nodeValue = o;
    }
    root.querySelectorAll<HTMLElement>("[data-tr-attrs]").forEach((el) => {
      const o = this.attrOriginals.get(el);
      if (o) for (const [k, v] of Object.entries(o)) el.setAttribute(k, v);
      el.removeAttribute("data-tr-attrs");
    });
    this.applying = false;
  }

  walk(root: HTMLElement) {
    if (root.closest?.("[data-no-translate]")) return;
    const it = document.createNodeIterator(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, {
      acceptNode: (n) => {
        if (n instanceof Element) return SKIP_TAGS.has(n.tagName) || n.hasAttribute("data-no-translate") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    let n: Node | null;
    while ((n = it.nextNode())) {
      if (n instanceof Text) this.node(n);
      else if (n instanceof Element) this.attrs(n);
    }
  }

  node(t: Text) {
    const parent = t.parentElement;
    if (!parent || parent.closest("[data-no-translate]") || SKIP_TAGS.has(parent.tagName)) return;
    const raw = t.nodeValue ?? "";
    const text = raw.trim();
    if (!text || !hasLetters(text) || isTranslated(this.lang, text) || looksLikeData(text)) return;
    if (!this.originals.has(t)) this.originals.set(t, raw);
    const lead = raw.slice(0, raw.length - raw.trimStart().length);
    const trail = raw.slice(raw.trimEnd().length);
    const hit = this.cache.get(text);
    if (hit) {
      this.set(t, lead + hit + trail);
      return;
    }
    this.request(text, () => {
      const now = (t.nodeValue ?? "").trim();
      const tr = this.cache.get(text);
      if (tr && now === text) this.set(t, lead + tr + trail);
    });
  }

  attrs(el: Element) {
    for (const a of ATTRS) {
      const v = el.getAttribute(a);
      if (!v || !hasLetters(v) || isTranslated(this.lang, v) || looksLikeData(v)) continue;
      const o = this.attrOriginals.get(el) ?? {};
      if (!(a in o)) {
        o[a] = v;
        this.attrOriginals.set(el, o);
        el.setAttribute("data-tr-attrs", "1");
      }
      const hit = this.cache.get(v);
      if (hit) {
        el.setAttribute(a, hit);
        continue;
      }
      this.request(v, () => {
        const tr = this.cache.get(v);
        if (tr && el.getAttribute(a) === v) el.setAttribute(a, tr);
      });
    }
  }

  set(t: Text, value: string) {
    if (t.nodeValue === value) return;
    this.applying = true;
    t.nodeValue = value;
    this.applying = false;
  }

  request(text: string, done: () => void) {
    const list = this.waiting.get(text) ?? [];
    list.push(done);
    this.waiting.set(text, list);
    this.pending.add(text);
    if (!this.timer) this.timer = setTimeout(() => this.flush(), 60);
  }

  async flush() {
    this.timer = null;
    const texts = [...this.pending].slice(0, 60);
    texts.forEach((t) => this.pending.delete(t));
    if (this.pending.size) this.timer = setTimeout(() => this.flush(), 20);
    if (!texts.length) return;
    try {
      const r = await fetch(`${API_URL}/v1/translate`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ lang: this.lang, texts }) });
      if (!r.ok) throw new Error(String(r.status));
      const { translations } = (await r.json()) as { translations: string[] };
      texts.forEach((t, i) => {
        if (translations[i] && translations[i] !== t) this.cache.set(t, translations[i]);
      });
      this.persist();
    } catch {
      // Left in English this time; the next walk tries again.
    }
    for (const t of texts) {
      const cbs = this.waiting.get(t) ?? [];
      this.waiting.delete(t);
      cbs.forEach((cb) => cb());
    }
  }

  persist() {
    try {
      const entries = [...this.cache.entries()].slice(-MAX_CACHE);
      localStorage.setItem(CACHE_KEY + this.lang, JSON.stringify(Object.fromEntries(entries)));
    } catch {}
  }
}

/** Mounted once; translates the page whenever a language other than English is chosen. */
export function AutoTranslate() {
  const { lang } = useLang();
  useEffect(() => {
    if (lang === "en") return;
    const root = document.body;
    const tr = new Translator(lang);
    tr.start(root);
    return () => {
      tr.stop();
      tr.restore(root);
    };
  }, [lang]);
  return null;
}
