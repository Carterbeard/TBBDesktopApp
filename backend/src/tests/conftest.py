import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if report.when not in {"call", "setup"}:
        return

    if report.when == "setup" and not report.skipped:
        return

    terminal_reporter = item.config.pluginmanager.getplugin("terminalreporter")
    if terminal_reporter is None:
        return

    if report.passed:
        status = "PASS"
    elif report.failed:
        status = "FAIL"
    else:
        status = "SKIP"

    duration = getattr(report, "duration", 0.0)
    terminal_reporter.write_line(f"[{status}] {item.nodeid} ({duration:.3f}s)")