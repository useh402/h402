"use client";

import { useEffect, useRef } from "react";

/**
 * A full-size WebGL canvas running one fragment shader with time, resolution
 * and a smoothed cursor as uniforms. The cursor is tracked on the nearest
 * positioned ancestor, so the light follows the mouse anywhere over the hero.
 */

const VERTEX = `attribute vec2 a; void main(){ gl_Position = vec4(a, 0.0, 1.0); }`;

export function GlCanvas({ fragment, className, speed = 1, mouseStrength = 1 }: { fragment: string; className?: string; speed?: number; mouseStrength?: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const gl = canvas.getContext("webgl", { antialias: false, alpha: false, premultipliedAlpha: false, powerPreference: "high-performance" });
    if (!gl) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const compile = (type: number, source: string) => {
      const shader = gl.createShader(type)!;
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        console.error(gl.getShaderInfoLog(shader));
      }
      return shader;
    };
    const program = gl.createProgram()!;
    gl.attachShader(program, compile(gl.VERTEX_SHADER, VERTEX));
    gl.attachShader(program, compile(gl.FRAGMENT_SHADER, fragment));
    gl.linkProgram(program);
    gl.useProgram(program);
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW);
    const a = gl.getAttribLocation(program, "a");
    gl.enableVertexAttribArray(a);
    gl.vertexAttribPointer(a, 2, gl.FLOAT, false, 0, 0);
    const uRes = gl.getUniformLocation(program, "u_res");
    const uTime = gl.getUniformLocation(program, "u_time");
    const uMouse = gl.getUniformLocation(program, "u_mouse");
    const uStrength = gl.getUniformLocation(program, "u_strength");
    const uTrail = gl.getUniformLocation(program, "u_trail");
    // A short ink trail: the last positions the cursor passed, each with an age that grows every frame.
    const TRAIL = 12;
    const trail = new Float32Array(TRAIL * 3);
    for (let i = 0; i < TRAIL; i++) trail[i * 3 + 2] = 1;
    let lastX = -1;
    let lastY = -1;

    const host = canvas.parentElement ?? canvas;
    const target = { x: 0.5, y: 0.45 };
    const mouse = { x: 0.5, y: 0.45 };
    let strength = 0;
    let targetStrength = 0;
    const onMove = (event: MouseEvent) => {
      const rect = host.getBoundingClientRect();
      target.x = (event.clientX - rect.left) / rect.width;
      target.y = 1 - (event.clientY - rect.top) / rect.height;
      targetStrength = mouseStrength;
      // Add a trail point when the cursor has moved a little, so the ink follows the path, not just the position.
      const dx = target.x - lastX;
      const dy = target.y - lastY;
      if (dx * dx + dy * dy > 0.00012) {
        trail.copyWithin(3, 0, (TRAIL - 1) * 3);
        trail[0] = target.x;
        trail[1] = target.y;
        trail[2] = 0;
        lastX = target.x;
        lastY = target.y;
      }
    };
    const onLeave = () => (targetStrength = 0);
    host.addEventListener("mousemove", onMove);
    host.addEventListener("mouseleave", onLeave);

    // The fog is soft by design, so one shader sample per CSS pixel is plenty. Rendering at retina
    // resolution more than doubled the pixels the fragment shader had to fill every frame.
    const dpr = Math.min(window.devicePixelRatio || 1, 1);
    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      canvas.width = Math.max(1, Math.floor(rect.width * dpr));
      canvas.height = Math.max(1, Math.floor(rect.height * dpr));
      gl.viewport(0, 0, canvas.width, canvas.height);
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);

    let visible = true;
    const io = new IntersectionObserver(([entry]) => (visible = entry?.isIntersecting ?? true));
    io.observe(canvas);

    let frame = 0;
    const start = performance.now();
    const draw = (now: number) => {
      frame = requestAnimationFrame(draw);
      if (!visible) return;
      mouse.x += (target.x - mouse.x) * 0.06;
      mouse.y += (target.y - mouse.y) * 0.06;
      strength += (targetStrength - strength) * 0.05;
      gl.uniform2f(uRes, canvas.width, canvas.height);
      gl.uniform1f(uTime, ((now - start) / 1000) * (reduced ? 0.15 : speed));
      gl.uniform2f(uMouse, mouse.x, mouse.y);
      gl.uniform1f(uStrength, strength);
      for (let i = 0; i < TRAIL; i++) trail[i * 3 + 2] = Math.min(1, trail[i * 3 + 2] + 0.016);
      gl.uniform3fv(uTrail, trail);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
    };
    frame = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      io.disconnect();
      host.removeEventListener("mousemove", onMove);
      host.removeEventListener("mouseleave", onLeave);
    };
  }, [fragment, speed, mouseStrength]);
  return <canvas ref={ref} className={className} aria-hidden />;
}

