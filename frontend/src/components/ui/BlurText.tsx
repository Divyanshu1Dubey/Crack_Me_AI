'use client';

import React, { useEffect, useRef, useState, useMemo } from 'react';
import './BlurText.css';

type BlurTextProps = {
  text?: string;
  delay?: number;
  className?: string;
  animateBy?: 'words' | 'letters';
  direction?: 'top' | 'bottom';
  threshold?: number;
  rootMargin?: string;
  onAnimationComplete?: () => void;
  stepDuration?: number;
};

const BlurText: React.FC<BlurTextProps> = ({
  text = '',
  delay = 120,
  className = '',
  animateBy = 'words',
  direction = 'top',
  threshold = 0.1,
  rootMargin = '0px',
  onAnimationComplete,
  stepDuration = 0.4
}) => {
  const elements = useMemo(() => {
    return animateBy === 'words' ? text.split(' ') : text.split('');
  }, [text, animateBy]);

  const [inView, setInView] = useState(false);
  const ref = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          observer.unobserve(ref.current as Element);
        }
      },
      { threshold, rootMargin }
    );
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [threshold, rootMargin]);

  useEffect(() => {
    if (inView && onAnimationComplete) {
      const totalTime = elements.length * delay + stepDuration * 1000;
      const timer = setTimeout(onAnimationComplete, totalTime);
      return () => clearTimeout(timer);
    }
  }, [inView, elements.length, delay, stepDuration, onAnimationComplete]);

  return (
    <p ref={ref} className={`blur-text-container ${className}`}>
      {elements.map((segment, index) => {
        const itemDelay = (index * delay) / 1000;

        const initialStyle: React.CSSProperties = {
          filter: inView ? 'blur(0px)' : 'blur(10px)',
          opacity: inView ? 1 : 0,
          transform: inView
            ? 'translateY(0px)'
            : direction === 'top'
            ? 'translateY(-20px)'
            : 'translateY(20px)',
          transitionDelay: `${itemDelay}s`,
          transitionDuration: `${stepDuration}s`
        };

        return (
          <span
            key={index}
            className="blur-text-word"
            style={initialStyle}
          >
            {segment === ' ' ? '\u00A0' : segment}
            {animateBy === 'words' && index < elements.length - 1 && '\u00A0'}
          </span>
        );
      })}
    </p>
  );
};

export default BlurText;
