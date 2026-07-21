import Link from "next/link";
import { ChevronRight, Home } from "lucide-react";

/**
 * Site-wide breadcrumb UI. Renders a semantic <nav aria-label="Breadcrumb">
 * with a JSON-LD-friendly item order. Each crumb links to its path.
 */
export default function Breadcrumbs({
    items,
}: {
    items: { name: string; path: string }[];
}) {
    return (
        <nav aria-label="Breadcrumb" className="text-xs text-muted-foreground">
            <ol className="flex flex-wrap items-center gap-1">
                <li className="flex items-center gap-1">
                    <Link href="/" className="inline-flex items-center gap-1 hover:text-foreground transition-colors">
                        <Home className="h-3 w-3" /> Home
                    </Link>
                    {items.length > 0 && <ChevronRight className="h-3 w-3 opacity-60" />}
                </li>
                {items.map((it, i) => {
                    const isLast = i === items.length - 1;
                    return (
                        <li key={it.path} className="flex items-center gap-1">
                            {isLast ? (
                                <span aria-current="page" className="font-semibold text-foreground">{it.name}</span>
                            ) : (
                                <>
                                    <Link href={it.path} className="hover:text-foreground transition-colors">{it.name}</Link>
                                    <ChevronRight className="h-3 w-3 opacity-60" />
                                </>
                            )}
                        </li>
                    );
                })}
            </ol>
        </nav>
    );
}
