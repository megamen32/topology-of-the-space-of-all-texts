# Babel Experiments

Мы строим **топологию пространства всех текстов**.

Где:

- расстояние определяется похожестью на человеческое распределение;
- адрес — это место текста в этой геометрии.

Это не просто генератор текста и не обычная компрессия. Цель проекта — построить доказуемую биекцию между адресами и всеми возможными страницами фиксированной длины, но переупорядочить это пространство так, чтобы человеческие тексты лежали ближе к началу, а случайный шум уходил в дальние области.

```text
[0, 2^32768) <-> all 4096-symbol pages over a 256-symbol alphabet
```

## Core idea

Обычная Библиотека Вавилона покрывает всё пространство текстов, но почти всё в ней выглядит как шум. Мы хотим сохранить полное покрытие, но изменить геометрию пространства.

Для каждой страницы вводится целочисленная энергия:

```text
energy(page) = насколько страница похожа на человеческий корпус
```

Затем все страницы упорядочиваются так:

```text
lower energy first, lexicographic tie-breaker inside equal energy
```

Такой порядок даёт строгую биекцию:

```text
rank(page) -> address
unrank(address) -> page
```

## Why not just Huffman or LLM?

Huffman/compression gives short codes to common patterns, but it does not automatically give a complete bijective ordering of all `256^4096` pages without holes and duplicates.

LLMs are good at estimating human-likeness, but exact `rank/unrank` requires combinatorial counting. A transformer hidden state is not a small finite state, so it is hard to use directly in a proof.

The current path is:

```text
datasets
↓
finite alphabet
↓
integer energy model
↓
exact enumerative ranking
↓
proof-preserving Library of Babel
```

## Current experiments

```text
repos/        external/source repos
experiments/  scripts and prototypes
datasets/     local raw/processed datasets, ignored by git
models/       trained models/alphabets, ignored by git except manifests if added later
notes/        theory, plans, decisions
workers/      future long-running jobs if needed
tasks/        task state/logs, ignored by git
```

### Existing pieces

- `experiments/taskctl.sh` — tiny named background task runner with logs/state.
- `experiments/build_top256_alphabet.py` — builds a 256-symbol alphabet from processed corpora.
- `experiments/train_alphabet_models.py` — trains unigram and Markov-3 models over the selected alphabet.
- `experiments/enumerative_babel_mvp.py` — minimal exact rank/unrank proof prototype for short fixed-length pages.
- `notes/action_plan.md` — execution plan.
- `notes/markov3_vs_transformer.md` — why finite-state models are proof-first and transformers are quality-first.
- `datasets/manifests/sources.md` — dataset source manifest.

## Mathematical target

For page length `4096` and alphabet size `256`:

```text
256^4096 = 2^32768
```

The target is an exact bijection:

```text
rank(page_4096_symbols) -> uint32768
unrank(uint32768) -> page_4096_symbols
```

with no missing pages and no duplicate addresses.

## Working hypothesis

Human-like text is not just low entropy. Pure likelihood collapses into degenerate minima such as endless spaces or repeated high-frequency symbols.

So the useful ordering is not plain probability, but a regularized energy:

```text
energy = language_cost
       + repetition_penalty
       + whitespace_penalty
       + invalid_symbol_penalty
       + structure_penalty
```

The first finite-state models are intentionally simple. They are proof laboratories, not the final aesthetic model.

## Near-term roadmap

1. Download social/internet corpora: VK/TG/Pikabu/comments/Twitter emoji.
2. Build a data-derived top-256 alphabet.
3. Convert corpora into this alphabet.
4. Train unigram and Markov-3 energy models.
5. Inspect low-rank pages and failure modes.
6. Add anti-collapse penalties.
7. Move from character models to token/FSM models.
8. Optionally use an LLM as a teacher, distilled into a finite model.

## Philosophy

We are not trying to generate one good text.

We are trying to assign every possible text a coordinate in a human-shaped geometry.

The result should still be a Library of Babel — complete, deterministic, reversible — but with meaningful regions, valleys, and distances.
