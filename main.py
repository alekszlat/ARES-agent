import re
import time
import requests
import sys
import webbrowser as web

from urllib.parse import quote_plus


def play_youtube_video(topic: str, timeout: int = 15) -> str:

    ### --------------------------------------------------------------------
    query = quote_plus(topic)
    search_url = f"https://www.youtube.com/results?search_query={query}"

    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(search_url, headers=headers, timeout=10)
    resp.raise_for_status()

    # Find first watch URL
    m = re.search(r'\"(/watch\?v=[^\"&]{11})', resp.text)
    if not m:
        raise Exception(f"No video found for topic: {topic!r}")

    watch_path = m.group(1)
    watch_url = f"https://www.youtube.com{watch_path}"

    ### --------------------------------------------------------------------


    try:
        web.open(watch_url, new=2)
        return watch_url
    except Exception as e:
        print(f"Error opening YouTube video: {e}", file=sys.stderr)
        return ""


if __name__ == "__main__":
    input_topic = input("Enter a topic to search on YouTube: ")
    topic = input_topic.strip()
    video_url = play_youtube_video(topic)
    print(f"Video URL: {video_url}")
