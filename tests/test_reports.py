import json

from analyzer.parser import LogParser
from analyzer.reports import ReportGenerator


def test_json_and_markdown_reports_are_consistent() -> None:
    parsed = LogParser().parse_text(
        "TEST alpha: FAIL\n"
        "ERROR: device did not respond\n"
        "ERROR: device did not respond\n",
        source_name="run.log",
    )

    json_report = json.loads(ReportGenerator.to_json(parsed))
    markdown_report = ReportGenerator.to_markdown(parsed)

    assert json_report["failed_tests"] == 1
    assert json_report["error_count"] == 2
    assert json_report["tests"][0]["line_number"] == 1
    assert json_report["tests"][0]["evidence"] == "TEST alpha: FAIL"
    assert json_report["messages"][0]["line_number"] == 2
    assert json_report["error_groups"][0]["count"] == 2
    assert "Failed tests: 1" in markdown_report
    assert "Error messages: 2" in markdown_report
    assert "lines 2, 3" in markdown_report
    assert "Line 2 **ERROR**: `ERROR: device did not respond`" in markdown_report


def test_markdown_report_escapes_untrusted_log_text() -> None:
    parsed = LogParser().parse_text(
        "TEST `broken`: FAIL\n"
        "ERROR: <script>alert(1)</script> `quoted`",
        source_name="<img src=x onerror=alert(1)>.log",
    )

    markdown_report = ReportGenerator.to_markdown(parsed)

    assert "<img" not in markdown_report
    assert "Regression report: &lt;img" in markdown_report
    assert "&lt;script&gt;alert\\(1\\)&lt;/script&gt;" in markdown_report
    assert "`` ERROR: <script>alert(1)</script> `quoted` ``" in markdown_report
