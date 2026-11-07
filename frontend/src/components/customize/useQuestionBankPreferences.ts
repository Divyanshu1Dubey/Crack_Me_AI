'use client';

import { useMemo } from 'react';
import {
    questionBankHidden,
    studyModeOf,
    type QuestionBankToolId,
    type StudyMode,
} from '@/lib/preferences';
import { useUiPreferences } from './usePreferences';

export interface QuestionBankPreferencesView {
    /** Whether the learner shows `tool` (every tool shows until their preferences are known). */
    shows: (tool: QuestionBankToolId) => boolean;
    /** The mode the question bank opens in. */
    studyMode: StudyMode;
    signedIn: boolean;
}

/**
 * The learner's question-bank choices (Settings > Customise) for the question bank and practice
 * pages. The defaults (every tool, practice mode) render while the preferences load and when
 * signed out; nothing waits for them. Hiding a tool only leaves it off the page: what a plan
 * unlocks is still decided by the server and the page.
 */
export function useQuestionBankPreferences(): QuestionBankPreferencesView {
    const { prefs, signedIn } = useUiPreferences();
    const part = prefs.question_bank;
    return useMemo(() => {
        const hidden = questionBankHidden(part);
        return {
            shows: (tool: QuestionBankToolId) => !hidden.has(tool),
            studyMode: studyModeOf(part),
            signedIn,
        };
    }, [part, signedIn]);
}
