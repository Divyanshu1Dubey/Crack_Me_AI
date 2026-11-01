'use client';

import React, { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useDock } from '@/context/DockContext';
import { useAuth } from '@/lib/auth';
import { isFloatingDockHiddenRoute } from '@/lib/appShellRoutes';
import { dockErrorNotice, parseDockReply, EMPTY_REPLY_TEXT, type DockCitation, type DockNotice } from '@/lib/dockChat';
import { MessageSquare, Layers, X, Send, Save, WifiOff, BookOpen } from 'lucide-react';
import { Button } from './ui/button';
import api from '@/lib/api';

// Replies are markdown. The renderer (react-markdown) loads on demand, so it
// is not in the bundle every page ships; it is fetched when the panel opens.
const ReplyMarkdown = dynamic(() => import('@/components/FloatingDockReply'), {
  ssr: false,
  loading: () => <p className="text-xs text-muted-foreground">Loading reply…</p>,
});

const NOTICE_CLASSES: Record<DockNotice['kind'], string> = {
  unavailable: 'border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-200',
  limit: 'border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-200',
  upgrade: 'border-primary/30 bg-primary/10 text-foreground',
  error: 'border-destructive/30 bg-destructive/10 text-destructive',
};

export function FloatingDock() {
  const { activePanel, setActivePanel, contextQuestionId, selectedText, setSelectedText } = useDock();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const pathname = usePathname();
  const [aiQuery, setAiQuery] = useState('');
  const [aiResponse, setAiResponse] = useState('');
  // Offline extract (no AI model, not charged) and its textbook sources.
  const [aiOffline, setAiOffline] = useState(false);
  const [aiCitations, setAiCitations] = useState<DockCitation[]>([]);
  // Outage / limit / upgrade message. Never stored as the reply, so it can
  // not be rated or saved as a flashcard's back.
  const [aiNotice, setAiNotice] = useState<DockNotice | null>(null);
  const [loading, setLoading] = useState(false);

  // Both actions call login-only endpoints, so anonymous visitors (and the
  // moment before auth resolves) get no dock; nor do the admin tools, the
  // AI Tutor and the timed test player (see isFloatingDockHiddenRoute).
  const hidden = authLoading || !isAuthenticated || isFloatingDockHiddenRoute(pathname);

  // Tell globals.css to reserve space under the page for the buttons, but
  // only while they are actually on screen.
  useEffect(() => {
    if (activePanel === 'none' && !hidden) {
      document.body.classList.add('floating-dock-visible');
    } else {
      document.body.classList.remove('floating-dock-visible');
    }
    return () => document.body.classList.remove('floating-dock-visible');
  }, [activePanel, hidden]);

  // Fetch the reply renderer while the user types (same chunk as ReplyMarkdown).
  useEffect(() => {
    if (activePanel === 'ask-ai') import('@/components/FloatingDockReply').catch(() => { /* loads on render */ });
  }, [activePanel]);

  const clearReply = () => {
    setAiResponse('');
    setAiOffline(false);
    setAiCitations([]);
  };

  const handleAskAI = async () => {
    if (!aiQuery.trim() || loading) return;
    setLoading(true);
    setAiNotice(null);
    try {
      const res = await api.post('/questions/chat/', {
        message: aiQuery,
        context_question_id: contextQuestionId
      });
      const reply = parseDockReply(res.data);
      if (reply) {
        setAiResponse(reply.text);
        setAiOffline(reply.offline);
        setAiCitations(reply.citations);
      } else {
        clearReply();
        setAiNotice({ kind: 'error', text: EMPTY_REPLY_TEXT });
      }
    } catch (err: unknown) {
      // 503 ai_unavailable (not charged), 402 upgrade_required (api.ts also
      // opens the upgrade modal), 429 token / rate limits, network errors.
      clearReply();
      setAiNotice(dockErrorNotice(err));
    } finally {
      setLoading(false);
    }
  };

  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const showStatus = (msg: string) => {
    setStatusMessage(msg);
    setTimeout(() => setStatusMessage(null), 3500);
  };

  const handleSaveFlashcard = async () => {
    try {
      await api.post('/questions/flashcards/', {
        front: selectedText || 'New Flashcard',
        back: aiResponse || '...',
      });
      showStatus('Flashcard saved successfully!');
      setTimeout(() => setActivePanel('none'), 1200);
    } catch (e) {
      showStatus('Error saving flashcard. Please try again.');
    }
  };

  if (hidden) return null;

  if (activePanel === 'none') {
    return (
      <div className="fixed bottom-[max(1rem,env(safe-area-inset-bottom))] right-4 sm:bottom-6 sm:right-6 flex flex-col gap-2 z-50">
        <Button
          variant="default"
          size="icon"
          aria-label="Open AI Assistant"
          className="rounded-full shadow-lg h-11 w-11 sm:h-12 sm:w-12 bg-primary hover:bg-primary/90 focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          onClick={() => setActivePanel('ask-ai')}
        >
          <MessageSquare className="h-5 w-5" aria-hidden="true" />
        </Button>
        {/* Phones and tablets get the AI button only: the stacked pair covered
            the right edge of cards and the exam-mode "Palette" button
            (bottom-20, below lg), and select-then-tap does not work well on
            touch. Keep in step with --floating-dock-reserve in globals.css. */}
        <Button
          variant="secondary"
          size="icon"
          aria-label="Create flashcard from selected text"
          className="hidden lg:inline-flex rounded-full shadow-lg h-11 w-11 sm:h-12 sm:w-12 focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          onClick={() => {
            const selection = window.getSelection()?.toString();
            if (selection) {
              setSelectedText(selection);
            }
            setActivePanel('flashcard');
          }}
        >
          <Layers className="h-5 w-5" aria-hidden="true" />
        </Button>
      </div>
    );
  }

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="floating-dock-title" className="fixed bottom-6 right-6 w-80 sm:w-96 bg-card border border-border shadow-2xl rounded-2xl flex flex-col z-50 overflow-hidden animate-in slide-in-from-bottom-5">
      <div className="flex justify-between items-center p-4 border-b bg-muted/50">
        <h3 id="floating-dock-title" className="font-semibold text-sm">
          {activePanel === 'ask-ai' ? 'Ask AI Assistant' : 'Create Flashcard'}
        </h3>
        <Button variant="ghost" size="icon" aria-label="Close floating panel" className="h-8 w-8 rounded-full" onClick={() => setActivePanel('none')}>
          <X className="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>

      {statusMessage && (
        <div role="status" className="bg-primary/10 text-primary border-b border-primary/20 text-xs px-4 py-2 font-medium animate-in fade-in">
          {statusMessage}
        </div>
      )}

      <div className="p-4 flex-1 flex flex-col gap-4 max-h-[60vh] overflow-y-auto">
        {activePanel === 'ask-ai' && (
          <>
            {contextQuestionId && (
              <div className="text-xs text-muted-foreground bg-muted p-2 rounded">
                Context: Question #{contextQuestionId}
              </div>
            )}
            <textarea
              aria-label="Your question for the AI assistant"
              className="w-full bg-background border rounded-md p-2 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-primary"
              rows={3}
              placeholder="Ask anything..."
              value={aiQuery}
              onChange={(e) => setAiQuery(e.target.value)}
            />
            <Button onClick={handleAskAI} disabled={loading} className="w-full">
              {loading ? 'Thinking...' : 'Send'} <Send className="w-4 h-4 ml-2" />
            </Button>
            {aiNotice && (
              <div role="status" className={`rounded-lg border px-3 py-2 text-xs leading-relaxed ${NOTICE_CLASSES[aiNotice.kind]}`}>
                <p>{aiNotice.text}</p>
                {aiNotice.href && aiNotice.linkLabel && (
                  <Link
                    href={aiNotice.href}
                    onClick={() => setActivePanel('none')}
                    className="mt-1 inline-block font-semibold underline underline-offset-2"
                  >
                    {aiNotice.linkLabel}
                  </Link>
                )}
              </div>
            )}
            {aiResponse && (
              <div className="mt-4 flex flex-col gap-2">
                {aiOffline && (
                  <p className="inline-flex w-fit items-center gap-1.5 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[11px] font-semibold text-amber-800 dark:text-amber-200">
                    <WifiOff className="h-3 w-3 shrink-0" aria-hidden="true" />
                    Offline answer · textbook library, no AI model · not charged
                  </p>
                )}
                <div className="bg-muted/30 p-3 rounded-lg border border-border/50">
                  <ReplyMarkdown text={aiResponse} />
                </div>
                {aiCitations.length > 0 && (
                  <div className="text-xs text-muted-foreground">
                    <p className="mb-1 flex items-center gap-1 font-semibold text-foreground">
                      <BookOpen className="h-3 w-3" aria-hidden="true" /> Sources
                    </p>
                    <ul className="space-y-0.5 break-words">
                      {aiCitations.map((c, i) => (
                        <li key={`${c.book}-${c.page}-${i}`}>
                          {c.book}{c.page ? ` · p. ${c.page}` : ''}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <div className="flex gap-2 justify-end">
                  <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={() => {
                    api.post('/ai/feedback/', { query: aiQuery, response_text: aiResponse, is_helpful: true })
                      .then(() => showStatus('Thanks for your feedback!'))
                      .catch(() => showStatus('Could not send feedback. Please try again.'));
                  }}>
                    👍 Helpful
                  </Button>
                  <Button variant="ghost" size="sm" className="h-6 text-xs text-destructive hover:text-destructive" onClick={() => {
                    api.post('/ai/feedback/', { query: aiQuery, response_text: aiResponse, is_helpful: false, report_reason: 'User report from dock' })
                      .then(() => showStatus('Response flagged for review.'))
                      .catch(() => showStatus('Could not send the report. Please try again.'));
                  }}>
                    👎 Report
                  </Button>
                </div>
              </div>
            )}
          </>
        )}

        {activePanel === 'flashcard' && (
          <>
            <div>
              <label className="text-xs font-semibold mb-1 block">Front (Selected Text)</label>
              <textarea
                className="w-full bg-background border rounded-md p-2 text-sm resize-none"
                rows={3}
                value={selectedText}
                onChange={(e) => setSelectedText(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs font-semibold mb-1 block">Back (Answer)</label>
              <textarea
                className="w-full bg-background border rounded-md p-2 text-sm resize-none"
                rows={3}
                value={aiResponse}
                onChange={(e) => setAiResponse(e.target.value)}
              />
            </div>
            <Button onClick={handleSaveFlashcard} className="w-full">
              Save Flashcard <Save className="w-4 h-4 ml-2" />
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
