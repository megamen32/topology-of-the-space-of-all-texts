# Топология пространства всех текстов

Проект строит координатную систему для пространства всех возможных страниц.

Главная мысль проста: генератор придумывает текст, а адресатор находит место уже существующего текста в полном пространстве. Для страницы длиной 4096 символов над алфавитом из 256 знаков существует ровно:

```text
256^4096 = 2^32768 страниц
```

Raw-слой уже даёт взаимно однозначное соответствие:

```text
целое число ↔ страница из 4096 символов
```

Следующий слой проекта пытается изменить порядок: страницы, похожие на человеческую речь, должны лежать ближе к нулю, а всё более шумные — дальше. Для этого конечный student assigns integer energy to every transition, а exact counting считает, сколько страниц находится ниже заданной энергии.

## Что можно проверить сейчас

Публичный explorer: [all.bezrabotnyi.com](https://all.bezrabotnyi.com/).

На главной странице доступны три разных, явно разделённых режима:

1. **Raw space.** Все `2^32768` страниц, exact rank/unrank для 4096 символов. Это полный лексикографический base-256 порядок, не semantic order.
2. **Cluster-energy exact MVP.** Полная energy-сортировка страниц длиной до 256 символов: сначала integer energy, затем точный raw tie-break.
3. **Hierarchical exact 4096.** 4096 символов собираются из 16 точных 256-символьных блоков. Биекция и обратимость сохраняются; это пока блочно-лексикографическая композиция, а не один глобальный energy-порядок всей страницы.

Atlas — отдельный литературный режим: он показывает детерминированные русские/английские тексты, книги и deep links. Это удобный интерфейс для чтения, но его процедурные координаты нельзя принимать за глобальную semantic-сортировку.

## Архитектура

```text
raw corpus
  → top-256 alphabet
  → context vectors / cluster student v2
  → finite transitions and integer energy
  → exact counting of paths
  → rank / unrank
  → public address-space explorer
```

Основные реализации:

- `experiments/cluster_counting_mvp.py` — exact cluster ranker и hierarchical block composition;
- `experiments/cluster_chunk_counting.py` — chunked counting experiments;
- `experiments/backend_app.py` — Flask API raw/rank/unrank/score/Atlas;
- `site/index.html` и `site/assets/address-space.js` — главный address-space explorer;
- `site/search.html` — полный режим Search / Rank / Score;
- `site/atlas.html` — литературная библиотека;
- `graphify-out/` — актуальный граф связей кода и документации.

## API-маршруты

```text
POST /api/rank
POST /api/unrank
POST /api/score
POST /api/search
GET  /api/counting-proof
GET  /api/atlas-page
```

Точные rank-значения передаются как строки и hex, потому что JavaScript Number не способен безопасно хранить такие целые числа.

## Исследовательская граница

Глобальный порядок «все 4096 символов сразу по общей semantic energy» ещё не заявлен как готовый результат. Для него нужны масштабируемые exact counting tables, компактные energy buckets и доказательство того, что порядок одновременно полон, бездубликов, обратим и соответствует выбранному student.

Это не декоративная оговорка, а центральная задача проекта: превратить человеческую вероятностную геометрию в строгую адресацию бесконечно большого на практике пространства.

## Где читать дальше

1. [Текущая архитектура](notes/current/architecture.md)
2. [Текущий статус](notes/current/status.md)
3. [Открытые задачи](notes/current/open_problems.md)
4. [План](notes/current/roadmap.md)

История экспериментов лежит в `notes/phases/`, `notes/research/` и `notes/experiments/`.
