# Copyright (c) 2026, akshayr11 and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from bin_management.bin_management.report.stock_by_bin.stock_by_bin import execute
from bin_management.tests.utils import (
	TEST_ABBR,
	TEST_COMPANY,
	TEST_ITEM,
	create_group_warehouse,
	TEST_UOM,
	create_test_company,
	create_test_uom,
	create_test_item,
	make_generator,
	set_bin_stock,
)


class IntegrationTestStockByBin(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_test_company()
		create_test_uom()
		create_test_item()

		# 2 aisles x 3 racks x 2 shelves x 2 bins = 24 bins
		cls.parent = create_group_warehouse()
		make_generator(cls.parent, bin_capacity=100, capacity_uom=TEST_UOM).generate()
		cls.prefix = frappe.db.get_value("Warehouse", cls.parent, "warehouse_name")
		cls.stocked_bin = cls.node("A-02-1-2")
		set_bin_stock(cls.stocked_bin, TEST_ITEM, 7)

	@classmethod
	def node(cls, code):
		return f"{cls.prefix}-{code} - {TEST_ABBR}"

	def run_report(self, **filters):
		_columns, data = execute({"company": TEST_COMPANY, "warehouse": self.parent, **filters})
		return data

	def test_stock_row_has_location_details(self):
		rows = [r for r in self.run_report(show_empty_bins=0)]

		self.assertEqual(len(rows), 1)
		row = rows[0]
		self.assertEqual(row["bin"], self.stocked_bin)
		self.assertEqual(row["item_code"], TEST_ITEM)
		self.assertEqual(row["actual_qty"], 7)
		self.assertEqual(
			(row["location_code"], row["aisle"], row["rack"], row["shelf"]), ("A-02-1-2", "A", "A-02", "A-02-1")
		)
		self.assertEqual(row["bin_capacity"], 100)

	def test_empty_bins_are_listed_when_asked(self):
		rows = self.run_report(show_empty_bins=1)

		self.assertEqual(len(rows), 24)
		self.assertEqual(sum(1 for r in rows if r.get("item_code")), 1)

	def test_aisle_and_rack_filters(self):
		self.assertEqual(len(self.run_report(show_empty_bins=1, aisle=self.node("B"))), 12)
		self.assertEqual(len(self.run_report(show_empty_bins=1, rack=self.node("B-03"))), 4)
		# a rack outside the chosen aisle gives nothing
		self.assertEqual(self.run_report(show_empty_bins=1, aisle=self.node("A"), rack=self.node("B-03")), [])

	def test_item_filter_hides_empty_bins(self):
		rows = self.run_report(show_empty_bins=1, item_code=TEST_ITEM)
		self.assertEqual([r["bin"] for r in rows], [self.stocked_bin])

		self.assertEqual(self.run_report(show_empty_bins=1, item_code="_Test No Such Item"), [])

	def test_bins_follow_tree_order(self):
		rows = self.run_report(show_empty_bins=1)
		codes = [r["location_code"] for r in rows]
		self.assertEqual(codes[:3], ["A-01-1-1", "A-01-1-2", "A-01-2-1"])
		self.assertEqual(codes[-1], "B-03-2-2")
