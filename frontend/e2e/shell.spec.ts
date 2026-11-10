import { expect, test } from '@playwright/test';
import axe from 'axe-core';

declare global {
  interface Window {
    axe: typeof axe;
  }
}

for (const width of [1440, 1024, 700, 390, 320]) {
  test(`shell reflows at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/');
    await expect(
      page.getByRole('heading', { level: 1, name: 'Overview' }),
    ).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: testInfo.outputPath('shell.png'),
      fullPage: true,
    });
    expect(
      await page.evaluate(() =>
        document.fonts.check('500 32px "Organic Source Serif"'),
      ),
    ).toBe(true);
    if (width < 1200) {
      const menu = page.getByRole('button', { name: 'Menu', exact: true });
      await menu.click();
      const dialog = page.getByRole('dialog');
      await expect(dialog).toBeVisible();
      await page.keyboard.press('Escape');
      await expect(dialog).not.toBeVisible();
      await expect(menu).toBeFocused();
    }
  });
}

test('navigation drawer traps focus and returns focus after Close', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 850 });
  await page.goto('/');
  await page.getByRole('button', { name: 'Menu', exact: true }).click();
  await page
    .getByRole('dialog')
    .getByRole('link', { name: 'Overview' })
    .focus();
  await page.keyboard.press('Tab');
  await expect(
    page.getByRole('button', { name: 'Close', exact: true }),
  ).toBeFocused();
  await page.getByRole('button', { name: 'Close', exact: true }).click();
  await expect(
    page.getByRole('button', { name: 'Menu', exact: true }),
  ).toBeFocused();
});

test('foundation has no serious automated accessibility violations', async ({
  page,
}) => {
  await page.goto('/');
  await page.addScriptTag({ content: axe.source });
  const violations = await page.evaluate(
    async () => (await window.axe.run()).violations,
  );
  expect(
    violations.filter((violation) =>
      ['critical', 'serious'].includes(violation.impact ?? ''),
    ),
  ).toEqual([]);
});

test('reduced motion disables button transitions', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  expect(
    await page
      .locator('.service-result button')
      .evaluate((element) => getComputedStyle(element).transitionDuration),
  ).toBe('0s');
});
