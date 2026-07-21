"""
Phase 1: Synthetic Data Generator for AIDA
===========================================
Generates a realistic quick-commerce dataset with:
  - 3 dark stores across a city
  - 15 suppliers
  - ~200 products across 8 categories
  - 90 days of hourly order history with promotion spikes
  - Inventory transactions (receipts, sales, adjustments)
  - Purchase orders to suppliers

Design decisions:
  - We inject REALISTIC NOISE: weekend bumps, rain-driven surges, promotion lift.
  - Order timestamps follow intraday patterns (morning coffee, evening snacks).
  - Inventory is decremented per sale so stockouts occur naturally.
  - Every sale writes an inventory_transaction row so the audit trail is complete.

Usage:
  pip install faker pandas numpy psycopg2-binary
  python generate_data.py --db postgresql://user:pass@localhost:5432/aida

  # Or for quick local dev without PostgreSQL:
  python generate_data.py --csv           # writes CSV files to ./synthetic_data/
"""

import argparse
import csv
import os
import random
import sys
from datetime import datetime, timedelta, date
from pathlib import Path

import numpy as np
from faker import Faker

fake = Faker("en_IN")  # Indian locale — realistic names, cities, addresses

# =============================================================================
# CONFIGURATION — tweak these to scale the dataset up or down
# =============================================================================
CONFIG = {
    "num_stores": 3,
    "num_suppliers": 15,
    "num_products": 200,
    "num_promotions": 8,
    "days_of_history": 90,               # how many days back to simulate
    "orders_per_store_per_day": (40, 80),  # min, max (poisson-distributed around mean)
    "items_per_order": (1, 6),           # min, max items per basket
    "stockout_threshold_pct": 0.05,      # ~5% of products will stock out at some point
    "promo_lift_factor": (2.0, 4.0),     # demand multiplier during promotion
    "weekend_lift": 1.3,                 # 30% more orders on Sat/Sun
    "rain_lift_days_pct": 0.10,          # 10% of days get a rain-surge boost
    "rain_lift_factor": 1.5,             # 50% more orders on rainy days
    "seed": 42,
}

random.seed(CONFIG["seed"])
np.random.seed(CONFIG["seed"])
Faker.seed(CONFIG["seed"])


# =============================================================================
# STEP 1: Generate dimension data
# =============================================================================

def generate_suppliers(num: int) -> list[dict]:
    categories = ["Dairy", "Bakery", "Beverages", "Snacks", "FMCG",
                  "Fruits & Vegetables", "Meat & Poultry", "Frozen Foods"]
    suppliers = []
    for i in range(1, num + 1):
        cat = random.choice(categories)
        suppliers.append({
            "supplier_id": i,
            "supplier_code": f"SUP-{cat[:3].upper()}-{i:04d}",
            "supplier_name": fake.company(),
            "category": cat,
            "contact_email": fake.company_email(),
            "contact_phone": f"+91-{random.randint(7000000000,9999999999)}",
            "sla_delivery_hours": random.choice([6, 12, 24, 48]),
            "payment_terms_days": random.choice([15, 30, 45, 60]),
            "is_active": True,
        })
    return suppliers


def generate_stores(num: int) -> list[dict]:
    cities_zones = [
        ("Bengaluru", ["Koramangala", "Indiranagar", "HSR Layout", "Whitefield", "JP Nagar"]),
        ("Mumbai",    ["Bandra", "Andheri", "Powai", "Lower Parel", "Juhu"]),
        ("Delhi",     ["Hauz Khas", "Lajpat Nagar", "Dwarka", "Rohini", "Karol Bagh"]),
    ]
    stores = []
    for i in range(1, num + 1):
        city = cities_zones[i - 1][0]
        zone = cities_zones[i - 1][1][i - 1]
        stores.append({
            "store_id": i,
            "store_code": f"DS-{city[:3].upper()}-{i:02d}",
            "store_name": f"Dark Store {zone}",
            "city": city,
            "zone": zone,
            "address": fake.address(),
            "area_sqft": random.randint(2000, 8000),
            "is_active": True,
            "opening_date": date(2024, random.randint(1, 6), random.randint(1, 28)),
        })
    return stores


