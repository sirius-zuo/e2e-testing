import { test as base } from "@playwright/test";

export const test = base.extend<{ appPage: string }>({ appPage: async ({}, use) => use("fixture-page") });
