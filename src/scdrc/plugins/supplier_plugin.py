"""
Semantic Kernel Plugin: Supplier lookup and terms.
"""

from __future__ import annotations
import json
from semantic_kernel.functions import kernel_function
from scdrc.data.repositories import SupplierRepository


class SupplierPlugin:
    """Tools for querying supplier options and contractual terms."""

    def __init__(self, repo: SupplierRepository):
        self.repo = repo

    @kernel_function(description="Find all suppliers capable of providing a specific SKU with pricing and lead times.")
    def find_alternative_suppliers(self, sku: str) -> str:
        suppliers = self.repo.find_suppliers_for_sku(sku)
        return json.dumps(suppliers, indent=2)

    @kernel_function(description="Get detailed commercial and delivery terms for a supplier providing a SKU.")
    def get_supplier_terms(self, supplier_id: str, sku: str) -> str:
        terms = self.repo.get_supplier_terms(supplier_id, sku)
        if not terms:
            return json.dumps({"error": f"No supplier terms found for {supplier_id} and {sku}"})
        return json.dumps(terms, indent=2)
