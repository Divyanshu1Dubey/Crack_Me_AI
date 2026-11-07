/**
 * lucide-react 1.x ships no brand logos: importing Github / Twitter / Linkedin (or another brand) from it
 * fails the build ("Export Twitter doesn't exist in target module", Dependabot #61). The site's brand
 * marks live in components/icons/BrandIcons.tsx.
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/lucide-brand-icons.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND = fileURLToPath(new URL('../../', import.meta.url));
const SRC = path.join(FRONTEND, 'src');
const BRANDS = ['Github', 'Gitlab', 'Twitter', 'Linkedin', 'Facebook', 'Instagram', 'Youtube', 'Twitch', 'Slack',
  'Dribbble', 'Figma', 'Framer', 'Codepen', 'Codesandbox', 'Chrome', 'Trello', 'Pocket'];

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) return sourceFiles(full);
    return /\.(tsx?|jsx?|mjs)$/.test(name) ? [full] : [];
  });
}

test('no source file imports a brand icon from lucide-react', () => {
  const offenders: string[] = [];
  for (const file of sourceFiles(SRC)) {
    const text = readFileSync(file, 'utf8');
    for (const match of text.matchAll(/import\s*(?:type\s*)?\{([^}]*)\}\s*from\s*['"]lucide-react['"]/g)) {
      const names = match[1].split(',').map((part) => part.trim().split(/\s+as\s+/)[0].trim()).filter(Boolean);
      for (const name of names) {
        const base = name.replace(/Icon$/, '');
        if (BRANDS.includes(base)) offenders.push(`${path.relative(FRONTEND, file)}: ${name}`);
      }
    }
  }
  assert.deepEqual(offenders, []);
});

test('the footer and the blog share bar use the local brand marks', () => {
  const footer = readFileSync(path.join(SRC, 'components/Footer.tsx'), 'utf8');
  assert.match(footer, /import \{ GithubIcon, LinkedinIcon, TwitterIcon \} from '@\/components\/icons\/BrandIcons'/);
  const blog = readFileSync(path.join(SRC, 'components/BlogPostLayout.tsx'), 'utf8');
  assert.match(blog, /import \{ TwitterIcon \} from '@\/components\/icons\/BrandIcons'/);
  const icons = readFileSync(path.join(SRC, 'components/icons/BrandIcons.tsx'), 'utf8');
  assert.match(icons, /ISC License/);           // the licence notice the drawings are copied under
  assert.doesNotMatch(icons, /'use client'/);   // usable from the server-rendered blog layout
});

test('package.json is on lucide-react 1.x', () => {
  const pkg = JSON.parse(readFileSync(path.join(FRONTEND, 'package.json'), 'utf8'));
  assert.match(pkg.dependencies['lucide-react'], /^\^1\./);
  const lock = JSON.parse(readFileSync(path.join(FRONTEND, 'package-lock.json'), 'utf8'));
  assert.match(lock.packages['node_modules/lucide-react'].version, /^1\./);
});
