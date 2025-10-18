# -*- coding: utf-8 -*-
# Copyright (c) 2017, Direction and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, erpnext
from frappe.utils import flt, cstr, nowdate, comma_and
from frappe import throw, msgprint, _
def pe_before_submit(self, method):
	if self.mode_of_payment == "Receivable Cheque" and self.payment_type == "Receive":
		notes_acc = frappe.db.get_value("Company", self.company, "receivable_notes_account")
		if not notes_acc:
			frappe.throw(_("Receivable Notes Account not defined in the company setup page"))
		rec_acc = frappe.db.get_value("Company", self.company, "default_receivable_account")
		if not rec_acc:
			frappe.throw(_("Default Receivable Account not defined in the company setup page"))
		self.db_set("paid_to", notes_acc)
		self.db_set("paid_from", rec_acc)
	if self.mode_of_payment == "Payable Cheque" and self.payment_type == "Pay":
		notes_acc = frappe.db.get_value("Company", self.company, "payable_notes_account")
		if not notes_acc:
			frappe.throw(_("Payable Notes Account not defined in the company setup page"))
		rec_acc = frappe.db.get_value("Company", self.company, "default_payable_account")
		if not rec_acc:
			frappe.throw(_("Default Payable Account not defined in the company setup page"))
		self.db_set("paid_from", notes_acc)
		self.db_set("paid_to", rec_acc)

def pe_on_submit(self, method):
	import frappe
	from frappe import _
	from frappe.utils import nowdate, comma_and
	import erpnext

	hh_currency = erpnext.get_company_currency(self.company)

	# --- Validate Currency ---
	if self.mode_of_payment == "Cheque":
		if self.paid_from_account_currency != hh_currency:
			frappe.throw(_("You cannot use foreign currencies with Mode of Payment Cheque"))
		if self.paid_to_account_currency != hh_currency:
			frappe.throw(_("You cannot use foreign currencies with Mode of Payment Cheque"))

	# --- Handle Received Cheques ---
	if self.mode_of_payment == "Cheque" and self.payment_type == "Receive":
		notes_acc = frappe.db.get_value("Company", self.company, "receivable_notes_account")
		if not notes_acc:
			frappe.throw(_("Receivable Notes Account not defined in the Company setup page"))

		self.db_set("paid_to", notes_acc)

		rec_acc = frappe.db.get_value("Company", self.company, "default_receivable_account")
		if not rec_acc:
			frappe.throw(_("Default Receivable Account not defined in the Company setup page"))

		# Create Receivable Cheque
		rc = frappe.new_doc("Receivable Cheques")
		rc.flags.ignore_permissions = True
		rc.flags.ignore_mandatory = True
		rc.flags.ignore_links = True
		rc.flags.ignore_validate = True
		rc.flags.ignore_workflow = True
		rc.flags.ignore_validate_update_after_submit = True

		rc.cheque_no = self.reference_no
		rc.cheque_date = self.reference_date
		rc.customer = self.party
		rc.company = self.company
		rc.payment_entry = self.name
		if self.project:
			rc.project = self.project
		rc.currency = hh_currency
		rc.amount = self.base_received_amount
		rc.exchange_rate = 1
		rc.remarks = self.remarks

		# Add initial status history only (not workflow)
		rc.set("status_history", [
			{
				"status": "Cheque Received",
				"transaction_date": nowdate(),
				"credit_account": rec_acc,
				"debit_account": notes_acc
			}
		])

		# 🚀 Insert and submit without triggering workflow transitions
		rc.insert(ignore_permissions=True, ignore_links=True, ignore_mandatory=True)
		rc.flags.ignore_workflow = True
		rc.submit()

		# ✅ Update workflow_state manually (after submit)
		if frappe.db.has_column("Receivable Cheques", "workflow_state"):
			frappe.db.set_value("Receivable Cheques", rc.name, "workflow_state", "Cheque Received")

		message = """<a href="#Form/Receivable Cheques/{0}" target="_blank">{1}</a>""".format(rc.name, rc.name)
		frappe.msgprint(_("Receivable Cheque {0} created").format(comma_and(message)))

	# --- Handle Payable Cheques ---
	if self.mode_of_payment == "Cheque" and self.payment_type == "Pay":
		notes_acc = frappe.db.get_value("Company", self.company, "payable_notes_account")
		if not notes_acc:
			frappe.throw(_("Payable Notes Account not defined in the Company setup page"))

		self.db_set("paid_from", notes_acc)

		rec_acc = frappe.db.get_value("Company", self.company, "default_payable_account")
		if not rec_acc:
			frappe.throw(_("Default Payable Account not defined in the Company setup page"))

		# Create Payable Cheque
		pc = frappe.new_doc("Payable Cheques")
		pc.flags.ignore_permissions = True
		pc.flags.ignore_mandatory = True
		pc.flags.ignore_links = True
		pc.flags.ignore_validate = True
		pc.flags.ignore_workflow = True
		pc.flags.ignore_validate_update_after_submit = True

		pc.cheque_no = self.reference_no
		pc.cheque_date = self.reference_date
		pc.party_type = self.party_type
		pc.party = self.party
		pc.company = self.company
		pc.payment_entry = self.name
		if self.project:
			pc.project = self.project
		pc.currency = hh_currency
		pc.amount = self.base_paid_amount
		pc.exchange_rate = 1
		pc.remarks = self.remarks

		pc.set("status_history", [
			{
				"status": "Cheque Issued",
				"transaction_date": nowdate(),
				"credit_account": notes_acc,
				"debit_account": rec_acc
			}
		])

		# 🚀 Insert and submit without triggering workflow transitions
		pc.insert(ignore_permissions=True, ignore_links=True, ignore_mandatory=True)
		pc.flags.ignore_workflow = True
		pc.submit()

		# ✅ Update workflow_state manually (after submit)
		if frappe.db.has_column("Payable Cheques", "workflow_state"):
			frappe.db.set_value("Payable Cheques", pc.name, "workflow_state", "Cheque Issued")

		message = """<a href="#Form/Payable Cheques/{0}" target="_blank">{1}</a>""".format(pc.name, pc.name)
		frappe.msgprint(_("Payable Cheque {0} created").format(comma_and(message)))





def pe_on_cancel(self, method):
	if frappe.db.sql("""select name from `tabReceivable Cheques` where payment_entry=%s and docstatus<>2  
				and not cheque_status in ("Cheque Cancelled","Cheque Rejected")""" , (self.name)):
		frappe.throw(_("Cannot Cancel this Payment Entry as it is Linked with Receivable Cheque"))
	if frappe.db.sql("""select name from `tabPayable Cheques` where payment_entry=%s and docstatus<>2  
				and cheque_status<>'Cheque Cancelled'""" , (self.name)):
		frappe.throw(_("Cannot Cancel this Payment Entry as it is Linked with Payable Cheque"))
	return
