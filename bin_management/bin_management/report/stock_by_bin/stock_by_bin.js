// Copyright (c) 2026, akshayr11 and contributors
// For license information, please see license.txt

function location_query(location_type) {
	return () => ({
		filters: {
			company: frappe.query_report.get_filter_value("company"),
			location_type,
		},
	});
}

frappe.query_reports["Stock by Bin"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
			get_query: () => ({
				filters: { company: frappe.query_report.get_filter_value("company"), is_group: 1 },
			}),
		},
		{
			fieldname: "aisle",
			label: __("Aisle"),
			fieldtype: "Link",
			options: "Warehouse",
			get_query: location_query("Aisle"),
		},
		{
			fieldname: "rack",
			label: __("Rack"),
			fieldtype: "Link",
			options: "Warehouse",
			get_query: location_query("Rack"),
		},
		{
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item",
		},
		{
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "Link",
			options: "Item Group",
		},
		{
			fieldname: "show_empty_bins",
			label: __("Show Empty Bins"),
			fieldtype: "Check",
			default: 1,
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "bin" && data && !data.item_code && data.bin) {
			value = `<span class="text-muted">${value}</span>`;
		}
		return value;
	},
};
