"""Tests for the post-deploy smoke test script."""




class TestSmokeScript:
    def test_step_result_dataclass(self):
        from scripts.post_deploy_smoke import StepResult

        r = StepResult(name="test", passed=True, status_code=200, duration_ms=42.0)
        assert r.passed is True
        assert r.status_code == 200
        assert r.duration_ms == 42.0
        assert r.error is None

    def test_print_report_all_pass(self, capsys):
        from scripts.post_deploy_smoke import StepResult, print_report

        results = [
            StepResult("healthz", True, 200, 10.0),
            StepResult("readyz", True, 200, 15.0),
        ]
        print_report(results)
        captured = capsys.readouterr()
        assert "All smoke tests passed" in captured.out

    def test_print_report_some_fail(self, capsys):
        from scripts.post_deploy_smoke import StepResult, print_report

        results = [
            StepResult("healthz", True, 200, 10.0),
            StepResult("readyz", False, 503, 100.0, "Connection refused"),
        ]
        print_report(results)
        captured = capsys.readouterr()
        assert "Smoke tests FAILED" in captured.out
        assert "readyz" in captured.out
