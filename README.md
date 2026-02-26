# BioEQ

`BioEQ Back MVP` — Python-проект мультиагентной системы для синтетического планирования дизайна исследований биоэквивалентности и извлечения PK-параметров из научных публикаций.

## Что умеет система

Система объединяет несколько специализированных агентов в единый конвейер:

1. **Планирование исследования (PlannerAgent)**
   - Читает входные параметры из `configs/user_input.json`.
   - Генерирует структурированный план дизайна биоэквивалентного исследования.

2. **Поиск литературы в PubMed**
   - Формирует запрос по `inn` и тематике PK/BE.
   - Получает релевантные PMID.
   - Загружает метаданные и abstracts публикаций.

3. **Проверка доступности full-text в PMC OA**
   - Разрешает `PMID -> PMCID`.
   - Определяет, есть ли PDF/XML в открытом доступе (OA subset).

4. **Загрузка и парсинг full-text**
   - Скачивает PDF/XML.
   - Валидирует файлы.
   - Парсит документы в чанки для дальнейшего поиска релевантных фрагментов.

5. **Retrieval + PK extraction**
   - Выбирает фрагменты текста под целевые параметры (`t_half`, `cmax`).
   - Извлекает доказательства (`EvidenceItem`) с привязкой к источнику (abstract/pdf/xml, страница/секция и т.д.).
   - Считает агрегаты (`mean/median`) при совместимых единицах измерения.

6. **Ревью результата (ReviewerAgent)**
   - Проверяет согласованность результата планировщика.

7. **Отчётность и артефакты**
   - Сохраняет артефакты выполнения в `data/runs/<timestamp>/...`:
     - `pdf_manifest.json`, `xml_manifest.json`
     - `pdf_chunks.jsonl`, `xml_chunks.jsonl`
     - `evidence.json`
   - Выводит в stdout JSON-ответы планировщика и ревьюера.

8. **Тестовый режим (по умолчанию сейчас включён)**
   - В `main.py` переменная `TEST_MODE = True`.
   - В тестовом режиме запускается synthetic-оценка на `configs/test_dataset.json`.
   - Формируется отчёт `reports/test_report.json` с ошибками и покрытием по `T_half/Cmax`.

---

## Требования

- Python **3.10+**
- CUDA/GPU для локального vLLM (рекомендуется)
- Доступ в интернет (PubMed/PMC и модель, если не закеширована локально)

### Важно про GPU в текущем скрипте vLLM

В `scripts/run_vllm_qwen.sh` сейчас зашито использование **двух видеокарт**:

- `CUDA_VISIBLE_DEVICES=0,1`
- `--tensor-parallel-size 2`

Если вы запускаете **на одной GPU**, обязательно поменяйте:

```bash
export CUDA_VISIBLE_DEVICES=0
# и
--tensor-parallel-size 1
```

Иначе запуск vLLM не соответствует доступным ресурсам.

---

## Установка зависимостей (Conda)

Ниже пример (через conda).

### 1) Создать и активировать окружение

```bash
conda create -n bioeq python=3.10 -y
conda activate bioeq
```

### 2) Установить проект в editable-режиме

Из корня репозитория:

```bash
pip install -e .
```

Это подтянет зависимости из `pyproject.toml`:

- `biopython`
- `beautifulsoup4`
- `openai`
- `pydantic`
- `python-dotenv`
- `pypdf`

### 4) Установить vLLM

pip install vllm

> Подберите версию `vllm` и CUDA под вашу систему/драйвер.

---

## Настройка окружения

Основные переменные, которые можно переопределить:

- `VLLM_BASE_URL` (по умолчанию `http://127.0.0.1:8000/v1`)
- `VLLM_API_KEY` (по умолчанию `local`)
- `VLLM_MODEL`
- `PLANNER_MODEL`
- `PK_MODEL` (или `ABSTRACT_ANALYSIS_MODEL`)
- `REVIEWER_MODEL`
- `USER_INPUT_PATH` (по умолчанию `configs/user_input.json`)
- `PUBMED_N_ARTICLES` (по умолчанию `5`)
- `PUBMED_CYCLES` (по умолчанию `2`)
- `PUBMED_SLEEP_SEC` (по умолчанию `1.0`)
- `ENTREZ_EMAIL`
- `ENTREZ_TOOL`
- `LOG_LEVEL` (например, `DEBUG`)
- `LLM_TEMPERATURE` (по умолчанию `0.0`)

При использовании `.env` файл автоматически подхватывается через `python-dotenv`.

---

## Как запустить

## Вариант A: стандартный запуск (основной пайплайн)

1. Убедитесь, что в `main.py` установлено:

```python
TEST_MODE = False
```

2. Поднимите vLLM:

```bash
bash scripts/run_vllm_qwen.sh
```

3. В отдельном терминале запустите приложение:

```bash
python main.py
```

## Вариант B: тестовый режим (текущий дефолт в коде)

При `TEST_MODE = True` приложение запустит synthetic-бенчмарк и сохранит отчёт:

```bash
python main.py
```

Результат: `reports/test_report.json`.

---

## Структура важных путей

- `main.py` — точка входа
- `scripts/run_vllm_qwen.sh` — запуск vLLM
- `configs/user_input.json` — входные параметры пользователя
- `configs/test_dataset.json` — датасет для test mode
- `reports/test_report.json` — отчёт test mode
- `src/be_system/orchestrator.py` — оркестрация пайплайна
- `src/be_system/agents/*` — специализированные агенты

---

## Логирование

Система использует централизованное логирование с ISO-таймстампами и таймингами этапов.

Для подробных логов:

```bash
export LOG_LEVEL=DEBUG
python main.py
```

