# BioEQ Back MVP

Минимальный рабочий python-проект мультиагентной системы для синтетического планирования дизайна биоэквивалентности.

## Быстрый старт

1. Запуск vLLM сервера:

```bash
bash scripts/run_vllm_qwen.sh
```

2. Запуск системы:

```bash
python main.py
```

По умолчанию используется модель `Qwen/Qwen2.5-7B-Instruct` (совместимо со скриптом `scripts/run_vllm_qwen.sh`).
При необходимости можно переопределить через переменные окружения:

```bash
export VLLM_MODEL="Qwen/Qwen2.5-7B-Instruct"
# или отдельно:
export PLANNER_MODEL="..."
export REVIEWER_MODEL="..."
```

## Логирование и тайминги

Теперь система использует централизованное логирование с ISO-таймстампами (`YYYY-MM-DDTHH:MM:SS`) и подробными таймингами по этапам:

- старт/окончание оркестрации
- `load_input`, `planner_call`, `reviewer_call`
- start/end LLM-запросов
- итоговое общее время выполнения (`Total elapsed`)

Включить детальные DEBUG-логи можно через переменную окружения:

```bash
export LOG_LEVEL=DEBUG
python main.py
```

## Что делает MVP

- читает входные параметры из `configs/user_input.json`
- запускает `PlannerAgent` для синтетического дизайна исследования
- передаёт результат в `ReviewerAgent` для проверки согласованности
- печатает оба JSON-результата в stdout
