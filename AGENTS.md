# KrotVPN — GRACE Engineering Protocol

## ⚠️ MANDATORY: ALL DEVELOPMENT STRICTLY VIA GRACE

**Это правило имеет абсолютный приоритет над всем остальным.**

### 🧭 Workflow Protocol
**Каждый шаг разработки должен начинаться с объявления используемого GRACE Skill.**
> Пример: *"Для решения этой задачи я буду использовать `$grace-plan` для проектирования контрактов..."*

1. **Всегда объявляй Skill перед действием.** Назови конкретный скилл: `$grace-plan`, `$grace-fix`, `$grace-refresh`, `$grace-exec` и т.д.
2. **Никогда не пиши код без MODULE_CONTRACT.** Контракт — источник истины. Код реализует контракт, а не наоборот.
3. **Никогда не меняй код без чтения GRACE-документов.** Порядок: `current-status.xml` → `knowledge-graph.xml` → `development-plan.xml` → `verification-plan.xml` → код.
4. **Никогда не коммить без passing verification.** Тесты должны пройти до коммита.
5. **Никогда не менять shared XML-артефакты без чтения их полностью.** `docs/*.xml` — load-bearing структура, не документация.
6. **После любого изменения кода — обновить MODULE_MAP, knowledge-graph, verification-plan (если тесты изменились).**
7. **Запрещено писать код напрямую.** Всегда следуй workflow выбранного скилла.
8. **Если верификацию невозможно запустить — скажи точно почему.** Не пропускай, не имплицируй покрытие.

**Это не рекомендация. Это engineering protocol violation, если нарушено.**

---

## Keywords
VPN, WireGuard, split-tunneling, routing, billing, subscriptions, Telegram bot, admin panel, FastAPI, Vue.js, YooKassa, Docker, AWG

## Annotation
KrotVPN is a production MVP in hardening/stabilization phase. A practical GRACE-governed project for a VPN service with split-tunneling, subscription billing, referral bonuses, and an admin dashboard.

## Read Order

Every new agent should read files in this exact order before changing code:

