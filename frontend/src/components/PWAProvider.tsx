'use client';

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';

interface PWAContextType {
    deferredPrompt: any;
    promptInstall: () => void;
}

const PWAContext = createContext<PWAContextType>({
    deferredPrompt: null,
    promptInstall: () => {},
});

export const usePWA = () => useContext(PWAContext);

export default function PWAProvider({ children }: { children: ReactNode }) {
    const [deferredPrompt, setDeferredPrompt] = useState<any>(null);

    useEffect(() => {
        // Register Service Worker
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js').catch(err => {
                console.error('Service Worker registration failed:', err);
            });
        }

        // Listen for beforeinstallprompt
        const handler = (e: Event) => {
            e.preventDefault();
            setDeferredPrompt(e);
        };
        window.addEventListener('beforeinstallprompt', handler);

        return () => {
            window.removeEventListener('beforeinstallprompt', handler);
        };
    }, []);

    const promptInstall = async () => {
        if (!deferredPrompt) {
            alert("App is already installed or your browser doesn't support installation from this device.");
            return;
        }
        deferredPrompt.prompt();
        const { outcome } = await deferredPrompt.userChoice;
        if (outcome === 'accepted') {
            setDeferredPrompt(null);
        }
    };

    return (
        <PWAContext.Provider value={{ deferredPrompt, promptInstall }}>
            {children}
        </PWAContext.Provider>
    );
}
