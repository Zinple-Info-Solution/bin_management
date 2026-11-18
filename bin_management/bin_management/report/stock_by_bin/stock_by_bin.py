# Copyright (c) 2026, akshayr11 and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder.functions import IfNull
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Bin"), "fieldname": "bin", "fieldtype": "Link", "options": "Warehouse", "width": 200},
		{"label": _("Location Code"), "fieldname": "location_code", "fieldtype": "Data", "width": 120},
		{"label": _("Aisle"), "fieldname": "aisle", "fieldtype": "Data", "width": 70},
		{"label": _("Rack"), "fieldname": "rack", "fieldtype": "Data", "width": 80},
		{"label": _("Shelf"), "fieldname": "shelf", "fieldtype": "Data", "width": 90},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": _("Qty"), "fieldname": "actual_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Reserved Qty"), "fieldname": "reserved_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Stock UOM"), "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 90},
		{"label": _("Stock Value"), "fieldname": "stock_value", "fieldtype": "Currency", "width": 120},
		{"label": _("Bin Capacity"), "fieldname": "bin_capacity", "fieldtype": "Float", "width": 110},
		{
			"label": _("Capacity UOM"),
			"fieldname": "capacity_uom",
			"fieldtype": "Link",
			"options": "UOM",
			"width": 100,
		},
	]


def get_data(filters):
	bins = get_bins(filters)
	if not bins:
		return []

	stock_by_bin = get_stock(filters, [b.name for b in bins])
	ancestors = get_location_ancestors(filters.company)
	show_empty = filters.show_empty_bins and not filters.item_code

	data = []
	for b in bins:
		location = {
			"bin": b.name,
			"location_code": b.location_code,
			"bin_capacity": b.bin_capacity,
			"capacity_uom": b.capacity_uom,
			**get_ancestor_codes(b.parent_warehouse, ancestors),
		}
		rows = stock_by_bin.get(b.name)
		if rows:
			data.extend({**location, **row} for row in rows)
		elif show_empty:
			data.append(location)
	return data


def get_bins(filters):
	warehouse = frappe.qb.DocType("Warehouse")
	query = (
		frappe.qb.from_(warehouse)
		.select(
			warehouse.name,
			warehouse.location_code,
			warehouse.parent_warehouse,
			warehouse.bin_capacity,
			warehouse.capacity_uom,
		)
		.where((warehouse.location_type == "Bin") & (warehouse.disabled == 0))
		.orderby(warehouse.lft)
	)
	if filters.company:
		query = query.where(warehouse.company == filters.company)

	# each filter limits the bins to that node's subtree; together they intersect
	for fieldname in ("warehouse", "aisle", "rack"):
		if filters.get(fieldname):
			bounds = frappe.db.get_value("Warehouse", filters.get(fieldname), ["lft", "rgt"], as_dict=True)
			if not bounds:
				return []
			query = query.where((warehouse.lft >= bounds.lft) & (warehouse.rgt <= bounds.rgt))

	return query.run(as_dict=True)


def get_stock(filters, bin_names):
	bin_ = frappe.qb.DocType("Bin")
	item = frappe.qb.DocType("Item")
	query = (
		frappe.qb.from_(bin_)
		.inner_join(item)
		.on(item.name == bin_.item_code)
		.select(
			bin_.warehouse,
			bin_.item_code,
			item.item_name,
			bin_.actual_qty,
			bin_.reserved_qty,
			bin_.stock_uom,
			bin_.stock_value,
		)
		.where(bin_.warehouse.isin(bin_names) & (IfNull(bin_.actual_qty, 0) != 0))
		.orderby(bin_.item_code)
	)
	if filters.item_code:
		query = query.where(bin_.item_code == filters.item_code)
	if filters.item_group:
		item_groups = frappe.db.get_descendants("Item Group", filters.item_group) or []
		query = query.where(item.item_group.isin([filters.item_group, *item_groups]))

	stock = {}
	for row in query.run(as_dict=True):
		row.actual_qty = flt(row.actual_qty)
		row.reserved_qty = flt(row.reserved_qty)
		stock.setdefault(row.pop("warehouse"), []).append(row)
	return stock


def get_location_ancestors(company):
	"""Map of every Aisle, Rack and Shelf warehouse to its type, code and parent."""
	filters = {"location_type": ("in", ("Aisle", "Rack", "Shelf"))}
	if company:
		filters["company"] = company
	return {
		w.name: w
		for w in frappe.get_all(
			"Warehouse", filters=filters, fields=["name", "location_type", "location_code", "parent_warehouse"]
		)
	}


def get_ancestor_codes(parent, ancestors):
	codes = {}
	while parent in ancestors:
		node = ancestors[parent]
		codes.setdefault(node.location_type.lower(), node.location_code or node.name)
		parent = node.parent_warehouse
	return codes
