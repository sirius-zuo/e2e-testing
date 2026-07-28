import assert from "node:assert/strict";
import {spawnSync} from "node:child_process";
import test from "node:test";

function run(driver, platform, scenario) {
  const result = spawnSync(
    process.execPath,
    ["test-support/mobile-driver.js", "--driver", driver, "--platform", platform, "--scenario", scenario],
    {cwd: new URL("..", import.meta.url), encoding: "utf8"},
  );
  return {result, payload: JSON.parse(result.stdout)};
}

for (const driver of ["appium", "maestro"]) {
  for (const platform of ["ios", "android"]) {
    test(`${driver} ${platform} fixture baseline`, () => {
      const {result, payload} = run(driver, platform, "pass");
      assert.equal(result.status, 0);
      assert.equal(payload.evidence_origin, "fixture");
      assert.equal(
        payload.target_reference,
        platform === "ios" ? `${driver}-ios-sim` : `${driver}-android-emu`,
      );
      assert.equal(
        payload.application_build_ref,
        `artifact-candidate-${platform}`,
      );
      assert.deepEqual(
        payload.lifecycle,
        ["target", "install", "app-reset", "permissions", "launch", "cleanup"],
      );
      assert.equal(payload.cleanup_successful, true);
    });
  }
}

test("upgrade preserves prior-to-candidate order", () => {
  const {result, payload} = run("appium", "ios", "upgrade");
  assert.equal(result.status, 0);
  assert.deepEqual(
    payload.lifecycle,
    ["target", "prior-install", "prior-state", "candidate-upgrade", "launch", "cleanup"],
  );
});

test("product defect, cleanup failure, and capability gaps stay distinct", () => {
  const product = run("maestro", "android", "product-defect");
  const cleanup = run("maestro", "ios", "cleanup-failure");
  const capability = run("appium", "android", "capability-unavailable");
  assert.equal(product.result.status, 1);
  assert.equal(product.payload.outcomes[0].status, "failed");
  assert.equal(cleanup.result.status, 1);
  assert.equal(cleanup.payload.cleanup_successful, false);
  assert.equal(capability.result.status, 2);
  assert.equal(capability.payload.capability_available, false);
});
