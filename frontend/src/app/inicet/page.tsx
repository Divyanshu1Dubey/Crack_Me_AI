import { permanentRedirect } from 'next/navigation';

/**
 * /inicet duplicated /ini-cet (different title, canonical and facts) and
 * split links between the two. /ini-cet is the canonical INI-CET page (it is
 * in the sitemap and matches the /neet-pg URL style), so this route
 * permanently redirects (308) there.
 */
export default function IniCetPage() {
    permanentRedirect('/ini-cet');
}
