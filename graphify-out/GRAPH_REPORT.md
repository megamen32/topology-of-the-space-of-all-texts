# Graph Report - graph-scores-gpu  (2026-11-20)

## Corpus Check
- 158 files · ~2,356,374 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1084 nodes · 1645 edges · 126 communities (96 shown, 30 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 40 edges (avg confidence: 0.6)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `78eed605`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- implementation_plan.md
- Community 33
- Community 34
- Community 35
- Community 36
- Этапы научной работы
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 50
- Community 51
- STAGE 5. Определение того, что должно находиться около нуля
- Community 53
- Community 54
- build_paragraph_student_v1.py
- build_sentence_student_v1.py
- fsm_astar_frontier.py
- run_hierarchical_students_pipeline.sh
- run_sentence_student_pipeline.sh
- run_word_student_pipeline.sh
- graphify-semantic.sh
- AGENTS.md
- Текущий план
- clone_tg_economic.sh
- Можно ли отдать начало библиотеки языковой модели?
- install_dataset_deps.sh
- dataset_policy.md
- eval_harness_v1.md
- eval_harness_v2.md
- experiment_b2_sentence_paragraph_frontier.md
- experiment_c_hierarchical.md
- markov3_vs_transformer.md
- markov_scaling.md
- 01_raw_bijection.md
- 02_fsm.md
- 03_hierarchical.md
- 04_evaluation.md
- 05_cluster.md
- 06_ranking.md
- ranking_plan.md
- worklog.md
- deploy-babel-walk.sh
- enable-babel-walk-tls.sh
- README.md
- atlas.js
- address-space.js
- Babel-1: инженерная декомпозиция после научного решения
- STAGE 7. Исследование разнообразия соседних страниц
- STAGE 10. Финальная научная валидация и заморозка `Babel-1`
- 12. Главные исследовательские вопросы
- STAGE 2. Теория латентных энергетических оболочек
- STAGE 4. Связь с точной вероятностной моделью языка
- STAGE 3. Теорема о глобальном `rank/unrank`
- STAGE 6. Проверка смыслового градиента и геометрии адресов
- STAGE 1. Теорема о контекстной перестановочной биекции
- STAGE 8. Условное расширение выразительности
- ROADMAP.md
- 2. Центральная математическая гипотеза
- STAGE 9. Масштабирование, точная арифметика и воспроизводимость
- STAGE 0. Формализация объекта библиотеки
- Задачи
- Какая маленькая модель удерживает развязку рассказа?
- student_comparison_pages.py
- Что открывается на восьми малых и восьми далёких адресах Qwen3
- evaluate_continuations.py
- Сохраняет ли Qwen смысл между половинами страницы

## God Nodes (most connected - your core abstractions)
1. `HierarchicalEnumeratorV1` - 25 edges
2. `BinaryShellRanker` - 19 edges
3. `ClusterRanker` - 18 edges
4. `RawClusterRanker` - 18 edges
5. `GenerativeAddress` - 15 edges
6. `self_test()` - 14 edges
7. `boot()` - 14 edges
8. `Markov5Rows` - 13 edges
9. `BabelRanker4096` - 12 edges
10. `main()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `ContextPermutationV1`  [INFERRED]
  experiments/evaluate_babel_1_shell.py → experiments/babel_shell_v1.py
- `main()` --calls--> `ContextPermutationMarkov5`  [INFERRED]
  experiments/evaluate_babel_1_shell.py → experiments/babel_shell_v1.py
- `babel_1_ranker()` --calls--> `BabelRanker4096`  [INFERRED]
  experiments/backend_app.py → experiments/babel_shell_v1.py
- `exact_cluster_ranker()` --calls--> `RawClusterRanker`  [INFERRED]
  experiments/backend_app.py → experiments/cluster_counting_mvp.py
- `main()` --calls--> `exact_cluster_ranker()`  [INFERRED]
  experiments/build_russian_walk.py → experiments/backend_app.py

## Import Cycles
- None detected.

## Communities (126 total, 30 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.10
Nodes (13): ClusterRanker, HierarchicalRawRanker, main(), parse_path(), Path, Exact ranker for fixed-length pages over the project's 256-symbol alphabet., Count raw-symbol suffixes, aggregating symbols by destination cluster., Exact energy-ordered enumerator for fixed-length cluster paths. (+5 more)

### Community 1 - "Community 1"
Cohesion: 0.10
Nodes (38): api_atlas_page(), api_babel_1_route(), api_counting_proof(), api_exact_neighbor(), api_generate(), api_rank(), api_russian_walk(), api_score() (+30 more)

### Community 2 - "Community 2"
Cohesion: 0.19
Nodes (21): boot(), cls(), detok(), escapeHtml(), generateFSM(), generateSentenceFromTemplate(), generateSentenceStudent(), hashSeed() (+13 more)

### Community 3 - "Community 3"
Cohesion: 0.18
Nodes (29): attachExpand(), B64MAP, babelApi(), boot(), decimalSci(), decodeAddressInput(), decodePage64(), encodeFixedPage64() (+21 more)

### Community 4 - "Community 4"
Cohesion: 0.13
Nodes (7): cls(), isCombining(), normalizeText(), normChar(), pageFromText(), rankText(), scoreText()

### Community 5 - "Community 5"
Cohesion: 0.16
Nodes (23): corpus_profile(), detok(), gen_fsm(), gen_paragraph(), gen_sentence(), gen_sentence_from_template(), gen_word(), generate() (+15 more)

### Community 6 - "Community 6"
Cohesion: 0.11
Nodes (10): demo(), HierarchicalEnumeratorV1, ParagraphShape, Normalize to the project alphabet, then right-pad to page length., Exactly count either one shape's token programs or the catalogue., Count the full space and its finite readable prefix exactly., A finite paragraph catalogue plus an exact raw-space fallback.      A structured, SentenceTemplate (+2 more)

### Community 7 - "Community 7"
Cohesion: 0.12
Nodes (16): 1. Long-page exact counting, 2. Paragraph hierarchy, 3. Energy compression, 4. Distilled transformer student, Canonical direction, Core idea, Hierarchical Student Master Note, Historical hierarchy direction (+8 more)

### Community 8 - "Community 8"
Cohesion: 0.27
Nodes (15): build_dp(), count_less_cost(), default_costs(), explain_first(), main(), rank_page(), rank_within_cost(), Return positive integer byte costs derived from -log2 probability.      smoothin (+7 more)

### Community 9 - "Community 9"
Cohesion: 0.28
Nodes (15): boot(), buildTinyRanker(), detok(), generateFSM(), generateParagraphStudent(), generateSentenceFromTemplate(), generateSentenceStudent(), isPunct() (+7 more)

### Community 10 - "Community 10"
Cohesion: 0.28
Nodes (6): ChunkedRawCounter, main(), Counter, Apply one exact raw-symbol transition to a state/energy vector., Return T[source][destination][energy] for exactly ``span`` steps., Count every raw page exactly, composing complete blocks then a tail.

### Community 11 - "Community 11"
Cohesion: 0.14
Nodes (13): Chunked page counting, Core insight, Counting strategy, Critical requirement, External-memory frontier, Hierarchical layers, Immediate implementation tasks, Main unresolved problem (+5 more)

### Community 12 - "Community 12"
Cohesion: 0.15
Nodes (12): 1. Long-page exact counting, 2. Hierarchical factorization proof, 3. Sentence/template composition, 4. Energy normalization, 5. Production-scale student_rank, Core idea, Current direction, Current unfinished areas / TODO (+4 more)

### Community 13 - "Community 13"
Cohesion: 0.41
Nodes (12): boot(), detok(), generateCluster(), generateClusterV2(), generateFSM(), generateParagraph(), generateSentence(), generateSentenceFromTemplate() (+4 more)

### Community 15 - "Community 15"
Cohesion: 0.17
Nodes (11): Current blocker, Goal, Hierarchical Student — Completion Roadmap, Introduce integer energies, Minimal grammar, Phase 1 — Freeze the hierarchy, Phase 2 — Unified energy model, Phase 3 — Exact compositional counting (+3 more)

### Community 16 - "Community 16"
Cohesion: 0.18
Nodes (10): 1. Hidden-state clustering, 2. VQ-VAE / vector quantization, 3. Finite-state abstraction, Cost model, Current ladder, MVP 3 / MVP 4: token automaton and discretized transformer, MVP 3: token automaton, MVP 4: tiny transformer teacher (+2 more)

### Community 17 - "Community 17"
Cohesion: 0.18
Nodes (10): Conclusion, Emerged automatically, Emergent Structure and Next Steps, Existing groundwork, Goal, Manually specified, Next step — Cluster Student, Phase 1 — Raw bijection (+2 more)

### Community 18 - "Community 18"
Cohesion: 0.42
Nodes (10): boot(), cfgName(), esc(), nextPair(), renderPair(), renderVotes(), rows, sampleFrom() (+2 more)

### Community 19 - "Community 19"
Cohesion: 0.42
Nodes (10): api(), boot(), compactCount(), current(), pageFromHash(), pages, setIndex(), showNeighbor() (+2 more)

### Community 20 - "Community 20"
Cohesion: 0.20
Nodes (9): Current architecture, Goal, How to connect, Product / architecture decisions, Student design, Teacher choice, Why finite student, Why this matters (+1 more)

### Community 21 - "Community 21"
Cohesion: 0.53
Nodes (8): conv(), human_int(), main(), mat_mul(), Counter, run(), trim_poly(), vec_mul()

### Community 22 - "Community 22"
Cohesion: 0.39
Nodes (6): fail(), log(), main(), need_file(), run_step(), run_pipeline.sh script

### Community 23 - "Community 23"
Cohesion: 0.06
Nodes (33): template(), tok_type(), build_clusterer(), build_model(), sentence_energy(), tokenize(), blind_plan(), distinct_ranks() (+25 more)

### Community 24 - "Community 24"
Cohesion: 0.53
Nodes (8): boot(), codeInfo(), esc(), fmt(), labelChar(), pct(), renderBars(), renderSummary()

### Community 25 - "Community 25"
Cohesion: 0.25
Nodes (3): Path, write_texts(), Redirect

### Community 26 - "Community 26"
Cohesion: 0.33
Nodes (6): Генерация по seed, Каталог и оболочки Babel-1, Кластерные блоки, Обычный адрес, Текущая архитектура, Эксперимент с языковой моделью

### Community 27 - "Community 27"
Cohesion: 0.25
Nodes (7): Advantages, Algorithm, B1 result: class-FSM collapse, Disadvantages, Experiment B — A* Low-Energy Frontier, Next: B2 sentence/word frontier, Status

### Community 28 - "Community 28"
Cohesion: 0.25
Nodes (7): Phase 1, Phase 2, Phase 3, Phase 4, Phase 5, Phase 6 (current), Project Phase Summary

### Community 29 - "Community 29"
Cohesion: 0.06
Nodes (28): BabelRanker4096, BinaryShellRanker, ContextPermutationMarkov5, ContextPermutationV1, ContextPermutationWordV1, _exhaustive_reduced_space_test(), Permutation, Path (+20 more)

### Community 30 - "Community 30"
Cohesion: 0.53
Nodes (8): api(), baseRank(), boot(), exactRank(), rankAddress(), selectedLength(), selectedMode(), usesServerExact()

### Community 32 - "implementation_plan.md"
Cohesion: 0.10
Nodes (35): GenerativeAddress, Exact experimental addresses for two generated half-pages of alphabet indices., _self_test(), canonical_json(), cold_generate(), decode(), digest(), generated_text() (+27 more)

### Community 33 - "Community 33"
Cohesion: 0.29
Nodes (6): Current status, Legacy: class-FSM student, Replacement direction, What it is, What it proved, Why it is legacy

### Community 34 - "Community 34"
Cohesion: 0.62
Nodes (6): esc(), load(), render(), showCluster(), summarizeFromMapping(), topTransitions()

### Community 35 - "Community 35"
Cohesion: 0.50
Nodes (4): Исследование полного порядка по стоимости, Как повторить проверку сайта, План реализации и проверок библиотеки, Сравнение генераторов

### Community 36 - "Community 36"
Cohesion: 0.53
Nodes (4): is_running(), taskctl.sh script, usage(), write_status()

### Community 37 - "Этапы научной работы"
Cohesion: 0.12
Nodes (15): S0. Зафиксировать объект и версию, S1. Доказать латентно-перестановочную биекцию, S2. Точное перечисление латентных оболочек, S3. Связать слоты с языком, S4. Проверить гипотезу «раннее похоже на человеческое», S5. Разнообразие и порядок внутри оболочки, S6. Решение о выпуске, Зависимости и параллельность (+7 more)

### Community 38 - "Community 38"
Cohesion: 0.33
Nodes (5): Counting Infinity — Experiments, Experiment A, Experiment B, Experiment C, Experiment D

### Community 39 - "Community 39"
Cohesion: 0.33
Nodes (5): Alphabet and corpus, Counting Infinity — Results, Exact rank MVP, Markov ladder, Student models

### Community 40 - "Community 40"
Cohesion: 0.33
Nodes (6): 1. Порядок всех страниц по стоимости исходной модели, 2. Масштабирование точного подсчёта, 3. Читаемость, 4. Проверки нового порядка, 5. Связность и адреса в эксперименте с LLM, Открытые задачи

### Community 41 - "Community 41"
Cohesion: 0.22
Nodes (9): Как восстановить исходную таблицу Markov-5, Полные страницы Qwen3, Результаты слепой проверки, Текущий статус, Что остаётся проверить, Что показало сравнение малых языковых моделей, Что проверено на публичном сайте, Что удавалось ранним моделям (+1 more)

### Community 42 - "Community 42"
Cohesion: 0.40
Nodes (4): Action plan: human-ordered bijective Babel, Do not do yet, Goal, Minimum path

### Community 43 - "Community 43"
Cohesion: 0.40
Nodes (4): Markov as a measurement instrument, Markov Theory Notes, Proof-first vs quality-first, Scaling observations

### Community 44 - "Community 44"
Cohesion: 0.70
Nodes (4): boot(), card(), esc(), tryFetch()

### Community 45 - "Community 45"
Cohesion: 0.70
Nodes (4): boot(), cfgName(), esc(), metricCards()

### Community 46 - "Community 46"
Cohesion: 0.50
Nodes (3): Babel enumerative MVP, Proof sketch, Run

### Community 47 - "Community 47"
Cohesion: 0.83
Nodes (3): human_int(), main(), run()

### Community 48 - "Community 48"
Cohesion: 0.29
Nodes (7): Библиотека Вавилона, Как текст получает адрес, Карта сайта, Локальный запуск, Откуда берётся читаемое начало, Что измеряет энергия Babel-1, Что показала слепая проверка

### Community 50 - "Community 50"
Cohesion: 0.50
Nodes (3): General observation, Markov Experimental Results, Observed behavior

### Community 51 - "Community 51"
Cohesion: 0.50
Nodes (3): Counting Infinity, The challenge, Why brute force does not work

### Community 52 - "STAGE 5. Определение того, что должно находиться около нуля"
Cohesion: 0.13
Nodes (15): STAGE 5. Определение того, что должно находиться около нуля, Возможное достоинство, Возможное достоинство, Гипотеза A. Вероятностный порядок, Гипотеза B. Локально-типичный порядок, Гипотеза C. Гибридный порядок, Гипотеза D. Типичная оболочка вместо минимальной энергии, Главный риск (+7 more)

### Community 57 - "build_sentence_student_v1.py"
Cohesion: 0.50
Nodes (4): Как повторить, Результаты, Связность текста по первым адресам Babel-1, Условия проверки 20 ноября 2026 года

### Community 67 - "Текущий план"
Cohesion: 0.50
Nodes (4): Проверить выводы о читаемости, Продолжить исследование точной нумерации, Сравнить полные страницы, Текущий план

### Community 69 - "Можно ли отдать начало библиотеки языковой модели?"
Cohesion: 0.33
Nodes (6): Как номер превращается в страницу, Можно ли отдать начало библиотеки языковой модели?, Первая проверка с языковой моделью, 20 ноября 2026 года, Следующий эксперимент и критерии решения, Что показали ещё 16 страниц, Что уже проверено

### Community 93 - "README.md"
Cohesion: 0.67
Nodes (3): consensus(), main(), Recompute the blinded story comparison from the published records.

### Community 104 - "atlas.js"
Cohesion: 0.19
Nodes (24): atlasApi(), atlasBoot(), atlasDirections, atlasDrag(), atlasDraw(), atlasHash(), atlasHexPoints(), atlasKey() (+16 more)

### Community 105 - "address-space.js"
Cohesion: 0.57
Nodes (7): facts(), formatAddress(), locateRaw(), locateSemantic(), openRaw(), post(), setResult()

### Community 106 - "Babel-1: инженерная декомпозиция после научного решения"
Cohesion: 0.17
Nodes (11): Babel-1: инженерная декомпозиция после научного решения, E0. Контракт версии (один короткий результат), E1. Латентный exact core, E2. Детерминированная контекстная перестановка, E3. Независимая проверка и property tests, E4. Эксперимент качества, E5. API, E6. Reader и язык интерфейса (+3 more)

### Community 107 - "STAGE 7. Исследование разнообразия соседних страниц"
Cohesion: 0.17
Nodes (12): 1. Тождественный порядок, 2. Аффинная перестановка, 3. Обратимая сеть Фейстеля, 4. Смешивание разрядов, STAGE 7. Исследование разнообразия соседних страниц, Важное ограничение, Кандидаты, Критерий завершения (+4 more)

### Community 108 - "STAGE 10. Финальная научная валидация и заморозка `Babel-1`"
Cohesion: 0.18
Nodes (11): 1. Формальная спецификация `Babel-1`, 2. Доказательный документ, 3. Экспериментальный отчёт, 4. Канонические тест-векторы, 5. Зафиксированное издание, STAGE 10. Финальная научная валидация и заморозка `Babel-1`, Доказуемые утверждения, Запрещённые утверждения (+3 more)

### Community 109 - "12. Главные исследовательские вопросы"
Cohesion: 0.20
Nodes (10): 12. Главные исследовательские вопросы, RQ1. Биективность, RQ2. Точный подсчёт, RQ3. Полный глобальный ранг, RQ4. Выразительность, RQ5. Определение начала, RQ6. Градиент, RQ7. Разнообразие (+2 more)

### Community 110 - "STAGE 2. Теория латентных энергетических оболочек"
Cohesion: 0.20
Nodes (10): 2.1. Общая стоимость, 2.2. Генерирующая функция, 2.3. Рекуррентная форма, 2.4. Бинарная базовая конструкция, 2.5. Точная нумерация внутри оболочки, STAGE 2. Теория латентных энергетических оболочек, Критерий завершения, Научный вопрос (+2 more)

### Community 111 - "STAGE 4. Связь с точной вероятностной моделью языка"
Cohesion: 0.20
Nodes (10): 4.1. Фиксированный спектр вероятностей, 4.2. Проекция существующей модели на фиксированный спектр, 4.3. Квантизация спектра, 4.4. Ошибка приближения полной страницы, STAGE 4. Связь с точной вероятностной моделью языка, Критерий завершения, Научный вопрос, Обязательные результаты Stage 4 (+2 more)

### Community 112 - "STAGE 3. Теорема о глобальном `rank/unrank`"
Cohesion: 0.22
Nodes (9): 3.1. Порядок оболочек, 3.2. Перемешивание внутри оболочки, 3.3. Глобальный ранг, 3.4. Глобальное восстановление, STAGE 3. Теорема о глобальном `rank/unrank`, Критерий завершения, Научный вопрос, Обязательный результат Stage 3 (+1 more)

### Community 113 - "STAGE 6. Проверка смыслового градиента и геометрии адресов"
Cohesion: 0.22
Nodes (9): 6.1. Операциональное определение человеческого качества, 6.2. Сэмплирование оболочек, 6.3. Основная статистическая гипотеза, 6.4. Необходимые сравнения, 6.5. Геометрия оболочек, 6.6. Критерии успеха, STAGE 6. Проверка смыслового градиента и геометрии адресов, Научный вопрос (+1 more)

### Community 114 - "STAGE 1. Теорема о контекстной перестановочной биекции"
Cohesion: 0.22
Nodes (9): STAGE 1. Теорема о контекстной перестановочной биекции, Критерий завершения, Логика доказательства, Научный вопрос, Обязательный научный результат Stage 1, Определение, Теорема 1. Контекстная биективность, Условия теоремы, которые нельзя ослаблять (+1 more)

### Community 115 - "STAGE 8. Условное расширение выразительности"
Cohesion: 0.22
Nodes (9): STAGE 8. Условное расширение выразительности, Критерий завершения, Критерий перехода на Stage 8, Принципиальное отличие от старого пути, Проблема фиксированного спектра, Расширение 8A. Позиционно-зависимые спектры, Расширение 8B. Периодические или блочные спектры, Расширение 8C. Малое латентное состояние (+1 more)

### Community 116 - "ROADMAP.md"
Cohesion: 0.40
Nodes (5): 13. Условия, при которых научная работа считается законченной, Математическая готовность, Модельная готовность, Репродуктивная готовность, Эмпирическая готовность

### Community 117 - "2. Центральная математическая гипотеза"
Cohesion: 0.25
Nodes (8): 1. Назначение документа, 2.1. Латентная страница, 2.2. Контекстная перестановка, 2.3. Главное математическое упрощение, 2. Центральная математическая гипотеза, Научная программа завершения математического ядра «Библиотеки Вавилона», Статистические свойства, Строго математические свойства

### Community 118 - "STAGE 9. Масштабирование, точная арифметика и воспроизводимость"
Cohesion: 0.25
Nodes (8): 9.1. Целочисленный порядок кандидатов, 9.2. Точные размеры оболочек, 9.3. Версионирование, 9.4. Набор канонических тест-векторов, 9.5. Независимые реализации, STAGE 9. Масштабирование, точная арифметика и воспроизводимость, Критерий завершения, Научный вопрос

### Community 119 - "STAGE 0. Формализация объекта библиотеки"
Cohesion: 0.33
Nodes (6): STAGE 0. Формализация объекта библиотеки, Критерий завершения, Научный вопрос, Обязательный научный результат Stage 0, Отдельная проблема коротких текстов, Рекомендуемое определение

### Community 120 - "Задачи"
Cohesion: 0.50
Nodes (4): Генераторы в браузере, Локальный запуск, Что считает Score, Шесть режимов генератора

### Community 121 - "Какая маленькая модель удерживает развязку рассказа?"
Cohesion: 0.67
Nodes (3): Из чего выбирали, Как перепроверить, Какая маленькая модель удерживает развязку рассказа?

### Community 122 - "student_comparison_pages.py"
Cohesion: 0.42
Nodes (8): main(), measure(), provenance(), Path, require_prefix(), seed_range(), write_sample(), range

### Community 123 - "Что открывается на восьми малых и восьми далёких адресах Qwen3"
Cohesion: 0.67
Nodes (3): Как воспроизвести адрес, Как отбирали страницы, Что открывается на восьми малых и восьми далёких адресах Qwen3

### Community 124 - "evaluate_continuations.py"
Cohesion: 0.36
Nodes (7): compare(), Read an anonymous page or reproduce the published continuation comparison., Each positive judgment must cite the original, unnormalized Unicode text., Exact two-sided sign test conditional on the discordant matched seeds., read_lines(), summarize(), validate_reading()

### Community 125 - "Сохраняет ли Qwen смысл между половинами страницы"
Cohesion: 0.33
Nodes (6): Для чего проверяли на двух компьютерах, Как повторить, Как сравнивали, Следующий шаг, Сохраняет ли Qwen смысл между половинами страницы, Что изменили в генераторе

## Knowledge Gaps
- **316 isolated node(s):** `clone_tg_economic.sh script`, `install_dataset_deps.sh script`, `deploy-babel-walk.sh script`, `enable-babel-walk-tls.sh script`, `graphify-semantic.sh script` (+311 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **30 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RawClusterRanker` connect `Community 0` to `Community 1`, `Community 10`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **Why does `HierarchicalEnumeratorV1` connect `Community 6` to `Community 1`?**
  _High betweenness centrality (0.015) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `HierarchicalEnumeratorV1` (e.g. with `catalogue_ranker()` and `main()`) actually correct?**
  _`HierarchicalEnumeratorV1` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `RawClusterRanker` (e.g. with `exact_cluster_ranker()` and `ChunkedRawCounter`) actually correct?**
  _`RawClusterRanker` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `clone_tg_economic.sh script`, `install_dataset_deps.sh script`, `deploy-babel-walk.sh script` to the rest of the system?**
  _316 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.09830866807610994 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.09523809523809523 - nodes in this community are weakly interconnected._