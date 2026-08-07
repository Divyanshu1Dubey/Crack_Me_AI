'use client';

import React, { ReactNode } from 'react';
import './GradientText.css';

interface GradientTextProps {
  children: ReactNode;
  className?: string;
  colors?: string[];
  animationSpeed?: number;
  showBorder?: boolean;
}

export default function GradientText({
  children,
  className = '',
  colors = ['#2563eb', '#7c3aed', '#0d9488'],
  animationSpeed = 6,
  showBorder = false
}: GradientTextProps) {
  const gradientStyle: React.CSSProperties = {
    backgroundImage: `linear-gradient(135deg, ${colors.join(', ')}, ${colors[0]})`,
    animationDuration: `${animationSpeed}s`
  };

  return (
    <span
      className={`animated-gradient-text ${showBorder ? 'with-border' : ''} ${className}`}
      style={gradientStyle}
    >
      {children}
    </span>
  );
}
