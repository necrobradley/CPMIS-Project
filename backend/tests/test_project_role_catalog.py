from app.services.project_role_catalog import PROJECT_MEMBER_ROLE_CODES, PROJECT_ROLE_CATALOG


def test_project_role_catalog_contains_construction_and_legacy_roles():
    expected_roles = {
        "project_admin",
        "project_manager",
        "division_lead",
        "staff",
        "site_engineer",
        "project_engineer",
        "qa_qc_engineer",
        "drafter",
        "quantity_surveyor",
        "finance_manager",
        "project_accountant",
        "hse_officer",
        "subcontractor",
        "viewer",
    }

    assert expected_roles.issubset(PROJECT_MEMBER_ROLE_CODES)
    assert len(PROJECT_ROLE_CATALOG) >= 35
    assert all(role["code"] and role["label"] for role in PROJECT_ROLE_CATALOG)