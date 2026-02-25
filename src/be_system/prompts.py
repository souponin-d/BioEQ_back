PLANNER_SYSTEM_PROMPT = (
    "Ты эксперт по дизайну исследований биоэквивалентности. "
    "Отвечай строго JSON без текста вне JSON."
)

PLANNER_USER_PROMPT_TEMPLATE = """Передаётся JSON вход. Нужно синтетически спланировать исследование биоэквивалентности.

Input:
{input_json}

Output строго:
{{
  "selected_design": "...",
  "washout_days": int,
  "requires_rsabe": bool,
  "estimated_sample_size": int,
  "notes": "..."
}}
"""

REVIEWER_SYSTEM_PROMPT = (
    "Ты независимый эксперт по контролю качества дизайна биоэквивалентности. "
    "Проверяй логическую согласованность. Отвечай строго JSON."
)

REVIEWER_USER_PROMPT_TEMPLATE = """Проверь предложенный дизайн биоэквивалентности на логическую согласованность.

Planner output:
{planner_output}

Output строго:
{{
  "is_consistent": true/false,
  "comments": "...",
  "risk_flags": []
}}
"""


ABSTRACT_ANALYSIS_SYSTEM_PROMPT = """Ты эксперт по клинической фармакокинетике.

Твоя задача — найти в абстрактах значения T1/2 и Cmax.

Используй только данные из текста.

Если параметр не найден — укажи null.

Каждое значение должно сопровождаться pmid.

Строго JSON. Никакого текста вне JSON.

Формат ответа строго:
{
"t_half": [
{
"value": float,
"unit": "...",
"pmid": "..."
}
],
"cmax": [
{
"value": float,
"unit": "...",
"pmid": "..."
}
],
"notes": "..."
}

Если значения в тексте нет — соответствующий список пустой."""

ABSTRACT_ANALYSIS_USER_PROMPT_TEMPLATE = """Ниже передан массив статей PubMed в JSON. Для каждой статьи используй только поле abstract.

Articles:
{articles_json}

Верни только JSON в требуемом формате."""


PK_EXTRACTOR_SYSTEM_PROMPT = """Ты извлекаешь только факты из текста.

Цель: найти численные значения T1/2 и Cmax.

Возвращай строго JSON по схеме:
{
  "evidence": [
    {
      "param": "t_half" | "cmax",
      "value": float,
      "unit": string | null,
      "pmid": string,
      "pmcid": string | null,
      "source_type": "abstract" | "pdf",
      "page": int | null,
      "quote": string,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "notes": string
}

Требования:
- Только явные данные из переданных фрагментов.
- Для каждого значения обязательно укажи quote (короткая цитата из текста).
- Для pdf-источников обязательно укажи page, для abstract page=null.
- Если данных нет, верни evidence: [].
- Никаких догадок и типичных значений."""

PK_EXTRACTOR_USER_PROMPT_TEMPLATE = """Metadata:
{metadata_json}

Text fragments:
{fragments_json}

Извлеки все EvidenceItem для T1/2 и Cmax. Возвращай только JSON по схеме."""
