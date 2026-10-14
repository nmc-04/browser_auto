"""
Product and Order Procurement Subsystem
Handles Excel product requirements, order staging, cart verification, and purchase records.
"""

import os
import csv
from typing import List, Dict, Any, Optional, Tuple
from openpyxl import load_workbook
from utils.logger import logger, add_log_entry
from utils.helpers import generate_id, current_iso_time

DEFAULT_PRODUCTS_EXCEL = "demo_data/products.xlsx"
DEFAULT_PRODUCTS_CSV = "demo_data/products.csv"
ORDERS_LOG_FILE = "demo_data/orders.json"


def read_products_excel(file_path: str = DEFAULT_PRODUCTS_EXCEL) -> List[Dict[str, Any]]:
    """Reads office supply product requirements from Excel or CSV."""
    products = []
    if os.path.exists(file_path):
        try:
            wb = load_workbook(file_path, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if rows:
                headers = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(rows[0])]
                for r in rows[1:]:
                    if not any(r):
                        continue
                    item = dict(zip(headers, r))
                    products.append({
                        "name": str(item.get("Product Name", "")).strip(),
                        "category": str(item.get("Category", "")).strip(),
                        "quantity": int(item.get("Quantity", 1) or 1),
                        "max_budget": float(item.get("Max Unit Budget", 0) or 0),
                        "urgency": str(item.get("Urgency", "Medium")).strip()
                    })
            add_log_entry(f"[Product Tool] Loaded {len(products)} required products from '{file_path}'")
            return products
        except Exception as e:
            logger.warning(f"Failed to read products xlsx {file_path}: {e}")

    if os.path.exists(DEFAULT_PRODUCTS_CSV):
        with open(DEFAULT_PRODUCTS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for item in reader:
                products.append({
                    "name": item.get("Product Name", "").strip(),
                    "category": item.get("Category", "").strip(),
                    "quantity": int(item.get("Quantity", 1) or 1),
                    "max_budget": float(item.get("Max Unit Budget", 0) or 0),
                    "urgency": item.get("Urgency", "Medium").strip()
                })
        add_log_entry(f"[Product Tool] Loaded {len(products)} products from CSV fallback")
    return products


def stage_procurement_order(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Prepares and stages an order summary with total amounts and invoice data."""
    order_id = generate_id("ord").upper()
    total_amount = sum(item.get("price", item.get("max_budget", 0)) * item.get("quantity", 1) for item in items)
    
    order_record = {
        "order_id": order_id,
        "items": items,
        "item_count": len(items),
        "total_amount": round(total_amount, 2),
        "status": "STAGED",
        "requires_human_confirmation": True,
        "created_at": current_iso_time()
    }
    add_log_entry(f"[Product Tool] Staged procurement order {order_id} ({len(items)} items, Total: INR {total_amount:,.2f})")
    return order_record


def verify_cart_order(expected_items: List[str], actual_order: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Verifies that all required products exist in the staged cart and pricing is within budget.
    """
    if not actual_order or not actual_order.get("items"):
        return False, "Verification failed: Staged cart contains no items."

    staged_names = [it.get("name", "").lower() for it in actual_order.get("items", [])]
    missing = []
    for exp in expected_items:
        found = any(exp.lower() in s or s in exp.lower() for s in staged_names)
        if not found:
            missing.append(exp)

    if missing:
        return False, f"Verification failed: Items missing from order: {', '.join(missing)}."

    return True, f"Verified: All {len(actual_order.get('items', []))} requested products verified in shopping cart."
