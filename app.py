"""Streamlit interface for the RegressAI demonstration."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from analyzer.ai_assistant import AIAssistant
from analyzer.parser import LogParser, ParsedLog
from analyzer.reports import ReportGenerator

SAMPLE_LOGS = Path(__file__).parent / "sample_logs"


def _render_analysis(parsed_log: ParsedLog) -> None:
    st.subheader(f"Analysis: {parsed_log.source_name}")
    metric_columns = st.columns(5)
    metric_columns[0].metric("Tests", parsed_log.total_tests)
    metric_columns[1].metric("Passed", parsed_log.passed_tests)
    metric_columns[2].metric("Failed", parsed_log.failed_tests)
    metric_columns[3].metric("Errors", parsed_log.error_count)
    metric_columns[4].metric("Warnings", parsed_log.warning_count)

    st.markdown("### Test results")
    if parsed_log.tests:
        st.dataframe(
            [
                {
                    "Result": test.status,
                    "Test": test.name,
                    "Line": test.line_number,
                    "Evidence": test.evidence,
                }
                for test in parsed_log.tests
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No test results were detected in this log.")

    st.markdown("### Repeated error patterns")
    if parsed_log.error_groups:
        st.dataframe(
            [
                {
                    "Severity": group.severity,
                    "Occurrences": group.count,
                    "Lines": ", ".join(map(str, group.line_numbers)),
                    "Message": group.message,
                }
                for group in parsed_log.error_groups
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No errors or warnings were detected.")

    with st.expander("All extracted log messages"):
        for message in parsed_log.messages:
            st.text(f"Line {message.line_number} [{message.severity}] {message.evidence}")

    st.markdown("### Optional Gemini diagnosis")
    st.caption(
        "Gemini is only used when you click the button below. The deterministic "
        "analysis and downloads work without an API key."
    )
    if st.button("Ask Gemini for diagnostic hypotheses"):
        result = AIAssistant().analyze(parsed_log)
        if result.available:
            st.markdown("#### AI-generated hypotheses (not deterministic facts)")
            st.write(result.summary)
            if result.cited_log_evidence:
                st.markdown("**Cited log evidence**")
                for citation in result.cited_log_evidence:
                    st.text(f"Line {citation.line_number}: {citation.quote}")
            if result.possible_causes:
                st.markdown("**Possible causes**")
                for cause in result.possible_causes:
                    st.markdown(f"- {cause}")
            if result.debugging_steps:
                st.markdown("**Debugging steps**")
                for step in result.debugging_steps:
                    st.markdown(f"- {step}")
            if result.missing_information:
                st.markdown("**Information still needed**")
                for item in result.missing_information:
                    st.markdown(f"- {item}")
        else:
            st.warning(result.error or "AI diagnosis is unavailable.")

    st.caption(
        "JSON and Markdown downloads contain deterministic results; Gemini output "
        "is shown separately and is not included in those reports."
    )
    json_report = ReportGenerator.to_json(parsed_log)
    markdown_report = ReportGenerator.to_markdown(parsed_log)
    download_columns = st.columns(2)
    download_columns[0].download_button(
        "Download JSON",
        data=json_report,
        file_name="regressai-report.json",
        mime="application/json",
    )
    download_columns[1].download_button(
        "Download Markdown",
        data=markdown_report,
        file_name="regressai-report.md",
        mime="text/markdown",
    )


def main() -> None:
    st.set_page_config(page_title="RegressAI", page_icon="🧪", layout="wide")
    st.title("RegressAI")
    st.caption("Deterministic regression log analysis with optional AI-assisted hypotheses.")

    source = st.sidebar.radio("Log source", ["Sample log", "Upload a log"])
    log_parser = LogParser()
    parsed_log: ParsedLog | None = None

    if source == "Sample log":
        sample_paths = sorted(SAMPLE_LOGS.glob("*.log"))
        if not sample_paths:
            st.error(f"No sample logs were found in {SAMPLE_LOGS}.")
            return
        selected_path = st.sidebar.selectbox(
            "Choose a sample",
            sample_paths,
            format_func=lambda path: path.name,
            index=1 if len(sample_paths) > 1 else 0,
        )
        try:
            parsed_log = log_parser.parse_file(selected_path)
        except (OSError, ValueError) as exc:
            st.error(f"Could not analyze the selected sample: {exc}")
            return
    else:
        uploaded_file = st.sidebar.file_uploader(
            "Upload a .log or .txt file",
            type=["log", "txt"],
        )
        if uploaded_file is not None:
            try:
                parsed_log = log_parser.parse_bytes(
                    uploaded_file.getvalue(),
                    source_name=uploaded_file.name,
                )
            except (OSError, ValueError) as exc:
                st.error(f"Could not analyze the uploaded log: {exc}")

    if parsed_log is not None:
        _render_analysis(parsed_log)
    else:
        st.info("Choose a sample log or upload a UTF-8 .log/.txt file to begin.")


if __name__ == "__main__":
    main()
