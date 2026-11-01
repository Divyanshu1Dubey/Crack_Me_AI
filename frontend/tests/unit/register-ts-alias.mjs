// Registers the "@/..." alias + extension-less .ts resolution for unit tests.
// Usage (from frontend/):
//   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/
import { register } from 'node:module';

register('./ts-alias-hooks.mjs', import.meta.url);