PRODUCT_SPECS = {
    "Dairy": [
        ("Full Cream Milk 500ml", "Milk", "Amul", 22, 28, True, 7),
        ("Toned Milk 1L", "Milk", "Nandini", 38, 48, True, 5),
        ("Paneer 200g", "Paneer", "Amul", 55, 75, True, 10),
        ("Fresh Cream 250ml", "Cream", "Amul", 28, 38, True, 7),
        ("Yogurt Plain 400g", "Yogurt", "Milky Mist", 30, 40, True, 14),
        ("Cheese Slices 200g", "Cheese", "Amul", 65, 85, True, 30),
        ("Butter 100g", "Butter", "Amul", 42, 55, True, 30),
        ("Buttermilk 1L", "Buttermilk", "Nandini", 15, 20, True, 5),
    ],
    "Bakery": [
        ("White Bread 400g", "Bread", "Britannia", 25, 35, True, 3),
        ("Brown Bread 400g", "Bread", "Modern", 30, 42, True, 3),
        ("Pav 6pc", "Buns", "Local", 12, 18, True, 2),
        ("Burger Buns 4pc", "Buns", "Modern", 20, 30, True, 3),
        ("Croissant", "Pastry", "Local", 18, 28, True, 2),
    ],
    "Beverages": [
        ("Coca Cola 750ml", "Soft Drinks", "Coca Cola", 30, 40, False, None),
        ("Pepsi 750ml", "Soft Drinks", "PepsiCo", 30, 40, False, None),
        ("Red Bull 250ml", "Energy Drink", "Red Bull", 85, 115, False, None),
        ("Tender Coconut Water 500ml", "Health Drink", "Raw Pressery", 45, 60, True, 30),
        ("Tata Tea 250g", "Tea", "Tata", 110, 140, False, None),
        ("Nescafe Instant 100g", "Coffee", "Nestle", 150, 195, False, None),
        ("Mineral Water 1L", "Water", "Bisleri", 12, 20, False, None),
    ],
    "Snacks": [
        ("Lays Classic 50g", "Chips", "Lays", 15, 20, False, None),
        ("Kurkure 75g", "Chips", "Kurkure", 15, 20, False, None),
        ("Nuts Mix 200g", "Nuts", "Happilo", 120, 160, False, None),
        ("Instant Noodles 70g", "Noodles", "Maggi", 12, 16, False, None),
        ("Dark Chocolate 150g", "Chocolate", "Amul", 75, 99, False, None),
    ],
    "FMCG": [
        ("Dishwash Liquid 500ml", "Cleaning", "Vim", 95, 130, False, None),
        ("Detergent Powder 1kg", "Laundry", "Surf Excel", 140, 185, False, None),
        ("Handwash 250ml", "Personal Care", "Dettol", 55, 75, False, None),
        ("Toothpaste 200g", "Oral Care", "Colgate", 60, 80, False, None),
        ("Shampoo 200ml", "Hair Care", "Sunsilk", 90, 120, False, None),
    ],
    "Fruits & Vegetables": [
        ("Onion 1kg", "Vegetables", "Local", 20, 30, True, 7),
        ("Tomato 1kg", "Vegetables", "Local", 20, 32, True, 5),
        ("Potato 1kg", "Vegetables", "Local", 18, 26, True, 14),
        ("Banana 6pc", "Fruits", "Local", 18, 28, True, 5),
        ("Apple 4pc", "Fruits", "Local", 80, 110, True, 10),
        ("Grapes 500g", "Fruits", "Local", 40, 60, True, 4),
    ],
    "Meat & Poultry": [
        ("Chicken Breast 500g", "Chicken", "Suguna", 120, 165, True, 3),
        ("Chicken Curry Cut 1kg", "Chicken", "Suguna", 200, 265, True, 2),
        ("Eggs 12pc", "Eggs", "Suguna", 70, 90, True, 14),
        ("Fish Fillet 500g", "Fish", "Local", 180, 240, True, 2),
    ],
    "Frozen Foods": [
        ("Frozen Peas 500g", "Vegetables", "Safal", 45, 60, True, 90),
        ("Frozen Paratha 5pc", "Ready Meals", "ITC", 75, 100, True, 60),
        ("Ice Cream Tub 500ml", "Dessert", "Amul", 120, 160, True, 90),
        ("Frozen Chicken Nuggets 400g", "Ready Meals", "Venky's", 130, 175, True, 60),
    ],
}


