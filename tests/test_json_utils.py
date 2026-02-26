from be_system.agents.json_utils import extract_json


def test_extract_json_parses_fenced_json():
    raw = """```json
{
  \"selected_design\": \"2x2 crossover\",
  \"washout_days\": 7
}
```"""

    data = extract_json(raw)

    assert data["selected_design"] == "2x2 crossover"
    assert data["washout_days"] == 7


def test_extract_json_parses_first_balanced_object_with_extra_braces_in_text():
    raw = (
        "Here is my draft {not json yet}. "
        "Final answer: {\"selected_design\":\"replicate\",\"washout_days\":14}"
    )

    data = extract_json(raw)

    assert data == {"selected_design": "replicate", "washout_days": 14}


def test_extract_json_removes_trailing_commas_and_invisible_chars():
    raw = "\ufeff{\n  \"selected_design\": \"2x2 crossover\",\n  \"washout_days\": 7,\n}"

    data = extract_json(raw)

    assert data == {"selected_design": "2x2 crossover", "washout_days": 7}
