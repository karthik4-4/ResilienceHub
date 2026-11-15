"""
Database seeder from CSV files.
Populates items, sites, inventory, suppliers, lanes, contacts, and cost rates.
"""

import csv
import os
from pathlib import Path
from typing import Optional

from scdrc.data.db import get_connection, init_db


def seed_database(db_path: Optional[str] = None, seed_dir: Optional[str] = None) -> None:
    """Populate database with CSV seed files."""
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()

    base_dir = Path(seed_dir) if seed_dir else Path("./data/seed")

    # 1. Items
    items_file = base_dir / "items.csv"
    if items_file.exists():
        with open(items_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO items (sku, name, category, unit, unit_cost_inr, criticality, standard_order_qty, min_safety_stock)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["sku"],
                        row["name"],
                        row["category"],
                        row["unit"],
                        float(row["unit_cost_inr"]),
                        row["criticality"],
                        int(row["standard_order_qty"]),
                        int(row["min_safety_stock"]),
                    ),
                )

    # 2. Sites
    sites_file = base_dir / "sites.csv"
    if sites_file.exists():
        with open(sites_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO sites (site_id, name, role, city, state, country, capacity_units)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["site_id"],
                        row["name"],
                        row["role"],
                        row["city"],
                        row["state"],
                        row["country"],
                        int(row["capacity_units"]),
                    ),
                )

    # 3. Inventory
    inv_file = base_dir / "inventory.csv"
    if inv_file.exists():
        with open(inv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO inventory (sku, site_id, on_hand, safety_stock, daily_demand, reorder_point)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["sku"],
                        row["site_id"],
                        int(row["on_hand"]),
                        int(row["safety_stock"]),
                        float(row["daily_demand"]),
                        int(row["reorder_point"]),
                    ),
                )

    # 4. In Transit
    in_transit_file = base_dir / "in_transit.csv"
    if in_transit_file.exists():
        with open(in_transit_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO in_transit (shipment_id, sku, origin, dest, qty, mode, eta_days, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["shipment_id"],
                        row["sku"],
                        row["origin"],
                        row["dest"],
                        int(row["qty"]),
                        row["mode"],
                        int(row["eta_days"]),
                        row["status"],
                    ),
                )

    # 5. Suppliers
    supp_file = base_dir / "suppliers.csv"
    if supp_file.exists():
        with open(supp_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO suppliers (supplier_id, name, location, country, reliability_score, payment_terms, status, contact_person, email, phone)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["supplier_id"],
                        row["name"],
                        row["location"],
                        row["country"],
                        float(row["reliability_score"]),
                        row["payment_terms"],
                        row["status"],
                        row.get("contact_person"),
                        row.get("email"),
                        row.get("phone"),
                    ),
                )

    # 6. Supplier Items
    supp_items_file = base_dir / "supplier_items.csv"
    if supp_items_file.exists():
        with open(supp_items_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO supplier_items (supplier_id, sku, unit_price_inr, moq, standard_lead_time_days, expedite_lead_time_days, max_capacity, is_primary, is_qualified, contract_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["supplier_id"],
                        row["sku"],
                        float(row["unit_price_inr"]),
                        int(row["moq"]),
                        int(row["standard_lead_time_days"]),
                        int(row["expedite_lead_time_days"]),
                        int(row["max_capacity"]),
                        int(row["is_primary"]),
                        int(row["is_qualified"]),
                        row.get("contract_id"),
                    ),
                )

    # 7. Lanes
    lanes_file = base_dir / "lanes.csv"
    if lanes_file.exists():
        with open(lanes_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO lanes (lane_id, origin, dest, mode, base_transit_days, base_freight_inr_per_unit, capacity_units, risk_rating, primary_carrier)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["lane_id"],
                        row["origin"],
                        row["dest"],
                        row["mode"],
                        int(row["base_transit_days"]),
                        float(row["base_freight_inr_per_unit"]),
                        int(row["capacity_units"]),
                        row["risk_rating"],
                        row.get("primary_carrier"),
                    ),
                )

    # 8. Contacts
    contacts_file = base_dir / "contacts.csv"
    if contacts_file.exists():
        with open(contacts_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO contacts (contact_id, name, role, site_id, email, phone, slack_handle)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["contact_id"],
                        row["name"],
                        row["role"],
                        row.get("site_id"),
                        row["email"],
                        row.get("phone"),
                        row.get("slack_handle"),
                    ),
                )

    # 9. Cost Rates
    cost_file = base_dir / "cost_rates.csv"
    if cost_file.exists():
        with open(cost_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO cost_rates (category, annual_holding_cost_rate, daily_holding_factor, stockout_penalty_per_unit_day, air_expedite_premium_rate, handling_charge_inr)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["category"],
                        float(row["annual_holding_cost_rate"]),
                        float(row["daily_holding_factor"]),
                        float(row["stockout_penalty_per_unit_day"]),
                        float(row["air_expedite_premium_rate"]),
                        float(row["handling_charge_inr"]),
                    ),
                )

    conn.commit()
    conn.close()
    print("Database seeding completed successfully.")


if __name__ == "__main__":
    seed_database()
