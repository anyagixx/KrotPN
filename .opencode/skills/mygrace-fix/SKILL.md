---
name: mygrace-fix
description: Debug and fix issues using MYGRACE methodology — knowledge graph navigation, contract analysis, and verified repairs.
---

# MYGRACE Fix

Debug and fix issues using MYGRACE semantic navigation through the knowledge graph.

## When to Activate

- User reports a bug: "не работает", "баг", "ошибка", "fix this"
- Tests fail
- Loop protection triggered (3 failed attempts)
- User says "исправь" or "почини"

## Process

### Step 1: Locate via Knowledge Graph

1. Read `docs/knowledge-graph.xml`
2. Identify which module(s) are affected
3. Read the module contract(s) from `docs/development-plan.xml`

### Step 2: Navigate to Block

1. Find the relevant `START_BLOCK`/`END_BLOCK` markers in source code
2. Read the specific code section
3. Read the function contract if present

### Step 3: Analyze

1. Compare actual behavior with contract intent
2. Identify the root cause
3. Classify the issue:
   - `CODE_DEFECT` — code doesn't match contract
   - `TEST_DEFECT` — test is wrong or missing
   - `CONTRACT_DRIFT` — contract is outdated
   - `PLAN_DRIFT` — implementation diverged from plan

### Step 4: Fix

1. **If CODE_DEFECT**: Update the code to match the contract
2. **If TEST_DEFECT**: Fix or add the test
3. **If CONTRACT_DRIFT**: Propose contract update first, ask user
4. **If PLAN_DRIFT**: Stop and ask user — this is an architectural issue

### Step 5: Verify

1. Run relevant tests
2. If fix fails, retry (max 3 attempts total)
3. On 3rd failure: **STOP and ask user** — explain what you tried and why it failed

### Step 6: Report (in Russian)

Tell the user:
- Что было не так
- Что исправлено
- Как проверить что работает
- Нужно ли обновить файлы знаний

## Rules

- **Never fix code without first reading its CONTRACT**
- If the fix requires architectural changes, stop and ask user
- Maximum 3 fix attempts per issue — then STOP
- After fixing, suggest running `mygrace-sync` if knowledge artifacts need updating
- All communication with user in Russian

## Semantic Markup Navigation

Use block markers to navigate precisely:
```
# START_BLOCK_<NAME>
... problematic code ...
# END_BLOCK_<NAME>
```

Block names describe WHAT, not HOW. Target ~500 tokens per block.