1. `docs/current-status.xml`
2. `docs/graph-index.xml`
3. `docs/modules/M-XXX.xml` (only the module you're changing)
4. `docs/plan-index.xml`
5. `docs/plans/Phase-N.xml` (only the relevant phase)
6. `docs/verification-index.xml`
7. `docs/verification/V-M-XXX.xml` (only the relevant verification)
8. `README.md`

For deep reference (rarely needed):
- `docs/archive/classic-grace/knowledge-graph.xml` — full detail if per-module file is insufficient
- `docs/archive/classic-grace/development-plan.xml` — complete contracts and architecture notes
- `docs/archive/classic-grace/verification-plan.xml` — global policy, philosophy, critical flows

## Project Reality

- `KrotVPN` is not a greenfield project. It is an implemented MVP in hardening/stabilization.
- The main risks are currently in security, deployment, VPN topology migration, and verification discipline.
- Code is the source of truth when docs lag, but docs must be updated after meaningful changes.
- **All development follows GRACE**: Contract-First → Semantic Markup → Knowledge Graph → Verification → Execute → Review

## Main Subsystems

- `backend/app/core`: config, DB, security, bootstrap
- `backend/app/users`: auth, profile, Telegram auth
- `backend/app/vpn`: VPN clients, configs, AWG integration, nodes/routes
- `backend/app/billing`: plans, subscriptions, payments, YooKassa
- `backend/app/referrals`: referral codes and bonuses
- `backend/app/admin`: admin analytics/system endpoints
- `backend/app/routing`: split-tunneling and host routing logic
- `frontend`: user dashboard
- `frontend-admin`: admin panel
- `telegram-bot`: bot client over backend API
- `deploy`, `install.sh`, `nginx`, `docker-compose.yml`: operational surface

## Core Principles

### 1. Never Write Code Without a Contract
Before generating or editing any module, create or update its MODULE_CONTRACT with PURPOSE, SCOPE, INPUTS, and OUTPUTS. The contract is the source of truth. Code implements the contract, not the other way around.

### 2. Semantic Markup Is Load-Bearing Structure
Markers like `# START_BLOCK_<NAME>` and `# END_BLOCK_<NAME>` are navigation anchors, not documentation. They must be:
- uniquely named
- paired
- proportionally sized so one block fits inside an LLM working window

### 3. Knowledge Graph Is Always Current
`docs/graph-index.xml` + `docs/modules/M-XXX.xml` is the project map. When you add a module, move a module, rename exports, or add dependencies, update both the index and the per-module file so future agents can navigate deterministically.

### 4. Verification Is a First-Class Artifact
Testing, traces, and log anchors are designed before large execution waves. `docs/verification-plan.xml` is part of the architecture, not an afterthought. Logs are evidence. Tests are executable contracts.

### 5. Top-Down Synthesis
Code generation follows:
`RequirementsAnalysis -> TechnologyStack -> DevelopmentPlan -> VerificationPlan -> Code + Tests`

Never jump straight to code when requirements, architecture, or verification intent are still unclear.

### 6. Governed Autonomy
Agents have freedom in HOW to implement, but not in WHAT to build. Contracts, plans, graph references, and verification requirements define the allowed space.

### 7. Lazy-Loading Navigation
MyGRACE uses indexes for navigation — never read all per-entity files.
1. Read `docs/graph-index.xml` → find module ID
2. Read `docs/modules/M-XXX.xml` → only that module
3. Done. ~145 lines vs ~6500.

## Semantic Markup Reference

### Module Level
```python
# FILE: path/to/file.ext
# VERSION: 1.0.0
# START_MODULE_CONTRACT
#   PURPOSE: [What this module does - one sentence]
#   SCOPE: [What operations are included]
#   DEPENDS: [List of module dependencies]
#   LINKS: [Knowledge graph references]
#   ROLE: [Optional: RUNTIME | TEST | BARREL | CONFIG | TYPES | SCRIPT]
#   MAP_MODE: [Optional: EXPORTS | LOCALS | SUMMARY | NONE]
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   exportedSymbol - one-line description
# END_MODULE_MAP
```

### Function or Component Level
```python
# START_CONTRACT: function_name
#   PURPOSE: [What it does]
#   INPUTS: { paramName: Type - description }
#   OUTPUTS: { ReturnType - description }
#   SIDE_EFFECTS: [External state changes or "none"]
#   LINKS: [Related modules/functions]
# END_CONTRACT: function_name
```

### Code Block Level
```python
# START_BLOCK_VALIDATE_INPUT
# ... code ...
# END_BLOCK_VALIDATE_INPUT
```

### Change Tracking
```python
# START_CHANGE_SUMMARY
#   LAST_CHANGE: [v1.2.0 - What changed and why]
# END_CHANGE_SUMMARY
```

### Optional Lint Semantics

Use `ROLE` and `MAP_MODE` only when the file should be linted differently from a normal runtime module.

- `RUNTIME` + `EXPORTS`: normal source files with public APIs
- `TEST` + `LOCALS`: tests where the map should describe helpers, fixtures, and assertion surfaces
- `BARREL` + `SUMMARY`: re-export aggregators and grouped entry points
- `CONFIG` + `NONE`: build or tool configuration files
- `TYPES` + `EXPORTS`: pure type/interface modules
- `SCRIPT` + `LOCALS`: CLI/bootstrap/smoke scripts

## Logging and Trace Convention

All important logs must point back to semantic blocks:
```python
logger.info(f"[ModuleName][function_name][BLOCK_NAME] message", extra={
    "correlation_id": correlation_id,
    "stable_field": value,
})
```

Rules:
- prefer structured fields over prose-heavy log lines
- redact secrets and high-risk payloads
- treat missing log anchors on critical branches as a verification defect
- update tests when log markers change intentionally

## Verification Conventions

`docs/verification-plan.xml` is the project-wide verification contract. Keep it current when module scope, test files, commands, critical log markers, or gate expectations change. Use `docs/operational-packets.xml` as the canonical schema for execution packets, graph deltas, verification deltas, and failure handoff packets.

Testing rules:
- deterministic assertions first
- trace or log assertions when trajectory matters
- test files may also carry MODULE_CONTRACT, MODULE_MAP, semantic blocks, and CHANGE_SUMMARY when they are substantial
- module-local tests should stay close to the module they verify
- wave-level and phase-level checks should be explicit in the verification plan

## Working Rules

- **Do not assume deployment is safe by default.**
- **Treat VPN and routing code as host-coupled**, not purely containerized.
- **If you change API shape, module ownership, or system behavior, update the GRACE docs.**
- **If verification cannot be run, say exactly why.**
- **Prefer targeted, truthful updates over broad aspirational docs.**
- **Never skip MODULE_CONTRACT review before editing governed files.**
- **After any meaningful change, update: MODULE_MAP → knowledge-graph → verification-plan (if tests/scenarios changed).**

## Development Workflow

For any new feature or change:

1. `$grace-plan` — design modules, contracts, dependencies (updates `docs/plan-index.xml` + `docs/plans/`)
2. `$grace-verification` — design tests, scenarios, log markers (updates `docs/verification-index.xml` + `docs/verification/`)
3. `$grace-execute` or `$grace-multiagent-execute` — implement with scoped reviews
4. `$grace-reviewer` — verify semantic integrity
5. `$grace-refresh` — sync indexes with per-entity files and codebase

For debugging:
1. `$grace-fix` — navigate via graph-index to the failing module
2. Analyze CONTRACT vs actual code
3. Fix within semantic block boundaries
4. Update graph-index and rerun verification

For refactoring:
1. `$grace-refactor` — classify the refactor type, build a RefactorPacket
2. Apply smallest safe change across all 6 artifacts
3. Verify by blast radius
4. `$grace-reviewer` + `$grace-refresh`

## File Structure
```
docs/
  graph-index.xml          - MyGRACE module index (≤120 lines, lazy-loading entry)
  plan-index.xml           - MyGRACE phase index (≤20 lines)
  verification-index.xml   - MyGRACE verification index (≤35 lines)
  modules/                 - Per-module files (M-001.xml … M-028.xml, 20-40 lines each)
  plans/                   - Per-phase files (Phase-1.xml … Phase-14.xml)
  verification/            - Per-verification files (V-M-001.xml … V-M-028.xml)
  current-status.xml       - Current project state and known risks
  decisions.xml            - Architectural decisions log
  requirements.xml         - Product requirements and use cases
  technology.xml           - Stack decisions, tooling, observability, testing
  operational-packets.xml  - Execution/delta/failure handoff packet templates
  archive/classic-grace/   - Archived monolithic GRACE files (reference only)
backend/app/               - FastAPI backend with GRACE markup
frontend/                  - User dashboard (Vue.js)
frontend-admin/            - Admin panel (Vue.js)
telegram-bot/              - Telegram bot client
deploy/                    - Deployment scripts and nginx config
```

## Documentation Artifacts - Unique Tag Convention

In `docs/*.xml`, repeated entities must use their unique ID as the XML tag name instead of a generic tag with an `ID` attribute.

### Tag naming conventions

| Entity type | Anti-pattern | Correct (unique tags) |
|---|---|---|
| Module | `<Module ID="M-CONFIG">...</Module>` | `<M-CONFIG NAME="Config" TYPE="UTILITY">...</M-CONFIG>` |
| Verification module | `<Verification ID="V-M-AUTH">...</Verification>` | `<V-M-AUTH MODULE="M-AUTH">...</V-M-AUTH>` |
| Phase | `<Phase number="1">...</Phase>` | `<Phase-1 name="Foundation">...</Phase-1>` |
| Flow | `<Flow ID="DF-SEARCH">...</Flow>` | `<DF-SEARCH NAME="...">...</DF-SEARCH>` |
| Use case | `<UseCase ID="UC-001">...</UseCase>` | `<UC-001>...</UC-001>` |
| Step | `<step order="1">...</step>` | `<step-1>...</step-1>` |
| Export | `<export name="config" .../>` | `<export-config .../>` |
| Function | `<function name="search" .../>` | `<fn-search .../>` |
| Type | `<type name="SearchResult" .../>` | `<type-SearchResult .../>` |
| Class | `<class name="Error" .../>` | `<class-Error .../>` |

### What NOT to change
- `CrossLink` tags stay self-closing
- single-use structural wrappers like `<contract>`, `<inputs>`, `<outputs>`, `<annotations>`, `<test-files>`, `<module-checks>`, and `<phase-gates>` stay generic
- code-level markup already uses unique names and stays as-is

## Rules for Modifications

1. **Read the MODULE_CONTRACT before editing any file.**
2. After editing source or test files, update MODULE_MAP in a way that matches the file's role and map mode.
3. After adding or removing modules, update `docs/graph-index.xml` and add/remove `docs/modules/M-XXX.xml`.
4. After changing test files, commands, critical scenarios, or log markers, update `docs/verification-index.xml` and `docs/verification/V-M-XXX.xml`.
5. After fixing bugs, add a CHANGE_SUMMARY entry and strengthen nearby verification if the old evidence was weak.
6. Never remove semantic markup anchors unless the structure is intentionally replaced with better anchors.
7. **Never modify docs/graph-index.xml, docs/plan-index.xml, or docs/verification-index.xml without reading them first.**
