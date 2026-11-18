frappe.ui.form.on("Warehouse", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.is_group || frm.doc.location_type === "Bin") return;

		frm.add_custom_button(__("Generate Bin Layout"), () => {
			frappe.route_options = { warehouse: frm.doc.name };
			frappe.set_route("Form", "Bin Layout Generator");
		});
	},
});
