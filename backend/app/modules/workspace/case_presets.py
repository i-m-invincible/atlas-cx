"""Starter templates copied into ordinary workspace configuration drafts."""

from typing import Literal

from pydantic import BaseModel

from app.modules.cases.schemas import Category, Definition, FieldDefinition
from app.modules.workspace.case_configuration import default_definition

PresetKey = Literal["saas", "service_business", "ecommerce", "education", "subscription"]


class CasePreset(BaseModel):
    key: PresetKey
    label: str
    definition: Definition


def starter_presets() -> list[CasePreset]:
    entries: list[tuple[PresetKey, str, list[tuple[str, str]], list[tuple[str, str, bool]]]] = [
        (
            "saas",
            "SaaS",
            [
                ("access", "Access"),
                ("billing_question", "Billing question"),
                ("product_issue", "Product issue"),
            ],
            [
                ("plan_name", "Plan name", False),
                ("environment", "Environment", False),
                ("subscription_ref", "Subscription reference", False),
            ],
        ),
        (
            "service_business",
            "Service business",
            [
                ("appointment", "Appointment"),
                ("work_request", "Work request"),
                ("service_complaint", "Service complaint"),
            ],
            [
                ("service_ref", "Service reference", False),
                ("appointment_date", "Appointment date", True),
            ],
        ),
        (
            "ecommerce",
            "E-commerce",
            [
                ("delivery_question", "Delivery question"),
                ("return_request", "Return request"),
                ("product_issue", "Product issue"),
            ],
            [("order_ref", "Order reference", False), ("item_ref", "Item reference", False)],
        ),
        (
            "education",
            "Education",
            [
                ("course_access", "Course access"),
                ("content_query", "Content query"),
                ("fee_question", "Fee question"),
            ],
            [
                ("course_ref", "Course reference", False),
                ("enrollment_ref", "Enrollment reference", False),
            ],
        ),
        (
            "subscription",
            "Subscription business",
            [
                ("renewal_question", "Renewal question"),
                ("access", "Access"),
                ("cancellation_request", "Cancellation request"),
            ],
            [
                ("subscription_ref", "Subscription reference", False),
                ("renewal_date", "Renewal date", True),
            ],
        ),
    ]
    presets = []
    for key, label, categories, fields in entries:
        definition = default_definition()
        definition.categories = [Category(key=code, label=name) for code, name in categories]
        definition.fields = [
            FieldDefinition(
                key=code,
                label=name,
                type="date" if is_date else "string",
                portal_visible=True,
                portal_editable_on_create=True,
            )
            for code, name, is_date in fields
        ]
        presets.append(CasePreset(key=key, label=label, definition=definition))
    return presets
