import html
import json
import os
import re
import sys
import urllib.parse
import requests


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


def main():
    api_url = os.environ.get("API_URL")
    if not api_url:
        sys.exit(1)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    response = requests.get(api_url, headers=headers, timeout=30)
    response.raise_for_status()

    raw_json = response.json()
    updated_json = process_data(raw_json)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(updated_json, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
