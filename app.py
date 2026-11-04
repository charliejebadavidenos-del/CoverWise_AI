from hashlib import sha256

import streamlit as st

import json

from src.clause_extractor import extract_clauses
from src.policy_comparator import compare_policies
from src.pdf_reader import extract_pdf_pages
from src.policy_qa import answer_question
from src.policy_retriever import PolicyRetriever

from pathlib import Path
from src.pdf_report import build_summary_pdf

from groq import RateLimitError

st.set_page_config(page_title="CoverWise", page_icon="📄")
st.title("CoverWise")
st.write("Upload a health insurance policy and ask a question about its terms.")
st.caption("Use a sample or redacted PDF. Relevant excerpts are sent to Groq when you ask a question.")


reports_dir = Path(__file__).resolve().parent / "reports"
if not reports_dir.is_dir():
    reports_dir = reports_dir.parent.parent / "reports"

with st.expander("Restriction score — SBI demo"):
    score_path = reports_dir / "SBI_Insurance_reviewed_scenario_score.json"

    if score_path.is_file():
        report = json.loads(score_path.read_text(encoding="utf-8"))
        st.write(report["scenario"])

        score = report["score"]
        if score is None:
            st.info("Restriction count withheld. Some rules need review.")
        else:
            st.metric("Applicable restrictions", f"{score}/{report['maximum']}")

        for rule in report["applicable"]:
            st.write(rule.replace("_", " ").capitalize())
    else:
        st.info("Run the risk scorer to generate the SBI demo report.")

def render_comparison(report):
    st.write(f"{report['current_document']} vs. {report['proposed_document']}")
    st.caption(report["scenario"])

    for row in report["comparison"]:
        rule = row["rule"].replace("_", " ").capitalize()
        st.markdown(f"**{rule}**")
        st.write(row["status"])

        current, proposed = st.columns(2)
        current.write("Current")
        proposed.write("Proposed")

        for column, values in (
            (current, row["current"]),
            (proposed, row["proposed"]),
        ):
            if values is None:
                column.write("Needs review")
            else:
                column.json(values)

with st.expander("Policy comparison — demo"):
    comparison_path = reports_dir / "policy_comparison.json"

    if comparison_path.is_file():
        report = json.loads(comparison_path.read_text(encoding="utf-8"))
        render_comparison(report)
    else:
        st.info("Run the policy comparator to generate the demo comparison.")



REVIEW_NUMERIC_FIELDS = {
    "copayment": {"percent_of_admissible_claim"},
    "initial_waiting_period": {"days"},
    "pre_existing_disease_waiting_period": {"base_months"},
    "room_or_icu_cap": {
        "room_board_nursing_percent_of_sum_insured_per_day",
        "icu_percent_of_sum_insured_per_day",
        "combined_percent_of_sum_insured_per_illness_or_injury",
    },
}


def parse_reviewed_terms(rule, terms, sources):
    label = rule.replace("_", " ").capitalize()
    try:
        parsed = json.loads(terms)
    except ValueError as exc:
        raise ValueError(f"{label}: enter valid JSON.") from exc

    if not isinstance(parsed, dict) or not sources:
        raise ValueError(f"{label}: enter a JSON object and select supporting pages.")

    numeric_fields = REVIEW_NUMERIC_FIELDS[rule]
    supplied_fields = parsed.keys() & numeric_fields
    if not supplied_fields or parsed.keys() - numeric_fields - {"condition"}:
        expected = ", ".join(sorted(numeric_fields))
        raise ValueError(f"{label}: enter at least one of {expected}. Condition is optional.")

    for field in supplied_fields:
        value = parsed[field]
        if field in {"days", "base_months"}:
            valid = type(value) is int and value >= 0
        else:
            valid = type(value) in (int, float) and 0 <= value <= 100
        if not valid:
            raise ValueError(f"{label}: invalid number for {field}.")

    if "condition" in parsed and not isinstance(parsed["condition"], str):
        raise ValueError(f"{label}: condition must be text.")

    return {**parsed, "source_pages": sources}



