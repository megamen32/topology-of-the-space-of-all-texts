# Babel Experiments

Мы строим **топологию пространства всех текстов**.

Где:

- расстояние определяется похожестью на человеческое распределение;
- адрес — это место текста в этой геометрии.

Это не генератор и не обычная компрессия. Цель — доказуемая биекция:

```text
[0, 2^32768) <-> all 4096-symbol pages over a 256-symbol alphabet
```

Но пространство упорядочено так, чтобы человеческие тексты лежали ближе к началу, а случайный шум уходил в дальние области.

## Current alphabet

Первый data-derived алфавит построен из книг, субтитров, VK/TG/Pikabu/comment-style корпусов и Twitter emoji.

```text
models/top256_alphabet/alphabet_top256.json
```

Покрытие корпуса:

```text
99.9648% of 37,274,388 characters
```

То есть 256 символов почти полностью покрывают живой RU/EN интернет-корпус.

В алфавит вошли не только буквы и пунктуация, но и интернет-эмоции:

```text
👍 😂 🙏 👎 ❤ 🌹 🤣 👏 💋 😍 😊 😁 😘 😄 😡 😀 🔥 🤔 😭
```

Забавные частые символы, которые **не вошли** в текущие 256:

```text
С Ю ë Ы ✨ Ü Ö 💕 ✅ 🎶 ÿ ä 😭 🚗 Δ ¬ þ 😍 ≠ л 😋 😘 ¹
```

Это не финальный алфавит. Это первая фотография распределения культуры.

## Phases

- [x] Enumerative rank/unrank MVP for small fixed-length pages
- [x] Dataset ingestion pipeline (books/subtitles/social/emoji corpora)
- [x] Data-derived top-256 alphabet with coverage analysis
- [x] Background task system for long-running experiments
- [ ] Retrain all models on the new top-256 alphabet
- [ ] Compare low-energy pages across unigram vs Markov-3
- [ ] Add anti-collapse penalties (spaces/repetition/degenerate loops)
- [x] Token/FSM experiments v0
- [ ] MVP 3: finite token automaton with integer costs
- [ ] MVP 4: tiny transformer teacher with discretized hidden states
- [ ] Exact large-N counting optimizations
- [ ] Distilled teacher-model energy experiments

## Core idea

Каждая страница получает целочисленную энергию:

```text
energy(page) = how human-like this page is under the chosen corpus/model
```

Порядок:

```text
lower energy first, lexicographic tie-breaker inside equal energy
```

Это даёт:

```text
rank(page) -> address
unrank(address) -> page
```

без пропусков и дублей, если counting layer реализован строго.

## Why not just Huffman or LLM?

Huffman/compression даёт короткие коды частым паттернам, но не гарантирует полный порядок всех `256^4096` страниц без дыр и дублей.

LLM хорошо оценивает human-likeness, но exact `rank/unrank` требует комбинаторного подсчёта. Поэтому путь сейчас такой:

```text
datasets -> finite alphabet -> integer energy -> enumerative ranking
```

LLM позже может быть teacher, но не ядром доказательства.

## Layout

```text
experiments/  scripts and prototypes
notes/        theory and plans
datasets/     local data, ignored by git
models/       trained alphabets/models, ignored by git
repos/        external repos, ignored by git
tasks/        background task logs/state, ignored by git
```

## Philosophy

Мы не пытаемся сгенерировать один хороший текст.

Мы пытаемся назначить каждому возможному тексту координату в human-shaped geometry.

Библиотека Вавилона остаётся полной, детерминированной и обратимой — но получает рельеф, долины и расстояния.

## Static prototype

A first static JS prototype lives in:

```text
site/
```

No Pyodide is required for the current student. The finite model is exported as JSON and runs directly in browser JavaScript.

## Teacher / student rule

Teacher can be neural. Student must be finite.

```text
Transformer = taste / human-likeness field
Finite student = proof / addressable geometry
```

All probability models are converted into integer costs:

```text
cost = floor(-log2(P) * scale)
```
