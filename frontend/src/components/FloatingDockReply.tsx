'use client';

import ReactMarkdown from 'react-markdown';

/**
 * Markdown body of a FloatingDock "Ask AI" reply (AI answers and the
 * offline textbook extract are markdown). FloatingDock loads this module on
 * demand, so react-markdown stays out of the bundle that every page loads.
 * `skipHtml`: model text is never rendered as markup.
 */
export default function FloatingDockReply({ text }: { text: string }) {
  return (
    <div className="formatted-text break-words text-sm text-foreground">
      <ReactMarkdown skipHtml>{text}</ReactMarkdown>
    </div>
  );
}
