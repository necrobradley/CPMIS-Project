"""Import paket data proyek menjadi satu proyek CPMIS yang operasional.

Importer menerima ZIP proyek, membuat akun lintas role, task/WBS yang dapat
dipakai melalui web dan Telegram, serta graph Digital Twin dan contoh reasoning
AI. Prosesnya idempotent per nama proyek.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import secrets
import zipfile
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.user import (
    ApprovalStatus,
    DigitalTwinNodeType,
    DigitalTwinRuleCategory,
    Division,
    Project,
    ProjectMembership,
    ProjectStatus,
    Task,
    TaskControl,
    TaskDependency,
    TaskMaterialSpecification,
    TaskPriority,
    TaskSpecification,
    TaskStatus,
    User,
    UserRole,
)
from app.schemas.schemas import (
    DigitalTwinDatasetImport,
    DigitalTwinNodeCreate,
    DigitalTwinReasoningExampleCreate,
    DigitalTwinRelationshipCreate,
    DigitalTwinRuleCreate,
)
from app.services.digital_twin import import_dataset
from app.services.project_staffing import (
    seed_ai_role_coverage_tasks,
    upsert_full_project_roster,
)


MASTER_FILE = "30_AI_Training_Dataset_Master.json"
GRAPH_FILE = "30_AI_Knowledge_Graph.json"
INSTRUCTION_FILE = "30_AI_Instruction_Dataset.jsonl"
DEMO_FEATURES_FILE = "CPMIS_Demo_Features.json"

NODE_TYPE_MAP = {
    "project": DigitalTwinNodeType.PROJECT,
    "wbs": DigitalTwinNodeType.WBS,
    "boq": DigitalTwinNodeType.BOQ,
    "activity": DigitalTwinNodeType.ACTIVITY,
    "material": DigitalTwinNodeType.MATERIAL,
    "equipment": DigitalTwinNodeType.EQUIPMENT,
    "risk": DigitalTwinNodeType.RISK,
}


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _safe_uid(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _project_slug(summary: dict) -> str:
    raw = str(summary.get("project_code") or summary.get("project_name") or "project")
    slug = re.sub(r"[^a-z0-9]+", ".", raw.lower()).strip(".")
    return (slug or "project")[:36]


def load_project_zip(content: bytes) -> tuple[dict, dict, list[dict], dict]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise ValueError("File dataset bukan ZIP yang valid") from exc

    with archive:
        names = set(archive.namelist())
        missing = {MASTER_FILE, GRAPH_FILE} - names
        if missing:
            raise ValueError(
                "Paket data proyek tidak lengkap; file wajib tidak ditemukan: "
                + ", ".join(sorted(missing))
            )
        master = json.loads(archive.read(MASTER_FILE))
        graph = json.loads(archive.read(GRAPH_FILE))
        examples: list[dict] = []
        if INSTRUCTION_FILE in names:
            raw = archive.read(INSTRUCTION_FILE).decode("utf-8-sig")
            examples = [json.loads(line) for line in raw.splitlines() if line.strip()]
        demo_features = (
            json.loads(archive.read(DEMO_FEATURES_FILE))
            if DEMO_FEATURES_FILE in names
            else {}
        )
    return master, graph, examples, demo_features


def _task_status(activity: dict) -> TaskStatus:
    progress = float(activity.get("progress_pct") or 0)
    raw_status = str(activity.get("status") or "").lower()
    if progress >= 100 or "complete" in raw_status:
        return TaskStatus.DONE
    if progress > 0 or "progress" in raw_status:
        return TaskStatus.IN_PROGRESS
    return TaskStatus.TODO


def _upsert_membership(
    db: Session,
    project: Project,
    user: User,
    division: Division,
    project_role: str,
) -> None:
    membership = db.query(ProjectMembership).filter(
        ProjectMembership.project_id == project.id,
        ProjectMembership.user_id == user.id,
    ).first()
    if not membership:
        membership = ProjectMembership(project_id=project.id, user_id=user.id)
        db.add(membership)
    membership.division_id = division.id
    membership.project_role = project_role
    membership.is_active = True


def _upsert_core_project(
    db: Session,
    master: dict,
    *,
    admin_email: str,
    admin_password: str,
    telegram_id: str | None,
    full_role_roster: bool = False,
) -> tuple[User, dict[str, User], dict[str, User], Project, Division, bool, list[dict]]:
    summary = master.get("project_summary") or {}
    project_name = summary.get("project_name") or "Proyek Impor"
    project_slug = _project_slug(summary)

    owner = db.query(User).filter(User.email == admin_email).first()
    owner_created = owner is None
    if not owner:
        owner = User(
            name="Administrator CPMIS",
            email=admin_email,
            password_hash=get_password_hash(admin_password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(owner)
        db.flush()
    elif admin_password:
        # The bootstrap secret authorizes repairing an existing demo account.
        # Authenticated dataset re-imports pass an empty password and therefore
        # never change credentials.
        owner.password_hash = get_password_hash(admin_password)
        owner.role = UserRole.ADMIN
        owner.is_active = True

    project = db.query(Project).filter(Project.project_name == project_name).first()
    if not project:
        project = Project(project_name=project_name, owner_id=owner.id)
        db.add(project)
        db.flush()
    project.description = (
        "Paket data proyek untuk AI CPMIS, Digital Twin, pengendalian proyek, "
        "dan pelaporan terintegrasi web/Telegram."
    )
    project.location = summary.get("location")
    project.contract_value = summary.get("contract_value_idr")
    project.start_date = _parse_date(summary.get("start"))
    project.end_date = _parse_date(summary.get("baseline_finish"))
    project.status = ProjectStatus.ACTIVE
    performance = master.get("performance_at_data_date") or {}
    project.progress_percent = float(performance.get("actual_pct") or 0)
    project.owner_id = owner.id

    division = db.query(Division).filter(
        Division.project_id == project.id,
        Division.division_name == "Project Controls & Digital Engineering",
    ).first()
    if not division:
        division = Division(
            project_id=project.id,
            division_name="Project Controls & Digital Engineering",
        )
        db.add(division)
    division.description = "WBS, schedule, cost control, Digital Twin, AI, dan laporan lapangan."
    division.manager_id = owner.id
    db.flush()

    if full_role_roster:
        role_users, project_role_users, generated_accounts = upsert_full_project_roster(
            db,
            project=project,
            project_slug=project_slug,
            owner=owner,
            initial_password=admin_password,
        )
    else:
        account_specs = (
            ("director", "Direktur Proyek", UserRole.DIRECTOR, "project_manager"),
            ("manager", "Manajer Proyek", UserRole.MANAGER, "project_manager"),
            ("staff", "Staf Lapangan", UserRole.STAFF, "site_engineer"),
            ("subcontractor", "Staf Subkontraktor", UserRole.SUBCONTRACTOR, "subcontractor"),
        )
        role_users = {}
        project_role_users = {}
        generated_accounts = []
        for key, label, global_role, project_role in account_specs:
            email = f"{key}.{project_slug}@cpmis.example.com"
            user = db.query(User).filter(User.email == email).first()
            created = user is None
            temporary_password = None
            if not user:
                temporary_password = admin_password or secrets.token_urlsafe(12)
                user = User(
                    name=f"{label} - {project_name}"[:100],
                    email=email,
                    password_hash=get_password_hash(temporary_password),
                    role=global_role,
                    is_active=True,
                )
                db.add(user)
                db.flush()
            elif admin_password:
                user.password_hash = get_password_hash(admin_password)
            user.role = global_role
            user.is_active = True
            user.division_id = division.id
            _upsert_membership(db, project, user, division, project_role)
            role_users[key] = user
            project_role_users[project_role] = user
            generated_accounts.append({
                "name": user.name,
                "email": user.email,
                "role": global_role.value,
                "project_role": project_role,
                "created": created,
                "temporary_password": temporary_password,
            })

    field_user = role_users["staff"]
    if telegram_id:
        duplicate = db.query(User).filter(
            User.telegram_id == telegram_id,
            User.id != field_user.id,
        ).first()
        if duplicate:
            raise ValueError("Telegram ID sudah dipakai oleh user lain")
        field_user.telegram_id = telegram_id

    _upsert_membership(db, project, owner, division, "project_manager")
    db.flush()
    return owner, role_users, project_role_users, project, division, owner_created, generated_accounts


def _upsert_tasks(
    db: Session,
    master: dict,
    owner: User,
    role_users: dict[str, User],
    project: Project,
    division: Division,
) -> tuple[dict[str, Task], dict[str, int]]:
    existing = {
        spec.wbs_code: spec.task
        for spec in db.query(TaskSpecification).join(Task).filter(
            Task.project_id == project.id
        ).all()
    }
    by_activity: dict[str, Task] = {}
    assignment_counts = {key: 0 for key in role_users}

    for index, chain in enumerate(master.get("linked_chains") or []):
        wbs = chain.get("wbs") or {}
        boq = chain.get("boq") or {}
        activity = chain.get("activity") or {}
        progress = chain.get("progress") or {}
        resource = chain.get("resource") or {}
        equipment = chain.get("equipment") or {}
        material = chain.get("material") or {}
        risk = chain.get("risk") or {}
        wbs_code = str(wbs.get("wbs_code") or activity.get("activity_id"))

        task = existing.get(wbs_code)
        if not task:
            task = Task(
                title=str(activity.get("name") or boq.get("description") or wbs_code)[:200],
                project_id=project.id,
                created_by=owner.id,
            )
            db.add(task)
            db.flush()
            task.specification = TaskSpecification(
                wbs_code=wbs_code,
                acceptance_criteria="Pekerjaan, mutu, volume, dan bukti lapangan sesuai dokumen proyek.",
            )
            existing[wbs_code] = task

        task.title = str(activity.get("name") or boq.get("description") or wbs_code)[:200]
        task.description = (
            f"WBS {wbs_code}. BOQ {boq.get('boq_id')}: {boq.get('description')}. "
            f"Risiko terkait: {risk.get('risk_event') or 'lihat risk register'}."
        )
        task.division_id = division.id
        searchable = " ".join(str(value or "") for value in (
            activity.get("name"),
            boq.get("description"),
            risk.get("risk_event"),
            material.get("description"),
            equipment.get("jenis"),
        )).lower()
        if str(activity.get("is_critical")).upper() == "YES":
            assignee_key = "manager" if index % 3 else "director"
        elif any(word in searchable for word in ("subkon", "vendor", "supply", "instal", "erection")):
            assignee_key = "subcontractor"
        else:
            assignee_key = "subcontractor" if index % 5 == 0 else "staff"
        task.assigned_to = role_users[assignee_key].id
        assignment_counts[assignee_key] += 1
        task.created_by = owner.id
        task.status = _task_status(activity)
        task.priority = (
            TaskPriority.CRITICAL
            if str(activity.get("is_critical")).upper() == "YES"
            else TaskPriority.MEDIUM
        )
        task.deadline = _parse_date(activity.get("early_finish"))
        task.progress_percent = float(activity.get("progress_pct") or 0)
        task.approval_status = ApprovalStatus.APPROVED.value
        task.ai_generated = True
        task.ai_source = "Paket data proyek terhubung"

        specification = task.specification
        specification.wbs_code = wbs_code
        specification.work_package = str(wbs.get("wbs_name") or task.title)[:200]
        specification.location = project.location or "Lokasi proyek"
        specification.reporting_instructions = (
            "Cantumkan progres/volume, pekerja, cuaca, kendala, dan kode WBS. "
            "Laporan dapat dikirim melalui Telegram."
        )
        specification.required_photo_count = 1 if task.status != TaskStatus.DONE else 0
        specification.required_document_count = 0

        if not task.control:
            task.control = TaskControl()
        task.control.planned_start = _parse_date(activity.get("early_start"))
        task.control.planned_finish = _parse_date(activity.get("early_finish"))
        task.control.location = project.location or "Lokasi proyek"
        task.control.unit = boq.get("unit")
        task.control.planned_quantity = float(boq.get("volume") or 0)
        task.control.actual_quantity = (
            float(boq.get("volume") or 0) * float(progress.get("progress_pct") or 0) / 100
        )
        task.control.boq_value = float(boq.get("total_price_idr") or 0)
        task.control.budget_cost = float(boq.get("total_price_idr") or 0)
        task.control.actual_cost = float(progress.get("actual_cost_idr") or 0)
        task.control.planned_manpower = int(resource.get("manpower") or 0) or None
        task.control.planned_equipment = equipment.get("jenis")

        material_code = material.get("material_code")
        if material_code:
            material_spec = next(
                (item for item in task.materials if item.material_code == material_code),
                None,
            )
            if not material_spec:
                material_spec = TaskMaterialSpecification(
                    material_code=str(material_code),
                    material_name=str(material.get("description") or material_code)[:200],
                )
                task.materials.append(material_spec)
            material_spec.unit = boq.get("unit")
            material_spec.planned_quantity = float(boq.get("volume") or 0)
            material_spec.technical_specification = material.get("quality_standard")
            material_spec.approved_manufacturer = material.get("vendor")
            material_spec.approval_required = False

        activity_id = str(activity.get("activity_id") or "")
        if activity_id:
            by_activity[activity_id] = task

    db.flush()

    for chain in master.get("linked_chains") or []:
        activity = chain.get("activity") or {}
        network = chain.get("network") or {}
        task = by_activity.get(str(activity.get("activity_id") or ""))
        if not task:
            continue
        for raw in network.get("predecessors") or []:
            parts = str(raw).split("|")
            predecessor = by_activity.get(parts[0])
            if not predecessor:
                continue
            dependency = db.query(TaskDependency).filter(
                TaskDependency.task_id == task.id,
                TaskDependency.depends_on_task_id == predecessor.id,
            ).first()
            if not dependency:
                dependency = TaskDependency(
                    task_id=task.id,
                    depends_on_task_id=predecessor.id,
                )
                db.add(dependency)
            relation = (parts[1] if len(parts) > 1 else "FS").upper()
            dependency.dependency_type = {
                "FS": "finish_to_start",
                "SS": "start_to_start",
                "FF": "finish_to_finish",
                "SF": "start_to_finish",
            }.get(relation, "finish_to_start")
            dependency.lag_days = int(parts[2]) if len(parts) > 2 and parts[2].lstrip("-").isdigit() else 0
            dependency.reason = "Diimpor dari relasi CPM pada paket data proyek."
    db.flush()
    return by_activity, assignment_counts


def _rule_category(value: str) -> DigitalTwinRuleCategory:
    lowered = (value or "").lower()
    mapping = {
        "sched": DigitalTwinRuleCategory.SCHEDULING,
        "jadwal": DigitalTwinRuleCategory.SCHEDULING,
        "resource": DigitalTwinRuleCategory.RESOURCE,
        "sumber": DigitalTwinRuleCategory.RESOURCE,
        "proc": DigitalTwinRuleCategory.PROCUREMENT,
        "pengadaan": DigitalTwinRuleCategory.PROCUREMENT,
        "quality": DigitalTwinRuleCategory.QUALITY,
        "mutu": DigitalTwinRuleCategory.QUALITY,
        "hse": DigitalTwinRuleCategory.HSE,
        "k3": DigitalTwinRuleCategory.HSE,
        "cost": DigitalTwinRuleCategory.COST,
        "biaya": DigitalTwinRuleCategory.COST,
        "risk": DigitalTwinRuleCategory.RISK,
        "risiko": DigitalTwinRuleCategory.RISK,
    }
    return next((category for key, category in mapping.items() if key in lowered), DigitalTwinRuleCategory.GENERAL)


def _build_digital_twin_payload(master: dict, graph: dict, examples: list[dict]) -> DigitalTwinDatasetImport:
    risk_mitigation: dict[str, str] = {}
    for chain in master.get("linked_chains") or []:
        risk = chain.get("risk") or {}
        if risk.get("risk_id") and risk.get("mitigation"):
            risk_mitigation[f"RSK:{risk['risk_id']}"] = risk["mitigation"]

    nodes: list[DigitalTwinNodeCreate] = []
    relationships: list[DigitalTwinRelationshipCreate] = []
    known_uids: set[str] = set()
    supplier_uids: dict[str, str] = {}

    for item in graph.get("nodes") or []:
        node_type = NODE_TYPE_MAP.get(str(item.get("type") or "").lower())
        if not node_type:
            continue
        uid = str(item.get("id"))
        metadata = {
            key: value
            for key, value in item.items()
            if key not in {"id", "type", "label"}
        }
        if uid in risk_mitigation:
            metadata["mitigation"] = risk_mitigation[uid]
        nodes.append(DigitalTwinNodeCreate(
            uid=uid,
            node_type=node_type,
            name=str(item.get("label") or uid)[:255],
            code=uid.split(":", 1)[-1][:120],
            source_table="30_AI_Knowledge_Graph.json",
            source_id=uid,
            metadata=metadata,
        ))
        known_uids.add(uid)

        if node_type == DigitalTwinNodeType.MATERIAL and item.get("vendor"):
            vendor = str(item["vendor"])
            supplier_uid = supplier_uids.setdefault(vendor, _safe_uid("SUP", vendor))
            if supplier_uid not in known_uids:
                nodes.append(DigitalTwinNodeCreate(
                    uid=supplier_uid,
                    node_type=DigitalTwinNodeType.SUPPLIER,
                    name=vendor[:255],
                    source_table="30_AI_Knowledge_Graph.json",
                    source_id=vendor,
                ))
                known_uids.add(supplier_uid)
            relationships.append(DigitalTwinRelationshipCreate(
                relationship_uid=_safe_uid("REL", f"{uid}|purchased_from|{supplier_uid}"),
                from_uid=uid,
                to_uid=supplier_uid,
                relationship_type="purchased_from",
                relationship_name="Material dibeli dari supplier",
                reason="Vendor material pada paket data proyek.",
            ))

    summary = master.get("project_summary") or {}
    project_code = str(summary.get("project_code") or _project_slug(summary)).upper()
    project_uid = next((
        node.uid for node in nodes if node.node_type == DigitalTwinNodeType.PROJECT
    ), f"PRJ:{project_code}")
    if project_uid not in known_uids:
        nodes.append(DigitalTwinNodeCreate(
            uid=project_uid,
            node_type=DigitalTwinNodeType.PROJECT,
            name=str(summary.get("project_name") or project_code)[:255],
            code=project_code[:120],
            source_table=MASTER_FILE,
            source_id="project_summary",
        ))
        known_uids.add(project_uid)
    contract_uid = f"CONTRACT:{project_code}"
    if contract_uid not in known_uids:
        nodes.append(DigitalTwinNodeCreate(
            uid=contract_uid,
            node_type=DigitalTwinNodeType.CONTRACT,
            name=f"Kontrak {project_code}",
            code=project_code[:120],
            source_table=MASTER_FILE,
            source_id="project_summary",
            metadata={"contract_value_idr": summary.get("contract_value_idr")},
        ))
        known_uids.add(contract_uid)
    relationships.append(DigitalTwinRelationshipCreate(
        relationship_uid=_safe_uid("REL", f"{project_uid}|has_contract|{contract_uid}"),
        from_uid=project_uid,
        to_uid=contract_uid,
        relationship_type="has_contract",
        relationship_name="Project memiliki kontrak",
        reason="Kontrak utama pada ringkasan proyek.",
    ))

    for index, edge in enumerate(graph.get("edges") or []):
        from_uid = str(edge.get("from"))
        to_uid = str(edge.get("to"))
        if from_uid not in known_uids or to_uid not in known_uids:
            continue
        relation = str(edge.get("rel") or "related_to")
        relationships.append(DigitalTwinRelationshipCreate(
            relationship_uid=_safe_uid("REL", f"{index}|{from_uid}|{relation}|{to_uid}"),
            from_uid=from_uid,
            to_uid=to_uid,
            relationship_type=relation.lower(),
            relationship_name=relation.replace("_", " ").title()[:160],
            reason="Relationship dari knowledge graph proyek.",
            metadata={
                key: value
                for key, value in edge.items()
                if key not in {"from", "to", "rel"}
            },
        ))

    rules = []
    for index, item in enumerate(master.get("rules_engine") or [], 1):
        rule_uid = str(item.get("rule_id") or f"{project_code}-RULE-{index:04d}")
        rules.append(DigitalTwinRuleCreate(
            rule_uid=rule_uid,
            category=_rule_category(str(item.get("kategori") or item.get("disiplin") or "")),
            title=str(item.get("aturan") or rule_uid)[:255],
            condition_text=str(item.get("kondisi_if") or item.get("aturan") or "Kondisi aturan proyek"),
            action_text=str(item.get("aksi_then") or "Tinjau dan tindak lanjuti aturan proyek."),
            machine_condition={"parameter": item.get("parameter"), "validation": item.get("validasi")},
            reference=str(item.get("sumber_standar") or "Paket data proyek"),
            severity="medium",
            is_active=bool(item.get("aktif", True)),
        ))

    reasoning_examples = []
    for index, item in enumerate(examples, 1):
        reasoning_examples.append(DigitalTwinReasoningExampleCreate(
            example_uid=f"{project_code}-INSTRUCTION-{index:04d}",
            question=str(item.get("instruction") or "Pertanyaan proyek"),
            context=str(item.get("input") or "Paket data proyek"),
            reasoning="Contoh jawaban terverifikasi dari dataset instruksi proyek.",
            answer=str(item.get("output") or ""),
            reference=INSTRUCTION_FILE,
        ))

    return DigitalTwinDatasetImport(
        nodes=nodes,
        relationships=relationships,
        rules=rules,
        reasoning_examples=reasoning_examples,
    )


def import_project_dataset(
    db: Session,
    content: bytes,
    *,
    admin_email: str,
    admin_password: str,
    telegram_id: str | None = None,
) -> dict:
    master, graph, examples, demo_features = load_project_zip(content)
    owner, role_users, project_role_users, project, division, owner_created, generated_accounts = _upsert_core_project(
        db,
        master,
        admin_email=admin_email.strip().lower(),
        admin_password=admin_password,
        telegram_id=(telegram_id or "").strip() or None,
        full_role_roster=bool(demo_features.get("seed_all_project_roles")),
    )
    task_map, assignment_counts = _upsert_tasks(db, master, owner, role_users, project, division)
    ai_role_task_count = 0
    role_assignment_counts: dict[str, int] = {}
    if demo_features.get("seed_all_project_roles"):
        ai_role_task_count, role_assignment_counts = seed_ai_role_coverage_tasks(
            db,
            project=project,
            owner=owner,
            users_by_project_role=project_role_users,
            data_date=_parse_date(demo_features.get("data_date")),
        )
    db.commit()

    payload = _build_digital_twin_payload(master, graph, examples)
    graph_result = import_dataset(db, project.id, payload)
    demo_result = {"demo_features_seeded": False}
    if demo_features.get("enabled"):
        from app.services.project_demo_seed import seed_project_demo

        demo_result = seed_project_demo(
            db,
            project_id=project.id,
            owner=owner,
            role_users=role_users,
            tasks_by_activity=task_map,
            manifest=demo_features,
        )
    return {
        "project_id": project.id,
        "project_name": project.project_name,
        "project_code": (master.get("project_summary") or {}).get("project_code"),
        "admin_email": owner.email,
        "admin_created": owner_created,
        "field_user_email": role_users["staff"].email,
        "telegram_linked": bool(role_users["staff"].telegram_id),
        "generated_accounts": generated_accounts,
        "assignment_counts": assignment_counts,
        "role_assignment_counts": role_assignment_counts,
        "project_roles_created": len(project_role_users),
        "ai_role_tasks": ai_role_task_count,
        "tasks_upserted": len(task_map) + ai_role_task_count,
        **graph_result,
        **demo_result,
    }
