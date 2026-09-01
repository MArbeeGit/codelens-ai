import os, json, zipfile, tempfile, difflib

os.environ.setdefault("GEMINI_MODEL", "gemini-3.5-flash-lite")
try:
    import streamlit as st

    if hasattr(st, "secrets"):
        for k in ["GEMINI_API_KEY", "GEMINI_MODEL", "NVIDIA_API_KEY", "NVIDIA_MODEL"]:
            if k in st.secrets:
                os.environ[k] = str(st.secrets[k])
except:
    pass
from dotenv import load_dotenv

load_dotenv(override=True)
import streamlit as st
from core.reviewer import review_code
from core.fixer import fix_code
from core.github_loader import fetch_github

st.set_page_config(page_title="CodeLens AI", layout="wide")
st.title("🔍 CodeLens AI — Reviewer & Bug Fixer")
st.caption(
    "Free-API: gemini-3.5-flash-lite (500 RPD) → cache + agentic retry | GitHub: MArbeeGit/codelens-ai"
)

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


with st.sidebar:
    st.header("Settings")
    lang = st.selectbox("Language", LANGS, index=0)
    gh = st.text_input(
        "GitHub file URL (optional)",
        placeholder="https://github.com/.../blob/main/file.py",
    )

tab1, tab2 = st.tabs(["Single File", "Multi-File ZIP"])
with tab1:
    code = st.text_area("Code", height=280, placeholder="paste code here")
    c1, c2 = st.columns(2)
    with c1:
        do_review = st.button("1. Review", type="primary", use_container_width=True)
    with c2:
        do_fix = st.button("2. Fix (agentic retry)", use_container_width=True)
    if do_review:
        c = code
        l = lang
        if gh.strip():
            try:
                c, fn = fetch_github(gh)
                l = fn.split(".")[-1] if "." in fn else l
                st.info(f"Fetched {fn}")
            except Exception as e:
                st.error(f"Fetch error: {e}")
                c = ""
        if not c.strip():
            st.warning("Paste code or GitHub URL")
        else:
            with st.spinner("Reviewing..."):
                j, _ = review_code(c, l)
                st.session_state["review"] = j
                st.session_state["code"] = c
                st.session_state["lang"] = l
                st.subheader(
                    f"Summary ({j.get('_model', '')}{' cached' if j.get('_cached') else ''})"
                )
                st.write(j.get("summary", ""))
                st.write(f"**Complexity:** {j.get('complexity', '-')}")
                bugs = j.get("bugs", [])
                if bugs:
                    st.table(bugs)
                else:
                    st.success("No bugs found")
                st.json(j)
    if do_fix:
        if "review" not in st.session_state:
            st.warning("Run Review first")
        else:
            with st.spinner("Fixing..."):
                res, _ = fix_code(
                    st.session_state["code"],
                    st.session_state["review"],
                    st.session_state["lang"],
                )
                fc = res.get("fixed_code", "")
                diff = res.get("diff", "") or make_diff(st.session_state["code"], fc)
                st.session_state["fixed"] = fc
                st.code(fc, language=st.session_state["lang"])
                st.code(diff, language="diff")
                st.info(
                    f"Model: {res.get('_model', '')} | Valid: {res.get('_valid')} {res.get('_validator_msg', '')} | {res.get('explanation', '')}"
                )
                st.download_button("Download fixed", fc, file_name="fixed.txt")

with tab2:
    st.write(
        "Upload ZIP with 4-5 code files — reviews each + creates patched.zip + REPORT.md"
    )
    ups = st.file_uploader(
        "ZIP or files",
        type=["zip", "py", "js", "java", "cpp", "ts"],
        accept_multiple_files=True,
    )
    zip_lang = st.selectbox("Default language", LANGS, index=0, key="zip_lang")
    if st.button("Review & Fix All", type="primary"):
        if not ups:
            st.warning("Upload ZIP")
        else:
            # call core directly
            out_md = ""
            combined = {}
            patched = {}
            report = "# CodeLens Report\n\n"
            for up in ups:
                if up.name.endswith(".zip"):
                    with zipfile.ZipFile(up) as z:
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
                            }.get(l, zip_lang)
                            j, _ = review_code(code, mp)
                            out_md += f"**{name}** ({mp}) — {len(j.get('bugs', []))} issues | {j.get('summary', '')[:80]}\n\n"
                            report += f"## {name} — {len(j.get('bugs', []))} issues\n{j.get('summary', '')}\n\n"
                            combined[name] = j
                            try:
                                fix, _ = fix_code(code, j, mp)
                                patched[name] = fix.get("fixed_code", code)
                            except:
                                patched[name] = code
                else:
                    code = up.getvalue().decode(errors="ignore")[:6000]
                    j, _ = review_code(code, zip_lang)
                    out_md += f"**{up.name}** — {len(j.get('bugs', []))} issues\n\n"
                    combined[up.name] = j
                    try:
                        fix, _ = fix_code(code, j, zip_lang)
                        patched[up.name] = fix.get("fixed_code", code)
                    except:
                        patched[up.name] = code
            st.markdown(out_md or "No code files")
            st.json(combined)
            st.markdown(report)
            if patched:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
                with zipfile.ZipFile(tmp.name, "w") as z:
                    for n, c in patched.items():
                        z.writestr(n, c)
                    z.writestr("REPORT.md", report)
                with open(tmp.name, "rb") as f:
                    st.download_button(
                        "Download patched.zip", f, file_name="patched.zip"
                    )
                st.download_button("Download REPORT.md", report, file_name="REPORT.md")
