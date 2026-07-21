import { CMS_VS_NEETPG } from '@/lib/comparisonData';
import ComparisonLayout, { buildComparisonMetadata } from '@/components/ComparisonLayout';
import type { Metadata } from 'next';

export const metadata: Metadata = buildComparisonMetadata(CMS_VS_NEETPG, '/cms/vs-neet-pg');

export default function CMSVsNEETPGPage() {
    return ComparisonLayout(CMS_VS_NEETPG);
}