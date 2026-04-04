#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';

const [, , manifestArg, outputArg] = process.argv;

const manifestPath = manifestArg || 'icons/icons-manifest.json';
const outputDir = outputArg || 'public/icons/custom';

const sanitize = (value) =>
  String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9-_]+/g, '-')
    .replace(/^-+|-+$/g, '');

const extFromUrl = (url) => {
  const clean = url.split('?')[0].split('#')[0];
  const maybe = path.extname(clean).toLowerCase();
  if (maybe === '.svg' || maybe === '.png' || maybe === '.webp' || maybe === '.jpg' || maybe === '.jpeg') {
    return maybe;
  }
  return '';
};

const extFromContentType = (contentType) => {
  const c = (contentType || '').toLowerCase();
  if (c.includes('image/svg')) return '.svg';
  if (c.includes('image/png')) return '.png';
  if (c.includes('image/webp')) return '.webp';
  if (c.includes('image/jpeg')) return '.jpg';
  return '.bin';
};

const run = async () => {
  const root = process.cwd();
  const manifestFile = path.resolve(root, manifestPath);
  const destDir = path.resolve(root, outputDir);

  const manifestRaw = await fs.readFile(manifestFile, 'utf8');
  const manifest = JSON.parse(manifestRaw);

  if (!Array.isArray(manifest) || manifest.length === 0) {
    throw new Error('Manifest must be a non-empty array.');
  }

  await fs.mkdir(destDir, { recursive: true });

  const index = [];

  for (const [idx, item] of manifest.entries()) {
    const name = sanitize(item.name || `icon-${idx + 1}`);
    const url = item.url;

    if (!url || !/^https?:\/\//i.test(url)) {
      console.warn(`Skipping ${name}: invalid url`);
      continue;
    }

    console.log(`Downloading ${name} ...`);
    const response = await fetch(url);
    if (!response.ok) {
      console.warn(`Failed ${name}: HTTP ${response.status}`);
      continue;
    }

    const bytes = Buffer.from(await response.arrayBuffer());
    const contentType = response.headers.get('content-type') || '';
    const extension = extFromUrl(url) || extFromContentType(contentType);

    const filename = `${name}${extension}`;
    const fullPath = path.join(destDir, filename);
    await fs.writeFile(fullPath, bytes);

    index.push({
      name,
      file: path.posix.join(outputDir.replace(/\\/g, '/'), filename),
      source: item.source || 'unknown',
      style: item.style || 'unknown',
      notes: item.notes || '',
      contentType,
      url,
    });
  }

  const indexPath = path.join(destDir, 'icons-index.json');
  await fs.writeFile(indexPath, JSON.stringify(index, null, 2));

  console.log(`Downloaded ${index.length} icons to ${destDir}`);
  console.log(`Index written to ${indexPath}`);
};

run().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});
