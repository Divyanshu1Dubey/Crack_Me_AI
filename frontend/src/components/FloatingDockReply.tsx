'use client';

import ReactMarkdown from 'react-markdown';
import { normalizeTutorMarkdown, tutorRehypePlugins, tutorRemarkPlugins } from '@/lib/tutorMarkdown';

/**
 * Markdown body of a FloatingDock "Ask AI" reply (AI answers and the
 * offline textbook extract are markdown). FloatingDock loads this module on
 * demand, so react-markdown stays out of the bundle that every page loads.
 * Same pipeline as the AI Tutor (src/lib/tutorMarkdown.ts): GFM tables, <br>
 * inside cells, raw HTML reduced to formatting tags by the shared allow-list.
 */
export default function FloatingDockReply({ text }: { text: string }) {
  return (
    <div className="formatted-text break-words text-sm text-foreground">
      <ReactMarkdown
        remarkPlugins={tutorRemarkPlugins}
        rehypePlugins={tutorRehypePlugins}
        components={{
          table: ({ children }) => <div className="formatted-table-wrap"><table>{children}</table></div>,
          // Model-written image links are often invented: show the description only.
          img: ({ alt }) => (alt ? <span>[{alt}]</span> : null),
        }}
      >
        {normalizeTutorMarkdown(text)}
      </ReactMarkdown>
    </div>
  );
}
