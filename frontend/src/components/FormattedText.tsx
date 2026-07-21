import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import { decodeMojiB } from '@/lib/textCleanup';

interface FormattedTextProps {
    text: string;
    className?: string;
}

/**
 * Renders medical question text with proper formatting.
 * Uses remark-breaks to honor line breaks exactly as typed in the admin panel.
 *
 * Also decodes UTF-8 mojibake so text originally stored with double-encoded
 * punctuation ("ΓÇÿ", "ΓÇÖ", etc.) renders correctly.
 */
export function FormattedText({ text, className = '' }: FormattedTextProps) {
    if (!text) return null;

    const clean = decodeMojiB(text);

    return (
        <div className={`formatted-text ${className}`}>
            <ReactMarkdown remarkPlugins={[remarkBreaks]}>{clean}</ReactMarkdown>
        </div>
    );
}

/**
 * Strips markdown symbols for plain-text previews (list cards, etc.).
 * Also decodes mojibake so the preview shows real punctuation.
 */
export function stripMarkdown(text: string): string {
    if (!text) return '';
    return decodeMojiB(text)
        .replace(/\*\*(.+?)\*\*/g, '$1')
        .replace(/\*(.+?)\*/g, '$1')
        .replace(/`(.+?)`/g, '$1')
        .replace(/!\[.*?\]\(.*?\)/g, '')
        .replace(/\[(.+?)\]\(.*?\)/g, '$1')
        .replace(/#/g, '')
        .trim();
}
