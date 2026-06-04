#!/usr/bin/env node
/*
 * FILE: scripts/phase64-premium-email-template-smoke.mjs
 * VERSION: 1.1.0
 * ROLE: TEST
 * MAP_MODE: LOCALS
 * START_MODULE_CONTRACT
 *   PURPOSE: Static and render smoke verification for Phase-64 premium Resend email templates
 *   SCOPE: Premium verification/reset shell, email-client-safe HTML, text fallback cleanliness, token redaction, public logo URL boundary, and protected deploy/runtime surfaces
 *   DEPENDS: M-079, M-040, M-062, M-069, M-072, M-080
 *   LINKS: V-M-079, docs/plans/Phase-64.xml
 * END_MODULE_CONTRACT
 *
 * START_MODULE_MAP
 *   read - Loads repository files for static assertions
 *   assertContains - Fails if a source lacks required content
 *   assertNotContains - Fails if a source contains prohibited content
 *   renderTemplates - Renders verification/reset templates through Python without printing tokens
 *   assertRenderedEmail - Verifies rendered HTML/text safety for one template
 *   assertProtectedDiffClean - Fails if Phase-64 touched protected deploy/provider/runtime surfaces
 *   main - Runs Phase-64 assertions and prints required markers
 * END_MODULE_MAP
 *
 * START_CHANGE_SUMMARY
 *   LAST_CHANGE: v1.1.0 - Aligned regression smoke with Phase-66 minimal email shell and larger logo
 *   LAST_CHANGE: v1.0.1 - Added safe test Settings environment for Python render smoke
 *   LAST_CHANGE: v1.0.0 - Added Phase-64 premium email template smoke gate
 * END_CHANGE_SUMMARY
 */

import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

const root = process.cwd()
const python = existsSync(join(root, '.venv/bin/python')) ? join(root, '.venv/bin/python') : 'python3'

function read(relativePath) {
  return readFileSync(join(root, relativePath), 'utf8')
}

function assertContains(source, needle, label) {
  if (!source.includes(needle)) {
    throw new Error(`${label} is missing required Phase-64 marker: ${needle}`)
  }
}

function assertNotContains(source, needle, label) {
  if (source.includes(needle)) {
    throw new Error(`${label} contains prohibited Phase-64 marker: ${needle}`)
  }
}

function assertContainsOne(source, needles, label) {
  if (!needles.some((needle) => source.includes(needle))) {
    throw new Error(`${label} is missing one of required Phase-64 markers: ${needles.join(' | ')}`)
  }
}

