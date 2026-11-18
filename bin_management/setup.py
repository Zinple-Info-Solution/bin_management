from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

LOCATION_TYPES = ("Aisle", "Rack", "Shelf", "Bin")


def after_install():
	make_custom_fields()


def after_migrate():
	make_custom_fields()


def make_custom_fields():
	create_custom_fields(get_custom_fields(), ignore_validate=True)


def get_custom_fields():
	is_bin = "eval:doc.location_type=='Bin'"
	return {
		"Warehouse": [
			{
				"fieldname": "bin_location_section",
				"fieldtype": "Section Break",
				"label": "Bin Location",
				"insert_after": "customer",
				"collapsible": 1,
				"collapsible_depends_on": "location_type",
			},
			{
				"fieldname": "location_type",
				"fieldtype": "Select",
				"label": "Location Type",
				"options": "\n" + "\n".join(LOCATION_TYPES),
				"insert_after": "bin_location_section",
				"in_standard_filter": 1,
				"in_list_view": 1,
				"description": "Aisle, Rack and Shelf must be group warehouses. A Bin must not be a group.",
			},
			{
				"fieldname": "location_code",
				"fieldtype": "Data",
				"label": "Location Code",
				"insert_after": "location_type",
				"depends_on": "location_type",
				"in_standard_filter": 1,
				"description": "Short code such as A-03-2-1",
			},
			{
				"fieldname": "bin_barcode",
				"fieldtype": "Data",
				"label": "Bin Barcode",
				"options": "Barcode",
				"insert_after": "location_code",
				"depends_on": is_bin,
				"search_index": 1,
			},
			{
				"fieldname": "bin_location_cb1",
				"fieldtype": "Column Break",
				"insert_after": "bin_barcode",
			},
			{
				"fieldname": "bin_capacity",
				"fieldtype": "Float",
				"label": "Capacity",
				"insert_after": "bin_location_cb1",
				"depends_on": is_bin,
				"non_negative": 1,
			},
			{
				"fieldname": "capacity_uom",
				"fieldtype": "Link",
				"label": "Capacity UOM",
				"options": "UOM",
				"insert_after": "bin_capacity",
				"depends_on": is_bin,
			},
			{
				"fieldname": "bin_location_cb2",
				"fieldtype": "Column Break",
				"insert_after": "capacity_uom",
			},
			{
				"fieldname": "bin_length",
				"fieldtype": "Float",
				"label": "Length",
				"insert_after": "bin_location_cb2",
				"depends_on": is_bin,
				"non_negative": 1,
			},
			{
				"fieldname": "bin_width",
				"fieldtype": "Float",
				"label": "Width",
				"insert_after": "bin_length",
				"depends_on": is_bin,
				"non_negative": 1,
			},
			{
				"fieldname": "bin_height",
				"fieldtype": "Float",
				"label": "Height",
				"insert_after": "bin_width",
				"depends_on": is_bin,
				"non_negative": 1,
			},
			{
				"fieldname": "dimension_uom",
				"fieldtype": "Link",
				"label": "Dimension UOM",
				"options": "UOM",
				"insert_after": "bin_height",
				"depends_on": is_bin,
			},
		]
	}
