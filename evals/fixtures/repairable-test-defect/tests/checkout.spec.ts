import { test, expect } from "@playwright/test";

test("journey-checkout submits an order", async ({ page }) => {
  await page.getByRole("button", { name: "Submit now" }).click();
  await expect(page.getByText("Order received")).toBeVisible();
});
