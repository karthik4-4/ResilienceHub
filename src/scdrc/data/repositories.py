"""
Repository interfaces and SQLite implementations for enterprise ERP/WMS abstraction.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import sqlite3

from scdrc.data.db import get_connection


# --- Abstract Repositories ---

class ItemRepository(ABC):
    @abstractmethod
    def get_by_sku(self, sku: str) -> Optional[Dict[str, Any]]: ...
    @abstractmethod
    def search_by_name(self, query: str) -> List[Dict[str, Any]]: ...
    @abstractmethod
    def list_all(self) -> List[Dict[str, Any]]: ...


class SiteRepository(ABC):
    @abstractmethod
    def get_by_id(self, site_id: str) -> Optional[Dict[str, Any]]: ...
    @abstractmethod
    def search_by_name(self, query: str) -> List[Dict[str, Any]]: ...
    @abstractmethod
    def list_all(self) -> List[Dict[str, Any]]: ...


class InventoryRepository(ABC):
    @abstractmethod
    def get_inventory(self, sku: str, site_id: str) -> Optional[Dict[str, Any]]: ...
    @abstractmethod
    def get_in_transit(self, sku: str, site_id: str) -> List[Dict[str, Any]]: ...
    @abstractmethod
    def get_all_by_sku(self, sku: str) -> List[Dict[str, Any]]: ...


class SupplierRepository(ABC):
    @abstractmethod
    def get_by_id(self, supplier_id: str) -> Optional[Dict[str, Any]]: ...
    @abstractmethod
    def find_suppliers_for_sku(self, sku: str) -> List[Dict[str, Any]]: ...
    @abstractmethod
    def get_supplier_terms(self, supplier_id: str, sku: str) -> Optional[Dict[str, Any]]: ...


class RouteRepository(ABC):
    @abstractmethod
    def get_by_id(self, lane_id: str) -> Optional[Dict[str, Any]]: ...
    @abstractmethod
    def find_routes(self, origin: str, dest: str) -> List[Dict[str, Any]]: ...
    @abstractmethod
    def find_routes_to_dest(self, dest: str) -> List[Dict[str, Any]]: ...


class CostRepository(ABC):
    @abstractmethod
    def get_rates_for_category(self, category: str) -> Optional[Dict[str, Any]]: ...
    @abstractmethod
    def get_item_unit_cost(self, sku: str) -> float: ...


class ContactRepository(ABC):
    @abstractmethod
    def get_contacts_by_role(self, role: str, site_id: Optional[str] = None) -> List[Dict[str, Any]]: ...
    @abstractmethod
    def get_by_id(self, contact_id: str) -> Optional[Dict[str, Any]]: ...


# --- SQLite Concrete Implementations ---

class SQLiteItemRepository(ItemRepository):
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def get_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        row = conn.execute("SELECT * FROM items WHERE UPPER(sku) = UPPER(?)", (sku,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def search_by_name(self, query: str) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        like_query = f"%{query}%"
        rows = conn.execute(
            "SELECT * FROM items WHERE name LIKE ? OR sku LIKE ?",
            (like_query, like_query),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def list_all(self) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        rows = conn.execute("SELECT * FROM items").fetchall()
        conn.close()
        return [dict(r) for r in rows]


class SQLiteSiteRepository(SiteRepository):
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def get_by_id(self, site_id: str) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        row = conn.execute("SELECT * FROM sites WHERE UPPER(site_id) = UPPER(?)", (site_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def search_by_name(self, query: str) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        like_query = f"%{query}%"
        rows = conn.execute(
            "SELECT * FROM sites WHERE name LIKE ? OR site_id LIKE ? OR city LIKE ?",
            (like_query, like_query, like_query),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def list_all(self) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        rows = conn.execute("SELECT * FROM sites").fetchall()
        conn.close()
        return [dict(r) for r in rows]


class SQLiteInventoryRepository(InventoryRepository):
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def get_inventory(self, sku: str, site_id: str) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        row = conn.execute(
            "SELECT * FROM inventory WHERE UPPER(sku) = UPPER(?) AND UPPER(site_id) = UPPER(?)",
            (sku, site_id),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_in_transit(self, sku: str, site_id: str) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        rows = conn.execute(
            "SELECT * FROM in_transit WHERE UPPER(sku) = UPPER(?) AND UPPER(dest) = UPPER(?) AND status != 'CANCELLED'",
            (sku, site_id),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_all_by_sku(self, sku: str) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        rows = conn.execute(
            "SELECT * FROM inventory WHERE UPPER(sku) = UPPER(?)",
            (sku,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


class SQLiteSupplierRepository(SupplierRepository):
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def get_by_id(self, supplier_id: str) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        row = conn.execute(
            "SELECT * FROM suppliers WHERE UPPER(supplier_id) = UPPER(?)",
            (supplier_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def find_suppliers_for_sku(self, sku: str) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        rows = conn.execute(
            """
            SELECT s.*, si.unit_price_inr, si.moq, si.standard_lead_time_days,
                   si.expedite_lead_time_days, si.max_capacity, si.is_primary,
                   si.is_qualified, si.contract_id
            FROM suppliers s
            JOIN supplier_items si ON s.supplier_id = si.supplier_id
            WHERE UPPER(si.sku) = UPPER(?)
            ORDER BY si.is_primary DESC, si.standard_lead_time_days ASC
            """,
            (sku,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_supplier_terms(self, supplier_id: str, sku: str) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        row = conn.execute(
            """
            SELECT s.*, si.unit_price_inr, si.moq, si.standard_lead_time_days,
                   si.expedite_lead_time_days, si.max_capacity, si.is_primary,
                   si.is_qualified, si.contract_id
            FROM suppliers s
            JOIN supplier_items si ON s.supplier_id = si.supplier_id
            WHERE UPPER(s.supplier_id) = UPPER(?) AND UPPER(si.sku) = UPPER(?)
            """,
            (supplier_id, sku),
        ).fetchone()
        conn.close()
        return dict(row) if row else None


class SQLiteRouteRepository(RouteRepository):
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def get_by_id(self, lane_id: str) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        row = conn.execute("SELECT * FROM lanes WHERE UPPER(lane_id) = UPPER(?)", (lane_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def find_routes(self, origin: str, dest: str) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        rows = conn.execute(
            "SELECT * FROM lanes WHERE UPPER(origin) = UPPER(?) AND UPPER(dest) = UPPER(?)",
            (origin, dest),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def find_routes_to_dest(self, dest: str) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        rows = conn.execute(
            "SELECT * FROM lanes WHERE UPPER(dest) = UPPER(?)",
            (dest,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


class SQLiteCostRepository(CostRepository):
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def get_rates_for_category(self, category: str) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        row = conn.execute("SELECT * FROM cost_rates WHERE category = ?", (category,)).fetchone()
        if not row:
            row = conn.execute("SELECT * FROM cost_rates WHERE category = 'DEFAULT'").fetchone()
        conn.close()
        return dict(row) if row else None

    def get_item_unit_cost(self, sku: str) -> float:
        conn = get_connection(self.db_path)
        row = conn.execute("SELECT unit_cost_inr FROM items WHERE UPPER(sku) = UPPER(?)", (sku,)).fetchone()
        conn.close()
        return float(row["unit_cost_inr"]) if row else 1000.0


class SQLiteContactRepository(ContactRepository):
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def get_contacts_by_role(self, role: str, site_id: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        query = "SELECT * FROM contacts WHERE UPPER(role) = UPPER(?)"
        params: List[Any] = [role]
        if site_id:
            query += " AND (site_id = ? OR site_id IS NULL OR site_id = '')"
            params.append(site_id)
        rows = conn.execute(query, params).fetchall()
        if not rows and site_id:
            # Fallback to general role contacts
            rows = conn.execute("SELECT * FROM contacts WHERE UPPER(role) = UPPER(?)", (role,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_by_id(self, contact_id: str) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        row = conn.execute("SELECT * FROM contacts WHERE UPPER(contact_id) = UPPER(?)", (contact_id,)).fetchone()
        conn.close()
        return dict(row) if row else None
