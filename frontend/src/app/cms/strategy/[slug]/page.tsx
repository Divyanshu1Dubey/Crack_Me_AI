import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getAllCmsStrategySlugs, getCmsStrategy } from '@/lib/strategyData';
import StrategyLayout, { buildStrategyMetadata } from '@/components/StrategyLayout';

export async function generateStaticParams() {
    return getAllCmsStrategySlugs().map((slug) => ({ slug }));
}

export async function generateMetadata(
    { params }: { params: Promise<{ slug: string }> },
): Promise<Metadata> {
    const { slug } = await params;
    const data = getCmsStrategy(slug);
    if (!data) return { title: 'UPSC CMS Strategy | CrackCMS', robots: { index: false } };
    return buildStrategyMetadata(data, `/cms/strategy/${slug}`);
}

export const revalidate = 86400;

export default async function CMSStrategyPage({ params }: { params: Promise<{ slug: string }> }) {
    const { slug } = await params;
    const data = getCmsStrategy(slug);
    if (!data) notFound();
    return StrategyLayout(data);
}