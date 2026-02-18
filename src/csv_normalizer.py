import csv
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple, Dict


@dataclass
class NormalizedRow:
    date: str        # YYYY-MM-DD
    store: str       # normalized key
    product: str
    qty: int
    price: int       # unit price
    amount: int      # qty * price


def _get_any(r: dict, keys: List[str]) -> str:
    for k in keys:
        v = r.get(k)
        if v is not None:
            return v
    return ""


def _parse_date(value: str) -> Optional[str]:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _to_int(value: str) -> Optional[int]:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _normalize_store(value: str) -> str:
    v = (value or "").strip().lower()
    v = v.replace(" ", "_")
    return v


def normalize_csv_with_errors(input_path: str) -> Tuple[List[NormalizedRow], List[Dict[str, str]]]:
    """
    returns (normalized_rows, errors)
    errors: list of dicts for writing errors.csv
    """
    rows: List[NormalizedRow] = []
    errors: List[Dict[str, str]] = []

    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, r in enumerate(reader, start=2):  # header is line 1
            raw_date = _get_any(r, ["date", "日付"])
            raw_store = _get_any(r, ["store", "店舗", "店舗名", "shop"])
            raw_product = _get_any(r, ["product", "商品", "商品名"])
            raw_qty = _get_any(r, ["qty", "数量", "個数"])
            raw_price = _get_any(r, ["price", "単価", "金額", "価格"])

            date = _parse_date(raw_date)
            store = _normalize_store(raw_store)
            product = (raw_product or "").strip()
            qty = _to_int(raw_qty)
            price = _to_int(raw_price)

            reasons = []
            if not date:
                reasons.append("invalid_date")
            if not store:
                reasons.append("empty_store")
            if not product:
                reasons.append("empty_product")
            if qty is None:
                reasons.append("invalid_qty")
            if price is None:
                reasons.append("invalid_price")

            if reasons:
                errors.append(
                    {
                        "line": str(i),
                        "reason": "|".join(reasons),
                        "raw_date": (raw_date or "").strip(),
                        "raw_store": (raw_store or "").strip(),
                        "raw_product": (raw_product or "").strip(),
                        "raw_qty": (raw_qty or "").strip(),
                        "raw_price": (raw_price or "").strip(),
                    }
                )
                continue

            amount = qty * price
            rows.append(NormalizedRow(date, store, product, qty, price, amount))

    return rows, errors


def write_normalized_csv(rows: List[NormalizedRow], output_path: str) -> None:
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "store", "product", "qty", "price", "amount"])
        for r in rows:
            writer.writerow([r.date, r.store, r.product, r.qty, r.price, r.amount])


def write_errors_csv(errors: List[Dict[str, str]], output_path: str) -> None:
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["line", "reason", "raw_date", "raw_store", "raw_product", "raw_qty", "raw_price"],
        )
        writer.writeheader()
        writer.writerows(errors)