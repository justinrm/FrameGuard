from frameguard.models import (
    CheckResult,
    Finding,
    calculate_status,
    exit_code,
)


def check(
    status: str = "completed", *, required: bool = True, reason: str | None = None
) -> CheckResult:
    return CheckResult("probe", status, required=required, reason_code=reason)


def finding(severity: str, *, provisional: bool = False) -> Finding:
    return Finding(
        code="TEST",
        severity=severity,
        title="test",
        explanation="test",
        check_id="probe",
        provisional=provisional,
    )


def test_status_and_exit_truth_table() -> None:
    assert calculate_status([check()], []) == "pass"
    assert calculate_status([check()], [finding("info")]) == "pass"
    assert calculate_status([check()], [finding("warning")]) == "warn"
    assert exit_code("warn") == 0
    assert calculate_status([check()], [finding("critical")]) == "fail"
    assert exit_code("fail") == 1
    assert calculate_status([check("failed")], [finding("critical")]) == "incomplete"
    assert exit_code("incomplete") == 2


def test_legitimate_optional_skips_do_not_force_incomplete() -> None:
    checks = [
        check("skipped", required=False, reason="not_configured"),
        CheckResult("silence", "skipped", required=False, reason_code="no_audio"),
    ]
    assert calculate_status(checks, [finding("info")]) == "pass"
    assert exit_code(None, execution_error=True) == 2
