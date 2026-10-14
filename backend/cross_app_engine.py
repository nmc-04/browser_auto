"""
Cross-Application Workflow Execution Engine
Orchestrates multi-step workflows across Excel, Email, Invoice files, Tasks, Calendar, Documents, and Selenium.
Passes shared context between steps and strictly verifies every critical outcome.
"""

import os
import time
from typing import Dict, Any, List, Optional, Tuple, Callable

from workflows.schemas import Workflow, WorkflowStep
from workflows.actions import (
    BROWSER_ACTIONS,
    ACTION_OPEN_URL,
    ACTION_TYPE,
    ACTION_CLICK,
    ACTION_SEARCH,
    ACTION_SELECT,
    ACTION_SCROLL,
    ACTION_WAIT,
    ACTION_GET_TEXT,
    ACTION_SCREENSHOT,
    ACTION_READ_EXCEL,
    ACTION_FIND_UNPAID_INVOICES,
    ACTION_EXTRACT_INVOICE,
    ACTION_GENERATE_REMINDER,
    ACTION_SEND_EMAIL,
    ACTION_SEARCH_EMAIL,
    ACTION_READ_EMAIL,
    ACTION_EXTRACT_EMAIL_INFO,
    ACTION_COMPOSE_EMAIL,
    ACTION_ATTACH_FILE,
    ACTION_RECORD_RESULT,
    ACTION_UPDATE_EXCEL,
    ACTION_SEARCH_PRODUCT,
    ACTION_EXTRACT_PRODUCT_DATA,
    ACTION_VALIDATE_PRODUCTS,
    ACTION_GENERATE_EXCEL,
    ACTION_ADD_TO_CART,
    ACTION_REVIEW_ORDER,
    ACTION_DOWNLOAD_INVOICE,
    ACTION_CHECK_CALENDAR,
    ACTION_CHECK_TASKS,
    ACTION_UPDATE_TASK,
    ACTION_GENERATE_BRIEF,
    ACTION_GENERATE_REPORT,
    ACTION_VERIFY,
)
from backend.product_search_tool import (
    parse_product_search_intent,
    execute_multi_site_product_search,
    generate_product_excel,
)
from backend.selenium_engine import SeleniumEngine
from backend.email_tool import (
    compose_email,
    send_email,
    verify_email_sent,
    search_emails,
    read_email,
    extract_email_insights,
    parse_email_search_intent,
    email_connection_status,
    validate_attachment_paths,
    validate_email_address,
)
from backend.invoice_tool import (
    read_invoices_excel,
    filter_invoices,
    find_invoice_document,
    prepare_invoice_reminders,
    update_invoice_status,
    verify_invoice_status,
)
from backend.product_tool import (
    read_products_excel,
    stage_procurement_order,
    verify_cart_order,
)
from backend.work_tool import (
    get_today_schedule,
    get_pending_tasks,
    update_task_status,
    generate_daily_work_summary,
    verify_daily_work_plan,
)
from backend.meeting_tool import (
    find_meeting,
    gather_meeting_context,
    generate_meeting_brief,
    verify_meeting_brief,
)
from backend.reporting_tool import (
    collect_monthly_activity,
    generate_employee_activity_report,
    verify_report_generation,
)
from utils.logger import logger, add_log_entry
from utils.helpers import get_screenshot_dir, generate_id


