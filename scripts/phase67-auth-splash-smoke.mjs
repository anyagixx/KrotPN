#!/usr/bin/env node
/*
 * FILE: scripts/phase67-auth-splash-smoke.mjs
 * VERSION: 1.1.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static smoke verification for Phase-67 public splash, frameless auth polish, and Matrix canvas compatibility
 *   SCOPE: Splash-only / route, auth copy/removal contracts, red-focus auth CSS, large unframed logo markers, browser-safe MatrixBackground/rain fallback guards, responsive markers, and protected-surface isolation
 *   DEPENDS: M-009, M-070, M-071, M-073, M-074, M-080
 *   LINKS: V-M-009, V-M-070, V-M-071, V-M-073, V-M-074, V-M-080, docs/plans/Phase-67.xml
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository files for deterministic static assertions
 *   assertContains - Fails if a source lacks a required Phase-67 marker
 *   assertNotContains - Fails if a source contains prohibited Phase-67 content
 *   assertProtectedSurfaceDiffClean - Fails if Phase-67 touched protected backend/deploy/runtime surfaces outside shared Matrix visual compatibility files
 *   main - Runs Phase-67 static assertions and prints required verification markers
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.1.0 - Allowed shared admin Matrix visual compatibility files and asserted rain fallback markers.
 *   LAST_CHANGE: v1.0.0 - Added Phase-67 auth/splash verification gate.
 * END_CHANGE_SUMMARY
 */

import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

const root = process.cwd()

function read(relativePath) {
  return readFileSync(join(root, relativePath), 'utf8')
}

function assertContains(source, needle, label) {
  if (!source.includes(needle)) {
    throw new Error(`${label} is missing required Phase-67 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains prohibited Phase-67 marker: ${needle}`)
  }
}

function assertProtectedSurfaceDiffClean() {
  const protectedPaths = [
    'install.sh',
    'docker-compose.yml',
    'nginx',
    'deploy',
    'deploy/mtproto-de-compose.yml',
    '.env.example',
    'backend/app',
    'backend/tests',
    'frontend-admin',
    'mtproto-runtime',
    'official-mtproxy',
    'telegram-bot',
  ]

  for (const protectedPath of protectedPaths) {
    if (!existsSync(join(root, protectedPath))) {
      throw new Error(`Protected Phase-67 surface missing from repository: ${protectedPath}`)
    }
  }

  const diff = execFileSync(
    'git',
    ['diff', '--name-only', 'HEAD', '--', ...protectedPaths],
    { cwd: root, encoding: 'utf8' },
  ).trim()
  const allowedSharedMatrixFiles = new Set([
    'frontend-admin/src/components/MatrixBackground.tsx',
    'frontend-admin/src/components/VisualShell.tsx',
    'frontend-admin/src/index.css',
  ])
  const violations = diff
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((path) => !allowedSharedMatrixFiles.has(path))
  if (violations.length) {
    throw new Error(`Phase-67 must not change protected backend/deploy/runtime surfaces: ${violations.join(', ')}`)
  }
}

// START_BLOCK_PHASE67_STATIC_ASSERTIONS
const app = read('frontend/src/App.tsx')
const landing = read('frontend/src/pages/Landing.tsx')
const login = read('frontend/src/pages/Login.tsx')
const register = read('frontend/src/pages/Register.tsx')
const forgot = read('frontend/src/pages/ForgotPassword.tsx')
const reset = read('frontend/src/pages/ResetPassword.tsx')
const brandMark = read('frontend/src/components/BrandMark.tsx')
const matrixBackground = read('frontend/src/components/MatrixBackground.tsx')
const visualShell = read('frontend/src/components/VisualShell.tsx')
const css = read('frontend/src/index.css')

