# Copyright (c) 2026, akshayr11 and contributors
# For license information, please see license.txt

import string
from dataclasses import dataclass

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

# larger layouts are built in a background job so the request does not time out
ENQUEUE_THRESHOLD = 300
SETTINGS_FIELDS = (
	"company",
	"warehouse",
	"name_prefix",
	"aisle_from",
	"aisle_to",
	"rack_from",
	"rack_to",
	"shelf_from",
	"shelf_to",
	"bin_from",
	"bin_to",
	"set_barcode",
	"bin_capacity",
	"capacity_uom",
)


@dataclass
class LayoutNode:
	code: str
	location_type: str
	parent_code: str | None

	@property
	def is_group(self):
		return self.location_type != "Bin"


class BinLayoutGenerator(Document):
	# begin: auto-generated types
	# end: auto-generated types

	def validate(self):
		self.validate_ranges()

	def validate_ranges(self):
		self.aisle_from = (self.aisle_from or "").strip().upper()
		self.aisle_to = (self.aisle_to or "").strip().upper()
		for value in (self.aisle_from, self.aisle_to):
			if len(value) != 1 or value not in string.ascii_uppercase:
				frappe.throw(_("Aisles must be single letters from A to Z, got {0}.").format(frappe.bold(value)))
		if self.aisle_from > self.aisle_to:
			frappe.throw(_("Aisle From must come before Aisle To."))

		for label in ("Rack", "Shelf", "Bin"):
			key = label.lower()
			start, end = cint(self.get(f"{key}_from")), cint(self.get(f"{key}_to"))
			if start < 1 or end < start:
				frappe.throw(_("{0} range must start at 1 or more and end at or after its start.").format(_(label)))

	def validate_parent(self):
		parent = frappe.db.get_value(
			"Warehouse", self.warehouse, ["company", "is_group", "disabled", "location_type"], as_dict=True
		)
		if not parent:
			frappe.throw(_("Warehouse {0} does not exist.").format(self.warehouse))
		if parent.company != self.company:
			frappe.throw(_("Warehouse {0} belongs to company {1}.").format(self.warehouse, parent.company))
		if not parent.is_group:
			frappe.throw(_("Warehouse {0} must be a group warehouse to hold aisles.").format(self.warehouse))
		if parent.disabled:
			frappe.throw(_("Warehouse {0} is disabled.").format(self.warehouse))
		if parent.location_type:
			frappe.throw(
				_("Warehouse {0} is already a {1}. Pick the warehouse above the aisles.").format(
					self.warehouse, parent.location_type
				)
			)

	def validate_numbering_matches_existing(self, nodes):
		"""Stop a re-run whose zero padding differs from the existing layout (e.g. shelf 1 vs 01),
		which would otherwise create a second, parallel set of locations."""
		lft, rgt = frappe.db.get_value("Warehouse", self.warehouse, ["lft", "rgt"])
		existing = frappe.get_all(
			"Warehouse",
			filters={"lft": (">", lft), "rgt": ("<", rgt), "location_type": ("in", ("Rack", "Shelf", "Bin"))},
			pluck="location_code",
		)
		if not existing:
			return

		existing_by_key = {numbering_key(code): code for code in existing if code}
		for node in nodes:
			current = existing_by_key.get(numbering_key(node.code))
			if current and current != node.code:
				frappe.throw(
					_(
						"This would create {0}, but {1} already exists. The layout has a different number of digits. "
						"Keep the same digit count, for example a To value with the same number of digits as before."
					).format(frappe.bold(node.code), frappe.bold(current)),
					title=_("Numbering Mismatch"),
				)

	@frappe.whitelist()
	def generate(self):
		frappe.has_permission("Warehouse", "create", throw=True)
		self.validate_ranges()
		self.validate_parent()

		settings = {field: self.get(field) for field in SETTINGS_FIELDS}
		nodes = get_layout_nodes(frappe._dict(settings))
		self.validate_numbering_matches_existing(nodes)
		total = len(nodes)

		if total > ENQUEUE_THRESHOLD:
			frappe.enqueue(
				"bin_management.bin_management.doctype.bin_layout_generator.bin_layout_generator.build_layout",
				queue="long",
				timeout=3600,
				settings=settings,
				notify=True,
			)
			return {"queued": True, "total": total}

		return build_layout(settings)


