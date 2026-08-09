import json
from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.models.user import (
    DigitalTwinNode, DigitalTwinNodeType, DigitalTwinReasoningExample,
    DigitalTwinRelationship, DigitalTwinRule, DigitalTwinRuleCategory,
    DigitalTwinValidationIssue, Project, Task, TaskControl,
    TaskDependency, TaskMaterialSpecification,
)


def _json_dumps(value: dict | list | None) -> str | None:
    if not value:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_loads(value: str | None) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except json.JSONDecodeError:
        return {"raw": value}


def _node_payload(node: DigitalTwinNode) -> dict:
    return {
        "id": node.id,
        "uid": node.uid,
        "project_id": node.project_id,
        "node_type": node.node_type.value if node.node_type else None,
        "code": node.code,
        "name": node.name,
        "description": node.description,
        "source_table": node.source_table,
        "source_id": node.source_id,
        "discipline": node.discipline,
        "zone": node.zone,
        "floor": node.floor,
        "revision": node.revision,
        "status": node.status,
        "metadata": _json_loads(node.metadata_json),
        "created_at": node.created_at,
        "updated_at": node.updated_at,
    }


def _relationship_payload(edge: DigitalTwinRelationship) -> dict:
    return {
        "id": edge.id,
        "relationship_uid": edge.relationship_uid,
        "project_id": edge.project_id,
        "from_node_id": edge.from_node_id,
        "to_node_id": edge.to_node_id,
        "from_uid": edge.from_node.uid if edge.from_node else None,
        "to_uid": edge.to_node.uid if edge.to_node else None,
        "relationship_type": edge.relationship_type,
        "relationship_name": edge.relationship_name,
        "reason": edge.reason,
        "rule_reference": edge.rule_reference,
        "confidence": edge.confidence,
        "metadata": _json_loads(edge.metadata_json),
        "created_at": edge.created_at,
        "updated_at": edge.updated_at,
    }


