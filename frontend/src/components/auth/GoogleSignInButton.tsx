'use client';

/**
 * "Sign in with Google" for the Django-native sign-in (NEXT_PUBLIC_AUTH_MODE=django).
 *
 * Renders Google's own button (Google Identity Services, popup mode). The
 * GIS script is loaded by this component only, so only on the pages that show
 * it (login, register, and Settings once "Connect Google" is clicked), and
 * only when NEXT_PUBLIC_GOOGLE_CLIENT_ID is set; otherwise nothing renders.
 * The ID token the visitor's choice produces goes to `onCredential`, which
 * posts it to the backend (lib/localAuth.ts googleSignIn / authAPI.googleLink).
 * GIS calls are in lib/googleIdentity.ts.
 */
import Script from 'next/script';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
    GSI_CLIENT_SRC,
    googleClientId,
    googleSignInConfigured,
    isGsiLoaded,
    renderGoogleButton,
    type GoogleButtonText,
    type GsiWindow,
} from '@/lib/googleIdentity';

interface GoogleSignInButtonProps {
    onCredential: (credential: string) => void;
    text?: GoogleButtonText;
    /** Dims the button and ignores clicks while the page handles a credential. */
    busy?: boolean;
}

export default function GoogleSignInButton({ onCredential, text = 'continue_with', busy = false }: GoogleSignInButtonProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const onCredentialRef = useRef(onCredential);
    const [loadFailed, setLoadFailed] = useState(false);
    const enabled = googleSignInConfigured();
    const clientId = googleClientId();

    useEffect(() => {
        onCredentialRef.current = onCredential;
    }, [onCredential]);

    const render = useCallback(() => {
        const container = containerRef.current;
        if (!container || !clientId) return;
        renderGoogleButton(window as unknown as GsiWindow, container, {
            clientId,
            text,
            onCredential: (credential) => onCredentialRef.current(credential),
        });
    }, [clientId, text]);

    // Script already loaded (another page rendered the button before).
    useEffect(() => {
        if (enabled && isGsiLoaded(window as unknown as GsiWindow)) render();
    }, [enabled, render]);

    if (!enabled) return null;

    return (
        <div className="w-full">
            <Script
                src={GSI_CLIENT_SRC}
                strategy="afterInteractive"
                onReady={render}
                onError={() => setLoadFailed(true)}
            />
            <div
                ref={containerRef}
                aria-busy={busy}
                className={`flex min-h-[44px] w-full justify-center ${busy ? 'pointer-events-none opacity-60' : ''}`}
            />
            {loadFailed && (
                <p className="mt-2 text-center text-xs text-muted-foreground">
                    Google sign-in could not be loaded. Check your connection or ad blocker, or use your email and password.
                </p>
            )}
        </div>
    );
}
