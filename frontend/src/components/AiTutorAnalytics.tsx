'use client';

/**
 * AiTutorAnalytics.tsx — Tracks AI Tutor lifecycle events.
 *
 * Wrap your AI Tutor UI in this provider and call the returned helpers
 * from `onMessageSent`, `onThumbsUp`, `onThumbsDown`, `onModeSwitch`, etc.
 *
 * Uses the unified `analytics` surface — GA4 + Clarity + PostHog + DD RUM.
 */

import { createContext, useContext, useEffect, useMemo } from 'react';
import { analytics } from '@/lib/analytics';

interface AiTutorContextValue {
    trackModeSwitch: (mode: string) => void;
    trackConversationStart: (mode: string) => void;
    trackMessage: (mode: string, length: number, hasAttachments: boolean) => void;
    trackFeedback: (sessionId: string, vote: 'up' | 'down') => void;
    trackFailure: (mode: string, errorMessage: string) => void;
}

const AiTutorAnalyticsContext = createContext<AiTutorContextValue | null>(null);

export function AiTutorAnalyticsProvider({
    initialMode,
    children,
}: {
    initialMode: string;
    children: React.ReactNode;
}) {
    useEffect(() => {
        analytics.aiTutorOpen(initialMode);
    }, [initialMode]);

    const value = useMemo<AiTutorContextValue>(
        () => ({
            trackModeSwitch: (mode: string) =>
                analytics.event('ai_tutor_mode_switch', { mode }),
            trackConversationStart: (mode: string) =>
                analytics.aiTutorConversationStart(mode),
            trackMessage: (mode: string, length: number, hasAttachments: boolean) =>
                analytics.aiTutorMessage(mode, length, hasAttachments),
            trackFeedback: (sessionId: string, vote: 'up' | 'down') =>
                analytics.aiTutorFeedback(sessionId, vote),
            trackFailure: (mode: string, errorMessage: string) =>
                analytics.error(errorMessage.slice(0, 200), `ai_tutor:${mode}`),
        }),
        [],
    );

    return (
        <AiTutorAnalyticsContext.Provider value={value}>
            {children}
        </AiTutorAnalyticsContext.Provider>
    );
}

export function useAiTutorAnalytics(): AiTutorContextValue {
    const ctx = useContext(AiTutorAnalyticsContext);
    return (
        ctx ?? {
            trackModeSwitch: () => undefined,
            trackConversationStart: () => undefined,
            trackMessage: () => undefined,
            trackFeedback: () => undefined,
            trackFailure: () => undefined,
        }
    );
}