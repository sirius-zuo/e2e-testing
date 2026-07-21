const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");

test("checkout.spec.ts targets the current submit control", () => {
  const spec = fs.readFileSync(__dirname + "/checkout.spec.ts", "utf8");
  assert.match(spec, /name: "Place order"/);
  assert.match(spec, /Order received/);
});
