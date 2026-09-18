'use client';

import { useEffect, useRef } from 'react';
import { Renderer, Program, Mesh, Triangle, Vec2, Color } from 'ogl';

import './NeuralBackground.css';

// ---------------------------------------------------------------
// Shader sources
// ---------------------------------------------------------------

const VERT = `#version 300 es
precision highp float;

in vec2 position;
out vec2 vUv;

void main() {
  vUv = position * 0.5 + 0.5;
  gl_Position = vec4(position, 0.0, 1.0);
}
`;

const FRAG = `#version 300 es
precision highp float;

in vec2 vUv;
out vec4 fragColor;

// --- Uniforms --------------------------------------------------
uniform float     uTime;
uniform vec2      uResolution;
uniform float     uParticleCount;
uniform float     uSpeed;
uniform float     uLineAlpha;
uniform float     uDotAlpha;
uniform vec3      uTint;          // accent color
uniform vec3      uBgDark;        // dark-mode background
uniform vec3      uBgLight;       // light-mode background
uniform float     uTheme;         // 0.0 = light, 1.0 = dark

// --- Particle state (packed into uniforms) ---------------------
// Each particle: vec4(x, y, vx, vy)  -> 16 max
#define MAX_PARTICLES 48

uniform vec4 uParticles[MAX_PARTICLES];

// --- Helpers ---------------------------------------------------
float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

// ---------------------------------------------------------------
void main() {
  vec2 uv = vUv;
  float aspect = uResolution.x / uResolution.y;
  vec2 uvA = vec2(uv.x * aspect, uv.y);

  // Background color blended by theme
  vec3 bg = mix(uBgLight, uBgDark, uTheme);
  vec3 col = bg;

  // ---- Particles ---------------------------------------------
  float alphaAccum = 0.0;
  int count = int(uParticleCount);

  for (int i = 0; i < MAX_PARTICLES; i++) {
    if (i >= count) break;

    vec4 p = uParticles[i];
    vec2 pos = p.xy;
    vec2 vel = p.zw;

    // Distance from pixel to particle (in aspect-corrected space)
    float d = distance(uvA, pos);
    float radius = 0.0045;

    // Soft glow dot
    float glow = exp(-d * d / (radius * radius * 8.0));
    alphaAccum += glow * uDotAlpha;

    // Connection lines -----------------------------------------
    for (int j = i + 1; j < MAX_PARTICLES; j++) {
      if (j >= count) break;
      vec4 q = uParticles[j];
      vec2 pa = p.xy;
      vec2 pb = q.xy;

      float lineLen = distance(pa, pb);
      float maxLen = 0.35;

      if (lineLen < maxLen) {
        // Distance from pixel to the line segment (approximate)
        vec2 dir = normalize(pb - pa);
        vec2 toPixel = uvA - pa;
        float proj = clamp(dot(toPixel, dir), 0.0, lineLen);
        vec2 closest = pa + dir * proj;
        float distToLine = distance(uvA, closest);

        float lineAlpha = (1.0 - lineLen / maxLen);
        lineAlpha *= uLineAlpha;
        float lineGlow = exp(-distToLine * distToLine / 0.00025);
        alphaAccum += lineGlow * lineAlpha * 0.6;
      }
    }
  }

  // Tint the accumulated alpha
  vec3 tinted = col + uTint * alphaAccum;
  fragColor = vec4(tinted, 1.0);
}
`;

// ---------------------------------------------------------------
// Types
// ---------------------------------------------------------------

export interface NeuralBackgroundProps {
  /** Number of particles (default 24). */
  particleCount?: number;
  /** Animation speed multiplier (default 1). */
  speed?: number;
  /** Connection-line opacity, 0–1 (default 0.35). */
  lineAlpha?: number;
  /** Dot opacity, 0–1 (default 0.7). */
  dotAlpha?: number;
  /** Accent tint RGB in CSS space (default accent-primary). */
  tint?: string;
  /** CSS class for the wrapper element. */
  className?: string;
  /** Inline styles for the wrapper. */
  style?: React.CSSProperties;
  /** If true, the canvas renders behind page content. */
  asOverlay?: boolean;
}

