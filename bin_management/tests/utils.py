"""Shared fixtures for the bin_management tests.

The records are inserted directly so the tests also run on a site whose ERPNext
setup wizard has not been completed. IntegrationTestCase rolls everything back
when each test class finishes, so nothing is left on the site.
"""

import frappe

TEST_COMPANY = "_Test Bin Company"
TEST_ABBR = "_TBC"
TEST_ACCOUNT = f"_Test Bin Stock - {TEST_ABBR}"
TEST_ITEM = "_Test Bin Item"
TEST_UOM = "_Test Bin UOM"


def create_test_company():
	if not frappe.db.exists("Company", TEST_COMPANY):
		frappe.get_doc(
			{
				"doctype": "Company",
				"name": TEST_COMPANY,
				"company_name": TEST_COMPANY,
				"abbr": TEST_ABBR,
				"default_currency": "INR",
				"country": "India",
				"enable_perpetual_inventory": 0,
			}
		).db_insert()
	frappe.clear_cache(doctype="Company")
	return TEST_COMPANY


def create_test_account():
	if not frappe.db.exists("Account", TEST_ACCOUNT):
		frappe.get_doc(
			{
				"doctype": "Account",
				"name": TEST_ACCOUNT,
				"account_name": "_Test Bin Stock",
				"company": TEST_COMPANY,
				"root_type": "Asset",
				"report_type": "Balance Sheet",
				"account_type": "Stock",
				"is_group": 0,
			}
		).db_insert()
	return TEST_ACCOUNT


def create_test_uom():
	if not frappe.db.exists("UOM", TEST_UOM):
		frappe.get_doc({"doctype": "UOM", "name": TEST_UOM, "uom_name": TEST_UOM}).db_insert()
	return TEST_UOM


def create_test_item():
	if not frappe.db.exists("Item", TEST_ITEM):
		frappe.get_doc(
			{
				"doctype": "Item",
				"name": TEST_ITEM,
				"item_code": TEST_ITEM,
				"item_name": "Test Bin Item",
				"stock_uom": TEST_UOM,
				"is_stock_item": 1,
			}
		).db_insert()
	return TEST_ITEM


def create_group_warehouse(warehouse_name=None, parent=None, account=None):
	"""A group warehouse with a random name, so tests in one class do not collide."""
	return (
		frappe.get_doc(
			{
				"doctype": "Warehouse",
				"warehouse_name": warehouse_name or f"_Test Store {frappe.generate_hash(length=6)}",
				"company": TEST_COMPANY,
				"parent_warehouse": parent,
				"is_group": 1,
				"account": account,
			}
		)
		.insert()
		.name
	)


def make_generator(warehouse, **overrides):
	"""Bin Layout Generator for 2 aisles x 3 racks x 2 shelves x 2 bins (44 nodes)."""
	generator = frappe.get_doc("Bin Layout Generator")
	generator.update(
		{
			"company": TEST_COMPANY,
			"warehouse": warehouse,
			"name_prefix": frappe.db.get_value("Warehouse", warehouse, "warehouse_name"),
			"aisle_from": "A",
			"aisle_to": "B",
			"rack_from": 1,
			"rack_to": 3,
			"shelf_from": 1,
			"shelf_to": 2,
			"bin_from": 1,
			"bin_to": 2,
			"set_barcode": 1,
			"bin_capacity": 0,
			"capacity_uom": None,
			**overrides,
		}
	)
	return generator


def set_bin_stock(warehouse, item_code, qty):
	frappe.get_doc(
		{
			"doctype": "Bin",
			"item_code": item_code,
			"warehouse": warehouse,
			"actual_qty": qty,
			"stock_uom": TEST_UOM,
		}
	).db_insert()
