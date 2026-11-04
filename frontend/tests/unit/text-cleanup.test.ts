/**
 * Display repair of UTF-8 text that an importer read as cp437 (frontend/src/lib/textCleanup.ts).
 *
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/text-cleanup.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { decodeMojiB, repairCp437Triplets } from '../../src/lib/textCleanup.ts';

test('cp437 triplets become the character they encode', () => {
  assert.equal(decodeMojiB('Glucose ΓåÆ pyruvate'), 'Glucose → pyruvate');
  assert.equal(decodeMojiB('COΓéé retention'), 'CO₂ retention');   // Γéé -> ₂
  assert.equal(decodeMojiB('pH ΓëÑ 7.45'), 'pH ≥ 7.45');           // ΓëÑ -> ≥
  assert.equal(decodeMojiB('doctorΓÇÖs'), 'doctor’s');             // ΓÇÖ -> ’
});

test('real Greek text and plain text are left alone, and the repair is idempotent', () => {
  assert.equal(repairCp437Triplets('Γάμμα κάμερα'), 'Γάμμα κάμερα');
  assert.equal(repairCp437Triplets('Gamma (Γ) distribution'), 'Gamma (Γ) distribution');
  const once = decodeMojiB('A ΓåÆ B');
  assert.equal(decodeMojiB(once), once);
  assert.equal(decodeMojiB(''), '');
});
