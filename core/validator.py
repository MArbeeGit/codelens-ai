import ast, json, re


def validate(code, lang):
    lang = (lang or "python").lower()
    if lang == "python":
        try:
            ast.parse(code)
            return True, "OK"
        except SyntaxError as e:
            return False, f"SyntaxError line {e.lineno}: {e.msg}"
    if lang in ("javascript", "js", "typescript", "ts"):
        if code.count("{") != code.count("}"):
            return False, "Mismatched braces {}"
        if code.count("(") != code.count(")"):
            return False, "Mismatched parentheses"
        return True, "OK"
    if lang in ("java", "cpp", "c++", "c"):
        if code.count("{") != code.count("}"):
            return False, "Mismatched braces"
        return True, "OK"
    try:
        ast.parse(code)
        return True, "OK"
    except:
        return True, "OK"


def extract_json(text):
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except:
        txt = m.group(0)
        txt = re.sub(r",\s*}", "}", txt)
        txt = re.sub(r",\s*]", "]", txt)
        try:
            return json.loads(txt)
        except:
            return None
