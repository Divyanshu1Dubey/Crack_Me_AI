/**
 * QuestionFocusContext — broadcast whether a question is currently being
 * "solved" anywhere in the app.
 *
 * Used by SidebarAutoHide to keep the sidebar collapsed while the user
 * is actively reading a question (not just browsing the bank list).
 *
 * State is intentionally minimal: a boolean + a setter. ExamQuestionBank
 * flips it to true whenever `selectedQuestion !== null`, false when it
 * goes back to null. SidebarAutoHide combines it with the pathname to
 * decide whether to apply auto-collapse.
 */
'use client';

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

interface QuestionFocusContextValue {
  isQuestionFocused: boolean;
  setQuestionFocused: (focused: boolean) => void;
}

const QuestionFocusContext = createContext<QuestionFocusContextValue | null>(null);

export function QuestionFocusProvider({ children }: { children: ReactNode }) {
  const [isQuestionFocused, setQuestionFocusedState] = useState<boolean>(false);

  const setQuestionFocused = useCallback((focused: boolean) => {
    setQuestionFocusedState(focused);
  }, []);

  const value = useMemo<QuestionFocusContextValue>(
    () => ({ isQuestionFocused, setQuestionFocused }),
    [isQuestionFocused, setQuestionFocused],
  );

  return <QuestionFocusContext.Provider value={value}>{children}</QuestionFocusContext.Provider>;
}

export function useQuestionFocus(): QuestionFocusContextValue {
  const ctx = useContext(QuestionFocusContext);
  if (!ctx) {
    throw new Error('useQuestionFocus must be used within a <QuestionFocusProvider>');
  }
  return ctx;
}