def numbering_key(code):
	"""A-03-2-1 and A-3-02-1 give the same key: ("A", 3, 2, 1)."""
	return tuple(int(part) if part.isdigit() else part for part in code.split("-"))


def get_layout_nodes(settings) -> list[LayoutNode]:
	"""Return every node in depth-first order, so each parent comes before its children."""
	rack_width = max(2, len(str(cint(settings.rack_to))))
	shelf_width = len(str(cint(settings.shelf_to)))
	bin_width = len(str(cint(settings.bin_to)))

	nodes = []
	for aisle_ord in range(ord(settings.aisle_from), ord(settings.aisle_to) + 1):
		aisle = chr(aisle_ord)
		nodes.append(LayoutNode(aisle, "Aisle", None))
		for rack_no in range(cint(settings.rack_from), cint(settings.rack_to) + 1):
			rack = f"{aisle}-{rack_no:0{rack_width}d}"
			nodes.append(LayoutNode(rack, "Rack", aisle))
			for shelf_no in range(cint(settings.shelf_from), cint(settings.shelf_to) + 1):
				shelf = f"{rack}-{shelf_no:0{shelf_width}d}"
				nodes.append(LayoutNode(shelf, "Shelf", rack))
				for bin_no in range(cint(settings.bin_from), cint(settings.bin_to) + 1):
					nodes.append(LayoutNode(f"{shelf}-{bin_no:0{bin_width}d}", "Bin", shelf))
	return nodes


def build_layout(settings, notify=False):
	"""Create the Aisle > Rack > Shelf > Bin tree. Nodes that already exist under the
	expected parent are kept, so a layout can be extended by running it again with wider ranges."""
	settings = frappe._dict(settings)
	parent = frappe.get_doc("Warehouse", settings.warehouse)
	abbr = frappe.get_cached_value("Company", parent.company, "abbr")
	account = get_inherited_account(parent)
	prefix = (settings.name_prefix or "").strip()

	nodes = get_layout_nodes(settings)
	name_by_code = {}
	created = existing = 0

	for idx, node in enumerate(nodes, start=1):
		parent_name = name_by_code[node.parent_code] if node.parent_code else parent.name
		warehouse_name = f"{prefix}-{node.code}" if prefix else node.code
		name = f"{warehouse_name} - {abbr}"

		current = frappe.db.get_value("Warehouse", name, ["parent_warehouse"], as_dict=True)
		if current:
			if current.parent_warehouse != parent_name:
				frappe.throw(
					_("Warehouse {0} already exists under {1}, not under {2}. Use a different Name Prefix.").format(
						frappe.bold(name), frappe.bold(current.parent_warehouse), frappe.bold(parent_name)
					)
				)
			existing += 1
		else:
			doc = frappe.get_doc(
				{
					"doctype": "Warehouse",
					"warehouse_name": warehouse_name,
					"company": parent.company,
					"parent_warehouse": parent_name,
					"is_group": cint(node.is_group),
					"account": account,
					"location_type": node.location_type,
					"location_code": node.code,
				}
			)
			if not node.is_group:
				if cint(settings.set_barcode):
					doc.bin_barcode = warehouse_name
				doc.bin_capacity = flt(settings.bin_capacity)
				doc.capacity_uom = settings.capacity_uom
			doc.insert()
			name = doc.name
			created += 1

		name_by_code[node.code] = name
		if idx % 25 == 0 or idx == len(nodes):
			frappe.publish_progress(
				idx * 100 / len(nodes), title=_("Generating Bin Layout"), description=node.code
			)

	result = {"created": created, "existing": existing, "total": len(nodes)}
	if notify:
		frappe.publish_realtime("bin_layout_generated", result, user=frappe.session.user)
	return result


def get_inherited_account(warehouse):
	"""The account set on the warehouse or its nearest ancestor that has one."""
	if warehouse.account:
		return warehouse.account

	return frappe.db.get_value(
		"Warehouse",
		{
			"lft": ("<", warehouse.lft),
			"rgt": (">", warehouse.rgt),
			"company": warehouse.company,
			"account": ("is", "set"),
		},
		"account",
		order_by="lft desc",
	)
