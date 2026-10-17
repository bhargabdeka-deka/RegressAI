from pathlib import Path

import pytest

from analyzer.parser import MAX_UPLOAD_SIZE_BYTES, LogParser

ROOT = Path(__file__).parents[1]
SAMPLE_LOGS = ROOT / "sample_logs"


def test_all_sample_logs_have_expected_results() -> None:
    parser = LogParser()
    successful = parser.parse_file(SAMPLE_LOGS / "successful_run.log")
    failed = parser.parse_file(SAMPLE_LOGS / "failed_run.log")
    repeated = parser.parse_file(SAMPLE_LOGS / "repeated_errors.log")

    assert (successful.total_tests, successful.passed_tests, successful.failed_tests) == (4, 4, 0)
    assert (failed.total_tests, failed.passed_tests, failed.failed_tests) == (4, 2, 2)
    assert (repeated.total_tests, repeated.passed_tests, repeated.failed_tests) == (2, 1, 1)
    assert len(repeated.error_groups) == 2
    assert repeated.error_groups[0].count == 3
    assert repeated.error_groups[0].line_numbers == [2, 3, 5]


def test_failed_test_count_is_independent_of_error_message_count() -> None:
    parsed = LogParser().parse_text(
        "TEST broken: FAIL\n"
        "ERROR: first detail\n"
        "ERROR: second detail\n"
    )

    assert parsed.failed_tests == 1
    assert parsed.error_count == 2


def test_empty_and_malformed_logs_are_safe() -> None:
    parser = LogParser()
    assert parser.parse_text("").total_tests == 0
    parsed = parser.parse_text("not a recognized line\n???\n")
    assert parsed.tests == []
    assert parsed.messages == []


def test_original_line_numbers_and_evidence_are_preserved() -> None:
    parsed = LogParser().parse_text(
        "unrecognized header\n\n[10:00:02] TEST memory_check: FAIL\n"
        "ERROR: allocation failed\n"
    )

    assert parsed.tests[0].line_number == 3
    assert parsed.tests[0].evidence == "[10:00:02] TEST memory_check: FAIL"
    assert parsed.messages[0].line_number == 4
    assert parsed.messages[0].evidence == "ERROR: allocation failed"


def test_missing_file_is_not_silently_ignored(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        LogParser().parse_file(tmp_path / "missing.log")


def test_oversized_upload_is_rejected() -> None:
    parser = LogParser()
    with pytest.raises(ValueError, match="upload limit"):
        parser.parse_bytes(b"x" * (MAX_UPLOAD_SIZE_BYTES + 1))


def test_invalid_utf8_upload_is_rejected() -> None:
    with pytest.raises(ValueError, match="UTF-8"):
        LogParser().parse_bytes(b"\xff\xfe")
