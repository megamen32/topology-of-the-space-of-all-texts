# Издание Babel Qwen v1

Образ `babel-qwen-reference:v1` содержит GGUF Qwen3 1.7B Q4_K_M, нативный `llama-server`, Python 3.12.16, алфавит и код адресации с промптами. Платформа — Linux amd64 с набором инструкций Haswell (AVX2, FMA, F16C, BMI2). Единственный вычислительный бэкенд загружается по абсолютному пути из образа.

## Запуск готового образа

Чтобы запустить тот же образ, что и на сайте, скачайте архив (1,36 ГБ) и файл SHA-256 из релиза. Из каталога загрузки выполните команды ниже. [Скачать издание Babel Qwen v1](https://github.com/megamen32/topology-of-the-space-of-all-texts/releases/tag/babel-qwen3-ref-v1)

```sh
sha256sum --check babel-qwen-reference-v1.tar.zst.sha256
docker load -i babel-qwen-reference-v1.tar.zst
docker image inspect --format '{{.Id}}' babel-qwen-reference:v1
docker run -d --name babel-qwen-reference-v1 --read-only \
  -p 127.0.0.1:18862:8081 babel-qwen-reference:v1
```

Ожидаемый ID — `sha256:1200cb258799be285aca6f5f63c5f3fd4dc0145ca42b604502ceb2ec49c8aa9f`. Контейнер открывает API адресации на порту 18862.

## Сборка из исходного кода

Из корня проекта на Linux с Docker Buildx, Bash, GNU coreutils, curl, tar и zstd выполните

```sh
./deploy/qwen-reference/build.sh
docker run -d --name babel-qwen-reference-v1 --read-only \
  -p 127.0.0.1:18861:8080 -p 127.0.0.1:18862:8081 \
  babel-qwen-reference:v1
curl -fsS --retry 60 --retry-all-errors --retry-delay 1 http://127.0.0.1:18862/health
```

Служба адресации на 18862 принимает `GET /health`, `POST /unrank` и `POST /rank`. Порт 18861 открывает нативные `GET /props` и `POST /completion`. Сервер обрабатывает один запрос за раз, адаптер передаёт `cache_prompt: false` при каждом расчёте. Готовность подтверждает HTTP 200 от `/health` после загрузки весов. Остановка контейнера завершает обе службы.

В сборку входят восемь файлов из официального архива Ollama 0.32.1. Версия llama.cpp — b9888, commit `cb295bf59663cd3577389315636772f4060bd1f5`. Сборка сверяет SHA-256 архива, каждого файла runtime, весов и кода издания. Для ускорения можно передать каталог установленного runtime через `BABEL_OLLAMA_LIB` и путь к GGUF через `BABEL_QWEN_GGUF`. Проверки байтов одинаковы для обоих источников. [Релиз Ollama](https://github.com/ollama/ollama/releases/tag/v0.32.1) · [Версия llama.cpp в релизе](https://github.com/ollama/ollama/blob/30c390384e20333b67cadab60da5bcb669407f01/LLAMA_CPP_VERSION) · [Модель Qwen3](https://ollama.com/library/qwen3:1.7b)

Для проверки содержимого запущенного контейнера выполните

```sh
docker exec babel-qwen-reference-v1 sha256sum --check --strict SHA256SUMS
```

Обе сборки из закреплённых исходных файлов содержали одинаковые байты кода, библиотек и весов. При сборке без кеша Docker изменил временные метки восьми каталогов, отчего изменился ID образа. Архив в релизе сохраняет точный ID экземпляра на публичном сайте. [Контрольные суммы и обе проверки адресации](../../notes/experiments/qwen_reference_verification.json)
