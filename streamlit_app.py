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
st.caption("AI-powered code review & agentic bug fixer — paste, import, or upload")

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
    st.header("⚙️ Settings")
    st.write("Choose language for accurate analysis")
    side_lang = st.selectbox("Language", LANGS, index=0)
    st.divider()
    with st.expander("ℹ️ About"):
        st.write(
            "Built for GenAI Build Sprint. Uses LLM + local validator + agentic retry. GitHub: MArbeeGit/codelens-ai"
        )
        st.write("Free tier with caching & rate-limit handling.")

tab1, tab2, tab3 = st.tabs(["📝 Paste Code", "🔗 GitHub Import", "📦 Multi-File ZIP"])

with tab1:
    st.info(
        "**How to use:** 1. Paste your code below → 2. Click **Review** to find bugs → 3. Click **Fix** to get patched code with diff"
    )
    code = st.text_area(
        "Code",
        height=280,
        placeholder="def add(a,b):\n    return a+b\nx = eval(input())",
        key="code_paste",
    )
    c1, c2 = st.columns(2)
    with c1:
        do_review = st.button(
            "1. Review", type="primary", use_container_width=True, key="rev1"
        )
    with c2:
        do_fix = st.button(
            "2. Fix (agentic retry)", use_container_width=True, key="fix1"
        )
    if do_review:
        c = code
        l = side_lang
        if not c.strip():
            st.warning("⚠️ Paste code first")
        else:
            status = st.status("🔍 Reviewing...", expanded=True)
            try:
                j, _ = review_code(c, l)
                status.update(
                    label=f"✅ Reviewed — {len(j.get('bugs', []))} issue(s) found",
                    state="complete",
                )
                st.session_state["review"] = j
                st.session_state["code"] = c
                st.session_state["lang"] = l
                st.divider()
                st.subheader("Summary")
                st.write(j.get("summary", ""))
                st.write(f"**Complexity:** {j.get('complexity', '-')}")
                bugs = j.get("bugs", [])
                if bugs:
                    st.dataframe(bugs, use_container_width=True)
                    st.success(f"Found {len(bugs)} issue(s) — now click Fix")
                else:
                    st.success("✅ No bugs found")
                with st.expander("Show technical details", expanded=False):
                    st.json(j)
            except Exception as e:
                status.update(label="❌ Review failed", state="error")
                st.error(str(e))
    if do_fix:
        if "review" not in st.session_state:
            st.warning("⚠️ Run **1. Review** first")
        else:
            status = st.status("🔧 Fixing...", expanded=True)
            try:
                res, _ = fix_code(
                    st.session_state["code"],
                    st.session_state["review"],
                    st.session_state["lang"],
                )
                fc = res.get("fixed_code", "")
                diff = res.get("diff", "") or make_diff(st.session_state["code"], fc)
                status.update(
                    label=f"✅ Fixed — Valid: {res.get('_valid')}", state="complete"
                )
                st.subheader("Fixed Code")
                st.code(fc, language=st.session_state["lang"])
                st.subheader("Diff")
                st.code(diff, language="diff")
                st.info(res.get("explanation", ""))
                st.download_button("⬇️ Download fixed", fc, file_name="fixed.txt")
            except Exception as e:
                status.update(label="❌ Fix failed", state="error")
                st.error(str(e))

