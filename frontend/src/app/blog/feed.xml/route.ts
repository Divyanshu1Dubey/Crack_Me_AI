import { getAllPosts } from '@/lib/blog';
import { siteName, siteUrl, defaultOgImage } from '@/lib/seo';

/**
 * RSS 2.0 feed for the CrackCMS blog — served at `/blog/feed.xml`.
 *
 * Generates a hand-formatted XML response so we don't pull in a
 * dependency for such a small file. Cached for an hour via the
 * standard `Cache-Control` header so feed readers don't hammer us.
 */
export async function GET() {
    const posts = getAllPosts();

    const escapeXml = (s: string) =>
        s
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&apos;');

    const items = posts
        .map((post) => {
            const url = `${siteUrl}/blog/${post.slug}`;
            const cover = post.coverImage
                ? `${siteUrl}${post.coverImage}`
                : `${siteUrl}${defaultOgImage}`;
            return `
    <item>
      <title>${escapeXml(post.title)}</title>
      <link>${url}</link>
      <guid isPermaLink="true">${url}</guid>
      <pubDate>${new Date(post.datePublished).toUTCString()}</pubDate>
      <dc:creator>${escapeXml(post.author)}</dc:creator>
      <category>${escapeXml(post.category)}</category>
      <description>${escapeXml(post.description)}</description>
      <content:encoded><![CDATA[${post.excerpt} — Read the full post at ${url}]]></content:encoded>
      <enclosure url="${cover}" type="image/png" />
    </item>`;
        })
        .join('');

    const feedUrl = `${siteUrl}/blog/feed.xml`;
    const homeUrl = `${siteUrl}/blog`;

    const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:atom="http://www.w3.org/2005/Atom"
     xmlns:dc="http://purl.org/dc/elements/1.1/"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>${escapeXml(siteName)} — Blog</title>
    <link>${homeUrl}</link>
    <description>High-yield exam strategies, last-day revision plans, mock-test scoring tactics and answer-writing guides for UPSC CMS, NEET PG, INI-CET and FMGE aspirants.</description>
    <language>en-IN</language>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
    <atom:link href="${feedUrl}" rel="self" type="application/rss+xml" />
    <image>
      <url>${siteUrl}${defaultOgImage}</url>
      <title>${escapeXml(siteName)}</title>
      <link>${homeUrl}</link>
    </image>
    ${items}
  </channel>
</rss>`;

    return new Response(xml, {
        headers: {
            'Content-Type': 'application/rss+xml; charset=utf-8',
            'Cache-Control': 'public, max-age=3600, s-maxage=3600',
        },
    });
}
