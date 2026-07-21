const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");

test("existing login coverage keeps the custom appPage fixture", () => {
  assert.match(fs.readFileSync(__dirname + "/fixtures.ts", "utf8"), /appPage/);
});
