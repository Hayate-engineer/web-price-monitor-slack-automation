# 🔔 Web Price Monitor & Slack Automation

WebページやGitHub RAWファイルの価格変更を検知し、
Slackへ自動通知するPython製の自動監視ツールです。

---

## ✨ 主な機能

- Webページ価格変更検知
- GitHub RAWファイル監視
- CSV正規化・集計
- 差額自動計算
- Slack自動通知

---

## 🧠 技術スタック

- Python 3.11+
- requests
- pyyaml
- Slack Incoming Webhooks

---

## 🚀 Cursorでの起動手順

1. このリポジトリをClone
2. Cursorで開く
3. ターミナルで以下を実行：

```bash
python -m venv .venv
source .venv/bin/activate   # Mac
pip install -r requirements.txt
cp config.example.yaml config.yaml