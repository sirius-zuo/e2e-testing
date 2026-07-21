const test = require("node:test");
const assert = require("node:assert/strict");
const { submitOrder } = require("../src/checkout.js");

test("a valid checkout confirms the order", () => {
  assert.deepEqual(submitOrder(), { ok: true, message: "Order confirmed" });
});
