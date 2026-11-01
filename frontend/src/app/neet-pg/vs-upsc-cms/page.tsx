import { permanentRedirect } from 'next/navigation';

/**
 * /neet-pg/vs-upsc-cms compared the same pair as /cms/vs-neet-pg but with
 * different (and partly wrong) facts — e.g. "NEET PG: no negative marking",
 * "UPSC CMS: offline OMR, 960 marks". One URL per comparison: this route now
 * permanently redirects (308) to the maintained page.
 */
export default function NEETPGVsUPSCPage() {
    permanentRedirect('/cms/vs-neet-pg');
}
