import { CMS_VS_INICET } from '@/lib/comparisonData';
import ComparisonLayout, { buildComparisonMetadata } from '@/components/ComparisonLayout';
import type { Metadata } from 'next';

export const metadata: Metadata = buildComparisonMetadata(CMS_VS_INICET, '/cms/vs-ini-cet');

export default function CMSVsINICETPage() {
    return ComparisonLayout(CMS_VS_INICET);
}