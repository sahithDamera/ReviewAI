import { expect, test } from "@playwright/test";

test("owner signs up, onboards, edits, logs out, and logs in", async ({ page }) => {
  const email = `browser-${Date.now()}-${Math.random().toString(36).slice(2)}@example.com`;
  const password = "a browser-only test passphrase";
  await page.goto("/signup");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await expect(page).toHaveURL(/\/onboarding$/, { timeout: 20000 });
  await page.getByLabel("Business name", { exact: true }).fill("Mario's Italian Kitchen");
  await page.getByLabel("Business category").selectOption({ label: "Restaurant" });
  await page.getByLabel("Google review link").fill("https://g.page/r/test-place/review");
  await page.getByLabel("I opened this link").check();
  await page.getByRole("button", { name: "Create business", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Mario's Italian Kitchen" })).toBeVisible();
  const reviewUrl = await page.getByLabel("Business review URL").inputValue();
  expect(reviewUrl).toMatch(/\/r\/[A-Za-z0-9_-]{22,}/);
  await page.addInitScript(() => {
    let copied = "";
    (window as Window & { __clipboardAt?: number }).__clipboardAt = 0;
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: async (value: string) => { (window as Window & { __clipboardAt?: number }).__clipboardAt = performance.now(); copied = value; }, readText: async () => copied },
    });
  });
  await page.route("https://g.page/**", route => route.abort());
  await page.goto(reviewUrl);
  await page.getByRole("radio", { name: "4 out of 5 stars" }).click();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByLabel("Food").check();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(page.getByText("Option 1")).toBeVisible();
  let copyEventAt = 0;
  page.on("request", request => { if (request.url().includes("/api/public/copy-event")) copyEventAt = performance.now(); });
  await page.getByRole("link", { name: "Copy & Continue to Google" }).click();
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toContain("Mario");
  await expect.poll(() => copyEventAt).toBeGreaterThan(0);
  expect(await page.evaluate(() => (window as Window & { __clipboardAt?: number }).__clipboardAt)).toBeLessThanOrEqual(copyEventAt);
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Mario's Italian Kitchen" })).toBeVisible();
  await page.getByRole("link", { name: "Edit business" }).click();
  await page.getByLabel("Business name", { exact: true }).fill("Mario's Neighborhood Kitchen");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("heading", { name: "Mario's Neighborhood Kitchen" })).toBeVisible();
  await expect(page.getByLabel("Business review URL")).toHaveValue(reviewUrl);
  await page.getByRole("button", { name: "Log out", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Mario's Neighborhood Kitchen" })).toBeVisible();
  await page.screenshot({ path: `test-results/owner-${test.info().project.name}.png`, fullPage: true });
});
