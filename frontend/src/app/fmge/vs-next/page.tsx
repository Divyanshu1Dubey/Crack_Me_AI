import { FMGE_VS_NEXT } from '@/lib/comparisonData';
import ComparisonLayout, { buildComparisonMetadata } from '@/components/ComparisonLayout';
import type { Metadata } from 'next';

export const metadata: Metadata = buildComparisonMetadata(FMGE_VS_NEXT, '/fmge/vs-next');

export default function FMGEVsNEXTPage() {
    return ComparisonLayout(FMGE_VS_NEXT);
}