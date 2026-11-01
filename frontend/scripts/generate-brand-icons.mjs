// Generates correctly sized brand icons + the default Open Graph image from
// public/cms-circle-logo.png (1254x1254), so the favicon, apple-touch icon,
// PWA manifest and og:image no longer ship the 900 KB source logo with
// wrong declared sizes.
//
// Usage (from frontend/):  node scripts/generate-brand-icons.mjs
// Uses sharp (installed with next). Output is deterministic for a given
// sharp/libvips version: plain resizes onto the logo's own black background,
// no text or fonts, no metadata.
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SRC = path.join(FRONTEND, 'public', 'cms-circle-logo.png');
const OUT = path.join(FRONTEND, 'public', 'brand');
const BLACK = { r: 0, g: 0, b: 0, alpha: 1 };
const PNG = { compressionLevel: 9, adaptiveFiltering: true };

mkdirSync(OUT, { recursive: true });

async function square(size, file) {
    await sharp(SRC).resize(size, size, { kernel: 'lanczos3' }).png(PNG).toFile(path.join(OUT, file));
}

/** Logo scaled to `scale` of the canvas, centred on black (maskable safe zone / OG card). */
async function padded(width, height, logoSize, file) {
    const logo = await sharp(SRC).resize(logoSize, logoSize, { kernel: 'lanczos3' }).png().toBuffer();
    const canvas = await sharp({ create: { width, height, channels: 4, background: BLACK } })
        .composite([{ input: logo, left: Math.round((width - logoSize) / 2), top: Math.round((height - logoSize) / 2) }])
        .png()
        .toBuffer();
    // Second pass: sharp applies flatten before composite within one
    // pipeline, so drop the (fully opaque) alpha channel here.
    await sharp(canvas).flatten({ background: BLACK }).png(PNG).toFile(path.join(OUT, file));
}

await square(32, 'favicon-32.png');
await square(180, 'apple-touch-icon.png');
await square(192, 'icon-192.png');
await square(512, 'icon-512.png');
// The ring spans ~87% of the source; at 88% of the canvas it sits inside
// the 80%-diameter safe zone that Android masks to.
await padded(512, 512, Math.round(512 * 0.88), 'icon-maskable-512.png');
// 1200x630 Open Graph / Twitter card: the logo centred on its own background.
await padded(1200, 630, 560, 'og-image.png');

console.log(`brand icons written to ${path.relative(FRONTEND, OUT)}`);
