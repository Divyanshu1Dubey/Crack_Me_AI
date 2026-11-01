// Node module-resolution hooks for the public-site unit tests.
//
// Lets `node --test` import the app's plain TypeScript modules directly
// (Node >= 22.18 strips the types): maps the "@/..." path alias to src/ and
// resolves extension-less relative imports to their .ts file. Only .ts
// modules are supported (no JSX), so tests target the pure data/logic files.
import { existsSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const SRC_DIR = fileURLToPath(new URL('../../src/', import.meta.url));

function firstExisting(base) {
    const candidates = [base, `${base}.ts`, `${base}.mts`, path.join(base, 'index.ts')];
    for (const candidate of candidates) {
        if (existsSync(candidate) && statSync(candidate).isFile()) return candidate;
    }
    return null;
}

export async function resolve(specifier, context, nextResolve) {
    if (specifier.startsWith('@/')) {
        const hit = firstExisting(path.join(SRC_DIR, specifier.slice(2)));
        if (hit) return nextResolve(pathToFileURL(hit).href, context);
    }
    if ((specifier.startsWith('./') || specifier.startsWith('../')) && context.parentURL?.startsWith('file:')) {
        const parentDir = path.dirname(fileURLToPath(context.parentURL));
        const target = path.resolve(parentDir, specifier);
        if (!existsSync(target) || !statSync(target).isFile()) {
            const hit = firstExisting(target);
            if (hit) return nextResolve(pathToFileURL(hit).href, context);
        }
    }
    return nextResolve(specifier, context);
}
