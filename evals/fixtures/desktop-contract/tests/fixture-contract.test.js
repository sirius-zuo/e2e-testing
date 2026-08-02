const test = require('node:test');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
function run(driver, platform, appKind, scenario) {
  return spawnSync(process.execPath, [
    'test-support/desktop-driver.js', '--driver', driver,
    '--platform', platform, '--app-kind', appKind, '--scenario', scenario,
  ], { cwd: root, encoding: 'utf8' });
}

for (const [driver, platform, appKind] of [
  ['appium-mac2', 'macos', 'native'],
  ['novawindows', 'windows', 'native'],
  ['webdriverio-electron', 'macos', 'electron'],
  ['webdriverio-electron', 'windows', 'electron'],
]) {
  test(`${driver} ${platform} emits bounded pass evidence`, () => {
    const result = run(driver, platform, appKind, 'pass');
    assert.equal(result.status, 0, result.stderr);
    const payload = JSON.parse(result.stdout);
    assert.equal(payload.fixture, true);
    assert.equal(payload.evidence_origin, 'fixture');
    assert.equal(payload.session_isolated, true);
    assert.equal(payload.cleanup_successful, true);
    assert.deepEqual(payload.check_ids, ['check-desktop-launch']);
  });
}

test('mocked OS behavior cannot pass', () => {
  const result = run('webdriverio-electron', 'macos', 'electron', 'mocked-os');
  assert.equal(result.status, 3);
  assert.equal(JSON.parse(result.stdout).real_os_evidence, false);
});

test('general session cannot execute', () => {
  const result = run('novawindows', 'windows', 'native', 'session-unavailable');
  assert.equal(result.status, 2);
  assert.equal(JSON.parse(result.stdout).session_isolated, false);
});

test('update emits ordered prior and candidate phases', () => {
  const result = run('appium-mac2', 'macos', 'native', 'update');
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout).lifecycle, [
    'target', 'session', 'baseline', 'prior-install', 'prior-state',
    'candidate-update', 'launch', 'check', 'cleanup', 'restore',
  ]);
});
