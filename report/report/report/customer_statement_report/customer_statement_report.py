import frappe
from frappe.utils import today, getdate, money_in_words, flt

def execute(filters=None):
    columns = [
        {"fieldname": "posting_date", "label": "Date", "fieldtype": "Date", "width": 130},
        {"fieldname": "name", "label": "Voucher No", "fieldtype": "Link", "options": "Sales Invoice", "width": 180},
        {"fieldname": "cost_center", "label": "Branch", "fieldtype": "Data", "width": 120},
        {"fieldname": "narration", "label": "Narration", "fieldtype": "Data", "width": 110},

        {"fieldname": "debit", "label": "Debit", "fieldtype": "Currency", "width": 110},
        {"fieldname": "credit", "label": "Credit", "fieldtype": "Currency", "width": 110},

        {"fieldname": "os_amount", "label": "O/S Amount", "fieldtype": "Currency", "width": 120},
        {"fieldname": "running_total", "label": "Running Total", "fieldtype": "Currency", "width": 130},
        {"fieldname": "ageing", "label": "Ageing (Days)", "fieldtype": "Int", "width": 130},
    ]

    condns = {"docstatus": 1}
    data = []
    address_display = None

    if filters:
        if filters.get("customer"):
            condns["customer"] = filters.customer

            address_name = frappe.db.get_value(
                "Dynamic Link",
                {
                    "link_doctype": "Customer",
                    "link_name": filters.customer,
                    "parenttype": "Address",
                },
                "parent",
            )
            if address_name:
                address_doc = frappe.get_doc("Address", address_name)
                address_display = frappe.get_attr(
                    "frappe.contacts.doctype.address.address.get_address_display"
                )(address_doc.as_dict())

        if filters.get("from_date") and filters.get("to_date"):
            condns["posting_date"] = ["between", [filters.from_date, filters.to_date]]
        elif filters.get("from_date"):
            condns["posting_date"] = [">=", filters.from_date]
        elif filters.get("to_date"):
            condns["posting_date"] = ["<=", filters.to_date]

    fields = [
        "name",
        "posting_date",
        "grand_total",
        "outstanding_amount",
        "cost_center",
        "customer",
        "customer_name",
        "is_return",
    ]

    meta = frappe.get_meta("Sales Invoice")
    if meta.has_field("custom_job_record"):
        fields.append("custom_job_record")
    if meta.has_field("custom_warehouse_job_record"):
        fields.append("custom_warehouse_job_record")

    condns["outstanding_amount"] = ["!=", 0]

    invoices = frappe.get_all(
        "Sales Invoice",
        filters=condns,
        fields=fields,
        order_by="posting_date",
    )

    if not invoices:
        return columns, []

    as_of_date = today()

    ageing = {
        "ageing_30": 0,
        "ageing_60": 0,
        "ageing_90": 0,
        "ageing_120": 0,
        "ageing_150": 0,
        "ageing_180": 0,
        "ageing_plus": 0,
    }

    running_total = 0
    total_debit = 0
    total_credit = 0
    net_balance = 0

    for idx, inv in enumerate(invoices):
        posting_date = inv.get("posting_date")
        os_amount = flt(inv.get("outstanding_amount"))
        grand_total = flt(inv.get("grand_total"))
        is_return = inv.get("is_return")

        inv["narration"] = (
            inv.get("custom_job_record")
            or inv.get("custom_warehouse_job_record")
            or ""
        )

        if is_return:
            inv["debit"] = 0
            inv["credit"] = abs(grand_total)
            effect = -abs(os_amount)
            total_credit += abs(grand_total)
        else:
            inv["debit"] = grand_total
            inv["credit"] = 0
            effect = os_amount
            total_debit += grand_total

        running_total += effect
        net_balance += effect

        inv["os_amount"] = os_amount
        inv["running_total"] = running_total

        if posting_date:
            age = (getdate(as_of_date) - getdate(posting_date)).days
        else:
            age = 0

        inv["ageing"] = age

        amt = abs(os_amount)
        if age < 30:
            ageing["ageing_30"] += amt
        elif age < 60:
            ageing["ageing_60"] += amt
        elif age < 90:
            ageing["ageing_90"] += amt
        elif age < 120:
            ageing["ageing_120"] += amt
        elif age < 150:
            ageing["ageing_150"] += amt
        elif age < 180:
            ageing["ageing_180"] += amt
        else:
            ageing["ageing_plus"] += amt

        if idx == 0 and address_display:
            inv["primary_address"] = address_display

    data.extend(invoices)

    data.append({
        "narration": "TOTAL",
        "debit": total_debit,
        "credit": total_credit,
        "os_amount": net_balance,
        "running_total": net_balance,
        "ageing": "",
        "amount_in_words": money_in_words(net_balance, "SAR") if net_balance else "",
        "primary_address": address_display,
        "customer": invoices[0]["customer"],
        "customer_name": invoices[0]["customer_name"],
        **ageing
    })

    return columns, data
