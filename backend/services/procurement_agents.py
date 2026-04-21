"""
Procurement module agent catalog.

Represents the 8 mandatory module agents in the end-to-end RFQ cycle:
Capture → Structure → Route → Supplier Interaction → Offers → Decision → Order → Feedback/Learn
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict


class ProcurementModuleAgent(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    module: str
    responsibility: str
    input_contract: str
    output_contract: str
    traceability_event: str


_PROCUREMENT_AGENTS: List[ProcurementModuleAgent] = [
    ProcurementModuleAgent(
        id="request_capture_agent",
        module="Request Capture Service",
        responsibility="Captura necesidades operativas desde planta y crea Request trazable.",
        input_contract="raw_input | attachments | guided_catalog | iot_alert",
        output_contract="Request",
        traceability_event="procurement.request.created",
    ),
    ProcurementModuleAgent(
        id="structuring_validation_agent",
        module="Structuring & Validation Engine",
        responsibility="Transforma raw_input en StructuredRequest validado y determina revisión humana.",
        input_contract="Request",
        output_contract="StructuredRequest",
        traceability_event="procurement.request.structured",
    ),
    ProcurementModuleAgent(
        id="routing_engine_agent",
        module="Routing Engine",
        responsibility="Selecciona proveedores objetivo según capacidad, SLA, localización y rating.",
        input_contract="StructuredRequest",
        output_contract="RoutingPlan",
        traceability_event="procurement.request.routed",
    ),
    ProcurementModuleAgent(
        id="supplier_interaction_agent",
        module="Supplier Interaction Service",
        responsibility="Genera y envía SupplierRequest con SLA y deadline por proveedor.",
        input_contract="RoutingPlan + StructuredRequest",
        output_contract="SupplierRequest",
        traceability_event="procurement.supplier_request.sent",
    ),
    ProcurementModuleAgent(
        id="offer_management_agent",
        module="Offer Management Engine",
        responsibility="Recibe y normaliza ofertas para comparabilidad automática.",
        input_contract="SupplierRequest responses",
        output_contract="Offer (normalized)",
        traceability_event="procurement.offer.received",
    ),
    ProcurementModuleAgent(
        id="decision_engine_agent",
        module="Decision Engine",
        responsibility="Calcula matriz de decisión y recomendación automática.",
        input_contract="Normalized Offers",
        output_contract="DecisionMatrix",
        traceability_event="procurement.decision.made",
    ),
    ProcurementModuleAgent(
        id="order_execution_agent",
        module="Order Execution Service",
        responsibility="Convierte oferta seleccionada en orden integrada y trazable.",
        input_contract="DecisionMatrix + selected_offer_id",
        output_contract="Order",
        traceability_event="procurement.order.created",
    ),
    ProcurementModuleAgent(
        id="feedback_learning_agent",
        module="Feedback & Learning Engine",
        responsibility="Cierra ciclo con feedback real y actualiza scoring del proveedor.",
        input_contract="Order execution outcome",
        output_contract="Feedback + supplier_score_update",
        traceability_event="procurement.feedback.submitted",
    ),
]


def list_procurement_agents() -> List[ProcurementModuleAgent]:
    return list(_PROCUREMENT_AGENTS)
