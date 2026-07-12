#!/usr/bin/env python3
"""
大学通信オンライン (univ-online.com) のRSSフィードから
新着記事を取得し、Slackに投稿するスクリプト。

GitHub Actions から1日1回実行される想定。
「前回実行時より新しい記事」だけを送るために、
リポジトリ内の state.json に最終投稿日時を保存する。
"""

import os
import sys
import json
import datetime
import urllib.request
import xml.etree.ElementTree as ET

FEED_URL = "https://univ-online.com/feed/"
STATE_FILE = "state.json"
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

MAX_ITEMS = 10  # 1回の通知で送る最大件数（初回や大量更新時の暴走防止）


def fetch_feed(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (daily-news-bot)"})
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read()


def parse_items(xml_bytes: bytes):
    root = ET.fromstring(xml_bytes)
    items = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date_raw = (item.findtext("pubDate") or "").strip()
        pub_date = None
        if pub_date_raw:
            try:
                # RFC 822形式 例: "Mon, 01 Jan 2026 07:00:00 +0900"
                pub_date = datetime.datetime.strptime(
                    pub_date_raw, "%a, %d %b %Y %H:%M:%S %z"
                )
            except ValueError:
                pub_date = None
        items.append({"title": title, "link": link, "pub_date": pub_date, "pub_date_raw": pub_date_raw})
    return items


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_posted_iso": None}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def post_to_slack(new_items):
    if not SLACK_WEBHOOK_URL:
        print("SLACK_WEBHOOK_URL が設定されていません。Secretsを確認してください。", file=sys.stderr)
        sys.exit(1)

    if not new_items:
        text = "本日の新着記事はありませんでした。"
    else:
        lines = [f"*本日の大学ニュース（{len(new_items)}件）*"]
        for it in new_items:
            lines.append(f"• <{it['link']}|{it['title']}>")
        text = "\n".join(lines)

    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        SLACK_WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        body = res.read().decode("utf-8")
        if body != "ok":
            print(f"Slack応答が想定外です: {body}", file=sys.stderr)


def main():
    state = load_state()
    last_posted = None
    if state.get("last_posted_iso"):
        last_posted = datetime.datetime.fromisoformat(state["last_posted_iso"])

    xml_bytes = fetch_feed(FEED_URL)
    items = parse_items(xml_bytes)

    # pub_dateでソート（新しい順）
    items_with_date = [it for it in items if it["pub_date"] is not None]
    items_with_date.sort(key=lambda x: x["pub_date"], reverse=True)

    if last_posted is None:
        # 初回実行: 直近のものだけ送る（フィード全件送りを防ぐ）
        new_items = items_with_date[:5]
    else:
        new_items = [it for it in items_with_date if it["pub_date"] > last_posted]
        new_items = new_items[:MAX_ITEMS]

    post_to_slack(new_items)

    if items_with_date:
        newest = items_with_date[0]["pub_date"]
        state["last_posted_iso"] = newest.isoformat()
        save_state(state)


if __name__ == "__main__":
    main()
