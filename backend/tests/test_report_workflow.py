from types import SimpleNamespace

from app.models.user import EvidenceType, ReportStatus
from app.services.report_workflow import apply_validation, validate_report


def build_report(photo_count=0, document_count=0, confirmed=True):
    requirements = [
        SimpleNamespace(id=1, code="WBS-QUALITY", title="Pemeriksaan mutu", is_mandatory=True),
        SimpleNamespace(id=2, code="WBS-SAFETY", title="Pemeriksaan K3", is_mandatory=True),
    ]
    task = SimpleNamespace(
        requirements=requirements,
        specification=SimpleNamespace(required_photo_count=2, required_document_count=1),
    )
    workflow = SimpleNamespace(task=task)
    evidence = [SimpleNamespace(evidence_type=EvidenceType.PHOTO) for _ in range(photo_count)]
    evidence += [SimpleNamespace(evidence_type=EvidenceType.DOCUMENT) for _ in range(document_count)]
    checks = [
        SimpleNamespace(requirement_id=item.id, confirmed=confirmed) for item in requirements
    ]
    return SimpleNamespace(
        report_text="Pekerjaan dilaksanakan sesuai metode kerja dan area yang ditetapkan.",
        work_progress="Volume pekerjaan mencapai target harian.",
        manpower_count=12,
        evidence=evidence,
        requirement_checks=checks,
        workflow=workflow,
    )


def test_validation_rejects_missing_evidence():
    result = validate_report(build_report(photo_count=1, document_count=0))
    assert result["passed"] is False
    assert result["score"] < 100
    failed_codes = {item["code"] for item in result["items"] if not item["passed"]}
    assert failed_codes == {"PHOTO_COUNT", "DOCUMENT_COUNT"}


def test_validation_accepts_complete_report():
    result = validate_report(build_report(photo_count=2, document_count=1))
    assert result["passed"] is True
    assert result["score"] == 100


def test_apply_validation_controls_workflow_status():
    workflow = SimpleNamespace(
        validation_passed=False,
        validation_score=0,
        validation_result=None,
        status=ReportStatus.DRAFT,
        submitted_at=None,
    )
    apply_validation(workflow, {"passed": False, "score": 75, "items": []})
    assert workflow.status == ReportStatus.NEEDS_REVISION