def generate_products(suppliers: list[dict]) -> list[dict]:
    """Expand product specs into full rows, assigning suppliers intelligently."""
    supplier_by_cat = {}
    for s in suppliers:
        supplier_by_cat.setdefault(s["category"], []).append(s)

    products = []
    pid = 1
    for category, specs in PRODUCT_SPECS.items():
        for (name, subcat, brand, cost, price, perishable, shelf_life) in specs:
            # Pick a supplier in the same category, or any supplier if none match
            pool = supplier_by_cat.get(category, suppliers)
            supplier = random.choice(pool)

            sku = f"{category[:4].upper()}-{name.replace(' ', '-').upper()[:20]}"
            products.append({
                "product_id": pid,
                "sku": sku,
                "product_name": f"{brand} {name}",
                "category": category,
                "subcategory": subcat,
                "brand": brand,
                "unit_of_measure": "each",
                "unit_cost": cost,
                "selling_price": price,
                "supplier_id": supplier["supplier_id"],
                "lead_time_days": random.choice([1, 1, 2, 3]),
                "min_order_qty": random.choice([1, 1, 6, 12]),
                "is_perishable": perishable,
                "shelf_life_days": shelf_life,
            })
            pid += 1
    return products


def generate_promotions(num: int, products: list[dict], start_date: date, end_date: date
                        ) -> tuple[list[dict], list[dict]]:
    """Create promotions and assign products to them."""
    promo_types = [
        ("percentage_discount", "Flat {}% Off - {}", 10, 30),
        ("bogo", "Buy One Get One Free - {}", None, None),
        ("flat_off", "Rs.{} Off on {}", 20, 100),
        ("free_delivery", "Free Delivery on {}", None, None),
    ]
    day_range = (end_date - start_date).days
    promotions = []
    promo_prods = []

    for i in range(1, num + 1):
        ptype, label_tmpl, lo, hi = random.choice(promo_types)
        cat = random.choice(list(PRODUCT_SPECS.keys()))
        if lo is not None and hi is not None:
            val = random.randint(lo, hi)
            name = label_tmpl.format(val, cat)
        else:
            name = label_tmpl.format(cat if ptype == "bogo" else "")
            val = None

        s_offset = random.randint(0, day_range - 14)
        starts = datetime.combine(start_date + timedelta(days=s_offset), datetime.min.time())
        ends = starts + timedelta(days=random.randint(3, 10))
        pct = round(random.uniform(5, 40), 2) if ptype in ("percentage_discount",) else None

        promotions.append({
            "promotion_id": i,
            "promotion_name": name,
            "promotion_type": ptype,
            "discount_pct": pct,
            "starts_at": starts,
            "ends_at": ends,
            "is_active": True,
        })

        # assign 3-10 random products to this promotion
        assigned = random.sample(products, k=min(len(products), random.randint(3, 10)))
        for p in assigned:
            promo_prods.append({"promotion_id": i, "product_id": p["product_id"]})

    return promotions, promo_prods


# =============================================================================
# STEP 2: Generate transactional data over time
# =============================================================================

def _is_promotion_day(d: date, promos: list[dict]) -> list[dict]:
    """Return active promotions for a given date."""
    dt = datetime.combine(d, datetime.min.time())
    return [p for p in promos if p["starts_at"] <= dt <= p["ends_at"]]


def _order_rate_multiplier(d: date, active_promos: list[dict]) -> float:
    """Compute demand multiplier for a given day."""
    mult = 1.0
    # weekend lift
    if d.weekday() >= 5:  # Sat=5, Sun=6
        mult *= CONFIG["weekend_lift"]
    # rain lift (pseudo-random, seeded for reproducibility)
    if hash(f"rain-{d.isoformat()}") % 1000 < CONFIG["rain_lift_days_pct"] * 1000:
        mult *= CONFIG["rain_lift_factor"]
    # promotion lift
    if active_promos:
        mult *= random.uniform(*CONFIG["promo_lift_factor"])
    return mult