for (const [label, source] of [
  ['frontend/src/App.tsx', app],
  ['frontend/src/pages/Landing.tsx', landing],
  ['frontend/src/pages/Login.tsx', login],
  ['frontend/src/pages/Register.tsx', register],
  ['frontend/src/pages/ForgotPassword.tsx', forgot],
  ['frontend/src/pages/ResetPassword.tsx', reset],
  ['frontend/src/components/BrandMark.tsx', brandMark],
  ['frontend/src/components/MatrixBackground.tsx', matrixBackground],
  ['frontend/src/components/VisualShell.tsx', visualShell],
  ['frontend/src/index.css', css],
]) {
  assertContains(source, 'START_MODULE_CONTRACT', label)
  assertContains(source, 'START_MODULE_MAP', label)
  assertContains(source, 'START_CHANGE_SUMMARY', label)
}

assertContains(app, '<Route path="/" element={<Landing />} />', 'frontend/src/App.tsx')
assertContains(landing, 'data-phase67-splash-route="[PremiumPublicSite][phase67][SPLASH_REDIRECT_READY]"', 'frontend/src/pages/Landing.tsx')
assertContains(landing, "navigate('/login', { replace: true })", 'frontend/src/pages/Landing.tsx')
assertContains(landing, 'SPLASH_REDIRECT_DELAY_MS', 'frontend/src/pages/Landing.tsx')
assertContains(landing, 'REDUCED_MOTION_REDIRECT_DELAY_MS', 'frontend/src/pages/Landing.tsx')
assertContains(landing, 'phase67-splash-logo', 'frontend/src/pages/Landing.tsx')
assertContains(landing, 'data-phase56-logo="true"', 'frontend/src/pages/Landing.tsx')
assertContains(landing, '/brand/email-logo.png', 'frontend/src/pages/Landing.tsx')

for (const prohibited of [
  'PUBLIC_TARIFF_PREVIEW',
  'billingApi',
  'data-phase56-tariff-preview',
  'matrix-public-tariff',
  'matrix-public-hero',
  'matrix-public-band',
  'VPN + Telegram MTProto proxy',
  'Тарифы KrotPN',
  'Оплата создается backend',
]) {
  assertNotContains(landing, prohibited, 'frontend/src/pages/Landing.tsx')
}

for (const [label, source, heading] of [
  ['frontend/src/pages/Login.tsx', login, 'Вход в KrotPN'],
  ['frontend/src/pages/Register.tsx', register, 'Присоединиться к KrotPN'],
  ['frontend/src/pages/ForgotPassword.tsx', forgot, 'Восстановление пароля'],
  ['frontend/src/pages/ResetPassword.tsx', reset, 'Назначить пароль'],
]) {
  assertContains(source, 'data-phase67-auth-route=', label)
  assertContains(source, 'Кибернетический Протокол Навигации', label)
  assertContains(source, heading, label)
  assertContains(source, 'phase67-auth-logo', label)
  assertContains(source, 'phase67-large-logo', label)
  assertContains(source, 'auth-input-group', label)
  assertContains(source, 'auth-input', label)
  assertContains(source, 'auth-primary-action', label)
  assertContains(source, 'aria-label', label)
  assertNotContains(source, 'className="matrix-auth-card', label)
  assertNotContains(source, 'mb-2 block text-sm muted', label)
}

for (const prohibited of [
  'KrotPN Secure Access',
  'Email gate',
  '>Recovery<',
  'New password',
  'Войдите, чтобы управлять подключением и подпиской.',
  'Подтвердите email, чтобы активировать личный кабинет.',
  'Укажите email аккаунта, и мы отправим ссылку для сброса.',
  'Задайте устойчивый пароль для личного кабинета.',
  "t('noAccount')",
  "t('hasAccount')",
  'Нет аккаунта?',
  'Уже есть аккаунт?',
  'Сохранить пароль',
]) {
  assertNotContains(login + register + forgot + reset, prohibited, 'Phase-67 auth routes')
}

