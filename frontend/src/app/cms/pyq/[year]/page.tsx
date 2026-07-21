import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getAllCmsYears, getCmsYear } from '@/lib/pyqYearData';
import PyqYearLandingLayout, { buildPyqYearMetadata } from '@/components/PyqYearLandingLayout';

export async function generateStaticParams() {
    return getAllCmsYears().map((year) => ({ year: String(year) }));
}

export async function generateMetadata(
    { params }: { params: Promise<{ year: string }> },
): Promise<Metadata> {
    const { year: y } = await params;
    const year = Number(y);
    if (!Number.isFinite(year)) return {};
    const data = getCmsYear(year);
    if (!data) return { title: 'UPSC CMS PYQs | CrackCMS', robots: { index: false } };
    return buildPyqYearMetadata(data);
}

export const revalidate = 86400; // 24 hours

export default async function CMSPyqYearPage({ params }: { params: Promise<{ year: string }> }) {
    const { year: y } = await params;
    const year = Number(y);
    if (!Number.isFinite(year)) notFound();
    const data = getCmsYear(year);
    if (!data) notFound();
    return PyqYearLandingLayout(data);
}
