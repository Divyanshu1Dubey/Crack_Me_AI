/**
 * Settings > Connected Devices (C8, wave 3 Z3), checked on the page source:
 *  - "This device" only on the row the API marks is_current
 *  - ?deviceLimit=1 leaves the URL (router.replace) when the notice is
 *    dismissed or a device is removed
 *  - the device-limit notice offers /subscription to free users (a plan
 *    allows 4 devices; the over-limit device may stay there, lib/deviceLimit.ts)
 *  - removing the current device signs this browser out right away
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/settings-devices.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { shouldOpenSettingsForDeviceLimit } from '../../src/lib/deviceLimit.ts';

const page = readFileSync(fileURLToPath(new URL('../../src/app/settings/page.tsx', import.meta.url)), 'utf8');

/** Source of the `const name = ...` handler, up to the next top-level marker. */
const handler = (name: string, end: string) => {
  const start = page.indexOf(`const ${name}`);
  assert.ok(start >= 0, `${name} not found`);
  return page.slice(start, page.indexOf(end, start + 1));
};

test('"This device" is shown only where the API sets is_current', () => {
  assert.equal(page.match(/>This device</g)?.length, 1);
  assert.match(page, /\{device\.is_current === true && \(\s*<span[^>]*>This device<\/span>/);
});

test('dismissing the notice or removing a device drops ?deviceLimit=1 with router.replace', () => {
  const dismiss = handler('dismissDeviceLimitNotice', 'useEffect(');
  assert.match(dismiss, /setDeviceLimitHit\(false\)/);
  assert.match(dismiss, /params\.delete\('deviceLimit'\)/);
  assert.match(dismiss, /router\.replace\(/);
  assert.match(page, /onClick=\{dismissDeviceLimitNotice\}/);

  const remove = handler('handleRemoveDevice', 'return (');
  assert.match(remove, /if \(deviceLimitHit\) \{\s*dismissDeviceLimitNotice\(\);/);
});

test('free users over the limit are offered a plan, which the over-limit device can buy', () => {
  assert.match(page, /\{user && !user\.is_subscribed && \([\s\S]*?<Link href="\/subscription"[\s\S]*?allows 4 devices/);
  assert.equal(shouldOpenSettingsForDeviceLimit('/subscription'), false);
});

test('removing the current device makes the follow-up request that signs this browser out', () => {
  const remove = handler('handleRemoveDevice', 'return (');
  assert.match(remove, /if \(device\.is_current === true\) \{[\s\S]*?fetchDevices\(\);\s*return;\s*\}/);
});
