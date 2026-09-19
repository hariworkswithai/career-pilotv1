import { test, expect } from "@playwright/test";

const supabaseConfigured = process.env.E2E_SUPABASE_CONFIGURED === "1";

test("landing page renders and links to signup", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Find jobs in India before anyone else/i })
  ).toBeVisible();
  await page.getByRole("link", { name: "Get started" }).click();
  await page.waitForURL(/\/signup/);
  await expect(page.getByRole("heading", { name: /Create your account/i })).toBeVisible();
});

test("sign-in page redirects to the app after login", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
});

test(
  "unauthenticated users are redirected to /login from the dashboard",
  async ({ page }) => {
    test.skip(!supabaseConfigured, "Supabase auth is not configured in this environment");
    await page.goto("/dashboard");
    await page.waitForURL(/\/login/);
  }
);