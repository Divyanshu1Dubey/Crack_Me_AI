// Registers the "@/..." alias + extension-less .ts resolution for unit tests.
// Usage (from frontend/; list files or quoted globs — passing the bare
// directory fails with ERR_UNSUPPORTED_DIR_IMPORT on Node 22):
//   node --import ./tests/unit/register-ts-alias.mjs --test "tests/unit/*.test.mjs" "tests/unit/*.test.ts"
import { register } from 'node:module';

register('./ts-alias-hooks.mjs', import.meta.url);
