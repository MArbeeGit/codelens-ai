import os, json, hashlib, time, requests

CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", ".cache.json")
_cache = {}
try:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            _cache = json.load(f)
except:
    _cache = {}


def _save_cache():
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(_cache, f)
    except:
        pass


def _hash(prompt, model):
    return hashlib.sha256(f"{model}::{prompt}".encode()).hexdigest()[:16]


def _call_gemini(prompt, model, api_key, retries=2):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 3000},
    }
    for i in range(retries + 1):
        try:
            r = requests.post(url, json=payload, timeout=30)
            if r.status_code == 429:
                time.sleep(1 * (2**i))
                continue
            r.raise_for_status()
            j = r.json()
            txt = j["candidates"][0]["content"]["parts"][0]["text"]
            return txt
        except Exception as e:
            if i == retries:
                raise e
            time.sleep(1 * (2**i))
    raise RuntimeError("gemini failed")


def _call_nvidia(prompt, api_key, model="meta/llama-3.1-70b-instruct"):
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 3000,
    }
    for i in range(3):
        r = requests.post(url, json=payload, headers=headers, timeout=40)
        if r.status_code == 429:
            time.sleep(1 * (2**i))
            continue
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    raise RuntimeError("nvidia 429")


def generate(prompt, use_cache=True):
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    nvidia_key = os.getenv("NVIDIA_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    nvidia_model = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")

    h = _hash(prompt, model)
    if use_cache and h in _cache:
        return _cache[h], True, "cache"

    last_err = None
    if gemini_key:
        try:
            out = _call_gemini(prompt, model, gemini_key)
            _cache[h] = out
            _save_cache()
            return out, False, model
        except Exception as e:
            last_err = str(e)

    if nvidia_key:
        try:
            h2 = _hash(prompt, nvidia_model)
            if use_cache and h2 in _cache:
                return _cache[h2], True, "cache"
            out = _call_nvidia(prompt, nvidia_key, nvidia_model)
            _cache[h2] = out
            _save_cache()
            return out, False, nvidia_model
        except Exception as e:
            last_err = str(e)

    if last_err:
        raise RuntimeError(f"All LLMs failed: {last_err}")
    raise RuntimeError(
        "No API key set. Set GEMINI_API_KEY or NVIDIA_API_KEY. Demo mode will use mock."
    )
