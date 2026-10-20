import hashlib
import sys

import pytest
from fastapi.testclient import TestClient

from parallax.domain.models import Claim, SourceRef
from parallax.ports.reproduction import SubprocessReproductionExecutor
from parallax.service.app import create_app
from parallax.service.repair import FileEdit, RepairPlan, RepairService
from parallax.service.store import RunRecord
from tests.conftest import make_settings


@pytest.fixture
def repair_case(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "calc.py").write_text("def divide(a, b):\n    return a / b\n", encoding="utf-8")
    (source / ".env").write_text("SECRET=never-copy-this", encoding="utf-8")
    claim = Claim(
        claim_id="c1",
        fingerprint="calc#boundary",
        statement="zero division",
        extracted_by="r1",
        source_refs=[SourceRef(evidence_id="e1", adapter="repo", locator="calc.py")],
    )
    plan = RepairPlan(
        explanation="Define zero divisor behavior",
        edits=[
            FileEdit(
                path="calc.py",
                before="    return a / b",
                after="    return None if b == 0 else a / b",
            )
        ],
        tests=[
            FileEdit(
                path="regression.py",
                before="",
                after=(
                    "from calc import divide\n"
                    "try:\n    assert divide(4, 2) == 2\n    assert divide(1, 0) is None\n"
                    "except Exception:\n    print('ZERO_DIVISOR_ASSERTION')\n    raise\n"
                ),
            )
        ],
        regression_command=[sys.executable, "regression.py"],
        baseline_failure_contains="ZERO_DIVISOR_ASSERTION",
    )
    service = RepairService(tmp_path / "repairs", executor_factory=SubprocessReproductionExecutor)
    return source, claim, plan, service


def test_reproduce_fix_and_regress_without_mutating_source(repair_case):
    source, claim, plan, service = repair_case
    original = (source / "calc.py").read_bytes()
    proposal = service.prepare(claim, source, plan, run_id="run1")
    directory = service.root / proposal["repair_id"]
    assert proposal["status"] == "awaiting_approval"
    assert not (directory / "baseline" / ".env").exists()
    assert not (directory / "fixed").exists()
    assert "regression.py" in proposal["patch"]
    result = service.approve_and_verify(
        proposal["repair_id"], proposal["approval_digest"], approved_by="test-operator"
    )
    assert result["baseline_result"]["exit_code"] == 1
    assert result["regression_result"]["exit_code"] == 0
    assert result["status"] == "regression_passed"
    assert result["claim"]["verification_status"] == "regression_passed"
    assert result["events"] == [
        "proposal_created",
        "approved",
        "reproduced",
        "fixed_in_copy",
        "regression_passed",
    ]
    assert (source / "calc.py").read_bytes() == original
    assert not (source / "regression.py").exists()
    with pytest.raises(ValueError, match="已执行"):
        service.approve_and_verify(
            proposal["repair_id"], proposal["approval_digest"], approved_by="test-operator"
        )


def test_approval_binds_exact_patch_and_tests(repair_case):
    source, claim, plan, service = repair_case
    proposal = service.prepare(claim, source, plan, run_id="run1")
    with pytest.raises(ValueError, match="摘要不匹配"):
        service.approve_and_verify(proposal["repair_id"], "0" * 64, approved_by="operator")
    assert service.get(proposal["repair_id"])["status"] == "awaiting_approval"


def test_tampered_baseline_cannot_be_approved(repair_case):
    source, claim, plan, service = repair_case
    proposal = service.prepare(claim, source, plan, run_id="run1")
    (service.root / proposal["repair_id"] / "baseline" / "calc.py").write_text("pass")
    with pytest.raises(ValueError, match="快照已变化"):
        service.approve_and_verify(
            proposal["repair_id"], proposal["approval_digest"], approved_by="operator"
        )


def test_startup_error_does_not_count_as_reproduction(repair_case):
    source, claim, plan, service = repair_case
    plan.regression_command = [sys.executable, "does-not-exist.py"]
    proposal = service.prepare(claim, source, plan, run_id="run1")
    result = service.approve_and_verify(
        proposal["repair_id"], proposal["approval_digest"], approved_by="operator"
    )
    assert result["status"] == "not_reproduced"
    assert "regression_result" not in result


