const test = require("node:test");
const assert = require("node:assert/strict");
const { checkoutButtonLabel } = require("../src/checkout.js");

test("journey-checkout uses the current submit control", () => {
  assert.equal(checkoutButtonLabel(), "Submit now");
});
