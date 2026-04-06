# ⚠️ MANDATORY: STRICT GRACE GOVERNANCE FOR ALL DEVELOPMENT

**Этот файл — инженерный мандат. Он имеет абсолютный приоритет.**

## Protocol

Вся разработка в этом проекте ведётся **строго** через GRACE. Это не рекомендация — это protocol.

### Absolute Rules (NEVER violate these)

| # | Rule | Violation |
|---|------|-----------|
| 1 | **No Contract → No Code** | Читай MODULE_CONTRACT до любого изменения файла |
| 2 | **No Docs → No Changes** | Читай GRACE-документы перед кодом: `current-status.xml` → `knowledge-graph.xml` → `development-plan.xml` → `verification-plan.xml` |
| 3 | **No Verification → No Commit** | Тесты проходят → коммит. Тесты не прошли → stop, file failure packet |
| 4 | **No Blind XML Edits** | Никогда не меняй `docs/*.xml` не прочитав файл полностью |
| 5 | **Always Sync Artifacts** | Код изменился → MODULE_MAP → knowledge-graph → verification-plan |
| 6 | **Always GRACE Workflow** | `$grace-plan` → `$grace-verification` → `$grace-execute` → `$grace-reviewer` → `$grace-refresh` |
| 7 | **No Silent Skips** | Не можешь запустить верификацию → скажи **точно почему** |

### Workflow Enforcement

Для **любого** изменения в проекте:

```
1. $grace-plan         — Спроектируй модули, контракты, зависимости
2. $grace-verification — Спроектируй тесты, сценарии, log-маркеры
3. $grace-execute      — Реализуй с scoped review и commit после verification
4. $grace-reviewer     — Проверь semantic integrity
5. $grace-refresh      — Синхронизируй graph с реальным кодом
```

Для **отладки**:
```
1. $grace-fix          — Найди через knowledge graph → MODULE_CONTRACT → START_BLOCK
2. Проанализируй CONTRACT vs код
3. Исправь в границах semantic block
4. Обнови метаданные + rerun verification
```

Для **рефакторинга**:
```
1. $grace-refactor     — Классифицируй тип, построй RefactorPacket
2. Примени минимальное безопасное изменение
3. $grace-reviewer + $grace-refresh
```

### What This Means For You (AI Agent)

- Ты **не имеешь права** писать код без контракта
- Ты **не имеешь права** пропускать верификацию
- Ты **не имеешь права** менять XML не прочитав
- Ты **обязан** следовать workflow для каждого изменения
- Ты **обязан** обновлять артефакты после каждого изменения
- Ты **обязан** сообщить если верификацию нельзя запустить

**Это не гибкие правила. Это engineering protocol.**

---

*Project: KrotVPN v2.8.0*
*Methodology: GRACE 3.7.0 (Graph-RAG Anchored Code Engineering)*
*Author: Vladimir Ivanov (@turboplanner)*
*Enforced: 2026-04-06*
