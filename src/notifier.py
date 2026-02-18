import requests


def post_slack(webhook_url: str, text: str) -> None:
    webhook_url = (webhook_url or "").strip()
    if not webhook_url:
        print("[slack] webhook_url is empty -> skipped")
        return

    r = requests.post(webhook_url, json={"text": text}, timeout=10)
    r.raise_for_status()