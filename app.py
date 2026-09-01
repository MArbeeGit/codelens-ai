import os, json, zipfile, tempfile, difflib
from dotenv import load_dotenv

load_dotenv(override=True)
import gradio as gr
from core.reviewer import review_code
from core.fixer import fix_code
from core.github_loader import fetch_github

LANGS = ["python", "javascript", "java", "cpp", "c", "typescript", "go"]


def make_diff(a, b):
    return "\n".join(
        difflib.unified_diff(
            a.splitlines(),
            b.splitlines(),
            fromfile="before",
            tofile="after",
            lineterm="",
        )
    )


def do_review(code, lang, gh_url):
    if gh_url and gh_url.strip():
        try:
            code, fname = fetch_github(gh_url)
            lang = fname.split(".")[-1] if "." in fname else lang
        except Exception as e:
            return f"Fetch error: {e}", "", "", ""
    if not code or not code.strip():
        return "Paste code or GitHub URL", "", "", ""
    try:
        j, raw = review_code(code, lang)
        md = f"### Summary ({j.get('_model', '')}{' cached' if j.get('_cached') else ''})\n{j.get('summary', '')}\n\n**Complexity:** {j.get('complexity', '-')}\n\n"
        bugs = j.get("bugs", [])
        if bugs:
            md += "| Line | Severity | Type | Message |\n|---|---|---|---|\n"
            for b in bugs:
                md += f"| {b.get('line', '-')} | {b.get('severity', '')} | {b.get('type', '')} | {b.get('message', '')} |\n"
        else:
            md += "_No bugs found._\n"
        sec = j.get("security", [])
        if sec:
            md += "\n**Security:** " + "; ".join([s.get("issue", "") for s in sec])
        return md, json.dumps(j, indent=2), code, lang
    except Exception as e:
        return f"Error: {e}", "", code, lang


def do_fix(code, lang, gh_url, review_json):
    if gh_url and gh_url.strip() and (not code or len(code) < 10):
        try:
            code, _ = fetch_github(gh_url)
        except Exception as e:
            return f"Fetch error: {e}", "", ""
    if not code or not code.strip():
        return "No code", "", ""
    try:
        j = json.loads(review_json) if review_json else {"bugs": []}
    except:
        j = {"bugs": []}
    try:
        res, raw = fix_code(code, j, lang)
        fc = res.get("fixed_code", "")
        diff = res.get("diff", "") or make_diff(code, fc)
        info = f"Model: {res.get('_model', '')} | Valid: {res.get('_valid')} {res.get('_validator_msg', '')} | {res.get('explanation', '')}"
        return fc, diff, info
    except Exception as e:
        return "", "", f"Error: {e}"


def do_zip_review(files, lang):
    if not files:
        return "Upload ZIP", "", "", None, ""
    out_md = ""
    combined = {}
    report = "# CodeLens Report\n\n"
    patched_files = {}
    try:
        for f in files if isinstance(files, list) else [files]:
            path = f.name if hasattr(f, "name") else f
            if path.endswith(".zip"):
                with zipfile.ZipFile(path) as z:
                    for name in z.namelist()[:5]:
                        if name.endswith("/") or "__MACOSX" in name:
                            continue
                        if not any(
                            name.endswith("." + e)
                            for e in ["py", "js", "java", "cpp", "ts", "go", "c"]
                        ):
                            continue
                        code = z.read(name).decode(errors="ignore")[:6000]
                        l = name.split(".")[-1]
                        mp = {
                            "py": "python",
                            "js": "javascript",
                            "java": "java",
                            "cpp": "cpp",
                            "ts": "typescript",
                        }.get(l, lang or "python")
                        j, _ = review_code(code, mp)
                        bugs = len(j.get("bugs", []))
                        out_md += f"**{name}** ({mp}) — {bugs} issues | {j.get('summary', '')[:80]}\n\n"
                        report += (
                            f"## {name} — {bugs} issues\n{j.get('summary', '')}\n\n"
                        )
                        combined[name] = j
                        try:
                            fix, _ = fix_code(code, j, mp)
                            patched_files[name] = fix.get("fixed_code", code)
                        except:
                            patched_files[name] = code
            else:
                with open(path) as fh:
                    code = fh.read()[:6000]
                    j, _ = review_code(code, lang or "python")
                    out_md += f"**{os.path.basename(path)}** — {len(j.get('bugs', []))} issues\n\n"
                    combined[os.path.basename(path)] = j
                    try:
                        fix, _ = fix_code(code, j, lang or "python")
                        patched_files[os.path.basename(path)] = fix.get(
                            "fixed_code", code
                        )
                    except:
                        patched_files[os.path.basename(path)] = code
        zip_path = None
        if patched_files:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            with zipfile.ZipFile(tmp.name, "w") as z:
                for n, c in patched_files.items():
                    z.writestr(n, c)
                z.writestr("REPORT.md", report)
            zip_path = tmp.name
        return (
            out_md or "No code files",
            json.dumps(combined, indent=2),
            report,
            zip_path,
            report,
        )
    except Exception as e:
        return f"Error: {e}", "", "", None, ""


