// Copyright (c) 2026, akshayr11 and contributors
// For license information, please see license.txt

const LAYOUT_FIELDS = [
	"name_prefix",
	"aisle_from",
	"aisle_to",
	"rack_from",
	"rack_to",
	"shelf_from",
	"shelf_to",
	"bin_from",
	"bin_to",
];

frappe.ui.form.on("Bin Layout Generator", {
	setup(frm) {
		frm.set_query("warehouse", () => ({
			filters: { company: frm.doc.company, is_group: 1, disabled: 0 },
		}));
	},

	onload(frm) {
		apply_route_options(frm);
	},

	refresh(frm) {
		apply_route_options(frm);
		frm.disable_save();
		frm.page.set_primary_action(__("Generate Layout"), () => generate(frm));
		render_preview(frm);
	},

	company(frm) {
		if (frm.doc.warehouse) frm.set_value("warehouse", null);
		render_preview(frm);
	},

	async warehouse(frm) {
		if (!frm.doc.warehouse) return;
		const { message } = await frappe.db.get_value("Warehouse", frm.doc.warehouse, [
			"company",
			"warehouse_name",
		]);
		if (message.company && message.company !== frm.doc.company) {
			frm.doc.company = message.company;
			frm.refresh_field("company");
		}
		frm.set_value("name_prefix", message.warehouse_name);
	},
});

LAYOUT_FIELDS.forEach((field) => {
	frappe.ui.form.on("Bin Layout Generator", field, render_preview);
});

function apply_route_options(frm) {
	if (frappe.route_options?.warehouse) {
		const warehouse = frappe.route_options.warehouse;
		frappe.route_options = null;
		frm.set_value("warehouse", warehouse);
	}
}

function span(from, to) {
	return to >= from && from > 0 ? to - from + 1 : 0;
}

function pad(value, width) {
	return String(value).padStart(width, "0");
}

function render_preview(frm) {
	const d = frm.doc;
	const a_from = (d.aisle_from || "").toUpperCase();
	const a_to = (d.aisle_to || "").toUpperCase();
	const aisles = a_from && a_to ? span(a_from.charCodeAt(0) - 64, a_to.charCodeAt(0) - 64) : 0;
	const racks = aisles * span(d.rack_from, d.rack_to);
	const shelves = racks * span(d.shelf_from, d.shelf_to);
	const bins = shelves * span(d.bin_from, d.bin_to);
	const total = aisles + racks + shelves + bins;

	let html = `<p class="text-muted">${__("Fill in the ranges to see what will be created.")}</p>`;
	if (bins) {
		const code = [
			a_from,
			pad(d.rack_from, Math.max(2, String(d.rack_to).length)),
			pad(d.shelf_from, String(d.shelf_to).length),
			pad(d.bin_from, String(d.bin_to).length),
		].join("-");
		const name = d.name_prefix ? `${d.name_prefix}-${code}` : code;
		html = `
			<p><b>${aisles}</b> ${__("aisles")} &middot; <b>${racks}</b> ${__("racks")} &middot;
			<b>${shelves}</b> ${__("shelves")} &middot; <b>${bins}</b> ${__("bins")}
			&mdash; <b>${total}</b> ${__("warehouses in all")}</p>
			<p class="text-muted">${__("First bin")}: <code>${frappe.utils.escape_html(name)}</code></p>`;
	}
	frm.get_field("preview").$wrapper.html(html);
}

function generate(frm) {
	frappe.confirm(__("Create the warehouse tree under {0}?", [frm.doc.warehouse.bold()]), async () => {
		const { message } = await frm.call({ method: "generate", doc: frm.doc, freeze: true });
		if (!message) return;
		if (message.queued) {
			frappe.show_alert({
				message: __("Creating {0} warehouses in the background. You will be notified when done.", [
					message.total,
				]),
				indicator: "blue",
			});
			frappe.realtime.off("bin_layout_generated");
			frappe.realtime.on("bin_layout_generated", (result) => show_result(frm, result));
		} else {
			show_result(frm, message);
		}
	});
}

function show_result(frm, result) {
	frappe.hide_progress();
	frappe.msgprint({
		title: __("Bin Layout Generated"),
		indicator: "green",
		message: __("{0} warehouses created, {1} already existed.", [result.created, result.existing]),
		primary_action: {
			label: __("View Warehouse Tree"),
			action: () => frappe.set_route("Tree", "Warehouse"),
		},
	});
}
