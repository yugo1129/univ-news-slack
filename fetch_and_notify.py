#!/usr/bin/env python3
"""
Googleニュースの検索RSS（全国の大学×AI関連ニュース）から
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
import urllib.parse
import xml.etree.ElementTree as ET

# 検索キーワード。ここを変えれば拾ってくるニュースの範囲を調整できる。
# 例: 「大学 (AI OR 人工知能 OR 生成AI)」
SEARCH_QUERY = "大学 (AI OR 人工知能 OR 生成AI)"

FEED_URL = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
    {"q": SEARCH_QUERY, "hl": "ja", "gl": "JP", "ceid": "JP:ja"}
)

STATE_FILE = "state.json"
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

MAX_ITEMS = 10  # 1回の通知で送る最大件数（初回や大量更新時の暴走防止）


def fetch_feed(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (daily-news-bot)",
            # サーバーがgzip等で圧縮して返してくると、そのままではXMLとして解析できないため
            # 非圧縮のレスポンスを明示的に要求する
            "Accept-Encoding": "identity",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read()


def _clean_xml_bytes(xml_bytes: bytes) -> bytes:
    """
    一部のWordPressサイトでは、RSSフィードの先頭にPHPの警告文や余分な
    改行・BOMなどが混入し、「<?xml ...?>」宣言が先頭に来ないことがある。
    その場合 ElementTree は
    "XML or text declaration not at start of entity" というエラーを出すため、
    実際のXML本体（<?xml から、または <rss / <feed タグから）が
    始まる位置を探して、それより前のゴミを読み飛ばす。
    """
    text = xml_bytes.decode("utf-8", errors="replace")

    candidates = []
    for marker in ("<?xml", "<rss", "<feed"):
        idx = text.find(marker)
        if idx != -1:
            candidates.append(idx)

    if candidates:
        start = min(candidates)
        if start > 0:
            print(f"警告: フィード先頭に{start}文字分の余分なデータがあったため読み飛ばしました。", file=sys.stderr)
        text = text[start:]

    return text.encode("utf-8")


def parse_items(xml_bytes: bytes):
    xml_bytes = _clean_xml_bytes(xml_bytes)
    root = ET.fromstring(xml_bytes)
    items = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        source = (item.findtext("source") or "").strip()  # Googleニュースの発行元名
        pub_date_raw = (item.findtext("pubDate") or "").strip()
        pub_date = None
        if pub_date_raw:
            # GoogleニュースのRSSは "Wed, 09 Jul 2026 03:00:00 GMT" のように
            # "GMT" 表記で終わることが多く、Pythonの %z はこれをそのままでは
            # 解釈できないため、"+0000" に置き換えてから解析する。
            normalized = pub_date_raw.replace("GMT", "+0000")
            try:
                pub_date = datetime.datetime.strptime(
                    normalized, "%a, %d %b %Y %H:%M:%S %z"
                )
            except ValueError:
                pub_date = None
        items.append({
            "title": title,
            "link": link,
            "source": source,
            "pub_date": pub_date,
            "pub_date_raw": pub_date_raw,
        })
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
        lines = [f"*本日の大学AIニュース（{len(new_items)}件）*"]
        for it in new_items:
            suffix = f"（{it['source']}）" if it.get("source") else ""
            lines.append(f"• <{it['link']}|{it['title']}>{suffix}")
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
