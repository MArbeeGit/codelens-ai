import json
from .llm_router import generate
from .validator import extract_json

REVIEW_PROMPT = """You are senior reviewer. Output ONLY valid JSON, no markdown/backticks.
Schema: {{"bugs":[{{"line":int,"type":"logic|security|performance|style","severity":"high|medium|low","message":str,"suggestion":str}}],"security":[{{"line":int,"issue":str}}],"style":[{{"line":int,"issue":str}}],"complexity":str,"summary":str}}
Rules: Max 5 bugs, be precise, line numbers accurate. If clean, empty arrays + summary "No issues".
Language:{lang}
Code:
```
{code}
```"""


def mock_review(code, lang):
    bugs = []
    if "==" in code and "===" not in code and lang in ("javascript", "js"):
        bugs.append(
            {
                "line": 1,
                "type": "logic",
                "severity": "medium",
                "message": "Use === instead of ==",
                "suggestion": "Replace ==",
            }
        )
    if "eval(" in code:
        bugs.append(
            {
                "line": 1,
                "type": "security",
                "severity": "high",
                "message": "eval is dangerous",
                "suggestion": "Avoid eval",
            }
        )
    if "except:" in code:
        bugs.append(
            {
                "line": 1,
                "type": "style",
                "severity": "low",
                "message": "Bare except",
                "suggestion": "except Exception",
            }
        )
    return {
        "bugs": bugs,
        "security": [],
        "style": [],
        "complexity": "O(n)",
        "summary": "Mock review (no API key set). Add GEMINI_API_KEY for full AI review.",
    }


def review_code(code, lang="python"):
    prompt = REVIEW_PROMPT.format(lang=lang, code=code[:6000])
    try:
        raw, cached, model = generate(prompt)
        j = extract_json(raw)
        if j and "bugs" in j:
            j["_model"] = model
            j["_cached"] = cached
            return j, raw
        raise ValueError("bad json")
    except Exception as e:
        m = mock_review(code, lang)
        m["_model"] = "mock"
        m["_error"] = str(e)[:200]
        return m, json.dumps(m)
