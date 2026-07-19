'use client';

import React, { useEffect, useState } from 'react';
import { useAuth } from '@/context/AuthContext';

export function WatermarkOverlay() {
  const { user } = useAuth();
  const [timestamp, setTimestamp] = useState('');

  useEffect(() => {
    // Update timestamp every minute
    const updateTime = () => setTimestamp(new Date().toLocaleString());
    updateTime();
    const interval = setInterval(updateTime, 60000);
    return () => clearInterval(interval);
  }, []);

  if (!user) return null;

  const watermarkText = `${user.email || user.username} • ${timestamp}`;

  return (
    <div className="fixed inset-0 pointer-events-none z-[9999] overflow-hidden opacity-[0.03] select-none flex flex-wrap justify-center items-center gap-24 transform -rotate-12 scale-150">
      {[...Array(50)].map((_, i) => (
        <span key={i} className="text-xl font-bold whitespace-nowrap text-foreground">
          {watermarkText}
        </span>
      ))}
    </div>
  );
}
