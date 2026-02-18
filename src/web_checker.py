import os
import requests
import difflib
import re
from typing import Tuple


def fetch_text(url: str) -> str:
    if url.startswith("file://"):
        path = url.replace("file://", "")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.text


def extract_price(html: str) -> str:
    m = re.search(r'id="price">(\d+)<', html)
    return m.group(1) if m else ""


def extract_price_kv(text: str) -> str:
    """
    price=1200 のような key=value 形式から価格を抜き出す
    """
    m = re.search(r"price\s*=\s*(\d+)", text)
    return m.group(1) if m else ""


def diff_value_and_update_snapshot(new_value: str, snapshot_path: str) -> Tuple[bool, str]:
    """
    return (changed, old_value)
    """
    old_value = ""
    if os.path.exists(snapshot_path):
        with open(snapshot_path, "r", encoding="utf-8") as f:
            old_value = f.read().strip()

    changed = (new_value != old_value)

    if changed:
        os.makedirs(os.path.dirname(snapshot_path), exist_ok=True)
        with open(snapshot_path, "w", encoding="utf-8") as f:
            f.write(new_value)

    return changed, old_value


def diff_and_update_snapshot(current: str, snapshot_path: str, max_diff_lines: int = 40) -> Tuple[bool, str]:
    """
    return (changed, diff_preview)
    - changed: True if content changed
    - diff_preview: unified diff preview (truncated)
    """
    old = ""
    if os.path.exists(snapshot_path):
        with open(snapshot_path, "r", encoding="utf-8") as f:
            old = f.read()

    changed = (current != old)
    if not changed:
        return False, ""

    # snapshot update
    os.makedirs(os.path.dirname(snapshot_path), exist_ok=True)
    with open(snapshot_path, "w", encoding="utf-8") as f:
        f.write(current)

    # diff（行単位）
    old_lines = old.splitlines()
    new_lines = current.splitlines()
    diff_lines = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="before",
            tofile="after",
            lineterm="",
            n=2,
        )
    )

    if not diff_lines:
        return True, "（差分は検出されたが、diff生成できませんでした）"

    # Slackに貼る用に短くする
    if len(diff_lines) > max_diff_lines:
        diff_lines = diff_lines[:max_diff_lines] + ["...（diffは省略しました）"]

    diff_preview = "\n".join(diff_lines)
    return True, diff_preview