with st.expander("Compare a proposed policy PDF"):
    current_path = reports_dir / "SBI_Insurance_reviewed_scenario_score.json"
    if not current_path.is_file():
        st.info("Generate the reviewed SBI score report to use this comparison.")
    else:
        current_report = json.loads(current_path.read_text(encoding="utf-8"))
        st.write(f"Current policy: {current_report['document_name']}")
        st.caption(current_report["scenario"])
        st.caption("Use a sample or redacted PDF. Extraction sends policy text to Groq.")

        proposed_pdf = st.file_uploader(
            "Proposed policy PDF", type=["pdf"], key="proposed_policy_pdf"
        )
        if proposed_pdf is None:
            st.session_state.pop("proposed_policy_review", None)
        else:
            proposed_bytes = proposed_pdf.getvalue()
            proposed_key = (proposed_pdf.name, sha256(proposed_bytes).hexdigest())
            if st.session_state.get("proposed_policy_review", {}).get("key") != proposed_key:
                st.session_state["proposed_policy_review"] = {"key": proposed_key}
            review = st.session_state["proposed_policy_review"]

            if st.button("Extract proposed policy clauses"):
                review.pop("findings", None)
                review.pop("comparison", None)
                try:
                    pages = extract_pdf_pages(proposed_bytes, proposed_pdf.name)

                    if proposed_pdf.name == "Family Medicare Policy.pdf":
                        pages = [page for page in pages if page["page_number"] == 6]
                        st.caption("Live demo scope: Family Medicare Policy, PDF page 6 only.")


                    if not any(page["text"].strip() for page in pages):
                        raise ValueError("The PDF has no extractable text.")

                    page_scope = tuple(page["page_number"] for page in pages)
                    completed_batches = review.setdefault("batches_by_scope", {}).setdefault(page_scope, {})

                    findings = {}
                    progress = st.progress(0, text="Extracting policy clauses...")

                    try:
                        for start in range(0, len(pages), 3):
                            if start not in completed_batches:
                                completed_batches[start] = extract_clauses(
                                    pages[start:start + 3]
                                )

                            for clause in completed_batches[start]["clauses"]:
                                if clause["status"] == "found":
                                    findings.setdefault(clause["name"], []).append(clause)

                            progress.progress(min(start + 3, len(pages)) / len(pages))
                    finally:
                        progress.empty()
                        if findings:
                            review["findings"] = findings

                except RateLimitError as exc:
                    retry_after = exc.response.headers.get("retry-after")
                    if retry_after:
                        st.warning(f"Groq rate limit reached. Retry-After: {retry_after}")
                    else:
                        st.warning("Groq rate limit reached. No retry time was provided.")
                except Exception as exc:
                    st.error(
                        f"Extraction failed ({type(exc).__name__}). "
                        "Check the PDF and Groq configuration, then retry."
                    )

            if "findings" in review:
                st.caption(
                    "Review the quoted evidence in the PDF. Enter a JSON object with "
                    "the applicable terms, or leave the field blank for Needs review. "
                    "Use the same field names as the current policy where applicable."
                )
                with st.form("proposed_review_" + proposed_key[1]):
                    entries = {}
                    for rule, current_values in current_report["reviewed_values"].items():
                        st.markdown(f"**{rule.replace('_', ' ').capitalize()}**")
                        if current_values:
                            st.json(current_values, expanded=False)
                        names = ("room_rent_limit", "icu_limit") if rule == "room_or_icu_cap" else (rule,)
                        evidence = [
                            clause for name in names
                            for clause in review["findings"].get(name, [])
                        ]
                        for clause in evidence:
                            st.caption(f"PDF page {clause['page_number']}")
                            st.text(clause["evidence"])
                        if not evidence:
                            st.caption("No verified passage was extracted for this term.")
                        else:
                            terms = st.text_area("Reviewed terms (JSON)", key=f"{proposed_key}_{rule}_terms")
                            sources = st.multiselect(
                                "Supporting PDF pages",
                                sorted({clause["page_number"] for clause in evidence}),
                                key=f"{proposed_key}_{rule}_pages",
                            )
                            entries[rule] = (terms, sources)
                    compare = st.form_submit_button("Compare reviewed terms")

                if compare:
                    review.pop("comparison", None)
                    try:
                        values = dict.fromkeys(current_report["reviewed_values"])
                        for rule, (terms, sources) in entries.items():
                            if not terms.strip():
                                continue
                            values[rule] = parse_reviewed_terms(rule, terms, sources)
                        review["comparison"] = compare_policies(
                            current_report,
                            {
                                "document_name": proposed_pdf.name,
                                "scenario": current_report["scenario"],
                                "reviewed_values": values,
                            },
                        )
                    except ValueError as exc:
                        st.error(str(exc))

                if "comparison" in review:
                    render_comparison(review["comparison"])


