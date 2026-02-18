import csv
from collections import defaultdict
from typing import Dict, List
from .csv_normalizer import NormalizedRow
from typing import Optional


def summarize_by_store(rows: List[NormalizedRow]) -> List[Dict[str, str]]:
    total_amount = defaultdict(int)
    total_qty = defaultdict(int)

    for r in rows:
        total_amount[r.store] += r.amount
        total_qty[r.store] += r.qty

    summary = []
    for store in sorted(total_amount.keys()):
        summary.append(
            {
                "store": store,
                "total_qty": str(total_qty[store]),
                "total_amount": str(total_amount[store]),
            }
        )
    return summary


def write_summary_csv(summary: List[Dict[str, str]], output_path: str) -> None:
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["store", "total_qty", "total_amount"])
        writer.writeheader()
        writer.writerows(summary)


def format_summary_for_slack(summary: List[Dict[str, str]], top_n: int = 5) -> str:
    """
    summary.csv の内容をSlackで見やすいテキストにする
    """
    if not summary:
        return "（集計対象データなし）"

    # total_amount を数値として並び替え（降順）
    def amount_of(item: Dict[str, str]) -> int:
        try:
            return int(item.get("total_amount", "0"))
        except ValueError:
            return 0

    sorted_summary = sorted(summary, key=amount_of, reverse=True)[:top_n]

    lines = ["📊 店舗別サマリー（上位）"]
    for item in sorted_summary:
        store = item["store"]
        qty = item["total_qty"]
        amt = item["total_amount"]
        lines.append(f"- {store}: qty={qty}, amount={amt}")

    return "\n".join(lines)