def generate_orders_and_transactions(
    stores: list[dict],
    products: list[dict],
    promos: list[dict],
    promo_prods: list[dict],
    start_date: date,
    end_date: date,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Walk day-by-day, store-by-store, generating orders with intraday patterns.
    Also maintain a running inventory per (store, product) and generate
    receipt transactions when stock hits the reorder point.
    """
    # Map promotion_id → set of product_ids
    promo_product_map: dict[int, set] = {}
    for pp in promo_prods:
        promo_product_map.setdefault(pp["promotion_id"], set()).add(pp["product_id"])

    # Initial inventory: seed each product with 2-4 weeks of stock
    inv: dict[tuple[int, int], int] = {}  # (store_id, product_id) → qty_on_hand
    reorder_point = 15
    reorder_qty = 60
    for store in stores:
        for prod in products:
            initial = random.randint(30, 120)
            inv[(store["store_id"], prod["product_id"])] = initial

    orders = []
    order_items = []
    transactions = []
    oid = 1
    oiid = 1
    tid = 1
    poiid = 1
    po_id = 1
    purchase_orders = []
    po_items = []

    d = start_date
    while d <= end_date:
        active_promos = _is_promotion_day(d, promos)
        base_rate = CONFIG["orders_per_store_per_day"]
        rate_mult = _order_rate_multiplier(d, active_promos)

        for store in stores:
            sid = store["store_id"]
            # Poisson-ish number of orders for this store today
            mean_orders = random.randint(*base_rate) * rate_mult
            n_orders = max(1, int(np.random.poisson(mean_orders)))

            for _ in range(n_orders):
                # Pick a random hour weighted toward peak times
                hour_weights = {
                    8: 3, 9: 5, 10: 4, 11: 3, 12: 3, 13: 4,
                    14: 2, 15: 2, 16: 3, 17: 4, 18: 5, 19: 6,
                    20: 5, 21: 4, 22: 3, 23: 1,
                    0: 0.2, 1: 0.1, 2: 0.1, 3: 0.1, 4: 0.2,
                    5: 0.5, 6: 1, 7: 2,
                }
                hours = list(hour_weights.keys())
                weights = list(hour_weights.values())
                hour = random.choices(hours, weights=weights, k=1)[0]
                minute = random.randint(0, 59)
                ts = datetime(d.year, d.month, d.day, hour, minute,
                              random.randint(0, 59))

                status_weights = [("delivered", 85), ("cancelled", 8), ("returned", 7)]
                status = random.choices(
                    [s[0] for s in status_weights],
                    weights=[s[1] for s in status_weights], k=1
                )[0]

                order_total = 0
                discount_total = 0
                items_in_order = []

                n_items = random.randint(*CONFIG["items_per_order"])
                # Pick random products, weighted toward popular ones
                chosen = random.choices(
                    products,
                    weights=[1.0 if p["category"] != "Frozen Foods" else 0.3
                             for p in products],
                    k=n_items,
                )

                # Determine if this order benefits from an active promotion
                applied_promo_id = None
                if active_promos:
                    promo = random.choice(active_promos)
                    promo_prods_set = promo_product_map.get(promo["promotion_id"], set())
                    # Apply only if at least one chosen product is covered
                    if any(c["product_id"] in promo_prods_set for c in chosen):
                        applied_promo_id = promo["promotion_id"]

                for prod in chosen:
                    pid = prod["product_id"]
                    qty = random.randint(1, 3)
                    price = prod["selling_price"]

                    # Check inventory — skip if no stock (stockout)
                    if inv.get((sid, pid), 0) < qty:
                        continue  # lost sale

                    # Decrement inventory
                    inv[(sid, pid)] -= qty

                    line_total = price * qty
                    items_in_order.append({
                        "order_item_id": oiid,
                        "order_id": oid,
                        "product_id": pid,
                        "quantity": qty,
                        "unit_price": price,
                        "line_total": line_total,
                    })

                    # Write sale transaction
                    transactions.append({
                        "transaction_id": tid,
                        "store_id": sid,
                        "product_id": pid,
                        "transaction_type": "sale",
                        "quantity": -qty,
                        "reference_type": "order",
                        "reference_id": oiid,
                        "unit_cost": prod["unit_cost"],
                        "running_qty": inv[(sid, pid)],
                        "notes": None,
                        "created_at": ts,
                    })
                    tid += 1
                    oiid += 1

                if not items_in_order:
                    continue  # skip empty orders (all items stocked out)

                order_total = sum(it["line_total"] for it in items_in_order)

                # Apply discount if promotion active
                if applied_promo_id:
                    promo = next(p for p in promos if p["promotion_id"] == applied_promo_id)
                    if promo["promotion_type"] == "percentage_discount":
                        discount_total = round(
                            order_total * (promo["discount_pct"] or 0) / 100, 2
                        )
                    elif promo["promotion_type"] == "flat_off":
                        discount_total = min(
                            random.randint(20, 100), order_total - 1
                        )
                    # bogo / free_delivery → no line-item discount
                    order_total -= discount_total

                delivered_ts = ts + timedelta(minutes=random.randint(15, 45)) \
                    if status == "delivered" else None

                orders.append({
                    "order_id": oid,
                    "store_id": sid,
                    "order_status": status,
                    "order_total": max(0, order_total),
                    "discount_total": discount_total,
                    "promotion_id": applied_promo_id,
                    "customer_zone": store["zone"],
                    "ordered_at": ts,
                    "delivered_at": delivered_ts,
                })
                order_items.extend(items_in_order)
                oid += 1

            # After each store-day: check if any product needs replenishment
            for prod in products:
                pid = prod["product_id"]
                curr = inv.get((sid, pid), 0)
                if curr <= reorder_point:
                    # Generate a receipt: supplier delivers ~reorder_qty units
                    delivered_qty = reorder_qty + random.randint(-10, 10)
                    delivered_qty = max(10, delivered_qty)
                    inv[(sid, pid)] += delivered_qty

                    receipt_ts = datetime(d.year, d.month, d.day, random.randint(8, 18),
                                         random.randint(0, 59)) + timedelta(hours=random.randint(1, 12))

                    # Create purchase order first
                    po = {
                        "po_id": po_id,
                        "supplier_id": prod["supplier_id"],
                        "store_id": sid,
                        "po_status": "received",
                        "ordered_at": receipt_ts - timedelta(hours=random.randint(6, 48)),
                        "expected_delivery": receipt_ts,
                        "received_at": receipt_ts,
                        "total_cost": round(delivered_qty * prod["unit_cost"], 2),
                    }
                    purchase_orders.append(po)
                    po_items.append({
                        "po_item_id": poiid,
                        "po_id": po_id,
                        "product_id": pid,
                        "quantity_ordered": delivered_qty + 5,
                        "quantity_received": delivered_qty,
                        "unit_cost": prod["unit_cost"],
                    })
                    poiid += 1
                    po_id += 1

                    # Receipt transaction
                    transactions.append({
                        "transaction_id": tid,
                        "store_id": sid,
                        "product_id": pid,
                        "transaction_type": "receipt",
                        "quantity": delivered_qty,
                        "reference_type": "purchase_order",
                        "reference_id": poiid - 1,
                        "unit_cost": prod["unit_cost"],
                        "running_qty": inv[(sid, pid)],
                        "notes": f"Auto-replenish: hit reorder point {reorder_point}",
                        "created_at": receipt_ts,
                    })
                    tid += 1

            # Add occasional stock adjustments (damage/wastage ~1% probability per product-month)
            if random.random() < 0.01:
                for prod in random.sample(products, k=random.randint(1, 5)):
                    pid = prod["product_id"]
                    wastage = random.randint(1, 5)
                    if inv.get((sid, pid), 0) >= wastage:
                        inv[(sid, pid)] -= wastage
                        transactions.append({
                            "transaction_id": tid,
                            "store_id": sid,
                            "product_id": pid,
                            "transaction_type": "adjustment",
                            "quantity": -wastage,
                            "reference_type": "manual",
                            "reference_id": None,
                            "unit_cost": prod["unit_cost"],
                            "running_qty": inv[(sid, pid)],
                            "notes": random.choice(["Damaged in storage", "Expired", "Missing"]),
                            "created_at": datetime(d.year, d.month, d.day, 22, 0, 0),
                        })
                        tid += 1

        d += timedelta(days=1)

    # Build final inventory_levels snapshot
    inventory_levels = []
    ilid = 1
    for (sid, pid), qty in inv.items():
        prod = next(p for p in products if p["product_id"] == pid)
        inventory_levels.append({
            "inventory_id": ilid,
            "store_id": sid,
            "product_id": pid,
            "qty_on_hand": qty,
            "qty_reserved": 0,
            "reorder_point": reorder_point,
            "reorder_qty": reorder_qty,
            "last_counted_at": end_date,
            "updated_at": datetime.combine(end_date, datetime.min.time()),
        })
        ilid += 1

    return (orders, order_items, transactions, inventory_levels,
            purchase_orders, po_items)


# =============================================================================
# STEP 3: Write output
# =============================================================================

def _dicts_to_csv(rows: list[dict], path: str, col_order: list[str]):
    """Write a list of dicts to CSV."""
    if not rows:
        print(f"  WARN empty -> skipping {path}")
        return
    # Infer columns from first row if not given
    cols = col_order if col_order else list(rows[0].keys())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  OK {path}  ({len(rows)} rows)")


def write_csvs(out_dir: str, **tables) -> None:
    """Write all generated tables as CSVs."""
    col_orders = {
        "suppliers": ["supplier_id", "supplier_code", "supplier_name", "category",
                       "contact_email", "contact_phone", "sla_delivery_hours",
                       "payment_terms_days", "is_active"],
        "stores": ["store_id", "store_code", "store_name", "city", "zone",
                    "address", "area_sqft", "is_active", "opening_date"],
        "products": ["product_id", "sku", "product_name", "category", "subcategory",
                      "brand", "unit_of_measure", "unit_cost", "selling_price",
                      "supplier_id", "lead_time_days", "min_order_qty",
                      "is_perishable", "shelf_life_days"],
        "promotions": ["promotion_id", "promotion_name", "promotion_type",
                        "discount_pct", "starts_at", "ends_at", "is_active"],
        "promotion_products": ["promotion_id", "product_id"],
        "inventory_levels": ["inventory_id", "store_id", "product_id",
                              "qty_on_hand", "qty_reserved",
                              "reorder_point", "reorder_qty",
                              "last_counted_at", "updated_at"],
        "inventory_transactions": ["transaction_id", "store_id", "product_id",
                                    "transaction_type", "quantity",
                                    "reference_type", "reference_id",
                                    "unit_cost", "running_qty", "notes",
                                    "created_at"],
        "orders": ["order_id", "store_id", "order_status", "order_total",
                    "discount_total", "promotion_id", "customer_zone",
                    "ordered_at", "delivered_at"],
        "order_items": ["order_item_id", "order_id", "product_id",
                         "quantity", "unit_price", "line_total", "created_at"],
        "purchase_orders": ["po_id", "supplier_id", "store_id", "po_status",
                             "ordered_at", "expected_delivery", "received_at",
                             "total_cost"],
        "purchase_order_items": ["po_item_id", "po_id", "product_id",
                                  "quantity_ordered", "quantity_received", "unit_cost"],
    }
    for name, rows in tables.items():
        cols = col_orders.get(name)
        _dicts_to_csv(rows, os.path.join(out_dir, f"{name}.csv"), cols)


def write_sql_inserts(out_dir: str, **tables) -> None:
    """Write PostgreSQL INSERT statements (for --db mode)."""
    path = os.path.join(out_dir, "seed_data.sql")
    lines = ["-- Auto-generated seed data for AIDA", f"-- Generated: {datetime.now()}", "", "BEGIN;", ""]

    for tname, rows in tables.items():
        if not rows:
            continue
        cols = list(rows[0].keys())
        col_str = ", ".join(cols)
        lines.append(f"-- {tname}")
        for row in rows:
            vals = []
            for c in cols:
                v = row[c]
                if v is None:
                    vals.append("NULL")
                elif isinstance(v, bool):
                    vals.append("TRUE" if v else "FALSE")
                elif isinstance(v, (int, float)):
                    vals.append(str(v))
                elif isinstance(v, datetime):
                    vals.append(f"'{v.isoformat()}'")
                elif isinstance(v, date):
                    vals.append(f"'{v.isoformat()}'")
                else:
                    escaped = str(v).replace("'", "''")
                    vals.append(f"'{escaped}'")
            lines.append(f"INSERT INTO {tname} ({col_str}) VALUES ({', '.join(vals)});")
        lines.append("")

    lines.append("COMMIT;")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  OK {path}  ({sum(1 for l in lines if l.startswith('INSERT'))} statements)")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Generate AIDA synthetic data")
    parser.add_argument("--csv", action="store_true", default=True,
                        help="Write output as CSV files (default)")
    parser.add_argument("--sql", action="store_true",
                        help="Also write SQL INSERT statements")
    parser.add_argument("--db", type=str, default=None,
                        help="PostgreSQL connection string (future: direct load)")
    parser.add_argument("--out", type=str,
                        default=str(Path(__file__).resolve().parent / "synthetic_data"),
                        help="Output directory for CSV/SQL files")
    args = parser.parse_args()

    print("=" * 60)
    print("AIDA — Synthetic Data Generator")
    print("=" * 60)
    print(f"Config: {CONFIG['num_stores']} stores, "
          f"{CONFIG['num_products']} products, "
          f"{CONFIG['num_suppliers']} suppliers")
    print(f"History: {CONFIG['days_of_history']} days "
          f"({CONFIG['orders_per_store_per_day'][0]}-{CONFIG['orders_per_store_per_day'][1]} "
          f"orders/store/day)")
    print()

    start_date = date.today() - timedelta(days=CONFIG["days_of_history"])
    end_date = date.today()

    print("Generating suppliers ...")
    suppliers = generate_suppliers(CONFIG["num_suppliers"])

    print("Generating stores ...")
    stores = generate_stores(CONFIG["num_stores"])

    print("Generating products ...")
    products = generate_products(suppliers)

    print("Generating promotions ...")
    promotions, promo_prods = generate_promotions(
        CONFIG["num_promotions"], products, start_date, end_date
    )

    print("Generating orders & transactions (this may take a minute) ...")
    orders, order_items, transactions, inventory_levels, pos, po_items = \
        generate_orders_and_transactions(
            stores, products, promotions, promo_prods, start_date, end_date
        )

    print(f"\nGenerated:")
    print(f"  {len(suppliers):>6} suppliers")
    print(f"  {len(stores):>6} stores")
    print(f"  {len(products):>6} products")
    print(f"  {len(promotions):>6} promotions ({len(promo_prods)} product assignments)")
    print(f"  {len(orders):>6} orders")
    print(f"  {len(order_items):>6} order line items")
    print(f"  {len(transactions):>6} inventory transactions")
    print(f"  {len(inventory_levels):>6} current inventory levels")
    print(f"  {len(pos):>6} purchase orders ({len(po_items)} line items)")
    print()

    tables = {
        "suppliers": suppliers,
        "stores": stores,
        "products": products,
        "promotions": promotions,
        "promotion_products": promo_prods,
        "inventory_levels": inventory_levels,
        "inventory_transactions": transactions,
        "orders": orders,
        "order_items": order_items,
        "purchase_orders": pos,
        "purchase_order_items": po_items,
    }

    print(f"Writing output to {args.out}/ ...")
    write_csvs(args.out, **tables)
    if args.sql:
        write_sql_inserts(args.out, **tables)

    print("\nDone!  Next step: load these CSVs into PostgreSQL or SQLite.")
    print("Tip: Use Schema Browser (Phase 2) to run analytical queries against this data.")


if __name__ == "__main__":
    main()
