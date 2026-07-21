import { test } from "@playwright/test";

test("journey-checkout deterministically fails", async () => { throw new Error("deterministic failure"); });
