const argv = process.argv.slice(2);
const options = {};
for (let index = 0; index < argv.length; index += 2) {
  const name = argv[index];
  const value = argv[index + 1];
  if (!name?.startsWith("--") || value === undefined) {
    process.stderr.write("invalid mobile fixture arguments\n");
    process.exit(64);
  }
  options[name.slice(2)] = value;
}

const driver = options.driver;
const platform = options.platform;
const scenario = options.scenario;
const drivers = new Set(["appium", "maestro"]);
const platforms = new Set(["ios", "android"]);
const scenarios = new Set([
  "pass",
  "product-defect",
  "cleanup-failure",
  "capability-unavailable",
  "upgrade",
]);
if (
  Object.keys(options).length !== 3
  || !drivers.has(driver)
  || !platforms.has(platform)
  || !scenarios.has(scenario)
) {
  process.stderr.write("invalid mobile fixture arguments\n");
  process.exit(64);
}

const targetReference = platform === "ios"
  ? `${driver}-ios-sim`
  : `${driver}-android-emu`;
const artifactReference = `artifact-candidate-${platform}`;

const payload = {
  fixture: true,
  evidence_origin: "fixture",
  driver,
  driver_version: "fixture-1.0",
  platform,
  os_version: "fixture-os",
  target_kind: platform === "ios" ? "simulator" : "emulator",
  application_build_ref: artifactReference,
  target_reference: targetReference,
  target_tier: "local",
  lifecycle: scenario === "upgrade"
    ? ["target", "prior-install", "prior-state", "candidate-upgrade", "launch", "cleanup"]
    : ["target", "install", "app-reset", "permissions", "launch", "cleanup"],
  check_ids: ["check-mobile-login"],
  outcomes: [{
    check_id: "check-mobile-login",
    status: scenario === "product-defect" ? "failed" : "passed",
  }],
  cleanup_successful: scenario !== "cleanup-failure",
  capability_available: scenario !== "capability-unavailable",
};

process.stdout.write(`${JSON.stringify(payload)}\n`);
if (scenario === "capability-unavailable") {
  process.exit(2);
}
if (scenario === "product-defect" || scenario === "cleanup-failure") {
  process.exit(1);
}
