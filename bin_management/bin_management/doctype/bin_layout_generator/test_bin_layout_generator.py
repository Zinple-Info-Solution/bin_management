# Copyright (c) 2026, akshayr11 and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from bin_management.bin_management.doctype.bin_layout_generator.bin_layout_generator import (
	get_layout_nodes,
)
from bin_management.tests.utils import (
	TEST_ABBR,
	create_group_warehouse,
	create_test_account,
	TEST_UOM,
	create_test_company,
	create_test_uom,
	make_generator,
)

# the tests make their own records; skip ERPNext's standard test records
IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Warehouse", "UOM"]


class IntegrationTestBinLayoutGenerator(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_test_company()
		create_test_uom()

	def get_tree(self, parent):
		lft, rgt = frappe.db.get_value("Warehouse", parent, ["lft", "rgt"])
		return frappe.get_all(
			"Warehouse",
			filters={"lft": (">", lft), "rgt": ("<", rgt)},
			fields=["name", "location_type", "location_code", "is_group", "parent_warehouse", "account"],
		)

	def test_codes_are_padded(self):
		settings = frappe._dict(
			aisle_from="A", aisle_to="A", rack_from=9, rack_to=10, shelf_from=1, shelf_to=1, bin_from=1, bin_to=1
		)
		codes = [node.code for node in get_layout_nodes(settings)]
		self.assertEqual(codes, ["A", "A-09", "A-09-1", "A-09-1-1", "A-10", "A-10-1", "A-10-1-1"])

	def test_generates_full_tree(self):
		parent = create_group_warehouse()
		result = make_generator(parent, bin_capacity=50, capacity_uom=TEST_UOM).generate()

		self.assertEqual(result, {"created": 44, "existing": 0, "total": 44})

		tree = self.get_tree(parent)
		counts = {t: sum(1 for w in tree if w.location_type == t) for t in ("Aisle", "Rack", "Shelf", "Bin")}
		self.assertEqual(counts, {"Aisle": 2, "Rack": 6, "Shelf": 12, "Bin": 24})

		prefix = frappe.db.get_value("Warehouse", parent, "warehouse_name")
		bin_ = frappe.get_doc("Warehouse", f"{prefix}-B-03-2-2 - {TEST_ABBR}")
		self.assertEqual(bin_.location_type, "Bin")
		self.assertEqual(bin_.location_code, "B-03-2-2")
		self.assertEqual(bin_.is_group, 0)
		self.assertEqual(bin_.bin_barcode, f"{prefix}-B-03-2-2")
		self.assertEqual(bin_.bin_capacity, 50)
		self.assertEqual(bin_.capacity_uom, TEST_UOM)

		# Bin > Shelf > Rack > Aisle > parent
		chain = []
		node = bin_.parent_warehouse
		while node != parent:
			chain.append(frappe.db.get_value("Warehouse", node, "location_code"))
			node = frappe.db.get_value("Warehouse", node, "parent_warehouse")
		self.assertEqual(chain, ["B-03-2", "B-03", "B"])

		for warehouse in tree:
			self.assertEqual(warehouse.is_group, int(warehouse.location_type != "Bin"))

	def test_rerun_only_adds_missing_nodes(self):
		parent = create_group_warehouse()
		make_generator(parent).generate()

		result = make_generator(parent, bin_to=3).generate()

		self.assertEqual(result, {"created": 12, "existing": 44, "total": 56})
		self.assertEqual(len(self.get_tree(parent)), 56)

	def test_extend_with_wider_numbers_is_blocked(self):
		parent = create_group_warehouse()
		make_generator(parent, shelf_to=9, bin_to=1, rack_to=1, aisle_to="A").generate()

		# 12 shelves would renumber 1..9 as 01..09 and duplicate them
		with self.assertRaises(frappe.ValidationError):
			make_generator(parent, shelf_to=12, bin_to=1, rack_to=1, aisle_to="A").generate()

		# more aisles and racks with the same widths still work
		result = make_generator(parent, shelf_to=9, bin_to=1, rack_to=2, aisle_to="B").generate()
		self.assertEqual(result["existing"], 1 + 1 + 9 + 9)

	def test_account_is_inherited_from_ancestor(self):
		account = create_test_account()
		top = create_group_warehouse(account=account)
		parent = create_group_warehouse(parent=top)

		make_generator(parent).generate()

		self.assertEqual({w.account for w in self.get_tree(parent)}, {account})

	def test_barcode_can_be_skipped(self):
		parent = create_group_warehouse()
		make_generator(parent, set_barcode=0).generate()

		barcodes = {w.name: frappe.db.get_value("Warehouse", w.name, "bin_barcode") for w in self.get_tree(parent)}
		self.assertEqual(set(barcodes.values()), {None})

	def test_same_prefix_under_another_parent_is_rejected(self):
		first = create_group_warehouse()
		second = create_group_warehouse()
		make_generator(first, name_prefix="_Test Shared").generate()

		with self.assertRaises(frappe.ValidationError):
			make_generator(second, name_prefix="_Test Shared").generate()

	def test_invalid_ranges_are_rejected(self):
		parent = create_group_warehouse()
		for overrides in (
			{"aisle_from": "AA"},
			{"aisle_from": "1"},
			{"aisle_from": "D", "aisle_to": "A"},
			{"rack_from": 0},
			{"shelf_from": 5, "shelf_to": 2},
		):
			with self.subTest(overrides=overrides), self.assertRaises(frappe.ValidationError):
				make_generator(parent, **overrides).generate()

	def test_aisle_letters_are_uppercased(self):
		parent = create_group_warehouse()
		generator = make_generator(parent, aisle_from="a", aisle_to="a", rack_to=1, shelf_to=1, bin_to=1)
		generator.generate()
		self.assertEqual(generator.aisle_from, "A")

	def test_parent_must_be_a_group_in_the_same_company(self):
		parent = create_group_warehouse()
		make_generator(parent, rack_to=1, shelf_to=1, bin_to=1).generate()
		leaf_bin = next(w.name for w in self.get_tree(parent) if w.location_type == "Bin")
		aisle = next(w.name for w in self.get_tree(parent) if w.location_type == "Aisle")

		for warehouse in (leaf_bin, aisle):
			with self.subTest(warehouse=warehouse), self.assertRaises(frappe.ValidationError):
				make_generator(warehouse).generate()

		with self.assertRaises(frappe.ValidationError):
			make_generator(parent, company="_Test Some Other Company").generate()

	def test_large_layout_runs_in_background(self):
		parent = create_group_warehouse()
		with patch("frappe.enqueue") as enqueue:
			result = make_generator(parent, rack_to=10, shelf_to=5, bin_to=4).generate()

		self.assertEqual(result, {"queued": True, "total": 522})
		enqueue.assert_called_once()
		self.assertEqual(enqueue.call_args.kwargs["settings"]["warehouse"], parent)
		self.assertEqual(self.get_tree(parent), [])