/**
 * Blue fog, as on the reference: large, slow, soft masses of navy and blue with
 * white cloud banks drifting upper right, black at the bottom, heavy grain. The
 * cursor leaves a small ink-like glow that drifts and fades.
 */
export const SMOKE = `
precision highp float;
uniform vec2 u_res; uniform float u_time; uniform vec2 u_mouse; uniform float u_strength;
uniform vec3 u_trail[12];

float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123); }
float noise(vec2 p){
  vec2 i = floor(p); vec2 f = fract(p);
  f = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
  float a = hash(i), b = hash(i + vec2(1.0, 0.0)), c = hash(i + vec2(0.0, 1.0)), d = hash(i + vec2(1.0, 1.0));
  return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}
float fbm(vec2 p){
  float v = 0.0; float amp = 0.55;
  mat2 rot = mat2(0.8, 0.6, -0.6, 0.8);
  for (int i = 0; i < 5; i++) { v += amp * noise(p); p = rot * p * 1.9 + 1.3; amp *= 0.5; }
  return v;
}
void main(){
  vec2 uv = gl_FragCoord.xy / u_res;
  float aspect = u_res.x / u_res.y;
  vec2 here = vec2(uv.x * aspect, uv.y);
  float t = u_time * 0.03;

  // Big, slow features: the scene is sampled at a low frequency so everything stays soft.
  vec2 p = here * 0.75;
  vec2 q = vec2(fbm(p + vec2(t * 0.6, t * 0.3)), fbm(p + vec2(3.1, 1.7) - t * 0.4));
  vec2 r = vec2(fbm(p + 1.8 * q + vec2(1.7, 9.2) + t * 0.35), fbm(p + 1.8 * q + vec2(8.3, 2.8) - t * 0.25));
  float f = fbm(p + 1.6 * r);
  float g = fbm(p * 0.5 + vec2(-t * 0.2, t * 0.15) + r * 0.6);

  // Tiles: a grid of boxes over the fog. Lighting is computed at each tile's centre, so a tile
  // lights as a whole when the cursor passes near it, then fades.
  float cellPx = 64.0;
  vec2 cellId = floor(gl_FragCoord.xy / cellPx);
  vec2 cellUv = fract(gl_FragCoord.xy / cellPx);
  vec2 cellCenter = (cellId + 0.5) * cellPx / u_res;
  vec2 cellHere = vec2(cellCenter.x * aspect, cellCenter.y);
  // Only the box the cursor is on (and the boxes it just left) lights up, one box at a time.
  float lit = 0.0;
  vec2 tiltDir = vec2(0.0);
  for (int i = 0; i < 12; i++) {
    vec3 tp = u_trail[i];
    float age = tp.z;
    if (age >= 1.0) continue;
    vec2 trailPx = tp.xy * u_res;
    vec2 trailCell = floor(trailPx / cellPx);
    if (trailCell.x == cellId.x && trailCell.y == cellId.y) {
      float life = (1.0 - age) * (1.0 - age);
      if (life > lit) {
        lit = life;
        // Where inside the box the cursor was: the box tips toward that side.
        tiltDir = (fract(trailPx / cellPx) - 0.5) * 2.0;
      }
    }
  }
  lit = min(lit, 1.0) * u_strength;
  // Self-running activity, no cursor needed.
  vec2 cells = floor(u_res / cellPx);
  // 1. Pulses that travel along a row or a column with a fading tail.
  float auto = 0.0;
  for (int k = 0; k < 6; k++) {
    float fk = float(k);
    float period = 7.0 + hash(vec2(fk, 1.3)) * 6.0;
    float phase = u_time / period + hash(vec2(fk, 2.7));
    float cycle = floor(phase);
    float ph = fract(phase);
    float horizontal = step(0.5, hash(vec2(cycle, fk + 7.1)));
    float forward = step(0.5, hash(vec2(cycle, fk + 3.9))) * 2.0 - 1.0;
    float tail = 7.0;
    float lane = floor(hash(vec2(cycle * 1.7, fk + 11.3)) * mix(cells.x, cells.y, horizontal));
    float along = mix(cellId.y, cellId.x, horizontal);
    float across = mix(cellId.x, cellId.y, horizontal);
    float len = mix(cells.y, cells.x, horizontal);
    float head = mix(len + tail - ph * (len + tail * 2.0), ph * (len + tail * 2.0) - tail, step(0.0, forward));
    float d = (head - along) * forward;
    float onLane = 1.0 - step(0.5, abs(across - lane));
    float inTail = step(0.0, d) * (1.0 - step(tail, d));
    auto += onLane * inTail * pow(clamp(1.0 - d / tail, 0.0, 1.0), 2.2);
  }
  // 2. Scattered tiles that blink on their own, a different set each few seconds.
  float bphase = u_time / 4.5 + hash(cellId + 0.5);
  float bepoch = floor(bphase);
  float chosen = step(0.9, hash(cellId * 1.3 + bepoch * 0.37));
  float blink = pow(sin(fract(bphase) * 3.14159), 12.0) * chosen;
  auto = min(auto + blink * 0.6, 1.0);
  // Faint slow twinkle under everything.
  float twinkle = pow(noise(cellId * 0.35 + vec2(u_time * 0.12, -u_time * 0.08)), 6.0) * 0.5;
  float edge = 1.4 / cellPx;
  float border = (1.0 - step(edge, cellUv.x)) + (1.0 - step(edge, cellUv.y));
  border = min(border, 1.0);

  vec3 black = vec3(0.004, 0.006, 0.014);
  vec3 navy = vec3(0.02, 0.07, 0.30);
  vec3 blue = vec3(0.10, 0.28, 0.80);
  vec3 ice = vec3(0.86, 0.92, 1.0);

  // Base: navy with blue where the fog is dense.
  float dense = smoothstep(0.3, 0.8, f);
  vec3 col = mix(black, navy, smoothstep(0.15, 0.65, g + f * 0.4));
  col = mix(col, blue, dense * 0.85);

  // White cloud banks: a second, softer mask, weighted toward the top right, as on the reference.
  // Strongest toward the top right, faint in the middle, none near the bottom.
  float bias = smoothstep(0.3, 1.1, uv.x * 0.6 + uv.y * 0.5) * 0.34 - 0.12;
  float keepDark = smoothstep(0.08, 0.45, uv.y);
  float clouds = smoothstep(0.58, 0.92, g * 0.55 + r.y * 0.6 + bias) * keepDark;
  // The large bank in the upper right: a soft blob shaped by the fog, drifting slowly.
  vec2 bankCenter = vec2(0.86 * aspect + sin(t * 2.0) * 0.05, 0.78 + cos(t * 1.6) * 0.04);
  float bank = exp(-pow(length((here - bankCenter) * vec2(0.9, 1.3)), 2.0) * 5.5);
  bank *= smoothstep(0.25, 0.75, f * 0.7 + r.x * 0.5);
  clouds = max(clouds, bank * 1.1);
  col = mix(col, ice, min(clouds, 1.0) * 0.92);
  // A few bright highlights in the densest cloud cores.
  col += ice * pow(clouds, 3.0) * 0.2;

  // Fade to black at the bottom; the section melts into the page.
  col *= 1.0 - smoothstep(0.5, 0.0, uv.y) * 0.96;
  // Slight darkening at the top edge, so the nav sits in a quiet band.
  col *= 0.9 + 0.1 * smoothstep(1.0, 0.85, uv.y);

  // The grid: hairline borders, faint everywhere, bright on lit tiles; lit tiles also gain a soft fill.
  float visible = 0.35 + 0.65 * smoothstep(0.0, 0.35, uv.y);
  float glow = max(lit, auto * 0.75);
  col += vec3(0.75, 0.82, 1.0) * border * (0.035 + glow * 0.5 + twinkle * 0.08) * visible;
  col += mix(blue, ice, 0.55) * (max(auto * 0.75, 0.0) * 0.22 + twinkle * 0.035) * visible;
  // The tilt: a lit box is shaded like a tile tipped toward the cursor, bright on the near side, dark on the far side,
  // drawn slightly inset so it reads as a raised tile.
  vec2 inBox = cellUv - 0.5;
  float slope = dot(inBox, tiltDir);
  float inset = step(0.06, cellUv.x) * step(cellUv.x, 0.94) * step(0.06, cellUv.y) * step(cellUv.y, 0.94);
  float face = (0.30 + slope * 0.55) * inset;
  float rim = (1.0 - inset) * 0.35;
  col += mix(blue, ice, 0.7) * lit * (face + rim) * visible;
  col -= vec3(0.05, 0.08, 0.2) * lit * max(-slope, 0.0) * inset * 0.6;

  // Heavy film grain.
  float grain = hash(gl_FragCoord.xy + fract(u_time) * 100.0) - 0.5;
  col += grain * 0.11;

  gl_FragColor = vec4(col, 1.0);
}`;
