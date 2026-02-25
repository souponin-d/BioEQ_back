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

## Что делает MVP

- читает входные параметры из `configs/user_input.json`
- запускает `PlannerAgent` для синтетического дизайна исследования
- передаёт результат в `ReviewerAgent` для проверки согласованности
- печатает оба JSON-результата в stdout
