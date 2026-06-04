#!/usr/bin/env node
/*
 * FILE: scripts/phase66-minimal-email-template-smoke.mjs
 * VERSION: 1.0.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static and render smoke verification for Phase-66 minimal Resend email templates
 *   SCOPE: Removed copy, larger logo, transparent outer wrapper, CTA/fallback preservation, token redaction markers, and protected provider/deploy/runtime surfaces
 *   DEPENDS: M-079, M-040, M-062, M-069, M-080
 *   LINKS: V-M-079, docs/plans/Phase-66.xml
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository text files for static assertions
 *   assertContains - Fails if a source lacks required content
 *   assertNotContains - Fails if a source contains prohibited content
 *   renderTemplates - Renders verification/reset templates through Python without printing tokens
 *   assertMinimalRenderedEmail - Verifies Phase-66 rendered HTML/text behavior
 *   assertProtectedDiffClean - Fails if Phase-66 touched protected deploy/provider/runtime surfaces
 *   main - Runs Phase-66 assertions and prints required markers
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.0.0 - Added Phase-66 minimal email template smoke gate
 * END_CHANGE_SUMMARY
 */

import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

const root = process.cwd()
const python = existsSync(join(root, '.venv/bin/python')) ? join(root, '.venv/bin/python') : 'python3'

const verificationForbidden = [
  'KrotPN Matrix Access',
  'Защищенная регистрация',
  'Один шаг подтверждает, что эта почта принадлежит вам, и подготавливает аккаунт KrotPN.',
  'Удаленные изображения необязательны: ссылки ниже достаточно для подтверждения.',
  'Не пересылайте ее в чаты или сообщения поддержки.',
  'KrotPN account security message. No password or payment data is requested in this email.',
]

const resetForbidden = [
  'KrotPN Matrix Access',
  'Восстановление доступа',
  'Используйте одноразовый маршрут, чтобы задать новый пароль для аккаунта KrotPN.',
  'Ссылка восстановления работает даже если почтовый клиент блокирует изображения.',
  'Не пересылайте ее в чаты или сообщения поддержки.',
  'KrotPN account security message. No password or payment data is requested in this email.',
]

function read(relativePath) {
  return readFileSync(join(root, relativePath), 'utf8')
}

function assertContains(source, needle, label) {
  if (!source.includes(needle)) {
    throw new Error(`${label} is missing required Phase-66 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains prohibited Phase-66 marker: ${needle}`)
  }
}

function renderTemplates() {
  const code = `
import json
from app.email.templates import build_password_reset_template, build_verification_template

verification = build_verification_template(
    "https://krotpn.xyz/verify-email?token=phase66-secret-token",
    language="ru",
    app_name="KrotPN",
    brand_base_url="https://krotpn.xyz",
)
reset = build_password_reset_template(
    "https://krotpn.xyz/reset-password?token=phase66-reset-token",
    language="ru",
    app_name="KrotPN",
    brand_base_url="https://krotpn.xyz",
)
print(json.dumps({
    "verification": {
        "subject": verification.subject,
        "html": verification.html,
        "text": verification.text,
    },
    "reset": {
        "subject": reset.subject,
        "html": reset.html,
        "text": reset.text,
    },
}, ensure_ascii=False))
`
  const stdout = execFileSync(
    python,
    ['-c', code],
    {
      cwd: root,
      encoding: 'utf8',
      env: {
        ...process.env,
        SECRET_KEY: 'test-secret-key-with-enough-length',
        DATA_ENCRYPTION_KEY: 'dpFmfSVqfdAK3yx5MQV6Tcv35RZuw5MzaH0yhxJ01q0=',
        PYTHONPATH: join(root, 'backend'),
      },
    },
  )
  return JSON.parse(stdout)
}