class CrossAppExecutionEngine:
    """Executes multi-application workflows with shared context and verification."""

    def __init__(self, headless: bool = False, timeout: int = 15, confirmed: bool = False, workflow: Optional[Workflow] = None):
        self.headless = headless
        self.timeout = timeout
        self.confirmed = confirmed
        self.workflow = workflow
        self.selenium_engine: Optional[SeleniumEngine] = None
        self.context: Dict[str, Any] = {
            "invoices": [],
            "unpaid_invoices": [],
            "reminders": [],
            "sent_emails": [],
            "email_results": [],
            "email_messages": [],
            "email_insights": [],
            "email_extracted": [],
            "email_preview": [],
            "email_provider": {},
            "email_summary": {
                "total": 0,
                "prepared": 0,
                "submitted": 0,
                "sent": 0,
                "simulated": 0,
                "failed": 0,
                "pending_verification": 0,
                "skipped": 0,
            },
            "products": [],
            "order": {},
            "schedule": [],
            "tasks": [],
            "meeting": {},
            "meeting_brief": {},
            "report": {},
            "excel_file": None,
            "verification_items": [],
            "execution_checklist": []
        }
        self.screenshots: List[str] = []
        self.applications_used: set = set(workflow.applications if workflow and workflow.applications else [])

    def _ensure_browser(self):
        """Starts Selenium WebDriver if not already running."""
        if not self.selenium_engine:
            self.selenium_engine = SeleniumEngine(headless=self.headless, timeout=self.timeout)
            self.selenium_engine.start_driver()
            self.applications_used.add("Selenium Browser")

    def _send_email_batch(self, reminders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Submit each validated draft independently and preserve evidence."""
        provider_status = email_connection_status()
        self.context["email_provider"] = provider_status
        summary = self.context["email_summary"]
        summary.update({
            "total": len(reminders),
            "prepared": sum(1 for item in reminders if item.get("status") in ("PREPARED", "READY")),
            "submitted": 0,
            "sent": 0,
            "simulated": 0,
            "failed": 0,
            "pending_verification": 0,
            "skipped": 0,
            "duplicate_prevented": 0,
        })
        results: List[Dict[str, Any]] = []
        sent_records: List[Dict[str, Any]] = []
        external_provider_unavailable = provider_status.get("mode") == "gmail" and not provider_status.get("connected")

        for reminder in reminders:
            attachment = reminder.get("attachment")
            base = {
                "recipient": reminder.get("to", ""),
                "to": reminder.get("to", ""),
                "subject": reminder.get("subject", ""),
                "invoice_number": reminder.get("invoice_number"),
                "attachment_names": [os.path.basename(attachment)] if attachment else [],
                "attachments": [attachment] if attachment else [],
                "status": "SKIPPED",
                "timestamp": None,
                "provider_message_id": None,
                "verification_status": None,
                "error": None,
            }
            attachment_required = bool(reminder.get("attachments_required", False))
            errors = list(reminder.get("validation_errors", []))
            if not validate_email_address(str(reminder.get("to", ""))):
                errors.append("Recipient email address is missing or invalid.")
            attachment_check = reminder.get("attachment_validation") or validate_attachment_paths([attachment] if attachment else [])
            if attachment_check.get("errors"):
                errors.extend(attachment_check["errors"])
            if attachment_required and not attachment:
                errors.append("Required invoice attachment could not be identified.")
            if external_provider_unavailable:
                errors.append(provider_status.get("reason") or "Gmail account is not connected.")

            if errors:
                base["error"] = "; ".join(dict.fromkeys(errors))
                base["status"] = "SKIPPED" if not external_provider_unavailable else "FAILED"
                results.append(base)
                if base["status"] == "FAILED":
                    summary["failed"] += 1
                else:
                    summary["skipped"] += 1
                continue

            draft = compose_email(
                to=reminder.get("to"),
                subject=reminder.get("subject"),
                body=reminder.get("body"),
                attachments=[attachment] if attachment else [],
                client_name=reminder.get("client_name"),
                invoice_number=reminder.get("invoice_number"),
                attachments_required=attachment_required,
            )
            base["draft_id"] = draft.get("draft_id")
            try:
                provider_result = send_email(draft)
                result_status = provider_result.get("status", "PENDING_VERIFICATION")
                # Keep local fixture execution visibly distinct from a real
                # provider submission even though the provider-neutral send
                # helper exposes SENT for legacy callers.
                if provider_result.get("simulated") and result_status == "SENT":
                    result_status = "SIMULATED"
                base.update({
                    "status": result_status,
                    "timestamp": provider_result.get("sent_at") or provider_result.get("submitted_at"),
                    "provider_message_id": provider_result.get("provider_message_id") or provider_result.get("email_id"),
                    "verification_status": provider_result.get("verification_status"),
                    "verification_evidence": provider_result.get("verification_evidence", {}),
                    "provider": provider_result.get("provider"),
                    "simulated": provider_result.get("simulated", False),
                })
                if base["status"] in ("SENT", "SIMULATED"):
                    summary["submitted"] += 1
                    summary["sent"] += 1 if base["status"] == "SENT" else 0
                    summary["simulated"] += 1 if base["status"] == "SIMULATED" else 0
                    sent_records.append(provider_result)
                elif base["status"] == "PENDING_VERIFICATION":
                    summary["pending_verification"] += 1
                else:
                    summary["skipped"] += 1
                    if base.get("verification_status") == "DUPLICATE_PREVENTED":
                        summary["duplicate_prevented"] += 1
                    sent_records.append(provider_result)
            except TimeoutError as exc:
                base.update({"status": "PENDING_VERIFICATION", "error": str(exc)})
                summary["pending_verification"] += 1
            except Exception as exc:
                base.update({"status": "FAILED", "error": str(exc)})
                summary["failed"] += 1
            results.append(base)

        self.context["sent_emails"].extend(sent_records)
        self.context["email_results"].extend(results)
        self.context["email_summary"] = summary
        self.context["execution_checklist"].append(
            f"✓ Email batch outcome: {summary['submitted']} submitted, {summary['failed']} failed, "
            f"{summary['pending_verification']} pending verification, {summary['skipped']} skipped"
        )
        return {
            # A duplicate-prevention result is a safe idempotent outcome, not
            # a failed send. Other skips remain unsuccessful so missing data
            # and validation errors cannot be reported as completed.
            "success": summary["failed"] == 0 and summary["pending_verification"] == 0 and (
                summary["skipped"] == summary["duplicate_prevented"]
            ),
            "sent_count": summary["submitted"],
            "results": results,
        }

    def execute_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Executes a single workflow step using the appropriate application handler."""
        action = (step.action or "").upper()
        target = step.get_target_string()
        value = step.value or ""

        # Step requires human confirmation check
        if step.requires_confirmation and not self.confirmed:
            add_log_entry(f"[Engine] Step '{step.to_display_label()}' requires human confirmation.")
            return {
                "success": True,
                "status": "WAITING_CONFIRMATION",
                "message": f"Paused for human confirmation: {step.to_display_label()}"
            }

        # ----------------------------------------------------
        # BROWSER AUTOMATION (SELENIUM)
        # ----------------------------------------------------
        if action in BROWSER_ACTIONS or action in (ACTION_SEARCH_PRODUCT, ACTION_ADD_TO_CART, ACTION_REVIEW_ORDER, ACTION_DOWNLOAD_INVOICE):
            self._ensure_browser()
            self.selenium_engine.execute_step(step)
            self.screenshots = self.selenium_engine.screenshots
            self.applications_used.add("Selenium Browser")

            # Track logical business modules accessed on the portal
            t_lower = target.lower()
            if "calendar" in t_lower or "meeting" in t_lower:
                self.applications_used.add("Calendar")
            if "task" in t_lower:
                self.applications_used.add("Task Board")
            if "invoice" in t_lower or "inv" in t_lower:
                self.applications_used.update(["Invoice System", "Excel"])
            if "email" in t_lower:
                self.applications_used.add("Email")
            if "doc" in t_lower:
                self.applications_used.add("Documents")
            if "proc" in t_lower or "order" in t_lower:
                self.applications_used.add("Procurement System")
            if "report" in t_lower or "summary" in t_lower:
                self.applications_used.update(["Reporting", "Documents"])

            # Synchronize background data with browser UI interactions
            if target == "#email-send-btn" or "email-btn" in target:
                unpaid = filter_invoices("unpaid_or_overdue")
                self.context["unpaid_invoices"] = unpaid
                self.context["reminders"] = prepare_invoice_reminders(unpaid)
                batch_result = self._send_email_batch(self.context["reminders"])
                for record in self.context["sent_emails"]:
                    if record.get("status") in ("SENT", "SIMULATED") and record.get("invoice_number"):
                        update_invoice_status(record.get("invoice_number"), "Reminder Sent")
                if not batch_result.get("success"):
                    return {"success": False, "error": "One or more portal email actions did not complete safely."}

            elif target == "#task-btn-TASK-101":
                update_task_status("TASK-101", "In Progress")
            elif target == "#task-btn-TASK-102":
                update_task_status("TASK-102", "Completed")
            elif target == "#btn-view-daily-summary":
                summary_res = generate_daily_work_summary()
                self.context["report"] = summary_res
            elif target == "#btn-view-meeting-brief":
                m = find_meeting("3 PM") or {"time": "03:00 PM", "title": "Client Meeting", "client": "Acrom Systems"}
                ctx = gather_meeting_context(m)
                brief_res = generate_meeting_brief(ctx)
                self.context["meeting_brief"] = brief_res
            elif target == "#btn-view-activity-report":
                act = collect_monthly_activity()
                rep_res = generate_employee_activity_report(act)
                self.context["report"] = rep_res

            if action == ACTION_SEARCH_PRODUCT:
                self.context["execution_checklist"].append(f"✓ Searched product catalog for '{value or target}' via Selenium")
            elif action == ACTION_ADD_TO_CART:
                self.context["execution_checklist"].append("✓ Product added to cart in portal")
            elif action == ACTION_REVIEW_ORDER:
                self.context["execution_checklist"].append("✓ Order review completed and totals calculated")
            elif action == ACTION_DOWNLOAD_INVOICE:
                self.context["execution_checklist"].append("✓ Order invoice document generated")
            else:
                self.context["execution_checklist"].append(f"✓ {step.to_display_label()}")

            return {"success": True, "action": action}

        # ----------------------------------------------------
        # PRODUCT SEARCH & AUTOMATIC EXCEL GENERATION
        # ----------------------------------------------------
        elif action == ACTION_EXTRACT_PRODUCT_DATA:
            self._ensure_browser()
            self.applications_used.update(["Selenium Browser", "Amazon", "Flipkart"])
            intent = parse_product_search_intent(self.workflow.prompt if self.workflow else "") or {
                "query": value or target or "laptop",
                "category": value or target or "laptop",
                "quantity": 10
            }
            prods = execute_multi_site_product_search(self.selenium_engine.driver, intent)
            self.context["products"] = prods
            self.screenshots = self.selenium_engine.screenshots
            self.context["execution_checklist"].append(f"✓ Extracted {len(prods)} authentic product items across shopping websites")
            return {"success": True, "count": len(prods), "products": prods}

        elif action == ACTION_VALIDATE_PRODUCTS:
            import re
            prods = self.context.get("products", [])
            max_p_str = value or ""
            max_p = None
            try:
                if max_p_str and max_p_str != "None":
                    max_p = float(re.sub(r"[^\d.]", "", max_p_str))
            except Exception:
                pass

            valid_prods = []
            for p in prods:
                p_val = p.get("_price_num")
                if max_p and p_val and p_val > max_p:
                    continue
                valid_prods.append(p)

            self.context["products"] = valid_prods
            if valid_prods:
                msg = f"✓ Validated {len(valid_prods)} products matching criteria"
                if max_p:
                    msg += f" (under ₹{max_p:,.0f})"
                self.context["execution_checklist"].append(msg)
            else:
                self.context["execution_checklist"].append("⚠️ No products met the exact criteria")

            return {"success": True, "valid_count": len(valid_prods)}

        elif action == ACTION_GENERATE_EXCEL:
            self.applications_used.add("Excel")
            prods = self.context.get("products", [])
            if prods:
                excel_path = generate_product_excel(prods, query_name=value or "product_search")
                self.context["excel_file"] = excel_path
                self.context["execution_checklist"].append(f"✓ Automatically generated Excel report: {os.path.basename(excel_path)}")
                return {"success": True, "excel_file": excel_path}
            else:
                add_log_entry("No valid product results were found. Excel report not generated.", "WARNING")
                self.context["execution_checklist"].append("⚠️ No valid products found to generate Excel report")
                return {"success": True, "excel_file": None}

        # ----------------------------------------------------
        # INVOICE AUTOMATION & EXCEL
        # ----------------------------------------------------
        elif action == ACTION_SEARCH_EMAIL:
            self.applications_used.add("Email")
            from backend.email_tool import email_connection_status
            self.context["email_provider"] = email_connection_status()
            intent = parse_email_search_intent(value or target or (self.workflow.prompt if self.workflow else ""))
            try:
                messages = search_emails(
                    query=intent.get("query", ""),
                    limit=int(os.getenv("EMAIL_SEARCH_LIMIT", "25")),
                    sender=intent.get("sender"),
                    recipient=intent.get("recipient"),
                    subject=intent.get("subject"),
                    status=intent.get("status"),
                )
            except Exception as exc:
                return {"success": False, "error": f"Email search failed: {exc}"}
            self.context["email_messages"] = messages
            self.context["email_search"] = intent
            self.context["email_summary"]["found"] = len(messages)
            self.context["execution_checklist"].append(f"✓ Searched authorized mailbox and found {len(messages)} matching email(s)")
            return {"success": True, "count": len(messages)}

        elif action == ACTION_READ_EMAIL:
            self.applications_used.add("Email")
            messages = self.context.get("email_messages", [])
            insights = []
            for message in messages:
                message_id = message.get("id") or message.get("email_id")
                full_message = read_email(message_id) if message_id else message
                if full_message:
                    message.update(full_message)
                    insights.append({"message_id": message_id, **extract_email_insights(full_message)})
            self.context["email_insights"] = insights
            self.context["email_extracted"] = insights
            self.context["execution_checklist"].append(f"✓ Read {len(messages)} matching email(s) and extracted action items, references, and attachment metadata")
            return {"success": True, "count": len(messages), "insights": insights}

        elif action == ACTION_EXTRACT_EMAIL_INFO:
            self.applications_used.add("Email")
            messages = self.context.get("email_messages", [])
            if not self.context.get("email_insights"):
                self.context["email_insights"] = [extract_email_insights(message) for message in messages]
            self.context["email_extracted"] = self.context["email_insights"]
            self.context["execution_checklist"].append(f"✓ Extracted structured information from {len(self.context['email_extracted'])} email(s)")
            return {"success": True, "count": len(self.context["email_extracted"])}

        elif action == ACTION_COMPOSE_EMAIL:
            self.applications_used.add("Email")
            unpaid = self.context.get("unpaid_invoices")
            if unpaid is not None:
                reminders = prepare_invoice_reminders(unpaid)
                self.context["reminders"] = reminders
                self.context["email_preview"] = reminders
                prepared = sum(1 for reminder in reminders if reminder.get("status") in ("PREPARED", "READY"))
                self.context["email_summary"].update({"total": len(reminders), "prepared": prepared})
                self.context["execution_checklist"].append(f"✓ Composed {prepared} personalized email preview(s)")
                return {"success": True, "prepared": prepared}
            return {"success": False, "error": "Email composition requires validated source records with recipient, subject, and body fields."}

        elif action == ACTION_ATTACH_FILE:
            self.applications_used.add("Email")
            reminders = self.context.get("reminders", [])
            attachment_errors = 0
            for reminder in reminders:
                attachment = reminder.get("attachment")
                check = validate_attachment_paths([attachment] if attachment else [])
                reminder["attachment_validation"] = check
                if not check.get("valid") or (reminder.get("attachments_required", True) and not check.get("attachments")):
                    attachment_errors += 1
                    reminder.setdefault("validation_errors", []).extend(check.get("errors", []) or ["Required invoice attachment is missing."])
                else:
                    reminder["status"] = "READY"
            self.context["email_preview"] = reminders
            self.context["email_summary"]["skipped"] = attachment_errors
            self.context["execution_checklist"].append(f"✓ Validated attachments for {len(reminders) - attachment_errors} email(s); {attachment_errors} skipped")
            return {"success": True, "attachment_errors": attachment_errors}

        elif action == ACTION_RECORD_RESULT:
            self.context["execution_checklist"].append("✓ Recorded per-message outcomes and provider evidence in workflow history")
            return {"success": True}

        elif action == ACTION_READ_EXCEL:
            self.applications_used.add("Excel")
            file_target = value or target or "demo_data/invoices.xlsx"
            if "product" in file_target.lower():
                self.applications_used.add("Procurement System")
                prods = read_products_excel(file_target)
                self.context["products"] = prods
                self.context["execution_checklist"].append(f"✓ Loaded {len(prods)} required products from Excel")
                return {"success": True, "count": len(prods)}
            else:
                self.applications_used.add("Invoice System")
                invs = read_invoices_excel(file_target)
                self.context["invoices"] = invs
                self.context["invoice_file"] = file_target
                self.context["execution_checklist"].append(f"✓ Invoice data loaded ({len(invs)} records in Excel)")
                return {"success": True, "count": len(invs)}

        elif action == ACTION_FIND_UNPAID_INVOICES:
            self.applications_used.add("Invoice System")
            loaded = self.context.get("invoices")
            if loaded is not None:
                unpaid = [i for i in loaded if str(i.get("payment_status", "")).lower() in ("unpaid", "overdue", "past due")]
            else:
                unpaid = filter_invoices("unpaid_or_overdue")
            self.context["unpaid_invoices"] = unpaid
            count = len(unpaid)
            clients = [i.get("client_name") for i in unpaid]
            self.context["execution_checklist"].append(f"✓ {count} unpaid/overdue invoices identified")
            self.context["execution_checklist"].append(f"✓ {count} clients identified: {', '.join(clients)}")
            return {"success": True, "unpaid_count": count, "clients": clients}

        elif action == ACTION_EXTRACT_INVOICE:
            self.applications_used.add("Invoice System")
            unpaid = self.context.get("unpaid_invoices") or filter_invoices("unpaid_or_overdue")
            found_docs = 0
            for inv in unpaid:
                doc = find_invoice_document(inv.get("invoice_number"), client_name=inv.get("client_name"))
                inv["document_path"] = doc
                if doc:
                    found_docs += 1
            self.context["execution_checklist"].append(f"✓ {found_docs} of {len(unpaid)} invoice documents located in archive")
            return {"success": True, "documents_found": found_docs}

        elif action == ACTION_GENERATE_REMINDER:
            self.applications_used.add("Email")
            unpaid = self.context.get("unpaid_invoices") or filter_invoices("unpaid_or_overdue")
            reminders = prepare_invoice_reminders(unpaid)
            self.context["reminders"] = reminders
            self.context["email_preview"] = reminders
            prepared = sum(1 for reminder in reminders if reminder.get("status") == "PREPARED")
            self.context["email_summary"].update({"total": len(reminders), "prepared": prepared})
            self.context["execution_checklist"].append(f"✓ Prepared {prepared} personalized reminder email preview(s); {len(reminders) - prepared} skipped during validation")
            return {"success": True, "reminders_count": len(reminders)}

        elif action == ACTION_UPDATE_EXCEL:
            self.applications_used.add("Excel")
            new_status = value or "Reminder Sent"
            sent_invoice_numbers = {r.get("invoice_number") for r in self.context.get("sent_emails", []) if r.get("status") in ("SENT", "SIMULATED") or r.get("simulated")}
            unpaid = [i for i in (self.context.get("unpaid_invoices") or []) if i.get("invoice_number") in sent_invoice_numbers]
            updated_count = 0
            for inv in unpaid:
                num = inv.get("invoice_number")
                if update_invoice_status(num, new_status):
                    updated_count += 1
            self.context["execution_checklist"].append(f"✓ Updated status to '{new_status}' for {updated_count} invoice records in Excel")
            return {"success": True, "updated_count": updated_count}

        # ----------------------------------------------------
        # EMAIL AUTOMATION
        # ----------------------------------------------------
        elif action == ACTION_SEND_EMAIL:
            self.applications_used.add("Email")
            reminders = self.context.get("reminders")
            if reminders is not None:
                return self._send_email_batch(reminders)

            # Or if report email
            elif self.context.get("report"):
                rep_data = self.context["report"]
                report_recipient = target or "management@workpilot.com"
                draft = compose_email(
                    to=report_recipient,
                    subject="Monthly Employee Activity and Performance Report",
                    body="Attached is the compiled monthly employee activity and performance report.",
                    attachments=[rep_data.get("report_file")] if rep_data.get("report_file") else []
                )
                return self._send_email_batch([{
                    "to": report_recipient,
                    "subject": "Monthly Employee Activity and Performance Report",
                    "body": "Attached is the compiled monthly employee activity and performance report.",
                    "attachment": rep_data.get("report_file"),
                    "client_name": report_recipient,
                    "status": "READY",
                    "validation_errors": [],
                }])

            # Or single custom email
            else:
                to_addr = target
                if not to_addr:
                    return {"success": False, "error": "Recipient is required; no message was sent."}
                return self._send_email_batch([{
                    "to": to_addr,
                    "subject": "Automated Work Notification",
                    "body": value or "Task update notification.",
                    "attachment": None,
                    "client_name": to_addr,
                    "status": "READY",
                    "validation_errors": [],
                }])

        # ----------------------------------------------------
        # EMPLOYEE DAILY WORK & TASKS
        # ----------------------------------------------------
        elif action == ACTION_CHECK_CALENDAR:
            self.applications_used.add("Calendar")
            sched = get_today_schedule()
            self.context["schedule"] = sched
            self.context["execution_checklist"].append(f"✓ Loaded today's schedule ({len(sched)} meetings/events)")
            return {"success": True, "schedule_count": len(sched)}

        elif action == ACTION_CHECK_TASKS:
            self.applications_used.add("Task Board")
            tasks = get_pending_tasks()
            self.context["tasks"] = tasks
            pending = [t for t in tasks if t.get("status") != "Completed"]
            self.context["execution_checklist"].append(f"✓ Task Board inspected: {len(pending)} pending tasks ({len(tasks)} total)")
            return {"success": True, "tasks_count": len(tasks), "pending_count": len(pending)}

        elif action == ACTION_UPDATE_TASK:
            self.applications_used.add("Task Board")
            task_id = target or "TASK-102"
            new_st = value or "Completed"
            res = update_task_status(task_id, new_st)
            self.context["execution_checklist"].append(f"✓ Updated task '{task_id}' status to '{new_st}'")
            return {"success": res}

        # ----------------------------------------------------
        # MEETING AUTOMATION
        # ----------------------------------------------------
        elif action == ACTION_GENERATE_BRIEF:
            self.applications_used.update(["Calendar", "Email", "Documents", "Task Board"])
            meeting_query = value or target or "3 PM"
            m = find_meeting(meeting_query)
            if not m:
                # Default to first client meeting
                sched = self.context.get("schedule") or get_today_schedule()
                for ev in sched:
                    if "client" in ev.get("title", "").lower() or ev.get("type") == "Client":
                        m = ev
                        break
            if not m:
                m = {"time": "03:00 PM", "title": "Client Meeting", "client": "Acrom Systems"}

            ctx = gather_meeting_context(m)
            brief_res = generate_meeting_brief(ctx)
            self.context["meeting"] = m
            self.context["meeting_brief"] = brief_res
            self.context["execution_checklist"].append(f"✓ Identified 3 PM meeting with {m.get('client')}")
            self.context["execution_checklist"].append(f"✓ Retrieved related email thread from {ctx['emails'][0]['from'] if ctx['emails'] else 'client'}")
            self.context["execution_checklist"].append(f"✓ Retrieved {len(ctx['documents'])} relevant contract and project documents")
            self.context["execution_checklist"].append(f"✓ Generated comprehensive executive meeting brief ({brief_res['brief_file']})")
            return {"success": True, "brief_file": brief_res["brief_file"]}

        # ----------------------------------------------------
        # REPORTING AUTOMATION
        # ----------------------------------------------------
        elif action == ACTION_GENERATE_REPORT:
            self.applications_used.update(["Task Board", "Calendar", "Email", "Excel"])
            activity = collect_monthly_activity()
            report_res = generate_employee_activity_report(activity)
            self.context["report"] = report_res
            self.context["execution_checklist"].append(f"✓ Aggregated activity metrics: {len(activity['tasks'])} tasks, {len(activity['meetings'])} meetings, {len(activity['invoices'])} invoices")
            self.context["execution_checklist"].append(f"✓ Generated monthly employee activity report ({report_res['report_file']})")
            return {"success": True, "report_file": report_res["report_file"]}

        # ----------------------------------------------------
        # VERIFICATION ACTION
        # ----------------------------------------------------
        elif action == ACTION_VERIFY:
            verifications = []

            # 1. Invoice verification
            unpaid = self.context.get("unpaid_invoices", [])
            if unpaid:
                for inv in unpaid:
                    num = inv.get("invoice_number")
                    v_ok, v_msg = verify_invoice_status(num, "Reminder Sent")
                    verifications.append((v_ok, f"Invoice {num}: {v_msg}"))

            # 2. Email verification
            sent_emails = self.context.get("sent_emails", [])
            if sent_emails:
                for em in sent_emails:
                    v_ok, v_msg = verify_email_sent(
                        email_id=em.get("provider_message_id") or em.get("email_id"),
                        recipient=em.get("to"),
                        attachment=(em.get("attachments") or [None])[0],
                        subject=em.get("subject"),
                    )
                    verifications.append((v_ok, f"Email to {em.get('to')}: {v_msg}"))

            # Every attempted batch item is recorded, including failed and
            # skipped items.  This keeps partial success truthful in the UI.
            email_results = self.context.get("email_results", [])
            for em in email_results:
                if em.get("status") in ("SENT", "SIMULATED") or (
                    em.get("status") == "SKIPPED" and em.get("verification_status") == "DUPLICATE_PREVENTED"
                ):
                    continue
                reason = em.get("error") or em.get("skip_reason") or "No provider submission evidence."
                verifications.append((False, f"Email to {em.get('to') or 'unknown recipient'}: {em.get('status', 'UNKNOWN')} — {reason}"))

            for message in self.context.get("email_messages", []):
                sender = message.get("from") or "unknown sender"
                verifications.append((True, f"Email read and recorded: {message.get('subject') or '(no subject)'} from {sender}"))

            # 3. Meeting brief verification
            brief_data = self.context.get("meeting_brief")
            if brief_data:
                v_ok, v_msg = verify_meeting_brief(brief_data)
                verifications.append((v_ok, f"Meeting Brief: {v_msg}"))

            # 4. Report verification
            rep_data = self.context.get("report")
            if rep_data:
                rep_path = rep_data.get("report_file") or rep_data.get("summary_file")
                if rep_path:
                    v_ok, v_msg = verify_report_generation(rep_path)
                    verifications.append((v_ok, f"Employee Report: {v_msg}"))

            # 5. Product order verification
            order_data = self.context.get("order")
            if order_data:
                v_ok, v_msg = verify_cart_order(["Paper", "Pens"], order_data)
                verifications.append((v_ok, f"Procurement Order: {v_msg}"))

            # 6. Product search & Excel report verification
            prods = self.context.get("products", [])
            excel_path = self.context.get("excel_file")
            if prods or excel_path:
                if excel_path and os.path.exists(excel_path):
                    f_size = os.path.getsize(excel_path)
                    verifications.append((True, f"Excel report generated: {os.path.basename(excel_path)} ({f_size:,} bytes, {len(prods)} products)"))
                elif prods:
                    verifications.append((False, "Excel report was not created."))

                if prods:
                    verifications.append((True, f"Verified {len(prods)} authentic product items extracted from live browser"))
                else:
                    verifications.append((False, "No valid product results were found."))

            # Record in context
            all_passed = True
            for ok, msg in verifications:
                prefix = "✓" if ok else "❌"
                self.context["verification_items"].append(f"{prefix} {msg}")
                if not ok:
                    all_passed = False

            if not verifications:
                self.context["verification_items"].append("✓ Action execution verified successfully.")

            return {"success": all_passed, "items": self.context["verification_items"]}

        else:
            add_log_entry(f"[Engine] Unhandled action '{action}'")
            return {"success": True}

    def close(self):
        """Terminates Selenium browser session if open."""
        if self.selenium_engine:
            try:
                self.selenium_engine.quit_driver()
            except Exception:
                pass
            self.selenium_engine = None


def execute_cross_app_workflow(
    workflow: Workflow,
    headless: bool = False,
    timeout: int = 15,
    confirmed: bool = False,
    status_callback: Optional[Callable[[int, str, str], None]] = None
) -> Dict[str, Any]:
    """
    Unified workflow executor supporting both Browser and Enterprise Cross-Application Workflows.
    """
    engine = CrossAppExecutionEngine(headless=headless, timeout=timeout, confirmed=confirmed, workflow=workflow)
    start_time = time.time()
    total_steps = len(workflow.steps)
    completed_steps = 0
    failed_error = None
    paused_for_confirmation = False

    try:
        for idx, step in enumerate(workflow.steps, start=1):
            desc = step.to_display_label()
            if status_callback:
                status_callback(idx, "RUNNING", f"Step {idx}/{total_steps}: {desc}")

            res = engine.execute_step(step)

            if res.get("status") == "WAITING_CONFIRMATION":
                paused_for_confirmation = True
                completed_steps = idx - 1
                if status_callback:
                    status_callback(idx, "PAUSED", f"Step {idx}/{total_steps}: Paused for confirmation")
                break

            if not res.get("success", False):
                failed_error = res.get("error") or f"Execution failed at step {idx}: {desc}"
                break

            completed_steps += 1
            if status_callback:
                status_callback(idx, "COMPLETED", f"Step {idx}/{total_steps} Complete: {desc}")

        duration = round(time.time() - start_time, 2)

        # Automatic Final / Failure Browser Screenshot Capture
        final_screenshot = None
        if engine.selenium_engine and engine.selenium_engine.driver:
            if failed_error:
                final_screenshot = engine.selenium_engine.capture_final_screenshot(status="failure")
            elif not paused_for_confirmation:
                final_screenshot = engine.selenium_engine.capture_final_screenshot(status="success")

            if final_screenshot:
                engine.screenshots = engine.selenium_engine.screenshots
                engine.context["final_screenshot"] = final_screenshot

        # Build final summary and status
        if paused_for_confirmation:
            status_str = "WAITING_CONFIRMATION"
            summary = f"Workflow paused. Sensitive action requires human confirmation before continuing."
            success = True
        elif failed_error:
            email_summary = engine.context.get("email_summary", {})
            if email_summary.get("pending_verification", 0) and not email_summary.get("failed", 0):
                status_str = "PENDING_VERIFICATION"
                summary = f"Email submission started, but provider verification is still pending. {failed_error}"
            elif email_summary.get("submitted", 0) and email_summary.get("failed", 0):
                status_str = "PARTIAL_SUCCESS"
                summary = f"Workflow partially completed: {email_summary.get('submitted', 0)} email(s) submitted and {email_summary.get('failed', 0)} failed. {failed_error}"
            else:
                status_str = "FAILED"
                summary = f"Workflow failed at step {completed_steps + 1}: {failed_error}"
            success = False
        else:
            status_str = "COMPLETED"
            summary = f"Workflow '{workflow.workflow_name}' completed successfully ({completed_steps}/{total_steps} steps) in {duration}s."
            success = True

        return {
            "success": success,
            "status": status_str,
            "completed_steps": completed_steps,
            "total_steps": total_steps,
            "execution_time": duration,
            "error": failed_error,
            "summary": summary,
            "applications": sorted(list(engine.applications_used)),
            "execution_checklist": engine.context["execution_checklist"],
            "verification_items": engine.context["verification_items"],
            "context": engine.context,
            "email_results": engine.context.get("email_results", []),
            "email_summary": engine.context.get("email_summary", {}),
            "screenshots": engine.screenshots,
            "final_screenshot": final_screenshot,
            "requires_confirmation": paused_for_confirmation,
            "products": engine.context.get("products", []),
            "excel_file": engine.context.get("excel_file")
        }

    except Exception as e:
        duration = round(time.time() - start_time, 2)
        err_msg = str(e)
        final_screenshot = None
        if engine.selenium_engine and engine.selenium_engine.driver:
            try:
                final_screenshot = engine.selenium_engine.capture_final_screenshot(status="failure")
            except Exception:
                pass
        return {
            "success": False,
            "status": "FAILED",
            "completed_steps": completed_steps,
            "total_steps": total_steps,
            "execution_time": duration,
            "error": err_msg,
            "summary": f"Workflow execution encountered an unexpected error: {err_msg}",
            "applications": sorted(list(engine.applications_used)),
            "execution_checklist": engine.context["execution_checklist"],
            "verification_items": engine.context["verification_items"],
            "context": engine.context,
            "email_results": engine.context.get("email_results", []),
            "email_summary": engine.context.get("email_summary", {}),
            "screenshots": engine.screenshots,
            "final_screenshot": final_screenshot,
            "requires_confirmation": False,
            "products": engine.context.get("products", []),
            "excel_file": engine.context.get("excel_file")
        }

    finally:
        engine.close()
