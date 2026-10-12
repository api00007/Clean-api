import html
import json
import os
import re
import shutil
import sys
import urllib.parse

OUTPUT_FILE = "api.json"


def clean_stream_url(raw_text):
    if not isinstance(raw_text, str) or not (
        "<iframe" in raw_text or "<div" in raw_text
    ):
        return raw_text

    text = html.unescape(raw_text)
    src_match = re.search(r'src=["\']([^"\']+)["\']', text)
    if not src_match:
        return raw_text
    url = src_match.group(1).strip()

    if "anym3u8player.com" in url or "player.php" in url:
        url_param_match = re.search(r"[?&]url=([^&]+)", url)
        if url_param_match:
            url = urllib.parse.unquote(url_param_match.group(1))

    play_param_match = re.search(r"[?&]play=(.+)$", url)
    if play_param_match:
        url = play_param_match.group(1).strip()

    k1_match = re.search(r"[&?]k1=([a-zA-Z0-9]+)", url)
    k2_match = re.search(r"[&?]k2=([a-zA-Z0-9]+)", url)

    if (".mpd" in url or "cenc" in url) and k1_match and k2_match:
        k1 = k1_match.group(1)
        k2 = k2_match.group(1)
        base_url = re.sub(r"[&?]k1=[^&]*", "", url)
        base_url = re.sub(r"[&?]k2=[^&]*", "", base_url)
        base_url = re.sub(r"[&?]$", "", base_url)
        url = f"{base_url}|drmScheme=clearkey&drmLicense={k1}:{k2}"

    return url


def process_data(item):
    if isinstance(item, dict):
        return {k: process_data(v) for k, v in item.items()}
    elif isinstance(item, list):
        return [process_data(v) for v in item]
    elif isinstance(item, str):
        return clean_stream_url(item)
    return item


def fetch_api_data(url):
    try:
        from curl_cffi import requests as cffi_requests

        res = cffi_requests.get(url, impersonate="chrome120", timeout=30)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(f"curl_cffi error: {e}", file=sys.stderr)

    try:
        import cloudscraper

        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "android", "desktop": False}
        )
        res = scraper.get(url, timeout=30)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(f"cloudscraper error: {e}", file=sys.stderr)

    try:
        import requests

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        res = requests.get(url, headers=headers, timeout=30)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(f"requests error: {e}", file=sys.stderr)

    return None


def push_to_github():
    github_token = os.getenv("GH_TOKEN")
    github_user = os.getenv("TGITHUB_USER")
    github_repo = os.getenv("TGITHUB_REPO")
    github_email = os.getenv("TGITHUB_EMAIL")

    if not github_token or not github_user or not github_repo:
        print("Missing required push secrets", file=sys.stderr)
        return

    temp_dir = "temp_external_repo"
    remote_url = f"https://{github_token}@github.com/{github_user}/{github_repo}.git"

    try:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

        clone_status = os.system(f"git clone {remote_url} {temp_dir}")
        if clone_status != 0:
            print("Git clone failed", file=sys.stderr)
            return

        shutil.copy(OUTPUT_FILE, os.path.join(temp_dir, OUTPUT_FILE))

        current_dir = os.getcwd()
        os.chdir(temp_dir)

        email_to_use = github_email if github_email else "action@github.com"
        os.system(f'git config user.email "{email_to_use}"')
        os.system(f'git config user.name "{github_user}"')
        os.system(f"git add {OUTPUT_FILE}")
        os.system(f'git commit -m "Auto Update: {OUTPUT_FILE}" || echo "No changes"')
        os.system("git pull --rebase origin main")
        push_status = os.system("git push origin main")

        os.chdir(current_dir)
        shutil.rmtree(temp_dir)

        if push_status != 0:
            print("Git push failed", file=sys.stderr)
    except Exception as e:
        print(f"Push failed: {e}", file=sys.stderr)


def main():
    api_url = os.getenv("API_URL")
    if not api_url:
        print("API_URL is missing from environment secrets", file=sys.stderr)
        sys.exit(1)

    raw_json = fetch_api_data(api_url)
    if not raw_json:
        print("Could not fetch API data", file=sys.stderr)
        sys.exit(1)

    updated_json = process_data(raw_json)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(updated_json, f, ensure_ascii=False, indent=2)

    push_to_github()


if __name__ == "__main__":
    main()
