# Текущая архитектура

Статус: источник текущей правды проекта.

## Два слоя адресации

Проект нельзя описывать одним словом «ранжировщик»: сейчас работают два разных порядка.

### 1. Полное raw-пространство

Алфавит фиксирован как top-256. Страница нормализуется, дополняется пробелами до 4096 символов и рассматривается как 4096 байт base-256. Поэтому:

```text
page ∈ Σ^4096
|Σ| = 256
|Σ^4096| = 2^32768
```

Этот слой даёт мгновенные `rank ↔ page` без дыр и повторов. Его порядок лексикографический, поэтому он сам по себе ничего не говорит о человеческой осмысленности.

### 2. Energy-пространство

Конечный student хранит стоимость переходов и эмиссий символов. Для страницы:

```text
energy(page) = сумма integer costs по пути student-а
```

Далее exact ranker считает число страниц с меньшей energy и использует raw-порядок как tie-break. Это и есть формальная версия гипотезы «смысл ближе к нулю».

## Реальные режимы

`RawClusterRanker` в `experiments/cluster_counting_mvp.py` сейчас поддерживает полный exact energy-order для длины `1..256`.

`HierarchicalRawRanker` собирает страницу длиной до 4096 из 16 блоков по 256 символов. Он сохраняет полную биекцию и обратимость, но его порядок описывается как:

```text
lexicographic composition of exact block ranks
```

Это не следует называть глобальной сортировкой 4096-символьных страниц по общей energy.

## Производственный путь данных

```text
dataset/cache
  → top-256 alphabet
  → context vectors
  → cluster student v2
  → finite transition / emission costs
  → sparse or chunked exact counting
  → rank / unrank API
  → browser explorer
```

Главные файлы:

| Область | Файл | Роль |
|---|---|---|
| Модель | `models/student_fsm_v1/student_fsm_v1.json` | компактные состояния, классы и стоимости |
| Exact core | `experiments/cluster_counting_mvp.py` | cluster rank/unrank и hierarchical composition |
| Counting | `experiments/cluster_chunk_counting.py` | chunked/external-memory направление |
| API | `experiments/backend_app.py` | raw, semantic, hierarchical, score и Atlas endpoints |
| Главная | `site/index.html` | объяснение пространства и интерактивный адресатор |
| Search | `site/search.html` | полный режим rank/score/unrank |
| Atlas | `site/atlas.html` | отдельный литературный reader |

## Правило честности интерфейса

Каждый экран должен явно указывать:

- покрывает ли он всё raw-пространство;
- является ли порядок semantic или только лексикографическим;
- для какой длины действует exact proof;
- является ли текст результатом адресации или процедурной демонстрацией.
