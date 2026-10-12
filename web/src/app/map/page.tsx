"use client";

import { useReducedMotion } from "framer-motion";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Globe, type Pin } from "@/components/globe";
import { Nav } from "@/components/nav";
import { RequesterMark } from "@/components/board/requester";
import { API_URL, money } from "@/lib/api";
import { labelOf } from "@/lib/types";

type MapTask = { taskId: string; title: string; type: string; categoryLabel: string | null; location: string; price: number; requester: string | null; deadline: number; lat: number; lng: number; exact: boolean; photos: boolean; mapsUrl: string | null };

export default function MapPage() {
  const router = useRouter();
  const still = !!useReducedMotion();
  const [tasks, setTasks] = useState<MapTask[]>([]);
  const [remote, setRemote] = useState(0);
  const [hover, setHover] = useState<{ pin: Pin; x: number; y: number } | null>(null);
  const [focus, setFocus] = useState<{ lat: number; lng: number; zoom?: number } | null>(null);
  const [city, setCity] = useState<string | null>(null);
  const [down, setDown] = useState(false);
  const [me, setMe] = useState<{ lat: number; lng: number } | null>(null);
  const [locating, setLocating] = useState(false);

  useEffect(() => {
    const load = () =>
      fetch(`${API_URL}/v1/tasks/map`)
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
        .then((d: { tasks: MapTask[]; remote: number }) => {
          setTasks(d.tasks);
          setRemote(d.remote);
          setDown(false);
        })
        .catch(() => setDown(true));
    const t = setTimeout(load, 0);
    const id = setInterval(load, 30_000);
    return () => {
      clearTimeout(t);
      clearInterval(id);
    };
  }, []);

  const pins = useMemo<Pin[]>(() => {
    const p: Pin[] = tasks.map((t) => ({ id: t.taskId, title: t.title, subtitle: `${money(t.price)} · ${t.location}${t.exact ? "" : " (city)"}`, lat: t.lat, lng: t.lng, exact: t.exact, weight: t.price / 1e6 }));
    if (me) p.push({ id: "you", title: "You are here", subtitle: "Your location, from this device", lat: me.lat, lng: me.lng, exact: true, weight: 3 });
    return p;
  }, [tasks, me]);
  const km = (a: { lat: number; lng: number }, b: { lat: number; lng: number }) => {
    const r = Math.PI / 180;
    const x = Math.sin(((b.lat - a.lat) * r) / 2) ** 2 + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(((b.lng - a.lng) * r) / 2) ** 2;
    return 6371 * 2 * Math.atan2(Math.sqrt(x), Math.sqrt(1 - x));
  };
  const locate = () => {
    if (!navigator.geolocation) return;
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const here = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        setMe(here);
        setFocus({ ...here, zoom: 1.7 });
        setLocating(false);
      },
      () => setLocating(false),
      { enableHighAccuracy: true, timeout: 15000 },
    );
  };
  const cities = useMemo(() => {
    const m: Record<string, { lat: number; lng: number; tasks: MapTask[] }> = {};
    for (const t of tasks) {
      const key = t.location;
      if (!m[key]) m[key] = { lat: t.exact ? t.lat : t.lat, lng: t.lng, tasks: [] };
      m[key].tasks.push(t);
    }
    return Object.entries(m).sort((a, b) => b[1].tasks.length - a[1].tasks.length);
  }, [tasks]);
  const shown = (city ? tasks.filter((t) => t.location === city) : tasks).slice().sort((a, b) => (me ? km(me, a) - km(me, b) : 0));

  return (
    <div className="min-h-screen bg-[#080808] text-white">
      <Nav />
      <main className="mx-auto max-w-[1600px] px-4 pb-24 pt-[90px] sm:px-8 sm:pt-[110px]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="flex items-center gap-2.5 font-serif text-[14px] text-white/70"><span className="h-[5px] w-[5px] bg-[#3b6cff]" />Map</div>
            <h1 className="mt-3 font-serif text-[34px] font-light leading-[1.06] tracking-[-1px] sm:text-[52px] sm:tracking-[-2px]">Where the work <em className="italic">is</em>.</h1>
          </div>
          <p className="max-w-[520px] font-serif text-[15px] font-light leading-[1.45] text-white/60">
            Every open task with a place. Gold pins need you at an exact spot; blue pins are anywhere in that city. Drag to turn, scroll to zoom, click a pin to open the task.
            {remote > 0 && <> {remote} more can be done from anywhere; they are on the <Link href="/tasks" className="text-white underline">board</Link>.</>}
          </p>
        </div>

        <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_380px]">
          <div className="relative h-[52vh] min-h-[360px] overflow-hidden rounded-[22px] border border-white/[0.1] bg-[radial-gradient(60%_60%_at_50%_40%,#0f1630_0%,#080808_70%)] lg:h-[72vh]">
            <Globe pins={pins} focus={focus} still={still} onHover={(pin, x, y) => setHover(pin ? { pin, x, y } : null)} onPick={(pin) => pin.id !== "you" && router.push(`/tasks/${pin.id}`)} />
            <button onClick={locate} disabled={locating} className="absolute right-4 top-4 h-[38px] rounded-full border border-white/20 bg-black/50 px-4 font-serif text-[13px] text-white backdrop-blur hover:bg-black/70 disabled:opacity-60">
              {locating ? "Finding you…" : me ? "Centre on me" : "Show my location"}
            </button>
            {hover && (
              <div className="pointer-events-none fixed z-50 max-w-[280px] rounded-[12px] border border-white/15 bg-[#0c0c12]/95 px-3.5 py-2.5 shadow-xl backdrop-blur" style={{ left: hover.x + 14, top: hover.y + 14 }}>
                <div className="font-serif text-[14px] leading-[1.3] text-white">{hover.pin.title}</div>
                <div className="mt-1 font-mono text-[12px] text-[#9be36b]">{hover.pin.subtitle}</div>
              </div>
            )}
            <div className="pointer-events-none absolute bottom-4 left-4 flex gap-4 font-serif text-[12px] text-white/60">
              <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-[#ffd166]" />Exact spot</span>
              <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-[#7ea2ff]" />In the city</span>
              {me && <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-[#4df0ff]" />You</span>}
            </div>
            {down && tasks.length === 0 && <div className="absolute inset-x-4 top-4 rounded-[12px] border border-amber-300/30 bg-amber-300/10 p-3 font-serif text-[13px] text-amber-100">The map cannot reach the service right now. It retries on its own.</div>}
            {!down && tasks.length === 0 && <div className="absolute inset-x-4 top-4 rounded-[12px] border border-white/10 bg-black/40 p-3 font-serif text-[13px] text-white/60">No task has a place right now.</div>}
          </div>

          <aside className="space-y-4">
            <div className="rounded-[18px] border border-white/[0.1] bg-[#0b0b0e] p-4">
              <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-white/45">Places</div>
              <div className="mt-3 flex flex-wrap gap-2">
                <button onClick={() => { setCity(null); setFocus({ lat: 39, lng: -98, zoom: 2.7 }); }} className={`rounded-full border px-3 py-1.5 font-serif text-[13px] ${city === null ? "border-white bg-white text-[#0a0a0f]" : "border-white/15 text-white/70 hover:border-white/40"}`}>All · {tasks.length}</button>
                {cities.map(([name, c]) => (
                  <button key={name} onClick={() => { setCity(name); setFocus({ lat: c.lat, lng: c.lng, zoom: 1.6 }); }} className={`rounded-full border px-3 py-1.5 font-serif text-[13px] ${city === name ? "border-white bg-white text-[#0a0a0f]" : "border-white/15 text-white/70 hover:border-white/40"}`}>
                    {name} · {c.tasks.length}
                  </button>
                ))}
              </div>
            </div>
            <div className="max-h-[60vh] space-y-2 overflow-y-auto pr-1">
              {shown.map((t) => (
                <div key={t.taskId} className="group flex items-start gap-3 rounded-[14px] border border-white/[0.08] bg-white/[0.02] p-3 hover:border-white/25">
                  <RequesterMark requester={t.requester} size={28} />
                  <div className="min-w-0 flex-1">
                    <Link href={`/tasks/${t.taskId}`} className="block font-serif text-[15px] leading-[1.3] text-white/95 hover:text-white">{t.title}</Link>
                    <div className="mt-1 font-serif text-[12px] text-white/50">{labelOf(t.type)} · {t.location}{t.exact ? " · exact spot" : ""}{t.photos ? " · photos" : ""}{me ? ` · ${Math.round(km(me, t))} km from you` : ""}</div>
                    <div className="mt-2 flex items-center gap-3">
                      <span className="font-mono text-[14px] text-[#9be36b]">{money(t.price)}</span>
                      <button onClick={() => setFocus({ lat: t.lat, lng: t.lng, zoom: 1.45 })} className="font-serif text-[12px] text-white/55 underline hover:text-white">Show on globe</button>
                      {t.mapsUrl && <a href={t.mapsUrl} target="_blank" rel="noreferrer" className="font-serif text-[12px] text-[#9db4ff] underline">Open in Maps ↗</a>}
                      {t.exact && <a href={`https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${t.lat},${t.lng}`} target="_blank" rel="noreferrer" className="font-serif text-[12px] text-[#9db4ff] underline">Street View ↗</a>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}
