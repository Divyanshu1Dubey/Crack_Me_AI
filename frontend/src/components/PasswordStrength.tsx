'use client';
import { useMemo } from 'react';

interface PasswordStrengthProps {
    password: string;
}

function getStrength(password: string): { score: number; label: string; color: string } {
    if (!password) return { score: 0, label: '', color: '' };
    let score = 0;
    if (password.length >= 8) score++;
    if (password.length >= 12) score++;
    if (/[A-Z]/.test(password)) score++;
    if (/[0-9]/.test(password)) score++;
    if (/[^A-Za-z0-9]/.test(password)) score++;

    if (score <= 1) return { score: 1, label: 'Weak', color: 'bg-red-500' };
    if (score <= 2) return { score: 2, label: 'Fair', color: 'bg-orange-500' };
    if (score <= 3) return { score: 3, label: 'Good', color: 'bg-yellow-500' };
    if (score <= 4) return { score: 4, label: 'Strong', color: 'bg-emerald-500' };
    return { score: 5, label: 'Very Strong', color: 'bg-green-600' };
}

export default function PasswordStrength({ password }: PasswordStrengthProps) {
    const strength = useMemo(() => getStrength(password), [password]);

    if (!password) return null;

    return (
        <div className="mt-1.5 space-y-1">
            <div className="flex gap-1 h-1">
                {[1, 2, 3, 4, 5].map(i => (
                    <div key={i} className={`flex-1 rounded-full transition-colors ${i <= strength.score ? strength.color : 'bg-muted'}`} />
                ))}
            </div>
            <p className={`text-[10px] font-medium ${strength.score <= 2 ? 'text-red-500' : strength.score <= 3 ? 'text-yellow-600' : 'text-emerald-600'}`}>
                {strength.label}
            </p>
        </div>
    );
}
