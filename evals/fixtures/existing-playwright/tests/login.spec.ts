import { test } from "./fixtures";

test("existing custom appPage fixture stays available", async ({ appPage }) => {
  if (appPage !== "fixture-page") throw new Error("fixture unavailable");
});