def _rule_payload(rule: DigitalTwinRule) -> dict:
    return {
        "id": rule.id,
        "rule_uid": rule.rule_uid,
        "project_id": rule.project_id,
        "category": rule.category.value if rule.category else None,
        "title": rule.title,
        "condition_text": rule.condition_text,
        "action_text": rule.action_text,
        "machine_condition": _json_loads(rule.machine_condition_json),
        "reference": rule.reference,
        "severity": rule.severity,
        "is_active": rule.is_active,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


def _example_payload(example: DigitalTwinReasoningExample) -> dict:
    return {
        "id": example.id,
        "example_uid": example.example_uid,
        "project_id": example.project_id,
        "question": example.question,
        "context": example.context,
        "reasoning": example.reasoning,
        "answer": example.answer,
        "reference": example.reference,
        "confidence": example.confidence,
        "related_node_id": example.related_node_id,
        "related_node_uid": example.related_node.uid if example.related_node else None,
        "metadata": _json_loads(example.metadata_json),
        "created_at": example.created_at,
    }


@dataclass
class ValidationIssue:
    code: str
    severity: str
    message: str
    node_uid: str | None = None
    relationship_uid: str | None = None


def upsert_node(db: Session, project_id: int, data) -> DigitalTwinNode:
    node = db.query(DigitalTwinNode).filter(
        DigitalTwinNode.project_id == project_id,
        DigitalTwinNode.uid == data.uid,
    ).first()
    if not node:
        node = DigitalTwinNode(project_id=project_id, uid=data.uid)
        db.add(node)

    for field in (
        "node_type", "name", "code", "description", "source_table", "source_id",
        "discipline", "zone", "floor", "revision", "status",
    ):
        setattr(node, field, getattr(data, field))
    node.metadata_json = _json_dumps(getattr(data, "metadata", {}))
    return node


def upsert_relationship(db: Session, project_id: int, data) -> DigitalTwinRelationship:
    from_node = db.query(DigitalTwinNode).filter(
        DigitalTwinNode.project_id == project_id,
        DigitalTwinNode.uid == data.from_uid,
    ).first()
    to_node = db.query(DigitalTwinNode).filter(
        DigitalTwinNode.project_id == project_id,
        DigitalTwinNode.uid == data.to_uid,
    ).first()
    if not from_node or not to_node:
        missing = data.from_uid if not from_node else data.to_uid
        raise ValueError(f"Node '{missing}' belum tersedia untuk relationship.")

    relationship_uid = (
        data.relationship_uid
        or f"REL-{data.from_uid}-{data.relationship_type}-{data.to_uid}"
    )
    edge = db.query(DigitalTwinRelationship).filter(
        DigitalTwinRelationship.project_id == project_id,
        DigitalTwinRelationship.relationship_uid == relationship_uid,
    ).first()
    if not edge:
        edge = DigitalTwinRelationship(
            project_id=project_id,
            relationship_uid=relationship_uid,
        )
        db.add(edge)

    edge.from_node = from_node
    edge.to_node = to_node
    edge.relationship_type = data.relationship_type
    edge.relationship_name = data.relationship_name
    edge.reason = data.reason
    edge.rule_reference = data.rule_reference
    edge.confidence = data.confidence
    edge.metadata_json = _json_dumps(data.metadata)
    return edge


def upsert_rule(db: Session, project_id: int | None, data) -> DigitalTwinRule:
    rule = db.query(DigitalTwinRule).filter(
        DigitalTwinRule.project_id == project_id,
        DigitalTwinRule.rule_uid == data.rule_uid,
    ).first()
    if not rule:
        rule = DigitalTwinRule(project_id=project_id, rule_uid=data.rule_uid)
        db.add(rule)

    rule.category = data.category
    rule.title = data.title
    rule.condition_text = data.condition_text
    rule.action_text = data.action_text
    rule.machine_condition_json = _json_dumps(data.machine_condition)
    rule.reference = data.reference
    rule.severity = data.severity
    rule.is_active = data.is_active
    return rule


def upsert_reasoning_example(db: Session, project_id: int, data) -> DigitalTwinReasoningExample:
    related_node = None
    if data.related_node_uid:
        related_node = db.query(DigitalTwinNode).filter(
            DigitalTwinNode.project_id == project_id,
            DigitalTwinNode.uid == data.related_node_uid,
        ).first()
        if not related_node:
            raise ValueError(f"Node '{data.related_node_uid}' belum tersedia untuk reasoning example.")

    example = db.query(DigitalTwinReasoningExample).filter(
        DigitalTwinReasoningExample.project_id == project_id,
        DigitalTwinReasoningExample.example_uid == data.example_uid,
    ).first()
    if not example:
        example = DigitalTwinReasoningExample(
            project_id=project_id,
            example_uid=data.example_uid,
        )
        db.add(example)

    example.question = data.question
    example.context = data.context
    example.reasoning = data.reasoning
    example.answer = data.answer
    example.reference = data.reference
    example.confidence = data.confidence
    example.related_node = related_node
    example.metadata_json = _json_dumps(data.metadata)
    return example


def import_dataset(db: Session, project_id: int, payload) -> dict:
    for node in payload.nodes:
        upsert_node(db, project_id, node)
    db.flush()

    for relationship in payload.relationships:
        upsert_relationship(db, project_id, relationship)
    for rule in payload.rules:
        upsert_rule(db, project_id, rule)
    db.flush()

    for example in payload.reasoning_examples:
        upsert_reasoning_example(db, project_id, example)

    db.commit()
    return {
        "project_id": project_id,
        "nodes_upserted": len(payload.nodes),
        "relationships_upserted": len(payload.relationships),
        "rules_upserted": len(payload.rules),
        "reasoning_examples_upserted": len(payload.reasoning_examples),
    }


def export_graph(db: Session, project_id: int) -> dict:
    nodes = db.query(DigitalTwinNode).filter(DigitalTwinNode.project_id == project_id).all()
    relationships = db.query(DigitalTwinRelationship).filter(
        DigitalTwinRelationship.project_id == project_id
    ).all()
    rules = db.query(DigitalTwinRule).filter(
        (DigitalTwinRule.project_id == project_id) | (DigitalTwinRule.project_id.is_(None))
    ).all()
    examples = db.query(DigitalTwinReasoningExample).filter(
        DigitalTwinReasoningExample.project_id == project_id
    ).all()
    return {
        "project_id": project_id,
        "nodes": [_node_payload(node) for node in nodes],
        "relationships": [_relationship_payload(edge) for edge in relationships],
        "rules": [_rule_payload(rule) for rule in rules],
        "reasoning_examples": [_example_payload(example) for example in examples],
    }


def _has_connected_type(
    relationships: Iterable[DigitalTwinRelationship],
    node: DigitalTwinNode,
    target_types: set[DigitalTwinNodeType],
    direction: str = "any",
) -> bool:
    for edge in relationships:
        if direction in {"any", "incoming"} and edge.to_node_id == node.id:
            if edge.from_node and edge.from_node.node_type in target_types:
                return True
        if direction in {"any", "outgoing"} and edge.from_node_id == node.id:
            if edge.to_node and edge.to_node.node_type in target_types:
                return True
    return False


def _activity_has_wbs(
    relationships: Iterable[DigitalTwinRelationship],
    node: DigitalTwinNode,
) -> bool:
    if _has_connected_type(relationships, node, {DigitalTwinNodeType.WBS}):
        return True
    connected_boq_ids = set()
    for edge in relationships:
        if edge.to_node_id == node.id and edge.from_node and edge.from_node.node_type == DigitalTwinNodeType.BOQ:
            connected_boq_ids.add(edge.from_node_id)
        if edge.from_node_id == node.id and edge.to_node and edge.to_node.node_type == DigitalTwinNodeType.BOQ:
            connected_boq_ids.add(edge.to_node_id)
    for edge in relationships:
        if edge.from_node_id in connected_boq_ids and edge.to_node and edge.to_node.node_type == DigitalTwinNodeType.WBS:
            return True
        if edge.to_node_id in connected_boq_ids and edge.from_node and edge.from_node.node_type == DigitalTwinNodeType.WBS:
            return True
    return False


def validate_dataset(db: Session, project_id: int, persist: bool = False) -> dict:
    nodes = db.query(DigitalTwinNode).filter(DigitalTwinNode.project_id == project_id).all()
    relationships = db.query(DigitalTwinRelationship).filter(
        DigitalTwinRelationship.project_id == project_id
    ).all()
    issues: list[ValidationIssue] = []

    def add(code: str, severity: str, message: str, node: DigitalTwinNode | None = None):
        issues.append(ValidationIssue(code, severity, message, node.uid if node else None))

    node_types = {node.node_type for node in nodes}
    required_foundation = [
        DigitalTwinNodeType.PROJECT,
        DigitalTwinNodeType.CONTRACT,
        DigitalTwinNodeType.WBS,
        DigitalTwinNodeType.BOQ,
        DigitalTwinNodeType.ACTIVITY,
    ]
    for node_type in required_foundation:
        if node_type not in node_types:
            add(
                "missing_foundation_node",
                "warning",
                f"Dataset belum memiliki node wajib tipe {node_type.value}.",
            )

    for node in nodes:
        metadata = _json_loads(node.metadata_json)
        if not node.uid:
            add("missing_node_uid", "error", "Node belum memiliki UID.", node)
        if node.node_type == DigitalTwinNodeType.WBS and not _has_connected_type(
            relationships, node, {DigitalTwinNodeType.BOQ}
        ):
            add("wbs_without_boq", "error", "WBS belum terhubung ke BOQ.", node)
        if node.node_type == DigitalTwinNodeType.ACTIVITY:
            if not _activity_has_wbs(relationships, node):
                add("activity_without_wbs", "error", "Activity belum terhubung ke WBS.", node)
            if not _has_connected_type(
                relationships, node,
                {DigitalTwinNodeType.MATERIAL, DigitalTwinNodeType.EQUIPMENT, DigitalTwinNodeType.LABOR, DigitalTwinNodeType.CREW},
                direction="outgoing",
            ):
                add("activity_without_resource", "warning", "Activity belum punya resource material/equipment/labor/crew.", node)
            is_start = metadata.get("is_start") is True or (node.code or "").lower() == "start"
            is_finish = metadata.get("is_finish") is True or (node.code or "").lower() == "finish"
            if not is_start and not _has_connected_type(
                relationships, node, {DigitalTwinNodeType.ACTIVITY}, direction="incoming"
            ):
                add("activity_without_predecessor", "warning", "Activity belum punya predecessor.", node)
            if not is_finish and not _has_connected_type(
                relationships, node, {DigitalTwinNodeType.ACTIVITY}, direction="outgoing"
            ):
                add("activity_without_successor", "warning", "Activity belum punya successor.", node)
            if metadata.get("duration_days") and not metadata.get("productivity_reference"):
                add("duration_without_productivity", "warning", "Durasi activity belum menjelaskan referensi produktivitas.", node)
        if node.node_type == DigitalTwinNodeType.MATERIAL and not _has_connected_type(
            relationships, node, {DigitalTwinNodeType.SUPPLIER}
        ):
            add("material_without_supplier", "error", "Material belum terhubung ke supplier.", node)
        if node.node_type in {DigitalTwinNodeType.RISK, DigitalTwinNodeType.ISSUE} and not metadata.get("mitigation"):
            add("risk_without_mitigation", "warning", "Risk/issue belum memiliki mitigasi.", node)

    for edge in relationships:
        if edge.from_node and edge.to_node and edge.from_node.project_id != edge.to_node.project_id:
            issues.append(ValidationIssue(
                "cross_project_relationship",
                "error",
                "Relationship menghubungkan node dari project berbeda.",
                relationship_uid=edge.relationship_uid,
            ))
        if not edge.relationship_name:
            issues.append(ValidationIssue(
                "relationship_without_name",
                "error",
                "Relationship belum memiliki nama.",
                relationship_uid=edge.relationship_uid,
            ))

    if persist:
        db.query(DigitalTwinValidationIssue).filter(
            DigitalTwinValidationIssue.project_id == project_id,
            DigitalTwinValidationIssue.is_resolved == False,
        ).update({"is_resolved": True}, synchronize_session=False)
        db.flush()
        node_by_uid = {node.uid: node for node in nodes}
        edge_by_uid = {edge.relationship_uid: edge for edge in relationships}
        for issue in issues:
            db.add(DigitalTwinValidationIssue(
                project_id=project_id,
                node_id=node_by_uid.get(issue.node_uid).id if issue.node_uid in node_by_uid else None,
                relationship_id=(
                    edge_by_uid.get(issue.relationship_uid).id
                    if issue.relationship_uid in edge_by_uid else None
                ),
                code=issue.code,
                severity=issue.severity,
                message=issue.message,
            ))
        db.commit()

    return {
        "project_id": project_id,
        "passed": not any(issue.severity == "error" for issue in issues),
        "issue_count": len(issues),
        "issues": [issue.__dict__ for issue in issues],
    }


def default_rule_payloads() -> list[dict]:
    return [
        {
            "rule_uid": "R-SCH-001",
            "category": DigitalTwinRuleCategory.SCHEDULING,
            "title": "Activity harus memiliki WBS",
            "condition_text": "IF Activity tidak terhubung ke WBS",
            "action_text": "THEN Activity tidak boleh dipakai untuk schedule resmi.",
            "machine_condition": {"node_type": "activity", "required_relationship_to": "wbs"},
            "reference": "PMBOK Schedule Management",
            "severity": "high",
        },
        {
            "rule_uid": "R-SCH-002",
            "category": DigitalTwinRuleCategory.SCHEDULING,
            "title": "Activity harus memiliki predecessor kecuali Start",
            "condition_text": "IF Activity bukan Start dan tidak memiliki predecessor",
            "action_text": "THEN CPM belum valid.",
            "machine_condition": {"node_type": "activity", "required_incoming_from": "activity", "except": "is_start"},
            "reference": "CPM scheduling logic",
            "severity": "medium",
        },
        {
            "rule_uid": "R-RES-001",
            "category": DigitalTwinRuleCategory.RESOURCE,
            "title": "Activity harus memiliki resource",
            "condition_text": "IF Activity tidak menggunakan material, equipment, labor, atau crew",
            "action_text": "THEN durasi dan biaya tidak boleh dianggap valid.",
            "machine_condition": {"node_type": "activity", "required_resource": ["material", "equipment", "labor", "crew"]},
            "reference": "Construction productivity planning",
            "severity": "medium",
        },
        {
            "rule_uid": "R-PROC-001",
            "category": DigitalTwinRuleCategory.PROCUREMENT,
            "title": "Material harus memiliki supplier",
            "condition_text": "IF Material tidak terhubung ke supplier",
            "action_text": "THEN procurement readiness belum lengkap.",
            "machine_condition": {"node_type": "material", "required_relationship_to": "supplier"},
            "reference": "Procurement control",
            "severity": "high",
        },
        {
            "rule_uid": "R-QUAL-001",
            "category": DigitalTwinRuleCategory.QUALITY,
            "title": "Pengecoran menunggu inspeksi QC",
            "condition_text": "IF Activity pengecoran belum memiliki QC Inspection approved",
            "action_text": "THEN status activity menjadi blocked.",
            "machine_condition": {"activity_keyword": "pengecoran", "required_relationship_to": "inspection"},
            "reference": "ITP / Quality Plan",
            "severity": "high",
        },
    ]


def seed_default_rules(db: Session, project_id: int | None = None) -> int:
    from app.schemas.schemas import DigitalTwinRuleCreate

    count = 0
    for item in default_rule_payloads():
        upsert_rule(db, project_id, DigitalTwinRuleCreate(**item))
        count += 1
    db.commit()
    return count


def sync_existing_project_facts(db: Session, project: Project) -> dict:
    from app.schemas.schemas import DigitalTwinDatasetImport, DigitalTwinNodeCreate, DigitalTwinRelationshipCreate

    nodes = [
        DigitalTwinNodeCreate(
            uid=f"project:{project.id}",
            node_type=DigitalTwinNodeType.PROJECT,
            code=f"PRJ-{project.id}",
            name=project.project_name,
            source_table="projects",
            source_id=str(project.id),
            status=project.status.value if project.status else None,
        )
    ]
    relationships: list[DigitalTwinRelationshipCreate] = []

    for task in project.tasks:
        task_uid = f"task:{task.id}"
        specification = task.specification
        control = task.control
        wbs_uid = None
        if specification and specification.wbs_code:
            wbs_uid = f"wbs:{project.id}:{specification.wbs_code}"
            nodes.append(DigitalTwinNodeCreate(
                uid=wbs_uid,
                node_type=DigitalTwinNodeType.WBS,
                code=specification.wbs_code,
                name=specification.work_package or f"WBS {specification.wbs_code}",
                source_table="task_specifications",
                source_id=str(specification.id),
                zone=specification.location,
                metadata={"template_name": specification.template_name},
            ))
            relationships.append(DigitalTwinRelationshipCreate(
                from_uid=f"project:{project.id}",
                to_uid=wbs_uid,
                relationship_type="has_wbs",
                relationship_name="Project memiliki WBS",
                reason="WBS diambil dari task specification CPMIS.",
                rule_reference="SYNC-CPMIS-WBS",
            ))
        nodes.append(DigitalTwinNodeCreate(
            uid=task_uid,
            node_type=DigitalTwinNodeType.ACTIVITY,
            code=specification.wbs_code if specification else f"TASK-{task.id}",
            name=task.title,
            description=task.description,
            source_table="tasks",
            source_id=str(task.id),
            discipline=task.division.division_name if task.division else None,
            zone=(control.location if control else None) or (specification.location if specification else None),
            status=task.status.value if task.status else None,
            metadata={
                "task_id": task.id,
                "priority": task.priority.value if task.priority else None,
                "deadline": task.deadline.isoformat() if task.deadline else None,
                "progress_percent": task.progress_percent or 0,
                "approval_status": task.approval_status,
            },
        ))
        relationships.append(DigitalTwinRelationshipCreate(
            from_uid=wbs_uid or f"project:{project.id}",
            to_uid=task_uid,
            relationship_type="has_activity",
            relationship_name="WBS memiliki activity/task" if wbs_uid else "Project memiliki activity/task",
            reason="Task operasional pada CPMIS disinkronkan sebagai activity digital twin.",
            rule_reference="SYNC-CPMIS-TASK",
        ))

        if control:
            boq_uid = f"boq:task:{task.id}"
            nodes.append(DigitalTwinNodeCreate(
                uid=boq_uid,
                node_type=DigitalTwinNodeType.BOQ,
                code=specification.wbs_code if specification else f"BOQ-{task.id}",
                name=f"BOQ - {task.title}",
                source_table="task_controls",
                source_id=str(control.id),
                metadata={
                    "unit": control.unit,
                    "planned_quantity": control.planned_quantity,
                    "actual_quantity": control.actual_quantity,
                    "boq_value": control.boq_value,
                    "productivity_reference": bool(control.planned_manpower or control.planned_equipment),
                },
            ))
            relationships.append(DigitalTwinRelationshipCreate(
                from_uid=boq_uid,
                to_uid=task_uid,
                relationship_type="defines_quantity_for",
                relationship_name="BOQ menjadi dasar volume activity",
                reason="Progress activity dihitung terhadap baseline quantity pada task control.",
                rule_reference="R-SCH-001",
            ))
            if wbs_uid:
                relationships.append(DigitalTwinRelationshipCreate(
                    from_uid=wbs_uid,
                    to_uid=boq_uid,
                    relationship_type="has_boq",
                    relationship_name="WBS memiliki BOQ",
                    reason="Task control CPMIS menjadi baseline BOQ untuk WBS terkait.",
                    rule_reference="SYNC-CPMIS-BOQ",
                ))

        for material in task.materials:
            material_uid = f"material:{material.id}"
            nodes.append(DigitalTwinNodeCreate(
                uid=material_uid,
                node_type=DigitalTwinNodeType.MATERIAL,
                code=material.material_code,
                name=material.material_name,
                source_table="task_material_specifications",
                source_id=str(material.id),
                revision=material.revision,
                status="approval_required" if material.approval_required else "registered",
                metadata={
                    "category": material.category,
                    "specification": material.technical_specification,
                    "standard": material.standard_reference,
                    "grade": material.grade,
                    "manufacturer": material.approved_manufacturer,
                    "quantity": material.planned_quantity,
                    "unit": material.unit,
                    "approval_required": material.approval_required,
                },
            ))
            relationships.append(DigitalTwinRelationshipCreate(
                from_uid=task_uid,
                to_uid=material_uid,
                relationship_type="uses_material",
                relationship_name="Activity menggunakan material",
                reason="Material specification terhubung langsung ke task.",
                rule_reference="R-RES-001",
            ))

    for dependency in db.query(TaskDependency).join(Task, TaskDependency.task_id == Task.id).filter(
        Task.project_id == project.id
    ).all():
        relationships.append(DigitalTwinRelationshipCreate(
            from_uid=f"task:{dependency.depends_on_task_id}",
            to_uid=f"task:{dependency.task_id}",
            relationship_type="precedes",
            relationship_name="Activity menjadi predecessor activity lain",
            reason=dependency.reason or "Dependency task CPMIS disinkronkan sebagai relationship schedule.",
            rule_reference="R-SCH-002",
        ))

    payload = DigitalTwinDatasetImport(nodes=nodes, relationships=relationships)
    return import_dataset(db, project.id, payload)
