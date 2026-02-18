import os
import glob
import yaml
from typing import List, Dict
from datetime import datetime

from src.csv_normalizer import (
    normalize_csv_with_errors,
    write_normalized_csv,
    write_errors_csv,
    NormalizedRow,
)
from src.aggregator import summarize_by_store, write_summary_csv, format_summary_for_slack
from src.web_checker import fetch_text, diff_and_update_snapshot, extract_price, diff_value_and_update_snapshot,extract_price_kv
from src.notifier import post_slack
from src.web_checker import extract_price, diff_value_and_update_snapshot


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"config.yaml is empty or invalid YAML: {path}")
    return data


def list_csv_files(input_dir: str) -> List[str]:
    patterns = [
        os.path.join(input_dir, "*.csv"),
        os.path.join(input_dir, "*.CSV"),
    ]
    files: List[str] = []
    for p in patterns:
        files.extend(glob.glob(p))
    return sorted(set(files))


def main() -> None:
    cfg = load_config("config.yaml")

    # ---- CSV: multi files ----
    input_dir = cfg["csv"]["input_dir"]
    files = list_csv_files(input_dir)
    if not files:
        raise FileNotFoundError(f"No CSV files found in: {input_dir}")

    all_rows: List[NormalizedRow] = []
    all_errors: List[Dict[str, str]] = []

    for path in files:
        rows, errors = normalize_csv_with_errors(path)

        # errors にファイル名を付与（実務で超大事）
        base = os.path.basename(path)
        for e in errors:
            e["file"] = base
        all_errors.extend(errors)
        all_rows.extend(rows)

    # errors.csv は file 列が増えたので、ここで並びを整える
    # write_errors_csv は fieldnames 固定だったので、file列込みの書き出しを簡易実装
    # （安全に動くために main 側で書く）
    errors_path = cfg["csv"]["errors_path"]
    os.makedirs(os.path.dirname(errors_path), exist_ok=True)
    import csv as _csv
    with open(errors_path, "w", newline="", encoding="utf-8") as f:
        writer = _csv.DictWriter(
            f,
            fieldnames=["file", "line", "reason", "raw_date", "raw_store", "raw_product", "raw_qty", "raw_price"],
        )
        writer.writeheader()
        writer.writerows(all_errors)

    normalized_path = cfg["csv"]["normalized_path"]
    summary_path = cfg["csv"]["summary_path"]

    os.makedirs(os.path.dirname(normalized_path), exist_ok=True)
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)

    write_normalized_csv(all_rows, normalized_path)

    summary = summarize_by_store(all_rows)
    write_summary_csv(summary, summary_path)

    print(f"[csv] files={len(files)} normalized={len(all_rows)} errors={len(all_errors)}")

    # ---- Web check + Slack ----
    url = cfg["web"]["url"]
    current = fetch_text(url)

    new_price = extract_price(current)

    price_changed, old_price = diff_value_and_update_snapshot(
        new_price,
        cfg["web"]["price_snapshot_path"]
    )

    changed, diff_preview = diff_and_update_snapshot(
        current,
        cfg["web"]["snapshot_path"],
        max_diff_lines=40,
    )

    # ① 価格が変わったとき：要約通知
    if price_changed and new_price:
        delta_text = ""
        try:
            if old_price:
                delta = int(new_price) - int(old_price)
                sign = "+" if delta >= 0 else ""
                delta_text = f"（{sign}{delta}円）"
        except Exception:
            pass

        summary_text = format_summary_for_slack(summary, top_n=5)
        msg = (
            f"🟠 価格が変更されました\n"
            f"URL: {url}\n"
            f"旧価格: {old_price or '（初回）'}円\n"
            f"新価格: {new_price}円 {delta_text}\n\n"
            f"{summary_text}\n\n"
            f"🧾 CSV取り込み結果: files={len(files)} / normalized={len(all_rows)} / errors={len(all_errors)}\n"
            f"（errorsの詳細: {errors_path}）"
        )
        post_slack(cfg["slack"]["webhook_url"], msg)

    # ② ページが変わったとき：diff通知（価格通知と二重にならない）
    elif changed:
        summary_text = format_summary_for_slack(summary, top_n=5)
        diff_block = f"```{diff_preview}```" if diff_preview else "（diffなし）"
        msg = (
            f"🟠 Webページに変更がありました\n"
            f"URL: {url}\n\n"
            f"{summary_text}\n\n"
            f"🧾 CSV取り込み結果: files={len(files)} / normalized={len(all_rows)} / errors={len(all_errors)}\n"
            f"（errorsの詳細: {errors_path}）\n\n"
            f"🧩 差分プレビュー（抜粋）\n"
            f"{diff_block}"
        )
        post_slack(cfg["slack"]["webhook_url"], msg)

    # ③ 何も変わってないとき：何もしない（落ちない）
    else:
        print("[web] no change detected -> slack skipped")


    from datetime import datetime

    # ---- GitHub RAW check + Slack ----
    gh_url = cfg["github"]["url"]
    gh_text = fetch_text(gh_url)
    gh_new_price = extract_price_kv(gh_text)

    value_path = cfg["github"]["value_snapshot_path"]
    prev_exists = os.path.exists(value_path)
    prev_value = ""

    if prev_exists:
        with open(value_path, "r", encoding="utf-8") as f:
            prev_value = f.read().strip()

    os.makedirs(os.path.dirname(value_path), exist_ok=True)
    with open(value_path, "w", encoding="utf-8") as f:
        f.write(gh_new_price)

    is_first = not prev_exists
    price_changed = (prev_value != gh_new_price) if prev_exists else True

    if (is_first or price_changed) and gh_new_price:
        delta_text = ""
        try:
            if prev_value:
                delta = int(gh_new_price) - int(prev_value)
                sign = "+" if delta >= 0 else ""
                delta_text = f"{sign}{delta:,}円"
        except Exception:
            pass

        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        msg = (
            "🔔【価格変更を検知しました】\n\n"
            "■ 監視対象\n"
            "GitHub RAW ファイル（watch_target.txt）\n\n"
            "■ 変更内容\n"
            f"旧価格：{prev_value or '（初回）'}円\n"
            f"新価格：{int(gh_new_price):,}円\n"
            f"差額：{delta_text or 'ー'}\n\n"
            f"■ 更新日時\n{now}\n\n"
            "■ 自動処理ステータス\n"
            "変更検知 → 差分抽出 → Slack通知 完了\n\n"
            "📊 CSV処理結果\n"
            f"・処理ファイル数：{len(files)}件\n"
            f"・正常データ：{len(all_rows)}件\n"
            f"・エラー：{len(all_errors)}件\n\n"
            "📌 本通知は自動監視システムにより送信されています"
        )

        post_slack(cfg["slack"]["webhook_url"], msg)


if __name__ == "__main__":
    main()