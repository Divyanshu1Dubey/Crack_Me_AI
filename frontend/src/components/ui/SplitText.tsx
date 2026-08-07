'use client';

import React, { useRef, useEffect, useMemo } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import './SplitText.css';

if (typeof window !== 'undefined') {
  gsap.registerPlugin(ScrollTrigger);
}

export interface SplitTextProps {
  text: string;
  className?: string;
  delay?: number;
  duration?: number;
  ease?: string;
  splitType?: 'chars' | 'words';
  from?: gsap.TweenVars;
  to?: gsap.TweenVars;
  threshold?: number;
  tag?: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6' | 'p' | 'span';
  textAlign?: React.CSSProperties['textAlign'];
  onLetterAnimationComplete?: () => void;
}

const SplitText: React.FC<SplitTextProps> = ({
  text,
  className = '',
  delay = 30,
  duration = 0.7,
  ease = 'power2.out',
  splitType = 'chars',
  from = { opacity: 0, y: 10 },
  to = { opacity: 1, y: 0 },
  threshold = 0.1,
  textAlign = 'left',
  tag = 'h1',
  onLetterAnimationComplete
}) => {
  const ref = useRef<HTMLElement>(null);
  const hasAnimatedRef = useRef(false);

  const splitUnits = useMemo(() => {
    if (!text) return [];
    if (splitType === 'words') {
      return text.split(' ').map((word, i) => ({ id: i, content: word, isSpace: false }));
    }
    return text.split('').map((char, i) => ({ id: i, content: char === ' ' ? '\u00A0' : char, isSpace: char === ' ' }));
  }, [text, splitType]);

  useEffect(() => {
    const el = ref.current;
    if (!el || splitUnits.length === 0 || hasAnimatedRef.current) return;

    // Check prefers-reduced-motion
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) {
      hasAnimatedRef.current = true;
      return;
    }

    const targets = el.querySelectorAll('.split-char');
    if (targets.length === 0) return;

    const ctx = gsap.context(() => {
      gsap.fromTo(
        targets,
        { ...from },
        {
          ...to,
          duration,
          ease,
          stagger: delay / 1000,
          scrollTrigger: {
            trigger: el,
            start: 'top bottom-=5%',
            once: true
          },
          onComplete: () => {
            hasAnimatedRef.current = true;
            onLetterAnimationComplete?.();
          }
        }
      );
    }, el);

    return () => ctx.revert();
  }, [splitUnits, delay, duration, ease, from, to, onLetterAnimationComplete]);

  const Tag = (tag || 'h1') as any;

  return (
    <Tag
      ref={ref}
      style={{ textAlign }}
      className={`split-parent ${className}`}
    >
      {splitUnits.map((unit, index) => (
        <span key={unit.id} className="split-char">
          {unit.content}
          {splitType === 'words' && index < splitUnits.length - 1 && '\u00A0'}
        </span>
      ))}
    </Tag>
  );
};

export default SplitText;
