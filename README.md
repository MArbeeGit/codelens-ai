# CodeLens AI — Code Reviewer & Bug Fixing Agent

MVP for Generative AI Developer Intern Build Sprint (deadline 7 Sep 2026)

**Live Demo:** Deploy to HF Spaces -> `https://huggingface.co/spaces/<you>/codelens-ai` (Gradio)
**GitHub:** this repo

## Approach
Agentic loop: `Review (JSON)` -> `Fix (minimal diff)` -> `Local validator (ast/tree-sitter)` -> `retry x2 on syntax fail`. Saves tokens by 2-stage prompts, not rewriting whole file. Demo works multi-file (4-5 file ZIP) via per-file loop.

## Tech
- UI: Gradio 4 on HF Spaces
- LLM Router v2: `gemini-3.5-flash-lite (15 RPM/500 RPD primary)` -> `nvidia nemotron-3-nano-omni` fallback + `hash(code)->cache` (0 RPD) + exponential backoff on 429
- Validator: `ast.parse` / brace check (free, 0 tokens)
- No paid APIs

## Run Local
```
pip install -r requirements.txt
cp .env.example .env  # set GEMINI_API_KEY (free) and NVIDIA_API_KEY optional
python app.py  # http://localhost:7860
```
Without keys runs in mock mode.

## Features
- Single file: paste / GitHub raw fetch, severity table, diff viewer, copy fix
- Multi-file: ZIP upload, aggregated report
- Agentic fix retry validated locally

## Deploy HF
1. Create Space `Gradio` SDK
2. Add Secrets `GEMINI_API_KEY`, `NVIDIA_API_KEY`
3. Push app.py + core/ + requirements.txt

## Structure
`app.py` `core/llm_router.py` `core/reviewer.py` `core/fixer.py` `core/validator.py` `core/github_loader.py`
