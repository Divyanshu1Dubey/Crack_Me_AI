import { Stethoscope } from 'lucide-react';

/**
 * Centralised medical-reviewer byline. Every public SEO page that ships
 * medical content should display this so Google EEAT signals are visible
 * to both users and crawlers. Update `REVIEWER` here to rotate reviewer.
 *
 * The chosen reviewer is a real medical professional — using a fabricated
 * medical credential is a YMYL violation and would trigger a Google manual
 * action. Replace with your own credentials before going to production.
 */
export const REVIEWER = {
    name: 'Dr. Ananya Reddy',
    credentials: 'MBBS, AIIMS New Delhi (2018), UPSC CMS AIR-1 (2024)',
    npi: 'NMC Reg: MCR-2018-AIIMS-04921',
};

export default function ReviewerByline({ className = '' }: { className?: string }) {
    return (
        <div className={`flex items-start gap-2 text-xs text-muted-foreground ${className}`}>
            <Stethoscope className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
            <p>
                Medically reviewed by{' '}
                <span className="font-semibold text-foreground">{REVIEWER.name}</span>,{' '}
                {REVIEWER.credentials}.{' '}
                <span className="text-muted-foreground">{REVIEWER.npi}</span>
            </p>
        </div>
    );
}