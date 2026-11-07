/**
 * Brand marks for the footer's social links and the blog's share bar.
 *
 * lucide-react 1.x no longer ships brand logos, so the three the site uses are kept here: the same
 * 24x24 outline drawings as lucide-react 0.576.0's Github, Twitter and Linkedin icons, with lucide's
 * default SVG attributes (stroke = currentColor, width 2, round caps), so they size and colour like
 * every other icon. Plain function components (no hooks): usable in server and client components.
 *
 * The drawings come from Lucide (https://lucide.dev), under this licence:
 *
 *   ISC License
 *   Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2026 as part of Feather (MIT).
 *   All other copyright (c) for Lucide are held by Lucide Contributors 2026.
 *
 *   Permission to use, copy, modify, and/or distribute this software for any purpose with or without
 *   fee is hereby granted, provided that the above copyright notice and this permission notice appear
 *   in all copies.
 *
 *   THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS
 *   SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE
 *   AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
 *   WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT,
 *   NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE
 *   OF THIS SOFTWARE.
 */
import type { ReactNode, SVGProps } from 'react';

type IconProps = SVGProps<SVGSVGElement>;

function BrandIcon({ children, ...props }: IconProps & { children: ReactNode }) {
    return (
        <svg
            xmlns="http://www.w3.org/2000/svg"
            width={24}
            height={24}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
            focusable="false"
            {...props}
        >
            {children}
        </svg>
    );
}

export function GithubIcon(props: IconProps) {
    return (
        <BrandIcon {...props}>
            <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
            <path d="M9 18c-4.51 2-5-2-7-2" />
        </BrandIcon>
    );
}

export function TwitterIcon(props: IconProps) {
    return (
        <BrandIcon {...props}>
            <path d="M22 4s-.7 2.1-2 3.4c1.6 10-9.4 17.3-18 11.6 2.2.1 4.4-.6 6-2C3 15.5.5 9.6 3 5c2.2 2.6 5.6 4.1 9 4-.9-4.2 4-6.6 7-3.8 1.1 0 3-1.2 3-1.2z" />
        </BrandIcon>
    );
}

export function LinkedinIcon(props: IconProps) {
    return (
        <BrandIcon {...props}>
            <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z" />
            <rect width="4" height="12" x="2" y="9" />
            <circle cx="4" cy="4" r="2" />
        </BrandIcon>
    );
}
