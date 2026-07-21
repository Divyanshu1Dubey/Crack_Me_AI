import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getAllCmsBookSlugs, getCmsBook } from '@/lib/bookDeepDiveData';
import BookDeepDiveLayout, { buildBookDeepDiveMetadata } from '@/components/BookDeepDiveLayout';

export async function generateStaticParams() {
    return getAllCmsBookSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata(
    { params }: { params: Promise<{ slug: string }> },
): Promise<Metadata> {
    const { slug } = await params;
    const data = getCmsBook(slug);
    if (!data) return { title: 'UPSC CMS Book | CrackCMS', robots: { index: false } };
    return buildBookDeepDiveMetadata(data, `/cms/books/${slug}`);
}

export const revalidate = 86400;

export default async function CMSBookPage({ params }: { params: Promise<{ slug: string }> }) {
    const { slug } = await params;
    const data = getCmsBook(slug);
    if (!data) notFound();
    return BookDeepDiveLayout(data);
}