function renderTemplates() {
  const code = `
import json
from app.email.templates import build_password_reset_template, build_verification_template

verification = build_verification_template(
    "https://krotpn.xyz/verify-email?token=phase64-secret-token",
    language="ru",
    app_name="KrotPN",
    brand_base_url="https://krotpn.xyz",
)
reset = build_password_reset_template(
    "https://krotpn.xyz/reset-password?token=phase64-reset-token",
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

function assertRenderedEmail(template, label, tokenNeedle) {
  assertContains(template.subject, 'KrotPN', `${label} subject`)
  assertContains(template.html, 'data-phase64-template="premium-action"', `${label} html`)
  assertContains(template.html, 'data-phase66-template="minimal-action"', `${label} html`)
  assertContains(template.html, 'https://krotpn.xyz/brand/email-logo.png', `${label} html`)
  assertContains(template.html, 'width="128" height="128"', `${label} html`)
  assertContains(template.html, 'role="presentation"', `${label} html`)
  assertContains(template.html, 'background:#07141b', `${label} html`)
  assertContains(template.html, 'background:#5cf2c8;color:#041014', `${label} html`)
  assertContains(template.html, tokenNeedle, `${label} html action URL`)
  assertContains(template.text, tokenNeedle, `${label} text action URL`)
  assertContains(template.text, 'KrotPN', `${label} text`)
  assertNotContains(template.html, 'KrotPN Matrix Access', `${label} html`)
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
    'backend/app/core/config.py',
    'backend/app/email/provider.py',
    'backend/app/users',
    'backend/app/billing',
    'frontend',
    'frontend-admin',
  ]
  const diff = execFileSync(
    'git',
    ['diff', '--name-only', 'HEAD', '--', ...protectedPaths],
    { cwd: root, encoding: 'utf8' },
  ).trim()
  if (diff) {
    throw new Error(`Phase-64 must not change protected deploy/provider/runtime/frontend surfaces: ${diff}`)
  }
}

// START_BLOCK_PHASE64_STATIC_ASSERTIONS
const templates = read('backend/app/email/templates.py')
const service = read('backend/app/email/service.py')
const tests = read('backend/tests/test_email_delivery.py')
const moduleDoc = read('docs/modules/M-079.xml')
const verificationDoc = read('docs/verification/V-M-079.xml')
const phaseDoc = read('docs/plans/Phase-64.xml')

for (const marker of [
  '[PremiumEmailTemplates][phase64][TEMPLATE_SHELL_READY]',
  '[PremiumEmailTemplates][phase64][VERIFICATION_EMAIL_SAFE]',
  '[PremiumEmailTemplates][phase64][RESET_EMAIL_SAFE]',
  '[PremiumEmailTemplates][phase64][TEXT_FALLBACK_SAFE]',
  '[PremiumEmailTemplates][phase64][TOKEN_REDACTION_SAFE]',
  '[PremiumEmailTemplates][phase64][BRAND_ASSET_BOUNDARY_SAFE]',
]) {
  assertContains(templates, marker, 'backend/app/email/templates.py')
  assertContains(verificationDoc, marker, 'docs/verification/V-M-079.xml')
}

for (const marker of [
  'data-phase64-template="premium-action"',
  'data-phase66-template="minimal-action"',
  'role="presentation"',
  'width="128" height="128"',
  '/brand/email-logo.png',
  '_render_text_fallback',
]) {
  assertContains(templates, marker, 'backend/app/email/templates.py')
}

for (const prohibited of [
  'KrotPN Matrix Access',
  'height:4px;background:#5cf2c8',
  '#04090d',
  'account security message',
]) {
  assertNotContains(templates, prohibited, 'backend/app/email/templates.py')
}

for (const prohibited of ['<script', '<style', 'canvas', '@font-face', 'fonts.googleapis', 'sender avatar', 'gmail avatar', 'apple avatar']) {
  assertNotContains(templates.toLowerCase(), prohibited, 'backend/app/email/templates.py')
}

assertContains(service, 'brand_base_url=app_settings.frontend_url', 'backend/app/email/service.py')
assertContains(tests, 'data-phase64-template="premium-action"', 'backend/tests/test_email_delivery.py')
assertContains(tests, 'data-phase66-template="minimal-action"', 'backend/tests/test_email_delivery.py')
assertContains(tests, 'TOKEN_REDACTION_SAFE', 'backend/tests/test_email_delivery.py')
assertContains(tests, 'PHASE66_VERIFICATION_FORBIDDEN_COPY', 'backend/tests/test_email_delivery.py')
assertContains(tests, '"brand/email-logo.png" not in text', 'backend/tests/test_email_delivery.py')
assertContainsOne(moduleDoc, ['STATUS="done-local-phase64"', 'STATUS="done-local-phase66"'], 'docs/modules/M-079.xml')
assertContains(phaseDoc, 'STATUS="done-local"', 'docs/plans/Phase-64.xml')

const rendered = renderTemplates()
assertRenderedEmail(rendered.verification, 'verification', 'phase64-secret-token')
assertRenderedEmail(rendered.reset, 'password reset', 'phase64-reset-token')

assertProtectedDiffClean()
// END_BLOCK_PHASE64_STATIC_ASSERTIONS

console.log('[PremiumEmailTemplates][phase64][TEMPLATE_SHELL_READY] ok')
console.log('[PremiumEmailTemplates][phase64][VERIFICATION_EMAIL_SAFE] ok')
console.log('[PremiumEmailTemplates][phase64][RESET_EMAIL_SAFE] ok')
console.log('[PremiumEmailTemplates][phase64][TEXT_FALLBACK_SAFE] ok')
console.log('[PremiumEmailTemplates][phase64][TOKEN_REDACTION_SAFE] ok')
console.log('[PremiumEmailTemplates][phase64][BRAND_ASSET_BOUNDARY_SAFE] ok')
console.log('[PremiumEmailTemplates][phase64][PROTECTED_SURFACE_GUARD] ok')
