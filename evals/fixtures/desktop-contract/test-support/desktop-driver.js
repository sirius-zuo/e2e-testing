const argv = process.argv.slice(2);
const options = {};
for (let index = 0; index < argv.length; index += 2) {
  const name = argv[index];
  const value = argv[index + 1];
  if (!name?.startsWith('--') || value === undefined) process.exit(64);
  options[name.slice(2)] = value;
}

const combinations = new Set([
  'appium-mac2:macos:native',
  'novawindows:windows:native',
  'webdriverio-electron:macos:electron',
  'webdriverio-electron:windows:electron',
]);
const scenarios = new Set([
  'pass', 'product-defect', 'cleanup-failure', 'capability-unavailable',
  'session-unavailable', 'mocked-os', 'update',
]);
const key = `${options.driver}:${options.platform}:${options['app-kind']}`;
if (Object.keys(options).length !== 4 || !combinations.has(key) || !scenarios.has(options.scenario)) {
  process.stderr.write('invalid desktop fixture arguments\n');
  process.exit(64);
}

const failure = options.scenario === 'product-defect';
const cleanupFailure = options.scenario === 'cleanup-failure';
const sessionUnavailable = options.scenario === 'session-unavailable';
const mocked = options.scenario === 'mocked-os';
const unavailable = options.scenario === 'capability-unavailable';
const lifecycle = options.scenario === 'update'
  ? ['target', 'session', 'baseline', 'prior-install', 'prior-state', 'candidate-update', 'launch', 'check', 'cleanup', 'restore']
  : ['target', 'session', 'baseline', 'install', 'launch', 'check', 'cleanup', 'restore'];
const payload = {
  fixture: true, evidence_origin: 'fixture', driver: options.driver,
  driver_version: 'fixture-1.0', adapter_version: 'fixture-1.0', backend_version: 'fixture-1.0',
  platform: options.platform, os_version: 'fixture-os', target_reference: `target-${options.platform}`,
  target_kind: 'local', target_tier: 'local', session_reference: `session-${options.platform}`,
  session_kind: 'dedicated-user', session_isolated: !sessionUnavailable,
  application_id: `app-${options['app-kind']}-${options.platform}`, application_kind: options['app-kind'],
  artifact_reference: `artifact-candidate-${options.platform}`, artifact_format: options.platform === 'macos' ? 'app' : 'msix',
  lifecycle_phase: 'verify', authorization_refs: ['authorization-desktop'], lifecycle,
  check_ids: ['check-desktop-launch'],
  outcomes: [{ check_id: 'check-desktop-launch', status: failure ? 'failed' : 'passed' }],
  cleanup_successful: !cleanupFailure, capability_available: !unavailable,
  real_os_evidence: !mocked, restored_baseline: !cleanupFailure,
};
process.stdout.write(`${JSON.stringify(payload)}\n`);
if (sessionUnavailable || unavailable) process.exit(2);
if (mocked) process.exit(3);
if (failure || cleanupFailure) process.exit(1);