with tab2:
    st.info(
        "**How to use:** 1. Copy a GitHub **file** URL (…/blob/main/path/file.py) → 2. Paste below → 3. Click **Fetch & Review** → 4. **Fix** if needed"
    )
    st.write(
        "Example: `https://github.com/MArbeeGit/codelens-ai/blob/main/core/validator.py`"
    )
    gh = st.text_input(
        "GitHub file URL",
        placeholder="https://github.com/user/repo/blob/main/file.py",
        key="gh_url",
    )
    g1, g2 = st.columns(2)
    with g1:
        do_gh_review = st.button(
            "Fetch & Review", type="primary", use_container_width=True, key="gh_rev"
        )
    with g2:
        do_gh_fix = st.button(
            "Fix fetched file", use_container_width=True, key="gh_fix"
        )
    if do_gh_review:
        if not gh.strip():
            st.warning("Paste a GitHub file URL")
        elif "github.com" not in gh or "/blob/" not in gh:
            st.error(
                "❌ Paste a file URL with /blob/ — e.g. .../blob/main/file.py. For entire repo, use Multi-File ZIP tab."
            )
        else:
            status = st.status("📥 Fetching & reviewing...", expanded=True)
            try:
                c, fn = fetch_github(gh)
                l = fn.split(".")[-1] if "." in fn else side_lang
                mp = {
                    "py": "python",
                    "js": "javascript",
                    "java": "java",
                    "cpp": "cpp",
                    "ts": "typescript",
                }.get(l, side_lang)
                st.info(f"Fetched `{fn}` ({len(c)} chars) — detected `{mp}`")
                j, _ = review_code(c, mp)
                status.update(label=f"✅ Reviewed {fn}", state="complete")
                st.session_state["gh_code"] = c
                st.session_state["gh_lang"] = mp
                st.session_state["gh_review"] = j
                st.subheader("Summary")
                st.write(j.get("summary", ""))
                bugs = j.get("bugs", [])
                if bugs:
                    st.dataframe(bugs, use_container_width=True)
                else:
                    st.success("✅ No bugs found")
                with st.expander("Show code", expanded=False):
                    st.code(c, language=mp)
                with st.expander("Show technical details", expanded=False):
                    st.json(j)
            except Exception as e:
                status.update(label="❌ Failed", state="error")
                st.error(str(e))
    if do_gh_fix:
        if "gh_review" not in st.session_state:
            st.warning("Fetch & Review first")
        else:
            status = st.status("🔧 Fixing...", expanded=True)
            try:
                res, _ = fix_code(
                    st.session_state["gh_code"],
                    st.session_state["gh_review"],
                    st.session_state["gh_lang"],
                )
                fc = res.get("fixed_code", "")
                diff = res.get("diff", "") or make_diff(st.session_state["gh_code"], fc)
                status.update(label="✅ Fixed", state="complete")
                st.code(fc, language=st.session_state["gh_lang"])
                st.code(diff, language="diff")
                st.download_button(
                    "⬇️ Download fixed", fc, file_name="fixed.txt", key="dl_gh"
                )
            except Exception as e:
                status.update(label="❌ Fix failed", state="error")
                st.error(str(e))

with tab3:
    st.info(
        "**How to use:** 1. Create a ZIP with 4-5 code files (.py/.js/.java/.cpp/.ts) → 2. Upload → 3. Click **Review & Fix All** → 4. Download `patched.zip` + `REPORT.md`"
    )
    ups = st.file_uploader(
        "ZIP or files",
        type=["zip", "py", "js", "java", "cpp", "ts"],
        accept_multiple_files=True,
    )
    zip_lang = st.selectbox(
        "Default language (for unknown extensions)", LANGS, index=0, key="zip_lang"
    )
    if st.button("Review & Fix All", type="primary", use_container_width=True):
        if not ups:
            st.warning("Upload a ZIP or code files")
        else:
            status = st.status("📦 Reviewing all files...", expanded=True)
            try:
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
                                    for e in [
                                        "py",
                                        "js",
                                        "java",
                                        "cpp",
                                        "ts",
                                        "go",
                                        "c",
                                    ]
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
                status.update(
                    label=f"✅ Reviewed {len(combined)} file(s)", state="complete"
                )
                st.markdown(out_md or "No code files")
                with st.expander("Show technical details", expanded=False):
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
                            "⬇️ Download patched.zip", f, file_name="patched.zip"
                        )
                    st.download_button(
                        "⬇️ Download REPORT.md", report, file_name="REPORT.md"
                    )
            except Exception as e:
                status.update(label="❌ Failed", state="error")
                st.error(str(e))
