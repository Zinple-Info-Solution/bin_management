import frappe
from frappe import _

GROUP_LOCATION_TYPES = ("Aisle", "Rack", "Shelf")


def validate(doc, method=None):
	validate_location_type(doc)
	validate_bin_barcode(doc)


def validate_location_type(doc):
	if doc.location_type == "Bin" and doc.is_group:
		frappe.throw(_("A warehouse with Location Type Bin cannot be a group warehouse."))

	if doc.location_type in GROUP_LOCATION_TYPES and not doc.is_group:
		frappe.throw(
			_("A warehouse with Location Type {0} must be a group warehouse.").format(_(doc.location_type))
		)

	if doc.location_type != "Bin":
		doc.bin_barcode = None


def validate_bin_barcode(doc):
	doc.bin_barcode = (doc.bin_barcode or "").strip() or None
	if not doc.bin_barcode:
		return

	duplicate = frappe.db.get_value(
		"Warehouse", {"bin_barcode": doc.bin_barcode, "name": ("!=", doc.name)}, "name"
	)
	if duplicate:
		frappe.throw(
			_("Bin Barcode {0} is already used by warehouse {1}.").format(
				frappe.bold(doc.bin_barcode), frappe.bold(duplicate)
			)
		)
