import { test, expect } from '@playwright/test'

const ADMIN = { email: 'admin@scada.local', password: 'admin123' }

async function login(page) {
  await page.goto('/login')
  await page.getByLabel(/email/i).fill(ADMIN.email)
  await page.getByLabel(/password/i).fill(ADMIN.password)
  await page.getByRole('button', { name: /sign in/i }).click()
  await expect(page).not.toHaveURL(/\/login/)
}

test.describe('Projects', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('overview page shows KPI cards', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText(/total projects/i)).toBeVisible()
  })

  test('table view lists projects', async ({ page }) => {
    await page.goto('/table')
    await expect(page.locator('table tbody tr').first()).toBeVisible()
  })

  test('kanban view loads columns', async ({ page }) => {
    await page.goto('/kanban')
    await expect(page.locator('[data-col]').first()).toBeVisible()
  })

  test('can create and delete a project', async ({ page }) => {
    await page.goto('/table')

    // Open create form
    await page.getByRole('button', { name: /new project|add project/i }).click()
    await expect(page.getByRole('dialog')).toBeVisible()

    // Fill form
    await page.getByLabel(/title|name/i).fill('E2E Test Project')
    await page.getByRole('button', { name: /save|create|submit/i }).click()

    // Project appears in table
    await expect(page.getByText('E2E Test Project')).toBeVisible()

    // Delete it
    const row = page.getByRole('row', { name: /E2E Test Project/i })
    await row.getByRole('button', { name: /delete|remove/i }).click()

    const confirmBtn = page.getByRole('button', { name: /confirm|yes|delete/i })
    if (await confirmBtn.isVisible()) await confirmBtn.click()

    await expect(page.getByText('E2E Test Project')).not.toBeVisible()
  })

  test('can toggle a task checkbox in project detail', async ({ page }) => {
    await page.goto('/table')

    // Open first project detail
    await page.locator('table tbody tr').first().click()
    await expect(page.getByRole('dialog')).toBeVisible()

    // Toggle first task checkbox
    const checkbox = page.locator('input[type="checkbox"]').first()
    const wasChecked = await checkbox.isChecked()
    await checkbox.click()
    await expect(checkbox).toBeChecked({ checked: !wasChecked })
  })
})
