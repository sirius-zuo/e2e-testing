import { test, expect } from "@playwright/test";

test("journey-checkout confirms a valid order", async ({ page }) => {
  await page.getByRole("button", { name: "Place order" }).click();
  await expect(page.getByText("Order confirmed")).toBeVisible();
});
