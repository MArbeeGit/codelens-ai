import re, requests


def fetch_github(url):
    url = url.strip()
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)/blob/[^/]+/(.+)", url)
    if m:
        user, repo, path = m.groups()
        raw = f"https://raw.githubusercontent.com/{user}/{repo}/HEAD/{path}"
        r = requests.get(raw, timeout=10)
        if r.ok:
            return r.text, path
    m2 = re.match(r"https://github\.com/([^/]+)/([^/]+)/?$", url)
    if m2:
        raise ValueError("Repo URL: paste file URL (blob) or upload ZIP for multi-file")
    if url.startswith("https://raw.githubusercontent.com"):
        r = requests.get(url, timeout=10)
        if r.ok:
            return r.text, url.split("/")[-1]
    r = requests.get(url, timeout=10)
    if r.ok and len(r.text) < 200000:
        return r.text, "fetched"
    raise ValueError("Could not fetch GitHub file. Use raw link or paste code.")
