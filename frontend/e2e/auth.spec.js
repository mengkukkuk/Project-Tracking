import { test, expect } from '@playwright/test'

const ADMIN = { email: 'admin@scada.local', password: 'admin123' }
const MEMBER = { email: 'a@scada.local', password: 'password' }

test.describe('Authentication', () => {
  test('login page loads', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/\/login/)
    await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible()
  })

  test('wrong password shows error', async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel(/email/i).fill(ADMIN.email)
    await page.getByLabel(/password/i).fill('wrongpassword')
    await page.getByRole('button', { name: /sign in/i }).click()
    await expect(page.getByText(/invalid email or password/i)).toBeVisible()
  })

  test('admin can log in and reach dashboard', async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel(/email/i).fill(ADMIN.email)
    await page.getByLabel(/password/i).fill(ADMIN.password)
    await page.getByRole('button', { name: /sign in/i }).click()
    await expect(page).not.toHaveURL(/\/login/)
    await expect(page.getByRole('navigation')).toBeVisible()
  })

  test('member can log in', async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel(/email/i).fill(MEMBER.email)
    await page.getByLabel(/password/i).fill(MEMBER.password)
    await page.getByRole('button', { name: /sign in/i }).click()
    await expect(page).not.toHaveURL(/\/login/)
  })

  test('logout clears session and redirects to login', async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel(/email/i).fill(ADMIN.email)
    await page.getByLabel(/password/i).fill(ADMIN.password)
    await page.getByRole('button', { name: /sign in/i }).click()
    await expect(page).not.toHaveURL(/\/login/)

    await page.getByRole('button', { name: /logout|sign out/i }).click()
    await expect(page).toHaveURL(/\/login/)

    // Navigating to protected route redirects back
    await page.goto('/')
    await expect(page).toHaveURL(/\/login/)
  })

  test('unauthenticated access to protected route redirects to login', async ({ page }) => {
    await page.goto('/kanban')
    await expect(page).toHaveURL(/\/login/)
  })
})