def test_failed_fix_not_marked_passed(repair_case):
    source, claim, plan, service = repair_case
    plan.edits[0].after = "    return a / (b + 0)"
    proposal = service.prepare(claim, source, plan, run_id="run1")
    result = service.approve_and_verify(
        proposal["repair_id"], proposal["approval_digest"], approved_by="operator"
    )
    assert result["status"] == "regression_failed"


@pytest.mark.parametrize(
    "path",
    ["../x.py", "/tmp/x", "C:/x", "a/../x", ".env", "a/.env.local", "node_modules/x.js", "a\\x.py"],
)
def test_rejects_unsafe_paths(path):
    with pytest.raises(ValueError):
        FileEdit(path=path, before="a", after="b")


def test_http_proposal_requires_explicit_digest_then_runs_regression(repair_case, tmp_path):
    source, claim, plan, _ = repair_case
    app = create_app(make_settings(enable_repair=True), runs_dir=tmp_path / "runs")
    app.state.repairs.executor_factory = SubprocessReproductionExecutor
    app.state.store.create(RunRecord(run_id="run1", status="done", repo_path=str(source)))
    app.state.store.save_claims("run1", [claim])
    app.state.store.save_source_hashes(
        "run1", {"calc.py": hashlib.sha256((source / "calc.py").read_bytes()).hexdigest()}
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/audits/run1/repairs",
            json={"claim_id": claim.claim_id, "plan": plan.model_dump()},
        )
        assert response.status_code == 201, response.text
        proposal = response.json()
        path = f"/api/v1/audits/run1/repairs/{proposal['repair_id']}"
        assert client.get(path).json()["status"] == "awaiting_approval"
        assert client.get(path.replace("run1", "other")).status_code == 404
        assert client.post(path + "/approve", json={"approval_digest": "0" * 64}).status_code == 422
        done = client.post(path + "/approve", json={"approval_digest": proposal["approval_digest"]})
        assert done.status_code == 200, done.text
        assert done.json()["status"] == "regression_passed"


def test_http_refuses_repair_after_source_drift(repair_case, tmp_path):
    source, claim, plan, _ = repair_case
    app = create_app(make_settings(enable_repair=True), runs_dir=tmp_path / "runs")
    store = app.state.store
    store.create(RunRecord(run_id="run1", status="done", repo_path=str(source)))
    store.save_claims("run1", [claim])
    store.save_source_hashes(
        "run1", {"calc.py": hashlib.sha256((source / "calc.py").read_bytes()).hexdigest()}
    )
    with TestClient(app) as client:
        proposal = client.post(
            "/api/v1/audits/run1/repairs",
            json={"claim_id": claim.claim_id, "plan": plan.model_dump()},
        ).json()
        (source / "calc.py").write_text("def divide(a,b): return 0\n", encoding="utf-8")
        assert (
            client.post(
                "/api/v1/audits/run1/repairs",
                json={"claim_id": claim.claim_id, "plan": plan.model_dump()},
            ).status_code
            == 409
        )
        assert (
            client.post(
                f"/api/v1/audits/run1/repairs/{proposal['repair_id']}/approve",
                json={"approval_digest": proposal["approval_digest"]},
            ).status_code
            == 409
        )


def test_internal_token_protects_api_but_keeps_probe_available(tmp_path):
    app = create_app(
        make_settings(gateway_internal_token="test-internal-token"), runs_dir=tmp_path / "runs"
    )
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/v1/meta").status_code == 401
        assert client.get("/api/v1/meta", headers={"X-Internal-Token": "wrong"}).status_code == 401
        assert (
            client.get(
                "/api/v1/meta", headers={"X-Internal-Token": "test-internal-token"}
            ).status_code
            == 200
        )


def test_snapshot_must_match_audited_version(repair_case):
    source, claim, plan, service = repair_case
    with pytest.raises(ValueError, match="偏离审查版本"):
        service.prepare(claim, source, plan, run_id="run1", expected_hashes={"calc.py": "0" * 64})