## Summary and advisory questions

with st.expander("Summary and advisor questions — SBI demo"):
    summary_path = reports_dir / "SBI_Insurance_reviewed_scenario_score.json"

    if summary_path.is_file():
        score_report = json.loads(summary_path.read_text(encoding="utf-8"))
        applicable = score_report["applicable"]
        unresolved = score_report["unresolved"]

        st.write(score_report["scenario"])
        st.write(
            f"{len(applicable)} applicable restrictions and "
            f"{len(unresolved)} rules needing review."
        )

        advisor_questions = {
            "copayment": "Is my preferred hospital in network, and what would I pay if it is outside the network?",
            "room_or_icu_cap": "Which room and ICU limits apply, and how would exceeding them affect the claim?",
            "initial_waiting_period": "When does my initial waiting period end, and which exceptions apply?",
            "pre_existing_disease_waiting_period": "How much continuity credit will you recognize, and what waiting period remains?",
        }

        st.download_button(
            "Download SBI summary as PDF",
            data=build_summary_pdf(score_report, advisor_questions),
            file_name="CoverWise_SBI_Demo_Summary.pdf",
            mime="application/pdf",
        )

        for rule in applicable + unresolved:
            label = rule.replace("_", " ").capitalize()
            values = score_report["reviewed_values"].get(rule) or {}
            pages = values.get("source_pages", [])

            st.markdown(f"**{label}**")
            st.write("Needs review" if rule in unresolved else "Applies in this scenario")
            if pages:
                st.caption("SBI PDF pages " + ", ".join(map(str, pages)))
            if rule in advisor_questions:
                st.write(advisor_questions[rule])
    else:
        st.info("Run the risk scorer to generate the SBI demo report.")

uploaded = st.file_uploader("Policy PDF", type=["pdf"])

if uploaded is None:
    st.session_state.pop("policy_qa", None)
    st.stop()

pdf_bytes = uploaded.getvalue()
document_key = (uploaded.name, sha256(pdf_bytes).hexdigest())

if st.session_state.get("policy_qa", {}).get("key") != document_key:
    st.session_state["policy_qa"] = {"key": document_key}

state = st.session_state["policy_qa"]

with st.form("policy_question"):
    question = st.text_input("Your question")
    submitted = st.form_submit_button("Ask CoverWise")

if submitted:
    state.pop("answer", None)

    if not question.strip():
        st.warning("Enter a question about the policy.")
    else:
        try:
            if "retriever" not in state:
                with st.spinner("Reading and indexing the PDF..."):
                    pages = extract_pdf_pages(pdf_bytes, uploaded.name)
                    state["retriever"] = PolicyRetriever(pages)

            with st.spinner("Checking the policy wording..."):
                state["answer"] = answer_question(
                    state["retriever"], question.strip()
                )

        except RateLimitError as exc:
            retry_after = exc.response.headers.get("retry-after", "").strip()
            if retry_after.isdecimal():
                st.warning(f"Groq rate limit reached. Try again in {retry_after} seconds.")
            else:
                st.warning("Groq rate limit reached. Please try again later.")

        except Exception as exc:
            st.error(
                f"CoverWise could not complete the request ({type(exc).__name__}). "
                "Check the PDF and your Groq configuration, then try again."
            )

if "answer" in state:
    st.subheader("Answer from the policy")
    st.text(state["answer"])