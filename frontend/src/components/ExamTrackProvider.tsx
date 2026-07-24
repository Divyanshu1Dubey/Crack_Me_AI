'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { useAuth } from '@/lib/auth';

interface ExamTrackContextType {
  activeTrack: string;
  setActiveTrack: (track: string) => void;
  /** True ONLY after the first client effect runs. Until then the
   *  provider has rendered on the server with the default 'cms' value.
   *  Consumers should hide any client-only branching on this flag to
   *  avoid React #418 hydration mismatches. */
  hydrated: boolean;
}

const ExamTrackContext = createContext<ExamTrackContextType>({
  activeTrack: 'cms',
  setActiveTrack: () => {},
  hydrated: false,
});

export function ExamTrackProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [activeTrack, setActiveTrack] = useState<string>('cms');
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    // If user has a selected track, use it, else default to 'cms'
    let track = 'cms';
    if (user?.target_exam) {
      const te = user.target_exam.toLowerCase();
      if (te.includes('neet')) track = 'neet_pg';
      else if (te.includes('usmle')) track = 'usmle';
      else if (te.includes('fmge')) track = 'fmge';
      else if (te.includes('ini')) track = 'ini_cet';
    }

    // Check if we have a locally saved preference overriding it
    const saved = localStorage.getItem('active_exam_track');
    if (saved) {
      track = saved;
    }

    setActiveTrack(track);
    setHydrated(true);
  }, [user]);

  useEffect(() => {
    if (!hydrated) return; // never write before the first read
    document.documentElement.setAttribute('data-track', activeTrack);
    localStorage.setItem('active_exam_track', activeTrack);
  }, [activeTrack, hydrated]);

  return (
    <ExamTrackContext.Provider value={{ activeTrack, setActiveTrack, hydrated }}>
      {children}
    </ExamTrackContext.Provider>
  );
}

export const useExamTrack = () => useContext(ExamTrackContext);
