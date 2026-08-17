## Обязательное состояние проекта

Перед **любой** работой в этом репозитории агент обязан полностью прочитать
`.agents/PROJECT_STATE.md`. Это единственный краткий источник актуальной
продуктовой истины; память чата, старые roadmap-ы и комментарии не заменяют его.

После каждого завершённого значимого шага агент обязан обновить этот файл до
коммита. Файл должен оставаться на русском языке, содержать не более **50 строк**
и включать: текущую цель, доказанные факты, недоказанные/неработающие вещи,
канонический production-вход, незавершённый следующий шаг и последние коммиты.
Если сведения конфликтуют, сначала исправить `PROJECT_STATE.md`, затем продолжать
работу. Нельзя завершать задачу, не сверив её с этим файлом.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
