# Текущий статус

Обновлено после сборки public address-space explorer.

## Готово

- подготовлен и зафиксирован top-256 alphabet;
- реализована raw bijection для 4096-символьных страниц;
- реализован cluster-energy exact rank/unrank для страниц длиной до 256;
- реализована hierarchical exact composition для 4096 символов из 16 блоков;
- добавлены точные decimal/hex адреса и обратное открытие страницы;
- добавлены `score`, `search`, `counting-proof` и exact-neighbor API;
- собран русский public explorer без логина на `all.bezrabotnyi.com`;
- Atlas работает как детерминированный литературный reader с RU/EN, книгами, поиском и deep links;
- публичный browser canary пройден: raw rank/unrank, semantic rank, мобильная ширина, console errors = 0;
- граф проекта обновлён через `graphify update .`.

## Что именно доказано

Для raw-слоя доказана полная адресация пространства `Σ^4096`: каждая страница имеет ровно один адрес, а каждый допустимый адрес восстанавливает страницу.

Для cluster-energy exact слоя доказана взаимная однозначность на поддерживаемых длинах до 256: порядок равен `energy → raw tie-break`, rank и unrank согласованы.

Для hierarchical 4096 доказаны полнота и обратимость блочной композиции. Это ещё не доказательство единого глобального semantic energy-order для всей 4096-символьной страницы.

## Сейчас в работе

- exact counting глобальной energy для 4096 символов;
- проверка качества порядка на frontier и человеческих контрольных страницах;
- компактные energy buckets и chunked tables;
- единый proof document с тестами completeness, uniqueness и reversibility;
- перевод оставшихся публичных пояснений и research notes на актуальную терминологию.

## Не считать готовым

- процедурные Atlas-тексты не являются результатом глобального semantic rank;
- hex-адрес сам по себе не означает «близость к смыслу» в raw-режиме;
- hierarchical exact 4096 не следует описывать как уже завершённую глобальную сортировку по energy.
