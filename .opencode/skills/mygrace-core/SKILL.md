---
name: mygrace-core
description: Complete MYGRACE methodology — init, plan, execute, review, sync, and ask. The single skill for managing your entire AI-driven development workflow.
---

# MYGRACE Core

Complete MYGRACE methodology in one skill. Handles the full development lifecycle from idea to release.

## When to Activate

- User says "MYGRACE", "mygrace", "инициализируй проект", "спланируй", "начни разработку"
- Starting a new project or working on an existing MYGRACE project
- User wants to follow structured AI-driven development

## Operating Principles

### Communication
- **ALL communication with the user must be in Russian**
- All artifacts (XML, code, contracts) must be in English
- Always explain WHAT you are doing and WHY before doing it
- Always ask for approval before: creating modules, changing architecture, deploying

### Core Rules
1. **Never write code without a contract** — Every module needs `MODULE_CONTRACT` first
2. **Knowledge graph is primary** — `docs/knowledge-graph.xml` is the source of truth
3. **Verification before code** — Design tests before implementation
4. **≤500 lines per file** — All files in `docs/` must not exceed 500 lines
5. **Loop protection** — Maximum 3 attempts to fix the same issue, then STOP and ask user
6. **Top-down synthesis** — Requirements → Technology → Plan → Verification → Code

---

## Phase 1: INIT — Initialize Project

**Trigger:** User wants to start a new MYGRACE project

### Steps

1. **Gather project information** (ask in Russian):
   - Название проекта
   - Описание (1-2 предложения)
   - Целевая аудитория
   - Технологический стек (предложи если нет предпочтений)
   - Главные цели для MVP

2. **Create knowledge artifacts** in `docs/`:
   - `docs/knowledge-graph.xml` — Project ontology with initial nodes
   - `docs/requirements.xml` — Requirements from user answers
   - `docs/development-plan.xml` — Initial development plan
   - `docs/verification-plan.xml` — Verification strategy
   - `docs/decisions.xml` — Empty decisions log

3. **Create project structure**:
   ```
   docs/
     knowledge-graph.xml
     requirements.xml
     development-plan.xml
     verification-plan.xml
     decisions.xml
   .mygrace/state/.gitkeep
   AGENTS.md (if not present)
   mygrace.toml (if not present)
   ```

4. **Present summary** (in Russian):
   - Что создано
   - Какие файлы знаний инициализированы
   - Следующий шаг: "Теперь скажи 'спланируй проект'"

---

## Phase 2: PLAN — Design Architecture

**Trigger:** User says "спланируй проект" or after init completes

### Steps

1. **Read** `docs/requirements.xml` and `docs/knowledge-graph.xml`

2. **Design modules** — for each module define:
   - Module ID (e.g., `M-AUTH`, `M-DATA`)
   - Type: ENTRY_POINT, CORE_LOGIC, DATA_LAYER, UI_COMPONENT, UTILITY, INTEGRATION
   - Purpose, Inputs, Outputs, Dependencies

3. **Design verification** — for each module:
   - Verification check ID (e.g., `V-M-AUTH`)
   - Test strategy and success criteria

4. **Update artifacts**:
   - `docs/development-plan.xml` — Module architecture, phases, data flows
   - `docs/knowledge-graph.xml` — Module nodes, dependency edges
   - `docs/verification-plan.xml` — Module checks, phase gates

5. **Present for approval** (in Russian):
   - Список модулей с описанием
   - Граф зависимостей
   - План фаз разработки
   - Спроси: "Одобряешь архитектуру? (да/нет)"

---

## Phase 3: EXECUTE — Implement

**Trigger:** Architecture approved, user says "начни разработку"

### Steps

For each module in the plan (in order):

1. **Read the contract** from the development plan
2. **Create the module file** with `START_MODULE_CONTRACT` header
3. **Implement the code** following the contract
4. **Add semantic markup** (`START_BLOCK`/`END_BLOCK` markers)
5. **Add logging** with block references: `logger.info('[Module][func][BLOCK] msg')`
6. **Self-review** against the contract

After each module, report progress (in Russian).
After each phase, ask: "Фаза N завершена. Продолжить? (да/нет/стоп)"

---

## Phase 4: REVIEW — Quality Check

**Trigger:** User says "проверь качество" or after a phase completes

### Checks

1. **Contract compliance** — does code match contracts?
2. **Semantic markup** — all `START_BLOCK`/`END_BLOCK` pairs balanced?
3. **Knowledge graph sync** — graph matches actual codebase?
4. **Verification coverage** — all checks have corresponding tests?
5. **File size** — all files in `docs/` ≤500 lines?

### Report (in Russian)
- Статус контрактов
- Статус разметки
- Статус графа знаний
- Статус верификации
- Итог: ПРОЙДЕН / ТРЕБУЕТ ИСПРАВЛЕНИЙ

---

## Phase 5: SYNC — Synchronize Artifacts

**Trigger:** User says "синхронизируй" or after significant code changes

### Steps

1. **Scan changes** — identify files changed since last sync
2. **Reconcile artifacts** — update knowledge-graph, development-plan, verification-plan, decisions
3. **Detect issues** — missing modules, orphaned modules, stale links, files >500 lines
4. **Propose updates** (in Russian) — show what changed, ask for approval
5. **Apply updates** — if approved, update all affected artifacts

---

## Phase 6: ASK — Answer Questions

**Trigger:** User asks any question about the project

### Steps

1. **Load context** — read all 5 XML files in `docs/`
2. **Identify relevant modules** — find in knowledge graph
3. **Read relevant source code**
4. **Answer** (in Russian) with citations to specific files and artifacts
5. **Suggest next steps** if applicable

---

## Semantic Markup Reference

### Module Level
```
# START_MODULE_CONTRACT: MODULE_ID
# PURPOSE: ...
# SCOPE: ...
# INPUTS: ...
# OUTPUTS: ...
# END_MODULE_CONTRACT: MODULE_ID
```

### Function Level
```
# START_CONTRACT: functionName
# Intent: ...
# Input: ...
# Output: ...
# END_CONTRACT: functionName
```

### Block Level
```
# START_BLOCK_<NAME>
... code (~500 tokens max) ...
# END_BLOCK_<NAME>
```

---

## XML Unique Tag Convention

Use entity ID as the XML tag name:
```xml
<M-AUTH NAME="Authentication" TYPE="CORE_LOGIC">
  <Purpose>User authentication and session management</Purpose>
</M-AUTH>
```

NOT:
```xml
<Module ID="M-AUTH">...</Module>
```

---

## Phase State Machine

```
IDEA -> REQUIREMENTS -> PLAN -> DEVELOPMENT -> TESTS -> RELEASE
  |          |             |          |             |         |
  +-- human approval at each gate --------------------------------+
```

Statuses: `PLANNED`, `IN_PROGRESS`, `TESTING`, `REVIEWING`, `DONE`, `BLOCKED`

---

## Security Gates

- Secrets: ENV variables only, no hardcoded keys
- SQL: Parameterized queries only
- Input: Explicit validation on public methods

---

## Commit Convention

```
mygrace(MODULE_ID): short description

Phase N, Step N
Module: module name (path)
Contract: one-line purpose
```
