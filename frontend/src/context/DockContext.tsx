'use client';

import React, { createContext, useContext, useState, ReactNode } from 'react';

type DockPanel = 'none' | 'ask-ai' | 'flashcard';

interface DockContextType {
  activePanel: DockPanel;
  setActivePanel: (panel: DockPanel) => void;
  contextQuestionId: number | null;
  setContextQuestionId: (id: number | null) => void;
  selectedText: string;
  setSelectedText: (text: string) => void;
}

const DockContext = createContext<DockContextType | undefined>(undefined);

export function DockProvider({ children }: { children: ReactNode }) {
  const [activePanel, setActivePanel] = useState<DockPanel>('none');
  const [contextQuestionId, setContextQuestionId] = useState<number | null>(null);
  const [selectedText, setSelectedText] = useState<string>('');

  return (
    <DockContext.Provider value={{
      activePanel, setActivePanel,
      contextQuestionId, setContextQuestionId,
      selectedText, setSelectedText
    }}>
      {children}
    </DockContext.Provider>
  );
}

export function useDock() {
  const context = useContext(DockContext);
  if (context === undefined) {
    throw new Error('useDock must be used within a DockProvider');
  }
  return context;
}
