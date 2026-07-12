[README.md](https://github.com/user-attachments/files/29935728/README.md)
# 大学ニュース → Slack 自動通知

「大学通信オンライン」(https://univ-online.com) のRSSフィードを毎日チェックし、
新着記事をSlackに自動投稿するGitHub Actionsです。

## セットアップ手順

### 1. GitHubリポジトリを作成する
1. GitHubで新規リポジトリを作成（**Public** でOK。無料・無制限で使えます）
2. このフォルダの中身（`fetch_and_notify.py` と `.github/workflows/daily-news.yml`）を
   そのリポジトリにアップロード（GitHub上の「Add file」→「Upload files」でドラッグ＆ドロップでOK）

### 2. Slack Incoming Webhook を発行する
1. https://api.slack.com/apps → 「Create New App」→「From scratch」
2. アプリ名を入力し、投稿したいワークスペースを選んで作成
3. 左メニュー「Incoming Webhooks」を **ON** にする
4. 「Add New Webhook to Workspace」→ 投稿先チャンネルを選択して許可
5. 発行された `https://hooks.slack.com/services/...` のURLをコピー

### 3. WebhookのURLをGitHub Secretsに登録する
1. リポジトリの「Settings」タブ →「Secrets and variables」→「Actions」
2. 「New repository secret」をクリック
3. Name: `SLACK_WEBHOOK_URL`
4. Secret: コピーしたWebhook URLを貼り付けて保存

### 4. 動作確認（手動実行）
1. リポジトリの「Actions」タブを開く
2. 「Daily University News to Slack」を選択
3. 右側の「Run workflow」ボタンで即座にテスト実行できる
4. Slackにメッセージが届けば成功

## 動作の仕組み
- 毎日 **朝7時（日本時間）** に自動実行されます（`.github/workflows/daily-news.yml` の cron設定）
- 前回実行以降の新着記事だけを送ります（`state.json` に最終投稿日時を記録）
- 初回実行時は直近5件を送信します
- 時刻を変更したい場合は `daily-news.yml` 内の `cron: "0 22 * * *"` を編集してください
  （UTC基準なので、日本時間からは9時間引いた値を指定します）

## 料金について
- Publicリポジトリなので GitHub Actions は完全無料・無制限です
- 実行時間も1回数十秒程度で、Slack送信のみなので追加コストは一切かかりません