// ---------------------------------------------------------------
// Default values (resolved at call time so theme tokens can be read)
// ---------------------------------------------------------------

function resolveTint(): string {
  if (typeof window === 'undefined') return '#3b82f6';
  const v = getComputedStyle(document.documentElement)
    .getPropertyValue('--accent-primary')
    .trim();
  return v || '#3b82f6';
}

function resolveBg(isDark: boolean): { light: Vec2; dark: Vec2 } | null {
  if (typeof window === 'undefined') return null;
  const root = document.documentElement;
  const getRgb = (varName: string): Vec2 => {
    const raw = getComputedStyle(root).getPropertyValue(varName).trim();
    const m = raw.match(/(\d+)\s+(\d+)\s+(\d+)/);
    if (!m) return isDark ? [0.035, 0.063, 0.09] : [0.973, 0.98, 0.988];
    return [m[1] / 255, m[2] / 255, m[3] / 255];
  };
  return {
    light: getRgb('--color-background'),
    dark: getRgb('--color-card'),
  };
}

function hexToVec3(hex: string): Vec2 {
  const c = new Color(hex);
  return [c.r, c.g, c.b];
}

// ---------------------------------------------------------------
// Component
// ---------------------------------------------------------------

export default function NeuralBackground({
  particleCount = 24,
  speed = 1,
  lineAlpha = 0.35,
  dotAlpha = 0.7,
  tint,
  className,
  style,
  asOverlay = true,
}: NeuralBackgroundProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const glRef = useRef<{
    renderer: ReturnType<typeof Renderer>;
    mesh: Mesh;
    program: ReturnType<typeof Program>;
    particles: Vec2[];
    velocities: Vec2[];
    animateId: number;
  } | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.offsetWidth || window.innerWidth;
    const height = container.offsetHeight || window.innerHeight;

    // --- Theme resolution ----------------------------------------
    const isDark = document.documentElement.classList.contains('dark');
    const resolvedTint = tint || resolveTint();
    const bgColors = resolveBg(isDark);
    const bgLight: Vec2 = bgColors ? bgColors.light : [0.973, 0.98, 0.988];
    const bgDark: Vec2 = bgColors ? bgColors.dark : [0.035, 0.063, 0.09];
    const tintVec: Vec2 = hexToVec3(resolvedTint);

    // --- Renderer -----------------------------------------------
    const renderer = new Renderer({
      alpha: true,
      premultipliedAlpha: true,
      antialias: false,
      dpr: Math.min(window.devicePixelRatio, 2),
    });
    renderer.gl.clearColor(0, 0, 0, 0);
    renderer.setSize(width, height);

    const gl = renderer.gl;
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);

    container.appendChild(gl.canvas as HTMLCanvasElement);

    // --- Geometry -----------------------------------------------
    const geometry = new Triangle(gl);
    if (geometry.attributes.uv) {
      delete geometry.attributes.uv;
    }

    // --- Particles ----------------------------------------------
    const count = Math.min(particleCount, 48);
    const aspect = width / height;
    const particles: Vec2[] = [];
    const velocities: Vec2[] = [];

    for (let i = 0; i < count; i++) {
      particles.push([
        Math.random() * aspect,
        Math.random(),
      ]);
      const angle = Math.random() * Math.PI * 2;
      const speedVal = 0.0004 + Math.random() * 0.0006;
      velocities.push([Math.cos(angle) * speedVal, Math.sin(angle) * speedVal]);
    }

    // Pack into uniform vec4 array
    const particleUniforms: Vec2[] = particles.map((p, i) => [
      p[0],
      p[1],
      velocities[i][0],
      velocities[i][1],
    ]);

    // --- Program ------------------------------------------------
    const program = new Program(gl, {
      vertex: VERT,
      fragment: FRAG,
      uniforms: {
        uTime:        { value: 0 },
        uResolution:  { value: [width, height] },
        uParticleCount: { value: count },
        uSpeed:       { value: speed },
        uLineAlpha:   { value: lineAlpha },
        uDotAlpha:    { value: dotAlpha },
        uTint:        { value: tintVec },
        uBgDark:      { value: bgDark },
        uBgLight:     { value: bgLight },
        uTheme:       { value: isDark ? 1.0 : 0.0 },
        uParticles:   { value: particleUniforms },
      },
    });

    const mesh = new Mesh(gl, { geometry, program });
    glRef.current = { renderer, mesh, program, particles, velocities, animateId: 0 };

    // --- Resize ------------------------------------------------
    const onResize = () => {
      if (!container) return;
      const w = container.offsetWidth || window.innerWidth;
      const h = container.offsetHeight || window.innerHeight;
      renderer.setSize(w, h);
      if (program) {
        program.uniforms.uResolution.value = [w, h];
      }
    };
    window.addEventListener('resize', onResize);

    // --- Animate -----------------------------------------------
    const animate = (t: number) => {
      const ref = glRef.current;
      if (!ref) return;
      ref.animateId = requestAnimationFrame(animate);

      const { program: prog, particles: pts, velocities: vels } = ref;
      const aspectNow = prog.uniforms.uResolution.value[0]
        / prog.uniforms.uResolution.value[1];
      const sp = prog.uniforms.uSpeed.value;
      const time = t * 0.001;

      for (let i = 0; i < count; i++) {
        let [x, y] = pts[i];
        let [vx, vy] = vels[i];

        // Gentle Brownian drift
        const drift = 0.00003;
        vx += (Math.random() - 0.5) * drift;
        vy += (Math.random() - 0.5) * drift;

        // Clamp velocity
        const maxV = 0.0012;
        const v = Math.sqrt(vx * vx + vy * vy);
        if (v > maxV) {
          vx = (vx / v) * maxV;
          vy = (vy / v) * maxV;
        }

        x += vx * sp;
        y += vy * sp;

        // Wrap around edges
        if (x < -0.05) x = aspectNow + 0.05;
        if (x > aspectNow + 0.05) x = -0.05;
        if (y < -0.05) y = 1.05;
        if (y > 1.05) y = -0.05;

        pts[i] = [x, y];
        vels[i] = [vx, vy];
        prog.uniforms.uParticles.value[i] = [x, y, vx, vy];
      }

      prog.uniforms.uTime.value = time;
      renderer.render({ scene: mesh });
    };
    ref.animateId = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(ref.animateId);
      window.removeEventListener('resize', onResize);
      if (gl.canvas.parentNode === container) {
        container.removeChild(gl.canvas as HTMLCanvasElement);
      }
      (gl.getExtension('WEBGL_lose_context') as WebGLExtension)?.loseContext();
    };
  }, [particleCount, speed, lineAlpha, dotAlpha, tint]);

  // Observe theme changes so light/dark switch propagates to shader
  useEffect(() => {
    const root = document.documentElement;
    const observer = new MutationObserver(() => {
      const ref = glRef.current;
      if (!ref) return;
      const isDark = root.classList.contains('dark');
      ref.program.uniforms.uTheme.value = isDark ? 1.0 : 0.0;
      const bg = resolveBg(isDark);
      if (bg) {
        ref.program.uniforms.uBgDark.value = bg.dark;
        ref.program.uniforms.uBgLight.value = bg.light;
      }
      const resolvedTint = tint || resolveTint();
      ref.program.uniforms.uTint.value = hexToVec3(resolvedTint);
    });
    observer.observe(root, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, [tint]);

  return (
    <div
      ref={containerRef}
      className={[
        'neural-bg',
        asOverlay ? 'neural-bg--overlay' : '',
        className || '',
      ]
        .filter(Boolean)
        .join(' ')}
      style={style}
      aria-hidden="true"
    />
  );
}
