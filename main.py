import html
import json
import os
import re
import shutil
import sys
import urllib.parse
from curl_cffi import requests

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


def push_to_github():
    github_token = os.getenv("GH_TOKEN")
    github_user = os.getenv("TGITHUB_USER")
    github_repo = os.getenv("TGITHUB_REPO")
    github_email = os.getenv("TGITHUB_EMAIL")

    if not github_token or not github_user or not github_repo:
        return

    temp_dir = "temp_external_repo"
    remote_url = f"https://{github_token}@github.com/{github_user}/{github_repo}.git"

    try:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

        clone_status = os.system(f"git clone {remote_url} {temp_dir}")
        if clone_status != 0:
            return

        shutil.copy(OUTPUT_FILE, os.path.join(temp_dir, OUTPUT_FILE))

        current_dir = os.getcwd()
        os.chdir(temp_dir)

        email_to_use = github_email if github_email else "action@github.com"
        os.system(f'git config user.email "{email_to_use}"')
        os.system(f'git config user.name "{github_user}"')
        os.system(f"git add {OUTPUT_FILE}")
        os.system(f'git commit -m "Auto Update: {OUTPUT_FILE}" || echo "No changes"')
        os.system("git push origin HEAD")

        os.chdir(current_dir)
        shutil.rmtree(temp_dir)
    except Exception:
        pass


def main():
    api_url = os.environ.get("API_URL")
    if not api_url:
        sys.exit(1)

    response = requests.get(api_url, impersonate="chrome120", timeout=30)

    if response.status_code != 200:
        sys.exit(1)

    raw_json = response.json()
    updated_json = process_data(raw_json)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(updated_json, f, ensure_ascii=False, indent=2)

    push_to_github()


if __name__ == "__main__":
    main()
