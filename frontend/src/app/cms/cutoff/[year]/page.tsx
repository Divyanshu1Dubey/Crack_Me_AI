import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getAllCmsCutoffYears, getCmsCutoff } from '@/lib/cutoffData';
import CutoffLayout, { buildCutoffMetadata } from '@/components/CutoffLayout';

export async function generateStaticParams() {
    return getAllCmsCutoffYears().map((year) => ({ year: String(year) }));
}

export async function generateMetadata(
    { params }: { params: Promise<{ year: string }> },
): Promise<Metadata> {
    const { year } = await params;
    const data = getCmsCutoff(Number(year));
    if (!data) return { title: 'UPSC CMS Cutoff | CrackCMS', robots: { index: false } };
    return buildCutoffMetadata(data, `/cms/cutoff/${year}`);
}

export const revalidate = 86400;

export default async function CMSCutoffYearPage({ params }: { params: Promise<{ year: string }> }) {
    const { year } = await params;
    const data = getCmsCutoff(Number(year));
    if (!data) notFound();
    return CutoffLayout(data);
}