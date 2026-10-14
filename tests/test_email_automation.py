"""Focused tests for the provider-backed email workflow.

These tests use an in-memory provider and never contact Gmail or send an
external message.
"""

import os
import unittest

from backend.cross_app_engine import CrossAppExecutionEngine
from backend.email_providers import BaseEmailProvider
from backend.email_tool import (
    extract_email_information,
    search_emails,
    set_email_provider,
)
from backend.workflow_generator import generate_workflow
from workflows.schemas import Workflow, WorkflowStep


class FakeProvider(BaseEmailProvider):
    name = "Fake provider"
    mode = "mock"

    def __init__(self):
        self.sent = {}

    def connection_status(self):
        return {"provider": self.name, "mode": self.mode, "connected": True, "external_send": False}

    def search(self, query, limit=10):
        return [{"id": "m1", "from": "sender@example.com", "to": "user@example.com", "subject": query, "body": "Please review by Friday."}][:limit]

    def read(self, email_id):
        return self.search("review", 1)[0] if email_id == "m1" else None

    def send(self, draft):
        if self.sent:
            prior = next(iter(self.sent.values()))
            return {
                **prior,
                "status": "SKIPPED",
                "verification_status": "DUPLICATE_PREVENTED",
                "verification_evidence": {"provider": self.name},
            }
        result = {
            "email_id": "fake-message-1",
            "provider_message_id": "fake-message-1",
            "to": draft["to"],
            "subject": draft["subject"],
            "attachments": draft.get("attachments", []),
            "status": "SENT",
            "verification_status": "PROVIDER_ACCEPTED",
            "verification_evidence": {"provider": self.name},
        }
        self.sent[result["provider_message_id"]] = result
        return result

    def verify(self, provider_message_id, expected=None):
        return {
            "verified": provider_message_id in self.sent,
            "status": "SENT",
            "provider_message_id": provider_message_id,
            "verification_status": "PROVIDER_MESSAGE_FOUND",
            "evidence": {"provider": self.name},
        }


class TestEmailAutomation(unittest.TestCase):
    def tearDown(self):
        set_email_provider(None)

    def test_dynamic_email_workflow_contains_safe_send_gate(self):
        workflow = generate_workflow("Find all unpaid invoices from the Excel sheet and send reminder emails with the invoice attached.")
        self.assertEqual(
            [step.action for step in workflow.steps],
            ["READ_EXCEL", "FIND_UNPAID_INVOICES", "EXTRACT_INVOICE", "COMPOSE_EMAIL", "ATTACH_FILE", "SEND_EMAIL", "VERIFY", "RECORD_RESULT"],
        )
        self.assertTrue(next(step for step in workflow.steps if step.action == "SEND_EMAIL").requires_confirmation)

    def test_fixture_search_and_information_extraction(self):
        set_email_provider(None)
        results = search_emails("Sarah Jenkins client meeting")
        self.assertEqual(len(results), 1)
        details = extract_email_information(results[0])
        self.assertIn("action_items", details)
        self.assertTrue(details["action_items"])

    def test_send_requires_confirmation_and_verifies_provider_evidence(self):
        provider = FakeProvider()
        set_email_provider(provider)
        attachment = os.path.join("demo_data", "invoices", "INV-2024-001.txt")
        workflow = Workflow(
            workflow_name="Email Test",
            prompt="send a test email",
            applications=["Email"],
            steps=[WorkflowStep(step=1, action="SEND_EMAIL", requires_confirmation=True)],
        )
        engine = CrossAppExecutionEngine(confirmed=False, workflow=workflow)
        engine.context["reminders"] = [{
            "to": "test-recipient@example.com",
            "client_name": "Test Recipient",
            "invoice_number": "INV-2024-001",
            "subject": "Test reminder",
            "body": "Controlled provider test.",
            "attachment": attachment,
            "attachments_required": True,
            "status": "READY",
        }]
        paused = engine.execute_step(workflow.steps[0])
        self.assertEqual(paused["status"], "WAITING_CONFIRMATION")

        engine.confirmed = True
        sent = engine.execute_step(workflow.steps[0])
        self.assertTrue(sent["success"])
        self.assertEqual(engine.context["email_results"][0]["status"], "SENT")
        verified = engine.execute_step(WorkflowStep(step=2, action="VERIFY"))
        self.assertTrue(verified["success"])

    def test_missing_attachment_is_skipped_and_not_sent(self):
        provider = FakeProvider()
        set_email_provider(provider)
        workflow = Workflow(workflow_name="Attachment Test", prompt="send", applications=["Email"], steps=[])
        engine = CrossAppExecutionEngine(confirmed=True, workflow=workflow)
        engine.context["reminders"] = [{
            "to": "test-recipient@example.com",
            "subject": "Missing attachment",
            "body": "This must not be sent.",
            "attachment": "does-not-exist.pdf",
            "attachments_required": True,
            "status": "READY",
        }]
        result = engine.execute_step(WorkflowStep(step=1, action="SEND_EMAIL"))
        self.assertFalse(result["success"])
        self.assertEqual(engine.context["email_results"][0]["status"], "SKIPPED")
        self.assertFalse(provider.sent)

    def test_retry_is_idempotently_marked_as_duplicate_prevented(self):
        provider = FakeProvider()
        set_email_provider(provider)
        workflow = Workflow(workflow_name="Retry Test", prompt="send", applications=["Email"], steps=[])
        engine = CrossAppExecutionEngine(confirmed=True, workflow=workflow)
        engine.context["reminders"] = [{
            "to": "test-recipient@example.com",
            "subject": "Retry-safe message",
            "body": "Controlled provider test.",
            "status": "READY",
        }]

        first = engine.execute_step(WorkflowStep(step=1, action="SEND_EMAIL"))
        second = engine.execute_step(WorkflowStep(step=1, action="SEND_EMAIL"))
        self.assertTrue(first["success"])
        self.assertTrue(second["success"])
        self.assertEqual(engine.context["email_results"][-1]["verification_status"], "DUPLICATE_PREVENTED")
        self.assertEqual(engine.context["email_summary"]["duplicate_prevented"], 1)


if __name__ == "__main__":
    unittest.main()

