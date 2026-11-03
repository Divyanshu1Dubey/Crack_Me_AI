/**
 * Unit tests for src/lib/deviceLimit.ts (api.ts device_limit_reached handling).
 *
 * Run (from frontend/):  node --test tests/unit/auth-device-limit.test.ts
 *
 * An over-limit device must be able to stay on /subscription (buy the
 * 4-device plan) and /settings (remove a device): background requests there
 * (Header token pill, announcements) used to bounce it to Settings.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { DEVICE_LIMIT_SETTINGS_URL, shouldOpenSettingsForDeviceLimit } from '../../src/lib/deviceLimit.ts';

test('Settings and Subscription keep an over-limit device where it is', () => {
  for (const path of ['/settings', '/settings/devices', '/subscription', '/subscription/']) {
    assert.equal(shouldOpenSettingsForDeviceLimit(path), false, path);
  }
});

test('every other page opens Settings', () => {
  for (const path of ['/dashboard', '/questions/practice', '/tests/12', '/subscriptions-faq', '/settingsx', '/']) {
    assert.equal(shouldOpenSettingsForDeviceLimit(path), true, path);
  }
  assert.equal(DEVICE_LIMIT_SETTINGS_URL, '/settings?deviceLimit=1');
});
