"""JSON and Markdown exports for deterministic log analysis."""

from __future__ import annotations

import html
import json
import re

from analyzer.parser import ParsedLog


def _escape_markdown_text(value: str) -> str:
    escaped = html.escape(value, quote=False).replace("\\", "\\\\")
    return re.sub(r"([`*_{}\[\]()#+\-.!|>])", r"\\\1", escaped)


def _inline_code(value: str) -> str:
    longest_tick_run = max(
        (len(match.group()) for match in re.finditer(r"`+", value)),
        default=0,
    )
    delimiter = "`" * (longest_tick_run + 1)
    padding = " " if value.startswith(("`", " ")) or value.endswith(("`", " ")) else ""
    return f"{delimiter}{padding}{value}{padding}{delimiter}"


class ReportGenerator:
    """Create portable reports from the same parsed analysis object."""

    @staticmethod
    def to_json(parsed_log: ParsedLog) -> str:
        return json.dumps(
            parsed_log.model_dump(mode="json"),
            indent=2,
            ensure_ascii=False,
        )

    @staticmethod
    def to_markdown(parsed_log: ParsedLog) -> str:
        lines = [
            f"# Regression report: {_escape_markdown_text(parsed_log.source_name)}",
            "",
            "## Summary",
            "",
            f"- Total tests: {parsed_log.total_tests}",
            f"- Passed tests: {parsed_log.passed_tests}",
            f"- Failed tests: {parsed_log.failed_tests}",
            f"- Error messages: {parsed_log.error_count}",
            f"- Warnings: {parsed_log.warning_count}",
            "",
            "## Test results",
            "",
        ]
        if parsed_log.tests:
            for test in parsed_log.tests:
                lines.append(
                    f"- **{test.status}** {_inline_code(test.name)} — "
                    f"line {test.line_number}: {_inline_code(test.evidence)}"
                )
        else:
            lines.append("No test results were detected.")

        lines.extend(["", "## Error groups", ""])
        if parsed_log.error_groups:
            for group in parsed_log.error_groups:
                lines.append(
                    f"- **{group.severity}** ({group.count} occurrence(s), "
                    f"lines {', '.join(map(str, group.line_numbers))}): "
                    f"{_escape_markdown_text(group.message)}"
                )
        else:
            lines.append("No errors or warnings were detected.")

        lines.extend(["", "## Supporting messages", ""])
        if parsed_log.messages:
            for message in parsed_log.messages:
                lines.append(
                    f"- Line {message.line_number} **{message.severity}**: "
                    f"{_inline_code(message.evidence)}"
                )
        else:
            lines.append("No supporting messages were detected.")

        return "\n".join(lines) + "\n"
