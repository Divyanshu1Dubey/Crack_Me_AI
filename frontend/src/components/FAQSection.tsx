import { GraduationCap } from "lucide-react";

/**
 * Reusable FAQ accordion component. The same items array can also be passed
 * to <StructuredData id="..." data={faqSchema(items)} /> to emit FAQPage JSON-LD.
 */
export interface FAQItem {
    q: string;
    a: string;
}

export default function FAQSection({
    items,
    title = "Frequently asked questions",
    showIcon = true,
}: {
    items: FAQItem[];
    title?: string;
    showIcon?: boolean;
}) {
    if (items.length === 0) return null;
    return (
        <section className="rounded-2xl border border-border bg-card p-6 sm:p-8">
            <h2 className="text-xl font-bold flex items-center gap-2">
                {showIcon ? <GraduationCap className="h-5 w-5 text-primary" /> : null}
                {title}
            </h2>
            <div className="mt-5 space-y-3">
                {items.map((f, i) => (
                    <details
                        key={f.q}
                        className="rounded-xl border border-border bg-background p-4 open:bg-accent/30"
                        open={i === 0}
                    >
                        <summary className="cursor-pointer text-sm font-bold text-foreground list-none">
                            {f.q}
                        </summary>
                        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{f.a}</p>
                    </details>
                ))}
            </div>
        </section>
    );
}
