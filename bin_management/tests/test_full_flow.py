# Copyright (c) 2026, akshayr11 and Contributors
# See license.txt

"""End-to-end flow with real ERPNext transactions:

generate a layout -> receive stock into a bin -> move it to another bin ->
check ERPNext's balances, the ledgers and the Stock by Bin report -> cancel -> check again.

It needs a company that has been through the ERPNext setup wizard (accounts, cost
center and a fiscal year for today). Everything is rolled back when the class finishes.
"""

import frappe
from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate, nowdate

from bin_management.bin_management.report.stock_by_bin.stock_by_bin import execute as stock_by_bin


def get_ready_company():
	"""First company with what a Stock Entry needs, or None."""
	today = getdate(nowdate())
	has_fiscal_year = frappe.db.exists(
		"Fiscal Year", {"year_start_date": ("<=", today), "year_end_date": (">=", today), "disabled": 0}
	)
	if not has_fiscal_year:
		return None

	for company in frappe.get_all(
		"Company",
		fields=["name", "abbr", "default_inventory_account", "stock_adjustment_account", "cost_center"],
		order_by="creation",
	):
		if company.default_inventory_account and company.stock_adjustment_account and company.cost_center:
			return company
	return None


class IntegrationTestBinFullFlow(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = get_ready_company()
		if not cls.company:
			raise frappe.ValidationError("Full flow test needs a company set up through the setup wizard")

		cls.uom = "Nos"
		cls.root = frappe.db.get_value(
			"Warehouse", {"company": cls.company.name, "parent_warehouse": ("is", "not set")}, "name"
		)
		cls.item = cls.make_item()

	@classmethod
	def make_item(cls):
		item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
		return (
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": f"_Test Bin Flow Item {frappe.generate_hash(length=5)}",
					"item_group": item_group,
					"stock_uom": cls.uom,
					"is_stock_item": 1,
					"valuation_rate": 100,
				}
			)
			.insert()
			.name
		)

	# helpers

	def bin_name(self, code):
		return f"{self.prefix}-{code} - {self.company.abbr}"

	def qty_in(self, warehouse):
		return frappe.db.get_value("Bin", {"item_code": self.item, "warehouse": warehouse}, "actual_qty") or 0

	def qty_in_subtree(self, warehouse):
		"""Item qty in a group warehouse and everything below it."""
		lft, rgt = frappe.db.get_value("Warehouse", warehouse, ["lft", "rgt"])
		result = frappe.db.sql(
			"""select coalesce(sum(b.actual_qty), 0) from `tabBin` b
			join `tabWarehouse` w on w.name = b.warehouse
			where b.item_code = %s and w.lft >= %s and w.rgt <= %s""",
			(self.item, lft, rgt),
		)
		return result[0][0]

	def report(self, **filters):
		_columns, data = stock_by_bin({"company": self.company.name, "warehouse": self.store, **filters})
		return data

	def stock_rows(self, **filters):
		return {r["location_code"]: r for r in self.report(**filters) if r.get("item_code") == self.item}

	# the flow

	def test_full_flow(self):
		self.step_1_create_store_and_generate_layout()
		self.step_2_receive_stock_into_a_bin()
		self.step_3_group_locations_cannot_hold_stock()
		self.step_4_transfer_between_bins()
		self.step_5_stock_by_bin_report()
		self.step_6_cancel_transfer()

	def step_1_create_store_and_generate_layout(self):
		self.prefix = f"_Test Flow {frappe.generate_hash(length=5)}"
		self.store = (
			frappe.get_doc(
				{
					"doctype": "Warehouse",
					"warehouse_name": self.prefix,
					"company": self.company.name,
					"parent_warehouse": self.root,
					"is_group": 1,
				}
			)
			.insert()
			.name
		)

		generator = frappe.get_doc("Bin Layout Generator")
		generator.update(
			{
				"company": self.company.name,
				"warehouse": self.store,
				"name_prefix": self.prefix,
				"aisle_from": "A",
				"aisle_to": "B",
				"rack_from": 1,
				"rack_to": 2,
				"shelf_from": 1,
				"shelf_to": 2,
				"bin_from": 1,
				"bin_to": 2,
				"set_barcode": 1,
				"bin_capacity": 50,
				"capacity_uom": self.uom,
			}
		)

		# 2 aisles + 4 racks + 8 shelves + 16 bins
		self.assertEqual(generator.generate(), {"created": 30, "existing": 0, "total": 30})

		self.source_bin = self.bin_name("A-01-1-1")
		self.target_bin = self.bin_name("B-02-2-2")
		bin_doc = frappe.get_doc("Warehouse", self.source_bin)
		self.assertEqual((bin_doc.location_type, bin_doc.is_group), ("Bin", 0))
		self.assertEqual(bin_doc.parent_warehouse, self.bin_name("A-01-1"))

	def step_2_receive_stock_into_a_bin(self):
		receipt = make_stock_entry(
			item_code=self.item,
			to_warehouse=self.source_bin,
			qty=10,
			basic_rate=100,
			company=self.company.name,
		)
		self.assertEqual(receipt.docstatus, 1)

		self.assertEqual(self.qty_in(self.source_bin), 10)
		self.assertEqual(self.qty_in_subtree(self.bin_name("A")), 10)
		self.assertEqual(self.qty_in_subtree(self.store), 10)

		ledger = frappe.get_all(
			"Stock Ledger Entry",
			filters={"voucher_no": receipt.name, "is_cancelled": 0},
			fields=["warehouse", "actual_qty", "stock_value_difference"],
		)
		self.assertEqual(len(ledger), 1)
		self.assertEqual(ledger[0].warehouse, self.source_bin)
		self.assertEqual((ledger[0].actual_qty, ledger[0].stock_value_difference), (10, 1000))

		# perpetual inventory: the bin's stock is booked in the accounts
		debits = frappe.get_all(
			"GL Entry", filters={"voucher_no": receipt.name, "is_cancelled": 0}, pluck="debit"
		)
		self.assertEqual(sum(debits), 1000)

	def step_3_group_locations_cannot_hold_stock(self):
		for group in (self.bin_name("A"), self.bin_name("A-01"), self.bin_name("A-01-1")):
			with self.subTest(group=group), self.assertRaises(frappe.ValidationError):
				make_stock_entry(
					item_code=self.item, to_warehouse=group, qty=1, basic_rate=100, company=self.company.name
				)
			frappe.clear_messages()

	def step_4_transfer_between_bins(self):
		self.transfer = make_stock_entry(
			item_code=self.item,
			from_warehouse=self.source_bin,
			to_warehouse=self.target_bin,
			qty=4,
			company=self.company.name,
		)
		self.assertEqual(self.transfer.purpose, "Material Transfer")

		self.assertEqual(self.qty_in(self.source_bin), 6)
		self.assertEqual(self.qty_in(self.target_bin), 4)
		self.assertEqual(self.qty_in_subtree(self.bin_name("A")), 6)
		self.assertEqual(self.qty_in_subtree(self.bin_name("B")), 4)
		self.assertEqual(self.qty_in_subtree(self.store), 10)

	def step_5_stock_by_bin_report(self):
		rows = self.stock_rows(show_empty_bins=0)
		self.assertEqual(set(rows), {"A-01-1-1", "B-02-2-2"})

		source = rows["A-01-1-1"]
		self.assertEqual((source["aisle"], source["rack"], source["shelf"]), ("A", "A-01", "A-01-1"))
		self.assertEqual((source["actual_qty"], source["stock_value"]), (6, 600))
		self.assertEqual((rows["B-02-2-2"]["actual_qty"], rows["B-02-2-2"]["stock_value"]), (4, 400))
		self.assertEqual(source["bin_capacity"], 50)

		# all 16 bins when empty ones are included; 14 of them are empty
		everything = self.report(show_empty_bins=1)
		self.assertEqual(len(everything), 16)
		self.assertEqual(sum(1 for r in everything if not r.get("item_code")), 14)

		# filters narrow to a part of the tree
		self.assertEqual(set(self.stock_rows(show_empty_bins=1, aisle=self.bin_name("B"))), {"B-02-2-2"})
		self.assertEqual(len(self.report(show_empty_bins=1, aisle=self.bin_name("B"))), 8)
		self.assertEqual(len(self.report(show_empty_bins=1, rack=self.bin_name("A-02"))), 4)
		self.assertEqual(self.stock_rows(show_empty_bins=1, rack=self.bin_name("A-02")), {})
		self.assertEqual(
			[r["bin"] for r in self.report(show_empty_bins=1, item_code=self.item)],
			[self.source_bin, self.target_bin],
		)

	def step_6_cancel_transfer(self):
		self.transfer.reload()
		self.transfer.cancel()

		self.assertEqual(self.qty_in(self.source_bin), 10)
		self.assertEqual(self.qty_in(self.target_bin), 0)
		self.assertEqual(set(self.stock_rows(show_empty_bins=0)), {"A-01-1-1"})
