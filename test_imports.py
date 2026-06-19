#!/usr/bin/env python
"""Quick import test to verify code changes."""

print("Testing imports...")

try:
    from fcmr_core.rules.registry import CATEGORIES, list_categories, resolve_rule_ids, run_pipeline
    print(f"✓ registry: {len(CATEGORIES)} categories")
except Exception as e:
    print(f"✗ registry: {e}")
    exit(1)

try:
    from fcmr_core.catalog import store
    print("✓ catalog.store")
except Exception as e:
    print(f"✗ catalog.store: {e}")
    exit(1)

try:
    from app.api import runs, uploads
    print("✓ api.runs, api.uploads")
except Exception as e:
    print(f"✗ api: {e}")
    exit(1)

print("\n✓ All imports successful")
print(f"\nCategories: {[c['id'] for c in CATEGORIES]}")

# Test resolve_rule_ids
result = resolve_rule_ids(["duplicates"], [])
print(f"resolve_rule_ids(['duplicates'], []): {len(result)} rules")

# Test list_categories
cats = list_categories()
print(f"list_categories(): {len(cats)} categories with descriptions")

print("\n✓ All functionality tests passed")
