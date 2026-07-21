import { NEETPG_VS_USMLE } from '@/lib/comparisonData';
import ComparisonLayout, { buildComparisonMetadata } from '@/components/ComparisonLayout';
import type { Metadata } from 'next';

export const metadata: Metadata = buildComparisonMetadata(NEETPG_VS_USMLE, '/neet-pg/vs-usmle');

export default function NEETPGVsUSMLEPage() {
    return ComparisonLayout(NEETPG_VS_USMLE);
}