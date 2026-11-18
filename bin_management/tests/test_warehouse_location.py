# Copyright (c) 2026, akshayr11 and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from bin_management.tests.utils import TEST_COMPANY, create_group_warehouse, create_test_company


def new_location(parent, location_type, is_group, **fields):
	return frappe.get_doc(
		{
			"doctype": "Warehouse",
			"warehouse_name": f"_Test Loc {frappe.generate_hash(length=6)}",
			"company": TEST_COMPANY,
			"parent_warehouse": parent,
			"location_type": location_type,
			"is_group": is_group,
			**fields,
		}
	)


class IntegrationTestWarehouseLocation(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_test_company()
		cls.parent = create_group_warehouse()

	def test_custom_fields_exist(self):
		meta = frappe.get_meta("Warehouse")
		for fieldname in (
			"location_type",
			"location_code",
			"bin_barcode",
			"bin_capacity",
			"capacity_uom",
			"bin_length",
			"bin_width",
			"bin_height",
			"dimension_uom",
		):
			self.assertTrue(meta.has_field(fieldname), fieldname)

	def test_bin_cannot_be_group(self):
		with self.assertRaises(frappe.ValidationError):
			new_location(self.parent, "Bin", 1).insert()

	def test_aisle_rack_shelf_must_be_group(self):
		for location_type in ("Aisle", "Rack", "Shelf"):
			with self.subTest(location_type=location_type), self.assertRaises(frappe.ValidationError):
				new_location(self.parent, location_type, 0).insert()
			new_location(self.parent, location_type, 1).insert()

	def test_bin_barcode_must_be_unique(self):
		barcode = f"_TEST-{frappe.generate_hash(length=6)}"
		new_location(self.parent, "Bin", 0, bin_barcode=barcode).insert()

		with self.assertRaises(frappe.ValidationError):
			new_location(self.parent, "Bin", 0, bin_barcode=barcode).insert()

	def test_barcode_is_trimmed_and_cleared_for_non_bins(self):
		bin_ = new_location(self.parent, "Bin", 0, bin_barcode="  _TEST-TRIM  ").insert()
		self.assertEqual(bin_.bin_barcode, "_TEST-TRIM")

		shelf = new_location(self.parent, "Shelf", 1, bin_barcode="_TEST-SHELF").insert()
		self.assertIsNone(shelf.bin_barcode)

	def test_plain_warehouse_is_unaffected(self):
		warehouse = new_location(self.parent, None, 0).insert()
		self.assertFalse(warehouse.location_type)