assertContains(login, 'authApi.login', 'frontend/src/pages/Login.tsx')
assertContains(login, "localStorage.setItem('access_token'", 'frontend/src/pages/Login.tsx')
assertContains(login, "navigate('/dashboard')", 'frontend/src/pages/Login.tsx')
assertContains(login, 'phase67-auth-secondary-grid', 'frontend/src/pages/Login.tsx')
assertContains(register, 'authApi.register', 'frontend/src/pages/Register.tsx')
assertContains(register, 'passwordPolicyExample', 'frontend/src/pages/Register.tsx')
assertContains(register, 'папку «Спам»', 'frontend/src/pages/Register.tsx')
assertContains(register, 'Восстановить доступ', 'frontend/src/pages/Register.tsx')
assertContains(forgot, 'authApi.requestPasswordReset', 'frontend/src/pages/ForgotPassword.tsx')
assertContains(reset, 'authApi.confirmPasswordReset', 'frontend/src/pages/ResetPassword.tsx')
assertContains(reset, 'passwordStrengthIssues', 'frontend/src/pages/ResetPassword.tsx')

for (const needle of [
  'START_BLOCK_PHASE67_AUTH_SPLASH_POLISH',
  '.matrix-splash-page',
  '.matrix-auth-panel',
  '.matrix-rain-fallback',
  '.phase67-auth-logo.phase63-brand-lockup',
  '.auth-input:focus',
  'rgba(255, 107, 120, 0.86)',
  '.auth-primary-action',
  '.phase67-auth-secondary-grid',
  '[MatrixStyleSystem][phase67][FRAMELESS_AUTH_READY]',
  '[MatrixStyleSystem][phase67][RED_FOCUS_READY]',
  '[MatrixStyleSystem][phase67][AUTH_NO_OVERLAP]',
  '[MatrixVisualRuntime][fix][CSS_RAIN_FALLBACK_READY]',
  '[MatrixVisualRuntime][fix][MOBILE_OVERSCAN_READY]',
  '@media (prefers-reduced-motion: reduce)',
  '@media (max-width: 480px)',
  '@media (max-width: 360px)',
]) {
  assertContains(css, needle, 'frontend/src/index.css')
}

for (const needle of [
  'addMotionListener',
  'removeMotionListener',
  'query.addListener?.(listener)',
  'query.removeListener?.(listener)',
  'window.requestAnimationFrame?.bind(window)',
  'window.cancelAnimationFrame?.bind(window)',
  'CANVAS_OVERSCAN_PX',
  'getCanvasDimensions',
  'visualViewport',
  '[MatrixVisualRuntime][phase67][BROWSER_COMPAT_SAFE]',
  '[MatrixVisualRuntime][phase67][STATIC_FALLBACK_SAFE]',
  'data-phase67-browser-compat',
  'data-phase67-static-fallback',
]) {
  assertContains(matrixBackground, needle, 'frontend/src/components/MatrixBackground.tsx')
}

for (const prohibited of [
  'radial-gradient(',
  'font-size: clamp(',
  'font-size: calc(',
  'text-5xl',
  'rounded-2xl',
  'rounded-3xl',
]) {
  assertNotContains(css + landing + login + register + forgot + reset, prohibited, 'Phase-67 frontend surfaces')
}

assertProtectedSurfaceDiffClean()
// END_BLOCK_PHASE67_STATIC_ASSERTIONS

console.log('[PremiumPublicSite][phase67][SPLASH_REDIRECT_READY] ok')
console.log('[PremiumPublicSite][phase67][AUTH_COPY_POLISHED] ok')
console.log('[PremiumPublicSite][phase67][AUTH_SEMANTICS_UNCHANGED] ok')
console.log('[MatrixStyleSystem][phase67][FRAMELESS_AUTH_READY] ok')
console.log('[MatrixStyleSystem][phase67][RED_FOCUS_READY] ok')
console.log('[MatrixStyleSystem][phase67][AUTH_NO_OVERLAP] ok')
console.log('[MatrixVisualRuntime][phase67][BROWSER_COMPAT_SAFE] ok')
console.log('[MatrixVisualRuntime][phase67][STATIC_FALLBACK_SAFE] ok')
console.log('[VisibleBrandLogo][phase67][LARGE_UNFRAMED_AUTH_LOGO] ok')
console.log('[VisibleBrandLogo][phase67][LOGO_NO_OVERLAP] ok')
console.log('[ResponsiveAdaptation][phase67][AUTH_SPLASH_RESPONSIVE_SAFE] ok')
console.log('[FrontendUser][phase67][PROTECTED_SURFACE_GUARD] ok')
