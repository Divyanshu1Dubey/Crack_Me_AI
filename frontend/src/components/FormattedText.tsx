import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkBreaks from 'remark-breaks';

interface FormattedTextProps {
    text: string;
    className?: string;
}

/**
 * Renders medical question text with proper formatting.
 * Uses remark-breaks to honor line breaks exactly as typed in the admin panel.
 */
export function FormattedText({ text, className = '' }: FormattedTextProps) {
    if (!text) return null;

    // We no longer strip starting numbers or do heavy string replacements
    // because that breaks exact spacing and formatting that admins type.
    // remark-breaks handles newline -> <br> natively.

    return (
        <div className={`formatted-text ${className}`} style={{ whiteSpace: 'pre-wrap' }}>
            <ReactMarkdown remarkPlugins={[remarkBreaks]}>{text}</ReactMarkdown>
        </div>
    );
}

/** 
 * Strips markdown symbols for plain-text previews (list cards, etc.) 
 * We keep this here if needed by other components.
 */
export function stripMarkdown(text: string): string {
    if (!text) return '';
    return text
        .replace(/\*\*(.+?)\*\*/g, '$1')   // **bold** → bold
        .replace(/\*(.+?)\*/g, '$1')       // *italic* → italic
        .replace(/`(.+?)`/g, '$1')         // `code` → code
        .replace(/!\[.*?\]\(.*?\)/g, '')   // remove images
        .replace(/\[(.+?)\]\(.*?\)/g, '$1')// [link](url) → link
        .replace(/#/g, '')                 // remove headers
        .trim();
}
