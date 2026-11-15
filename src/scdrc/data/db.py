"""
SQLite Database manager and schema definitions for SCDRC.
Uses standard library sqlite3 for maximum portability, zero external C-extension issues,
and full transactional ACID integrity.
"""

import sqlite3
import os
from pathlib import Path
from typing import Generator, Optional


DEFAULT_DB_PATH = Path("./data/scdrc.db")


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get a connection to the SQLite database with row factory enabled."""
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize database tables and indexes."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS items (
        sku TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        unit TEXT NOT NULL DEFAULT 'pcs',
        unit_cost_inr REAL NOT NULL,
        criticality TEXT NOT NULL DEFAULT 'MEDIUM',
        standard_order_qty INTEGER NOT NULL DEFAULT 1000,
        min_safety_stock INTEGER NOT NULL DEFAULT 200
    );

    CREATE TABLE IF NOT EXISTS sites (
        site_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        city TEXT NOT NULL,
        state TEXT NOT NULL,
        country TEXT NOT NULL DEFAULT 'India',
        capacity_units INTEGER NOT NULL DEFAULT 50000
    );

    CREATE TABLE IF NOT EXISTS inventory (
        sku TEXT NOT NULL,
        site_id TEXT NOT NULL,
        on_hand INTEGER NOT NULL,
        safety_stock INTEGER NOT NULL,
        daily_demand REAL NOT NULL,
        reorder_point INTEGER NOT NULL,
        PRIMARY KEY (sku, site_id),
        FOREIGN KEY (sku) REFERENCES items(sku),
        FOREIGN KEY (site_id) REFERENCES sites(site_id)
    );

    CREATE TABLE IF NOT EXISTS in_transit (
        shipment_id TEXT PRIMARY KEY,
        sku TEXT NOT NULL,
        origin TEXT NOT NULL,
        dest TEXT NOT NULL,
        qty INTEGER NOT NULL,
        mode TEXT NOT NULL,
        eta_days INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'IN_TRANSIT',
        FOREIGN KEY (sku) REFERENCES items(sku)
    );

    CREATE TABLE IF NOT EXISTS suppliers (
        supplier_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        location TEXT NOT NULL,
        country TEXT NOT NULL,
        reliability_score REAL NOT NULL,
        payment_terms TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        contact_person TEXT,
        email TEXT,
        phone TEXT
    );

    CREATE TABLE IF NOT EXISTS supplier_items (
        supplier_id TEXT NOT NULL,
        sku TEXT NOT NULL,
        unit_price_inr REAL NOT NULL,
        moq INTEGER NOT NULL,
        standard_lead_time_days INTEGER NOT NULL,
        expedite_lead_time_days INTEGER NOT NULL,
        max_capacity INTEGER NOT NULL,
        is_primary INTEGER NOT NULL DEFAULT 0,
        is_qualified INTEGER NOT NULL DEFAULT 1,
        contract_id TEXT,
        PRIMARY KEY (supplier_id, sku),
        FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
        FOREIGN KEY (sku) REFERENCES items(sku)
    );

    CREATE TABLE IF NOT EXISTS lanes (
        lane_id TEXT PRIMARY KEY,
        origin TEXT NOT NULL,
        dest TEXT NOT NULL,
        mode TEXT NOT NULL,
        base_transit_days INTEGER NOT NULL,
        base_freight_inr_per_unit REAL NOT NULL,
        capacity_units INTEGER NOT NULL,
        risk_rating TEXT NOT NULL DEFAULT 'LOW',
        primary_carrier TEXT
    );

    CREATE TABLE IF NOT EXISTS contacts (
        contact_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        site_id TEXT,
        email TEXT NOT NULL,
        phone TEXT,
        slack_handle TEXT
    );

    CREATE TABLE IF NOT EXISTS cost_rates (
        category TEXT PRIMARY KEY,
        annual_holding_cost_rate REAL NOT NULL,
        daily_holding_factor REAL NOT NULL,
        stockout_penalty_per_unit_day REAL NOT NULL,
        air_expedite_premium_rate REAL NOT NULL,
        handling_charge_inr REAL NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_inv_sku ON inventory(sku);
    CREATE INDEX IF NOT EXISTS idx_inv_site ON inventory(site_id);
    CREATE INDEX IF NOT EXISTS idx_supp_items_sku ON supplier_items(sku);
    CREATE INDEX IF NOT EXISTS idx_lanes_od ON lanes(origin, dest);
    CREATE INDEX IF NOT EXISTS idx_contacts_role ON contacts(role);
    """)

    conn.commit()
    conn.close()
