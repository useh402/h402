"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

export type Pin = { id: string; title: string; subtitle: string; lat: number; lng: number; exact: boolean; weight: number };

const R = 100;

/** lat/lng to a point on the sphere, in the same orientation as the equirectangular texture. */
export function toVector(lat: number, lng: number, r = R) {
  const phi = ((90 - lat) * Math.PI) / 180;
  const theta = ((90 - lng) * Math.PI) / 180;
  return new THREE.Vector3(r * Math.sin(phi) * Math.cos(theta), r * Math.cos(phi), r * Math.sin(phi) * Math.sin(theta));
}

/**
 * A dark globe with a pin for every task that has a place. Drag to turn it, scroll to zoom, hover a pin for the task,
 * click to open it. `focus` flies the camera to a place.
 */
export function Globe({ pins, focus, onHover, onPick, still = false }: { pins: Pin[]; focus: { lat: number; lng: number; zoom?: number } | null; onHover: (pin: Pin | null, x: number, y: number) => void; onPick: (pin: Pin) => void; still?: boolean }) {
  const host = useRef<HTMLDivElement>(null);
  const scene = useRef<{ pins: THREE.Group; camera: THREE.PerspectiveCamera; controls: OrbitControls; fly: (lat: number, lng: number, dist: number) => void; renderer: THREE.WebGLRenderer } | null>(null);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(el.clientWidth, el.clientHeight);
    el.appendChild(renderer.domElement);
    const sc = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(38, el.clientWidth / el.clientHeight, 1, 2000);
    const start = toVector(39, -98, R * 2.7);
    camera.position.copy(start);

    const loader = new THREE.TextureLoader();
    const material = new THREE.MeshPhongMaterial({ color: 0x1a2340, shininess: 12, specular: 0x334466 });
    const globe = new THREE.Mesh(new THREE.SphereGeometry(R, 128, 128), material);
    globe.rotation.y = -Math.PI / 2; // the texture's prime meridian lines up with the lat/lng conversion used for pins
    sc.add(globe);
    loader.load("/earth-blue-marble.jpg", (tex) => {
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.anisotropy = 8;
      material.map = tex;
      material.color.set(0xffffff);
      material.needsUpdate = true;
    });
    loader.load("/earth-topology.png", (tex) => {
      material.bumpMap = tex;
      material.bumpScale = 0.9;
      material.needsUpdate = true;
    });
    loader.load("/earth-water.png", (tex) => {
      material.specularMap = tex;
      material.needsUpdate = true;
    });
    loader.load("/night-sky.png", (tex) => {
      tex.colorSpace = THREE.SRGBColorSpace;
      const stars = new THREE.Mesh(new THREE.SphereGeometry(R * 12, 32, 32), new THREE.MeshBasicMaterial({ map: tex, side: THREE.BackSide, transparent: true, opacity: 0.55 }));
      sc.add(stars);
    });
    sc.add(new THREE.AmbientLight(0xffffff, 1.9));
    const sun = new THREE.DirectionalLight(0xffffff, 1.3);
    sun.position.set(-250, 150, 220);
    sc.add(sun);
    // A faint atmosphere: a slightly larger sphere drawn from the back.
    const glow = new THREE.Mesh(new THREE.SphereGeometry(R * 1.04, 64, 64), new THREE.MeshBasicMaterial({ color: 0x5c8bff, transparent: true, opacity: 0.16, side: THREE.BackSide }));
    sc.add(glow);


    const pinGroup = new THREE.Group();
    sc.add(pinGroup);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.minDistance = R * 1.35;
    controls.maxDistance = R * 4;
    controls.enablePan = false;
    controls.autoRotate = !still;
    controls.autoRotateSpeed = 0.35;
    controls.addEventListener("start", () => (controls.autoRotate = false));

    // Fly: ease the camera toward a place while keeping its distance.
    let flight: { from: THREE.Vector3; to: THREE.Vector3; t: number } | null = null;
    const fly = (lat: number, lng: number, dist: number) => {
      controls.autoRotate = false;
      flight = { from: camera.position.clone(), to: toVector(lat, lng, dist), t: 0 };
    };

    const ray = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    let hovered: THREE.Object3D | null = null;
    const pick = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      mouse.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(mouse, camera);
      const hits = ray.intersectObjects(pinGroup.children, true).filter((h) => h.object.userData.pin);
      // A pin behind the globe is not visible: its hit must come before the globe's.
      const globeHit = ray.intersectObject(globe, false)[0];
      const hit = hits.find((h) => !globeHit || h.distance < globeHit.distance + 2);
      return hit ? hit.object : null;
    };
    const onMove = (e: PointerEvent) => {
      const o = pick(e);
      if (o !== hovered) {
        hovered = o;
        el.style.cursor = o ? "pointer" : "grab";
        onHover(o ? (o.userData.pin as Pin) : null, e.clientX, e.clientY);
      } else if (o) {
        onHover(o.userData.pin as Pin, e.clientX, e.clientY);
      }
    };
    const onClick = (e: PointerEvent) => {
      const o = pick(e);
      if (o) onPick(o.userData.pin as Pin);
    };
    el.addEventListener("pointermove", onMove);
    el.addEventListener("click", onClick);
    el.addEventListener("pointerleave", () => onHover(null, 0, 0));

    let frame = 0;
    const tick = () => {
      frame = requestAnimationFrame(tick);
      if (flight) {
        flight.t = Math.min(1, flight.t + 0.03);
        const k = 1 - Math.pow(1 - flight.t, 3);
        camera.position.copy(flight.from.clone().lerp(flight.to, k).setLength(THREE.MathUtils.lerp(flight.from.length(), flight.to.length(), k)));
        if (flight.t >= 1) flight = null;
      }
      controls.update();
      // Pins keep a steady size on screen: smaller as the camera comes closer. Hovered pins stay larger.
      const k = THREE.MathUtils.clamp(camera.position.length() / (R * 2.7), 0.3, 1.1);
      const s = k * (1 + 0.08 * Math.sin(performance.now() / 500));
      pinGroup.children.forEach((p) => {
        const head = p.getObjectByName("head");
        if (head) head.scale.setScalar(head === hovered ? k * 1.6 : s);
        const halo = p.getObjectByName("halo");
        if (halo) halo.scale.setScalar(k);
      });
      renderer.render(sc, camera);
    };
    tick();

    const onResize = () => {
      renderer.setSize(el.clientWidth, el.clientHeight);
      camera.aspect = el.clientWidth / el.clientHeight;
      camera.updateProjectionMatrix();
    };
    const ro = new ResizeObserver(onResize);
    ro.observe(el);
    scene.current = { pins: pinGroup, camera, controls, fly, renderer };
    return () => {
      cancelAnimationFrame(frame);
      ro.disconnect();
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("click", onClick);
      controls.dispose();
      renderer.dispose();
      el.removeChild(renderer.domElement);
      scene.current = null;
    };
    // The scene is built once; pins and focus are applied by the effects below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [still]);

  // Pins: one small sphere on a stem per task; a group of tasks in one city stacks their stems.
  useEffect(() => {
    const s = scene.current;
    if (!s) return;
    s.pins.clear();
    const perPlace: Record<string, number> = {};
    for (const pin of pins) {
      const key = `${pin.lat.toFixed(2)},${pin.lng.toFixed(2)}`;
      const n = perPlace[key] ?? 0;
      perPlace[key] = n + 1;
      const base = toVector(pin.lat, pin.lng, R);
      const dir = base.clone().normalize();
      const height = 4 + n * 2.2 + Math.min(6, pin.weight);
      const top = dir.clone().multiplyScalar(R + height);
      const color = pin.id === "you" ? 0x4df0ff : pin.exact ? 0xffd166 : 0x7ea2ff;
      const group = new THREE.Group();
      const stem = new THREE.Line(new THREE.BufferGeometry().setFromPoints([base, top]), new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.7 }));
      group.add(stem);
      const head = new THREE.Mesh(new THREE.SphereGeometry(1.0 + Math.min(0.8, pin.weight / 20), 12, 12), new THREE.MeshBasicMaterial({ color }));
      head.position.copy(top);
      head.name = "head";
      head.userData.pin = pin;
      group.add(head);
      const halo = new THREE.Mesh(new THREE.RingGeometry(1.2, 1.9, 24), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.35, side: THREE.DoubleSide }));
      halo.name = "halo";
      halo.position.copy(base.clone().multiplyScalar(1.002));
      halo.lookAt(base.clone().multiplyScalar(2));
      group.add(halo);
      s.pins.add(group);
    }
  }, [pins]);

  useEffect(() => {
    const s = scene.current;
    if (!s || !focus) return;
    s.fly(focus.lat, focus.lng, R * (focus.zoom ?? 1.9));
  }, [focus]);

  return <div ref={host} className="h-full w-full cursor-grab active:cursor-grabbing" />;
}
