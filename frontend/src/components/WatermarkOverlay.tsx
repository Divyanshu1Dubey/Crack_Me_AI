'use client';

import React, { useEffect, useState } from 'react';
import { useAuth } from '@/lib/auth';

export function WatermarkOverlay() {
  const { user } = useAuth();
  const [timestamp, setTimestamp] = useState('');
  // mounted gate — SSR returns null for the overlay because useAuth has no
  // session on the server. Without this gate, the client's first paint
  // renders 50 timestamped spans while the server rendered nothing,
  // triggering React #418 (text content mismatch).
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    // Update timestamp every minute
    const updateTime = () => setTimestamp(new Date().toLocaleString());
    updateTime();
    const interval = setInterval(updateTime, 60000);
    return () => clearInterval(interval);
  }, []);

  if (!mounted || !user) return null;

  const watermarkText = `${user.email || user.username} • ${timestamp}`;

  return (
    <div aria-hidden="true" className="fixed inset-0 pointer-events-none z-[9999] overflow-hidden opacity-[0.015] select-none flex flex-wrap justify-center items-center gap-24 transform -rotate-12 scale-150">
      {[...Array(30)].map((_, i) => (
        <span key={i} aria-hidden="true" className="text-xl font-medium whitespace-nowrap text-foreground">
          {watermarkText}
        </span>
      ))}
    </div>
  );
}
