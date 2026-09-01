import re, json
from .llm_router import generate
from .validator import validate, extract_json

FIX_PROMPT = """You are a bug-fixing agent. Fix ONLY the bugs listed. Make MINIMAL edits, preserve style.
Return ONLY valid JSON, no markdown.
Schema: {{"fixed_code": str, "diff": str, "changes": [{{"line": int, "what": str}}], "explanation": str}}
Language: {lang}
Bugs: {bugs}
Original Code:
```
{code}
```
If validator error provided, fix that too: {verr}
Return JSON only."""


def mock_fix(code, lang):
    fixed = code.replace("==", "===") if lang in ("js", "javascript") else code
    if "except:" in fixed:
        fixed = fixed.replace("except:", "except Exception:")
    diff = f"- original\n+ fixed (mock, {len(fixed)} chars)"
    return {
        "fixed_code": fixed,
        "diff": diff,
        "changes": [{"line": 1, "what": "Mock fix - add API key for AI fix"}],
        "explanation": "Mock fix (no API key). Set GEMINI_API_KEY.",
    }


def fix_code(code, bugs_json, lang="python", verr=""):
    bugs = json.dumps(bugs_json.get("bugs", [])[:5])
    prompt = FIX_PROMPT.format(
        lang=lang, bugs=bugs, code=code[:6000], verr=verr or "none"
    )
    try:
        raw, cached, model = generate(prompt)
        j = extract_json(raw)
        if j and "fixed_code" in j:
            fc = j["fixed_code"]
            ok, msg = validate(fc, lang)
            if not ok and verr == "":
                return fix_code(code, bugs_json, lang, verr=msg)
            j["_model"] = model
            j["_cached"] = cached
            j["_valid"] = ok
            j["_validator_msg"] = msg
            return j, raw
        raise ValueError("bad json")
    except Exception as e:
        m = mock_fix(code, lang)
        m["_model"] = "mock"
        m["_valid"] = True
        m["_error"] = str(e)[:200]
        return m, json.dumps(m)