function assertMinimalRenderedEmail(template, label, actionNeedle, forbiddenCopy) {
  assertContains(template.subject, 'KrotPN', `${label} subject`)
  assertContains(template.html, 'data-phase64-template="premium-action"', `${label} html`)
  assertContains(template.html, 'data-phase66-template="minimal-action"', `${label} html`)
  assertContains(template.html, 'https://krotpn.xyz/brand/email-logo.png', `${label} html`)
  assertContains(template.html, 'width="128" height="128"', `${label} html`)
  assertContains(template.html, 'background:#07141b', `${label} html dark card`)
  assertContains(template.html, 'background:#5cf2c8;color:#041014', `${label} html CTA`)
  assertContains(template.html, 'role="presentation"', `${label} html`)
  assertContains(template.html, actionNeedle, `${label} html action URL`)
  assertContains(template.text, actionNeedle, `${label} text action URL`)
  assertContains(template.text, 'KrotPN', `${label} text`)
  assertNotContains(template.html, 'height:4px;background:#5cf2c8', `${label} html`)
  assertNotContains(template.html, '#04090d', `${label} html`)
  assertNotContains(template.text, 'brand/email-logo.png', `${label} text`)
  assertNotContains(template.text, '<table', `${label} text`)
  assertNotContains(template.text, '<a ', `${label} text`)
  assertNotContains(template.html.toLowerCase(), '<script', `${label} html`)
  assertNotContains(template.html.toLowerCase(), '<style', `${label} html`)
  assertNotContains(template.html.toLowerCase(), 'canvas', `${label} html`)
  assertNotContains(template.html.toLowerCase(), '@font-face', `${label} html`)
  assertNotContains(template.html.toLowerCase(), 'fonts.googleapis', `${label} html`)
  for (const forbidden of forbiddenCopy) {
    assertNotContains(template.html, forbidden, `${label} html`)
    assertNotContains(template.text, forbidden, `${label} text`)
  }
}

function assertProtectedDiffClean() {
  const protectedPaths = [
    'install.sh',
    'docker-compose.yml',
    'nginx',
    'deploy',
    'deploy/mtproto-de-compose.yml',
    '.env.example',
    'mtproto-runtime',
    'official-mtproxy',
    'telegram-bot',
    'backend/app/core',
    'backend/app/email/provider.py',
    'backend/app/users',
    'backend/app/billing',
    'backend/app/vpn',
    'frontend',
    'frontend-admin',
  ]
  const diff = execFileSync(
    'git',
    ['diff', '--name-only', 'HEAD', '--', ...protectedPaths],
    { cwd: root, encoding: 'utf8' },
  ).trim()
  if (diff) {
    throw new Error(`Phase-66 must not change protected deploy/provider/runtime/frontend surfaces: ${diff}`)
  }
}

// START_BLOCK_PHASE66_STATIC_ASSERTIONS
const templates = read('backend/app/email/templates.py')
const tests = read('backend/tests/test_email_delivery.py')
const phaseDoc = read('docs/plans/Phase-66.xml')
const moduleDoc = read('docs/modules/M-079.xml')
const verificationDoc = read('docs/verification/V-M-079.xml')

for (const marker of [
  '[PremiumEmailTemplates][phase66][NEGATIVE_COPY_SAFE]',
  '[PremiumEmailTemplates][phase66][MINIMAL_STYLE_SAFE]',
  '[PremiumEmailTemplates][phase66][ACTION_FALLBACK_SAFE]',
]) {
  assertContains(templates, marker, 'backend/app/email/templates.py')
  assertContains(verificationDoc, marker, 'docs/verification/V-M-079.xml')
}

for (const marker of [
  'data-phase66-template="minimal-action"',
  'width="128" height="128"',
  'background:#07141b',
  '_render_text_fallback',
]) {
  assertContains(templates, marker, 'backend/app/email/templates.py')
}

for (const forbidden of [...verificationForbidden, ...resetForbidden, 'height:4px;background:#5cf2c8', '#04090d']) {
  assertNotContains(templates, forbidden, 'backend/app/email/templates.py')
}

for (const marker of [
  'PHASE66_VERIFICATION_FORBIDDEN_COPY',
  'PHASE66_RESET_FORBIDDEN_COPY',
  'data-phase66-template="minimal-action"',
  'width="128" height="128"',
]) {
  assertContains(tests, marker, 'backend/tests/test_email_delivery.py')
}

assertContains(phaseDoc, 'STATUS="done-local"', 'docs/plans/Phase-66.xml')
assertContains(moduleDoc, 'STATUS="done-local-phase66"', 'docs/modules/M-079.xml')
assertContains(verificationDoc, 'STATUS="pass-local-phase66"', 'docs/verification/V-M-079.xml')

const rendered = renderTemplates()
assertMinimalRenderedEmail(rendered.verification, 'verification', 'phase66-secret-token', verificationForbidden)
assertMinimalRenderedEmail(rendered.reset, 'password reset', 'phase66-reset-token', resetForbidden)

assertProtectedDiffClean()
// END_BLOCK_PHASE66_STATIC_ASSERTIONS

console.log('[PremiumEmailTemplates][phase66][NEGATIVE_COPY_SAFE] ok')
console.log('[PremiumEmailTemplates][phase66][MINIMAL_STYLE_SAFE] ok')
console.log('[PremiumEmailTemplates][phase66][ACTION_FALLBACK_SAFE] ok')
console.log('[PremiumEmailTemplates][phase66][PROTECTED_SURFACE_GUARD] ok')
