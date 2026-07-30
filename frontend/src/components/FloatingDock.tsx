'use client';

import React, { useState } from 'react';
import { useDock } from '@/context/DockContext';
import { MessageSquare, Layers, X, Send, Save } from 'lucide-react';
import { Button } from './ui/button';
import api from '@/lib/api';

export function FloatingDock() {
  const { activePanel, setActivePanel, contextQuestionId, selectedText, setSelectedText } = useDock();
  const [aiQuery, setAiQuery] = useState('');
  const [aiResponse, setAiResponse] = useState('');
  const [loading, setLoading] = useState(false);

  const handleAskAI = async () => {
    if (!aiQuery.trim()) return;
    setLoading(true);
    try {
      const res = await api.post('/questions/chat/', {
        message: aiQuery,
        context_question_id: contextQuestionId
      });
      setAiResponse(res.data.reply || 'No response generated.');
    } catch (e: any) {
      setAiResponse('Error connecting to AI.');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveFlashcard = async () => {
    try {
      await api.post('/questions/flashcards/', {
        front: selectedText || 'New Flashcard',
        back: aiResponse || '...',
      });
      alert('Flashcard Saved');
      setActivePanel('none');
    } catch (e) {
      alert('Error saving flashcard');
    }
  };

  if (activePanel === 'none') {
    return (
      <div className="fixed bottom-6 right-6 flex flex-col gap-2 z-50">
        <Button
          variant="default"
          size="icon"
          aria-label="Open AI Assistant"
          className="rounded-full shadow-lg h-12 w-12 bg-primary hover:bg-primary/90"
          onClick={() => setActivePanel('ask-ai')}
        >
          <MessageSquare className="h-5 w-5" aria-hidden="true" />
        </Button>
        <Button
          variant="secondary"
          size="icon"
          aria-label="Create flashcard from selected text"
          className="rounded-full shadow-lg h-12 w-12"
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

      <div className="p-4 flex-1 flex flex-col gap-4 max-h-[60vh] overflow-y-auto">
        {activePanel === 'ask-ai' && (
          <>
            {contextQuestionId && (
              <div className="text-xs text-muted-foreground bg-muted p-2 rounded">
                Context: Question #{contextQuestionId}
              </div>
            )}
            <textarea
              className="w-full bg-background border rounded-md p-2 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-primary"
              rows={3}
              placeholder="Ask anything..."
              value={aiQuery}
              onChange={(e) => setAiQuery(e.target.value)}
            />
            <Button onClick={handleAskAI} disabled={loading} className="w-full">
              {loading ? 'Thinking...' : 'Send'} <Send className="w-4 h-4 ml-2" />
            </Button>
            {aiResponse && (
              <div className="mt-4 flex flex-col gap-2">
                <div className="text-sm bg-muted/30 p-3 rounded-lg whitespace-pre-wrap border border-border/50">
                  {aiResponse}
                </div>
                <div className="flex gap-2 justify-end">
                  <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={() => {
                    api.post('/ai/feedback/', { query: aiQuery, response_text: aiResponse, is_helpful: true });
                    alert('Feedback sent: Thanks for your feedback!');
                  }}>
                    👍 Helpful
                  </Button>
                  <Button variant="ghost" size="sm" className="h-6 text-xs text-destructive hover:text-destructive" onClick={() => {
                    api.post('/ai/feedback/', { query: aiQuery, response_text: aiResponse, is_helpful: false, report_reason: 'User report from dock' });
                    alert('Reported: This response has been flagged for review.');
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
