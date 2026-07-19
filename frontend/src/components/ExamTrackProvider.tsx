'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { useAuth } from '@/lib/auth';

interface ExamTrackContextType {
  activeTrack: string;
  setActiveTrack: (track: string) => void;
}

const ExamTrackContext = createContext<ExamTrackContextType>({
  activeTrack: 'cms',
  setActiveTrack: () => {},
});

export function ExamTrackProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [activeTrack, setActiveTrack] = useState<string>('cms');

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
  }, [user]);

  useEffect(() => {
    // Apply track to HTML root
    document.documentElement.setAttribute('data-track', activeTrack);
    localStorage.setItem('active_exam_track', activeTrack);
  }, [activeTrack]);

  return (
    <ExamTrackContext.Provider value={{ activeTrack, setActiveTrack }}>
      {children}
    </ExamTrackContext.Provider>
  );
}

export const useExamTrack = () => useContext(ExamTrackContext);
