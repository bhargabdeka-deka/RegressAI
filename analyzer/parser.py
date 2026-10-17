"""Deterministic parsing for common text-based test logs."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, computed_field

MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024

_TIMESTAMP_PATTERN = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]")
_TEST_PATTERN = re.compile(
    r"\bTEST\s+(?P<name>.+?)\s*:\s*(?P<status>PASS|FAIL)\b",
    re.IGNORECASE,
)
_ERROR_PATTERN = re.compile(
    r"(?:^|\s)(?:ERROR|FATAL|CRITICAL)\s*:?\s*(?P<message>.*)",
    re.IGNORECASE,
)
_WARNING_PATTERN = re.compile(
    r"(?:^|\s)(?:WARNING|WARN)\s*:?\s*(?P<message>.*)",
    re.IGNORECASE,
)
_TIMEOUT_PATTERN = re.compile(r"\btimeout\b", re.IGNORECASE)


class TestResult(BaseModel):
    """One test result, with its original source location."""

    model_config = ConfigDict(frozen=True)

    name: str
    status: Literal["PASS", "FAIL"]
    line_number: int
    timestamp: str | None = None
    evidence: str


class ErrorMessage(BaseModel):
    """One error or warning extracted from the original log."""

    model_config = ConfigDict(frozen=True)

    severity: Literal["ERROR", "WARNING"]
    message: str
    line_number: int
    timestamp: str | None = None
    evidence: str


class ErrorGroup(BaseModel):
    """Repeated, identical error messages grouped deterministically."""

    severity: Literal["ERROR", "WARNING"]
    message: str
    count: int
    line_numbers: list[int]


class ParsedLog(BaseModel):
    """Parsed test results and messages, retaining original line evidence."""

    source_name: str
    tests: list[TestResult]
    messages: list[ErrorMessage]

    @computed_field
    @property
    def total_tests(self) -> int:
        return len(self.tests)

    @computed_field
    @property
    def passed_tests(self) -> int:
        return sum(test.status == "PASS" for test in self.tests)

    @computed_field
    @property
    def failed_tests(self) -> int:
        return sum(test.status == "FAIL" for test in self.tests)

    @computed_field
    @property
    def error_count(self) -> int:
        return sum(message.severity == "ERROR" for message in self.messages)

    @computed_field
    @property
    def warning_count(self) -> int:
        return sum(message.severity == "WARNING" for message in self.messages)

    @computed_field
    @property
    def error_groups(self) -> list[ErrorGroup]:
        groups: dict[tuple[str, str], list[ErrorMessage]] = defaultdict(list)
        for message in self.messages:
            groups[(message.severity, message.message.casefold())].append(message)
        return [
            ErrorGroup(
                severity=items[0].severity,
                message=items[0].message,
                count=len(items),
                line_numbers=[item.line_number for item in items],
            )
            for items in groups.values()
        ]


class LogParser:
    """Parse supported log lines without inferring test counts from messages."""

    max_upload_size_bytes = MAX_UPLOAD_SIZE_BYTES

    def parse_file(self, path: str | Path) -> ParsedLog:
        log_path = Path(path)
        content = log_path.read_bytes()
        return self.parse_bytes(content, source_name=log_path.name)

    def parse_bytes(self, content: bytes, source_name: str = "uploaded.log") -> ParsedLog:
        if len(content) > self.max_upload_size_bytes:
            raise ValueError(
                f"Log exceeds the {self.max_upload_size_bytes // (1024 * 1024)} MB upload limit."
            )
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Log files must use UTF-8 text encoding.") from exc
        return self.parse_text(text, source_name=source_name)

    def parse_text(self, text: str, source_name: str = "uploaded.log") -> ParsedLog:
        if len(text.encode("utf-8")) > self.max_upload_size_bytes:
            raise ValueError(
                f"Log exceeds the {self.max_upload_size_bytes // (1024 * 1024)} MB upload limit."
            )

        tests: list[TestResult] = []
        messages: list[ErrorMessage] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            timestamp_match = _TIMESTAMP_PATTERN.search(line)
            timestamp = timestamp_match.group(1) if timestamp_match else None

            test_match = _TEST_PATTERN.search(line)
            if test_match:
                status: Literal["PASS", "FAIL"] = (
                    "PASS"
                    if test_match.group("status").upper() == "PASS"
                    else "FAIL"
                )
                tests.append(
                    TestResult(
                        name=test_match.group("name").strip(),
                        status=status,
                        line_number=line_number,
                        timestamp=timestamp,
                        evidence=line,
                    )
                )
                continue

            error_match = _ERROR_PATTERN.search(line)
            warning_match = _WARNING_PATTERN.search(line)
            if error_match:
                severity: Literal["ERROR", "WARNING"] = "ERROR"
                message_text = error_match.group("message").strip() or line.strip()
            elif warning_match:
                severity = "WARNING"
                message_text = warning_match.group("message").strip() or line.strip()
            elif _TIMEOUT_PATTERN.search(line):
                severity = "ERROR"
                message_text = line.strip()
            else:
                continue

            messages.append(
                ErrorMessage(
                    severity=severity,
                    message=message_text,
                    line_number=line_number,
                    timestamp=timestamp,
                    evidence=line,
                )
            )

        return ParsedLog(source_name=source_name, tests=tests, messages=messages)
