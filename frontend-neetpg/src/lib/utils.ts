import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Conditional class joining + Tailwind merge (used by every component). */
export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}