with gr.Blocks(
    title="CodeLens AI - Code Reviewer & Fixer", theme=gr.themes.Soft()
) as demo:
    gr.Markdown(
        "# 🔍 CodeLens AI — Code Reviewer & Bug Fixing Agent\nPaste code · GitHub URL · or ZIP (4-5 files). Free-API: `gemini-3.5-flash-lite (500 RPD)` → `nvidia` + cache + agentic retry loop."
    )
    with gr.Tab("Single File"):
        with gr.Row():
            lang = gr.Dropdown(LANGS, value="python", label="Language")
            gh = gr.Textbox(
                label="GitHub file URL (optional)",
                placeholder="https://github.com/user/repo/blob/main/file.py",
            )
        code_in = gr.Code(label="Code", language="python", lines=14)
        with gr.Row():
            btn_review = gr.Button("1. Review", variant="primary")
            btn_fix = gr.Button("2. Fix (agentic retry)", variant="secondary")
        review_md = gr.Markdown()
        review_json = gr.Code(label="Review JSON", language="json", lines=8)
        code_hidden = gr.Textbox(visible=False)
        lang_hidden = gr.Textbox(visible=False)
        fixed = gr.Code(label="Fixed Code", language="python", lines=14)
        diff = gr.Code(label="Diff (unified)", language="python", lines=10)
        info = gr.Markdown()
        btn_review.click(
            do_review,
            [code_in, lang, gh],
            [review_md, review_json, code_hidden, lang_hidden],
        )
        btn_fix.click(
            do_fix, [code_hidden, lang_hidden, gh, review_json], [fixed, diff, info]
        )

    with gr.Tab("Multi-File ZIP (Wow)"):
        gr.Markdown(
            "Upload ZIP with 4-5 files. Returns review + auto-fixed patched.zip + REPORT.md"
        )
        zip_in = gr.File(
            label="ZIP or files",
            file_count="multiple",
            file_types=[".zip", ".py", ".js", ".java", ".cpp", ".ts"],
        )
        zip_lang = gr.Dropdown(LANGS, value="python", label="Default language")
        zip_btn = gr.Button("Review & Fix All", variant="primary")
        zip_md = gr.Markdown()
        zip_json = gr.Code(label="Combined JSON", language="json", lines=10)
        zip_report = gr.Markdown()
        zip_out = gr.File(label="Download patched.zip")
        zip_btn.click(
            do_zip_review,
            [zip_in, zip_lang],
            [zip_md, zip_json, zip_report, zip_out, zip_report],
        )

    gr.Markdown(
        "**Setup:** Set `GEMINI_API_KEY` (free 500 RPD) and `NVIDIA_API_KEY` optionally as HF Space Secrets or `.env`. No keys = mock demo. | Repo: CodeLens AI | Built for GenAI Sprint"
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=int(os.getenv("PORT", "7860")))
