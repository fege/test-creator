#!/usr/bin/env python3
"""Deterministic evidence checks used by the test-plan quality gate.

Scope coverage is intentionally based on the structured AC/NFR identifiers in Section 1.3,
not on trying to decide whether arbitrary strategy prose is semantically similar to plan prose.
Actionability checks the explicit, operational fields in Section 3.
"""

import re
from pathlib import Path

from scripts.utils.consolidate_gaps import ACTIONABILITY_TEST_DATA_GAP, ACTIONABILITY_VERSION_LABELS
from scripts.utils.markdown_utils import (
    extract_section,
    parse_citations,
    parse_numbered_objectives,
    parse_table_rows,
    strip_markdown_presentation,
)
from scripts.utils.schemas import TEMPLATE_HEADINGS
from scripts.utils.strat_utils import parse_acceptance_criteria, parse_nfr


_VERSION_LABELS = ACTIONABILITY_VERSION_LABELS
_TBD_RE = re.compile(r"\bTBD\b", re.IGNORECASE)
_VAGUE_VERSION_RE = re.compile(
    r"^(?:latest|current|the supported version|to be determined|unknown|unspecified|not specified|pending|"
    r"unavailable|\d+(?:\.\d+){0,2}\+)$",
    re.IGNORECASE,
)
_VAGUE_VERSION_HINT_RE = re.compile(
    r"\b(?:latest|current|supported|unknown|unspecified|not specified|pending|unavailable|"
    r"not available|not applicable|to be determined|to be decided|selected|provided|confirmed|determined|"
    r"specified|defined|stable|minimum|maximum|range|or\s+(?:later|newer)|and\s+(?:above|newer))\b"
    r"|(?:\d+(?:\.\d+){0,2})\s*(?:\+|\.?\s*[xX])"
    r"|(?:\d+(?:\.\d+){0,2})\s*[-\u2013\u2014/]\s*\d",
    re.IGNORECASE,
)
_VERSION_FIELD_RE = re.compile(
    r"^\s*(?:[-*+]\s+)?(?P<label>"
    r"OpenShift(?:\s+AI)?\s+version|"
    r"OpenShift\s+cluster\s*[-\u2013\u2014]\s*version|"
    r"RHOAI\s+version|"
    r"RHOAI(?:\s+[^:]+?)?\s*[-\u2013\u2014]\s*(?:exact\s+)?build"
    r")\s*:\s*(?P<value>.*?)\s*$",
    re.IGNORECASE,
)
_OBJECTIVE_REF_RE = re.compile(r"\(Objective:\s*#(\d+)\)", re.IGNORECASE)
_NOT_APPLICABLE_RE = re.compile(r"^\*\*Not Applicable\*\*", re.IGNORECASE)
_NFR_SECTIONS = frozenset({"7.1", "7.2", "7.3", "7.4", "7.5"})
_TBD_RESOLUTION_RE = re.compile(
    r"\bTBD — Resolution:\s*"
    r"(?i:resolve|retrieve|obtain|confirm|determine|check|verify|derive)\b.*?"
    r"\b(?P<connector>(?i:from|with|by|before|after|using))\b\s*(?P<target>[^.;\n]+)",
)
_GENERIC_RESOLUTION_TARGET_RE = re.compile(
    r"^(?:(?:the|a|an|some|any|appropriate|relevant|responsible|right|correct)\s+)*"
    r"(?:(?:test(?:ing)?|feature|product|project|development|developer|qa|qe|quality assurance|engineering)\s+)*"
    r"(?:someone|somebody|anyone|anybody|person|people|teams?|owners?|stakeholders?|engineering|"
    r"documentation|docs?|source|information|details?)$",
    re.IGNORECASE,
)
_NAMED_SOURCE_OR_OWNER_RE = re.compile(
    r"\b[A-Z][A-Z0-9]+-\d+\b"
    r"|\b(?:[\w/-]+\s+)+(?:teams?|engineering|owners?|managers?|administrators?|leads?|maintainers?|operators?)\b"
    r"|\b(?:ADR|API spec(?:ification)?|feature refinement|design doc(?:ument)?|"
    r"design[- ]?spec(?:ification)?|Jira (?:issue|ticket))\b"
    r"|\b(?:[\w/-]+\s+)+(?:matrix|runbook|guide|roadmap|document|specification|release notes)\b"
    r"|\boverlay(?:\s+\d+|\s+(?:requirements?|documentation|docs?))\b",
    re.IGNORECASE,
)
_CONCRETE_TIMING_RE = re.compile(
    r"\b(?:before|after|by)\s+(?:the\s+)?(?:(?:end of|next)\s+)?(?:environment\s+)?"
    r"(?:setup|provisioning|test(?:ing)?(?:\s+(?:setup|execution))?|release|deployment|"
    r"kickoff|go/no-go(?:\s+decision)?|design review|sprint planning)\b",
    re.IGNORECASE,
)
_CONCRETE_PERMISSION_RE = re.compile(
    r"\b(?:create|get|list|watch|update|patch|delete|read|write|use|admin|cluster-admin)\b", re.IGNORECASE
)
_CONCRETE_PROSE_RESOURCE_RE = re.compile(
    r"\b[a-z0-9][\w.-]*\s+(?:namespaces?|projects?|service accounts?|endpoints?|apis?|crds?|models?|"
    r"stores?|pipelines?|dashboards?|resources?)\b",
    re.IGNORECASE,
)
_BROAD_PROSE_RESOURCE_RE = re.compile(
    r"\b(?:all|any|every)\s+(?:[a-z0-9][\w.-]*\s+){0,3}(?:namespaces?|projects?|service accounts?|"
    r"endpoints?|apis?|crds?|models?|stores?|pipelines?|dashboards?|resources?)\b",
    re.IGNORECASE,
)
_GENERIC_RESOURCE_VALUES = {"resource", "resources", "the resource", "all resources", "*"}
_INFRASTRUCTURE_DETAIL_RE = re.compile(
    r"\b(?:with|using|via|uses?|installed?|provision(?:ed|ing)?|deploy(?:ed|ment)?|running|"
    r"support(?:s|ing)?|includes?|requires?|namespace|project|node|gpu|cpu|memory|storage|"
    r"network|operator|service|registry|database|quota|capacity|secret|credential(?:s)?)\b",
    re.IGNORECASE,
)
_UNAVAILABLE_INFRA_VALUE_RE = re.compile(r"^(?:unavailable|not available)$", re.IGNORECASE)
_TEST_DATA_FORMAT_RE = re.compile(r"\b[*_]{0,2}formats?[*_]{0,2}\s*:\s*[*_]{0,2}(?P<value>[^;\n|]*)", re.IGNORECASE)
_TEST_DATA_FORMAT_WORD_RE = re.compile(
    r"\b(?:json|yaml|yml|xml|csv|payload|schema|object|record|field|"
    r"string|strings|identifier|identifiers|manifest|manifests|uri|uris|url|urls|"
    r"name|names|path|paths|secret|secrets)\b",
    re.IGNORECASE,
)
_TEST_DATA_EXAMPLE_CLAUSE_RE = re.compile(
    r"\b(?:for\s+example|e\.g\.)\s*(?:[,;:=]|is|such\s+as|[-\u2013\u2014])?\s*"
    r"(?P<value>[^;\n|]+)",
    re.IGNORECASE,
)
_TEST_DATA_EXAMPLE_LABEL_RE = re.compile(
    r"(?im)(?:^|(?<=[.;|,(:]))\s*(?:[-*+]\s+)?[*_]{0,2}(?:example|sample|fixture)"
    r"(?:\s+(?:value|payload|data|manifest|uri|url))?[*_]{0,2}\s*"
    r"(?::|=|is|such\s+as|[-\u2013\u2014])[*_]{0,2}\s*(?P<value>[^;\n|]+)",
)
_BACKTICKED_VALUE_RE = re.compile(r"`([^`\n]+)`")
_STRUCTURED_EXAMPLE_RE = re.compile(r"\{[^{}\n]+\}|\[[^\[\]\n]+\]|<[^<>\n]+>")
_QUOTED_EXAMPLE_RE = re.compile(r"(['\"])(?P<value>[^'\"\n]+)\1")
_URI_EXAMPLE_RE = re.compile(r"\b(?:https?|hf)://[^\s)>,|;]+", re.IGNORECASE)
_MANIFEST_FIELD_RE = re.compile(r"\b(?:apiVersion|kind|metadata|spec)\s*:\s*(?P<value>[^\n;|]+)", re.IGNORECASE)
_GENERIC_EXAMPLE_VALUES = frozenset(
    {
        "a valid token",
        "a model identifier",
        "an api payload",
        "a json object",
        "a yaml manifest",
    }
)
_MARKDOWN_ENTRY_START_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+\.\s+|\|\s*|#{1,6}\s+)")
_FIELD_ENTRY_START_RE = re.compile(r"^[A-Za-z][^:\n]{0,80}:(?=\s|$)")


def _is_field_entry_start(line: str) -> bool:
    """Return whether a physical line starts a standalone field.

    Colons in prose continuations, such as ``... — label:`` or ``...(Owner: ...``, do not
    introduce a new logical entry. A simple ``Owner: ...`` line still does, preserving the
    generic-owner rejection for wrapped resolution paths.
    """
    normalized = re.sub(r"[*_`]", "", line).lstrip()
    if not _FIELD_ENTRY_START_RE.match(normalized):
        return False
    label = normalized.split(":", 1)[0]
    return not re.search(r"[—–]|\([^)]*$", label)


def _missing(section: str, text: str, reason: str) -> dict:
    return {"section": section, "text": text, "reason": reason}


def _objective_records(content: str) -> list[dict]:
    lines, start_line = extract_section(content, TEMPLATE_HEADINGS["1.3"])
    if not lines:
        return []
    return [
        {
            "section": "1.3",
            "number": objective["num"],
            "text": objective["text"],
            "line_number": start_line + objective["line_index"],
        }
        for objective in parse_numbered_objectives(lines)
    ]


def _scope_entries(lines: list[str], section: str) -> list[dict]:
    """Return meaningful entries from a scope-bearing section and their objective references.

    The contract intentionally requires an explicit ``(Objective: #N)`` marker. It does not try
    to derive a relationship from free-form wording. Section 8's table rows use the risk cell as
    the displayed entry while searching the whole row for the marker.
    """
    entries = []
    paragraph = []
    in_out_of_scope = False

    def add_paragraph() -> None:
        if not paragraph or in_out_of_scope:
            return
        text = " ".join(paragraph)
        entries.append({"section": section, "text": paragraph[0], "references": _OBJECTIVE_REF_RE.findall(text)})

    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            add_paragraph()
            paragraph = []
            table_lines = []
            while index < len(lines):
                candidate = lines[index].strip()
                if not (candidate.startswith("|") and candidate.endswith("|")):
                    break
                table_lines.append(candidate)
                index += 1
            rows = parse_table_rows(table_lines)
            for row in rows:
                if row and not in_out_of_scope:
                    entries.append(
                        {"section": section, "text": row[0], "references": _OBJECTIVE_REF_RE.findall(" | ".join(row))}
                    )
            continue
        if not stripped:
            add_paragraph()
            paragraph = []
        elif stripped.startswith("#"):
            add_paragraph()
            paragraph = []
            in_out_of_scope = section == "1.2" and "out of scope" in stripped.casefold()
        elif re.fullmatch(r"-{3,}", stripped):
            add_paragraph()
            paragraph = []
        elif re.match(r"^\d+\.\s+", stripped):
            add_paragraph()
            paragraph = [re.sub(r"^\d+\.\s+", "", stripped)]
        elif re.match(r"^[-*+]\s+", stripped):
            add_paragraph()
            paragraph = [re.sub(r"^[-*+]\s+", "", stripped)]
        else:
            paragraph.append(stripped)
        index += 1
    add_paragraph()
    return entries


def _scope_records(content: str) -> list[dict]:
    records = []
    for section in ("1.2", "2.3", "7.1", "7.2", "7.3", "7.4", "7.5", "8"):
        _, lines = _section_text(content, section)
        records.extend(_scope_entries(lines, section))
    return records


def validate_scope_coverage(testplan_path: str, strategy_content: str) -> dict:
    """Check both directions of the structured strategy-requirement/objective mapping.

    A strategy requirement is covered only when a Section 1.3 objective cites its AC number or
    NFR category. Conversely, every recognized citation in an objective must resolve to a real
    requirement. This deliberately does not compare arbitrary prose from Sections 1.2, 2.3, 7.x,
    or 8 with Jira text: that would produce unreliable false matches for STRAT-specific language.
    """
    path = Path(testplan_path)
    if not path.exists():
        return {
            "valid": False,
            "missing": [_missing("1.3", "TestPlan.md", "test plan is missing")],
            "unmapped_objectives": [],
        }

    ac_requirements = parse_acceptance_criteria(strategy_content)["acceptance_criteria"]
    nfr_requirements = parse_nfr(strategy_content)["requirements"]
    requirements = {
        ("AC", requirement["num"]): f"AC #{requirement['num']} — {requirement['text']}"
        for requirement in ac_requirements
    }
    requirements.update(
        {
            ("NFR", requirement["category"].casefold()): f"NFR: {requirement['category']} — {requirement['text']}"
            for requirement in nfr_requirements
        }
    )

    content = path.read_text()
    objectives = _objective_records(content)
    objective_numbers = {objective["number"] for objective in objectives}
    cited_keys: set[tuple[str, int | str]] = set()
    unmapped_objectives = []
    for objective in objectives:
        citations = parse_citations(objective["text"])
        if not citations:
            unmapped_objectives.append(_missing("1.3", objective["text"], "no grounded strategy requirement"))
            continue
        unresolved = []
        for citation in citations:
            if citation["kind"] == "AC":
                key = ("AC", citation["number"])
            else:
                key = ("NFR", (citation["category"] or "").casefold())
            if key not in requirements:
                unresolved.append(citation)
            else:
                cited_keys.add(key)
        if unresolved:
            unmapped_objectives.append(
                _missing("1.3", objective["text"], "citation does not resolve to a strategy requirement")
            )

    missing = []
    for key, requirement_text in requirements.items():
        if key not in cited_keys:
            missing.append(_missing("1.3", requirement_text, "no Section 1.3 objective"))

    for scope_entry in _scope_records(content):
        if not scope_entry["references"]:
            is_ungrounded_not_applicable = scope_entry["section"] in _NFR_SECTIONS and _NOT_APPLICABLE_RE.match(
                scope_entry["text"]
            )
            if is_ungrounded_not_applicable:
                continue
            missing.append(_missing(scope_entry["section"], scope_entry["text"], "no Section 1.3 objective mapping"))
            continue
        for reference in scope_entry["references"]:
            if int(reference) not in objective_numbers:
                missing.append(
                    _missing(
                        scope_entry["section"],
                        scope_entry["text"],
                        f"Objective #{reference} does not exist in Section 1.3",
                    )
                )

    return {
        "valid": not missing and not unmapped_objectives,
        "missing": missing,
        "unmapped_objectives": unmapped_objectives,
    }


def _section_text(content: str, section: str) -> tuple[str, list[str]]:
    lines, _ = extract_section(content, TEMPLATE_HEADINGS[section])
    return "\n".join(lines).strip(), lines


def _is_placeholder(text: str) -> bool:
    # Remove Markdown blockquote prefixes without discarding a closing angle bracket from a
    # delimited value such as ``<sample payload>``.
    normalized = re.sub(r"(?m)^\s*>\s?", "", text)
    normalized = re.sub(r"[*_`]", "", normalized).strip().casefold()
    delimited = len(normalized) >= 2 and normalized[0] + normalized[-1] in {"[]", "<>", "{}", "()"}
    if delimited:
        normalized = normalized[1:-1].strip()
    return (
        not normalized
        or normalized in {"tbd", "n/a", "not applicable", "-"}
        or "{what" in normalized
        or (
            delimited
            and bool(
                re.fullmatch(
                    r"(?:what|your|some|any|a|an|the|valid|unique)?\s*"
                    r"(?:value|data|payload|format|example|sample|placeholder|identifier|id|name|manifest|"
                    r"uri|url|string|token|resource|namespace|version|build)(?:[-\s].*)?",
                    normalized,
                )
            )
        )
        or bool(
            re.fullmatch(r"(?:sample|example|placeholder|test[ -]?data)(?:[ -]?(?:payload|data|value))?", normalized)
        )
    )


def _has_tbd_resolution_path(value: str) -> bool:
    """Require a concrete, identifiable resolution path for a ``TBD`` value.

    The canonical ``TBD — Resolution:`` label requires a concrete action plus either a named
    source/owner or a concrete timing/decision point. This deliberately rejects label-less
    rationales and generic placeholders such as ``with someone`` so they cannot make an
    otherwise unknown environment version actionable.
    """
    if _is_placeholder(value):
        return False

    for match in _TBD_RESOLUTION_RE.finditer(value):
        target = match.group("target").strip(" \t:;-—–,()")
        if _CONCRETE_TIMING_RE.search(f"{match.group('connector')} {target}"):
            return True

        source_or_owner = re.split(r"\b(?:by|before|after)\b", target, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        if not _GENERIC_RESOLUTION_TARGET_RE.fullmatch(source_or_owner) and _NAMED_SOURCE_OR_OWNER_RE.search(
            source_or_owner
        ):
            return True
    return False


def _flush_logical_entry(entries: list[str], current: list[str]) -> None:
    """Append one accumulated Markdown entry and clear its physical-line buffer."""
    if current:
        entries.append(" ".join(current))
        current.clear()


def _logical_entries(section_text: str) -> list[str]:
    """Join wrapped Markdown lines into logical entries for unresolved-value checks.

    A resolution path may wrap across indented lines, while a paragraph may contain more than
    one independent field. Entry boundaries preserve the former and make it possible to inspect
    each ``TBD`` occurrence independently in the latter.
    """
    entries = []
    current = []

    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped:
            _flush_logical_entry(entries, current)
            continue
        normalized = re.sub(r"[*_`]", "", line)
        if _MARKDOWN_ENTRY_START_RE.match(line) or _is_field_entry_start(line) or _VERSION_FIELD_RE.match(normalized):
            _flush_logical_entry(entries, current)
        current.append(stripped)
    _flush_logical_entry(entries, current)
    return entries


def _tbd_label(entry: str, position: int) -> str:
    """Extract a useful field label for an unresolved ``TBD`` occurrence."""
    prefix = entry[:position]
    # Treat periods as occurrence boundaries unless they are part of a dotted version number.
    # This keeps ``RHOAI 3.6 EA2 — exact build`` intact for canonical label detection while
    # still isolating sentence-separated fields and numbered Markdown entries.
    prefix = re.split(r"[;|]|(?<!\d)\.(?!\d)|(?<=\d)\.(?!\d)", prefix)[-1]
    prefix = re.sub(r"^\s*(?:[-*+]\s+|\d+\.\s+)", "", prefix)
    # Keep the field separator until the label regex has extracted it. Removing the colon here
    # would turn ``GPU configuration: TBD`` into an unhelpful generic label.
    prefix = re.sub(r"[*_`]", "", prefix).strip(" \t-—–")

    field = re.search(r"(?P<label>[^:]+):\s*$", prefix)
    if field:
        label = field.group("label").strip(" \t-:—–")
    else:
        field = re.search(r"(?P<label>[\w][\w ./'()\-]{1,80}?)\s+(?:is|are|has|have)\s*$", prefix, re.IGNORECASE)
        label = field.group("label").strip() if field else "unresolved TBD"

    label = re.sub(r"^(?:the|a|an)\s+", "", label, flags=re.IGNORECASE)
    if label.casefold().startswith("openshift") and re.search(r"\b(?:version|build)\b", label, re.IGNORECASE):
        return _VERSION_LABELS[0]
    if label.casefold().startswith("rhoai") and re.search(r"\b(?:version|build)\b", label, re.IGNORECASE):
        return _VERSION_LABELS[1]
    return " ".join(label.split()) or "unresolved TBD"


def _unresolved_tbd_fields(section_text: str) -> list[str]:
    """Return labels for bare/unresolved ``TBD`` values in a required Section 3 subsection.

    This is the single TBD classifier used for infrastructure, test data, and RBAC. A complete
    ``TBD — Resolution:`` path is intentionally ignored here, regardless of which subsection
    contains it.
    """
    unresolved, _ = _tbd_field_states(section_text)
    return unresolved


def _tbd_field_states(section_text: str) -> tuple[list[str], list[str]]:
    """Return unresolved and explicitly resolved TBD labels in occurrence order."""
    unresolved = []
    resolved = []
    for entry in _logical_entries(section_text):
        matches = list(_TBD_RE.finditer(entry))
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(entry)
            value = entry[match.start() : end].strip()
            label = _tbd_label(entry, match.start())
            destination = resolved if _has_tbd_resolution_path(value) else unresolved
            if label not in destination:
                destination.append(label)
    return unresolved, resolved


def _match_version_field(line: str):
    """Match a supported version/build label after removing Markdown presentation syntax."""
    normalized = re.sub(r"[*_`]", "", line)
    return _VERSION_FIELD_RE.match(normalized)


def _canonical_version_label(label: str) -> str:
    return _VERSION_LABELS[0] if label.casefold().startswith("openshift") else _VERSION_LABELS[1]


def _is_vague_version(value: str) -> bool:
    normalized = re.sub(r"[*_`]", "", value).strip()
    return bool(
        _VAGUE_VERSION_RE.fullmatch(normalized)
        or _VAGUE_VERSION_HINT_RE.search(normalized)
        or not re.search(r"\d", normalized)
    )


def _version_fields(section_text: str) -> dict[str, tuple[int, str]]:
    """Extract supported version fields, including wrapped Markdown list/value forms."""
    lines = section_text.splitlines()
    fields = {}
    for index, line in enumerate(lines):
        match = _match_version_field(line)
        if match is None:
            continue

        label = _canonical_version_label(match.group("label"))
        value = match.group("value").strip()
        continuation = []
        for next_line in lines[index + 1 :]:
            if _match_version_field(next_line) is not None:
                break
            if re.match(r"^\s*[-*+]\s+", next_line) or re.match(r"^\s*#{1,6}\s+", next_line):
                break
            if _is_field_entry_start(next_line):
                break
            if not next_line.strip() or not re.match(r"^(?:\s+|[*_`])", next_line):
                break
            continuation.append(next_line.strip())
        if continuation:
            value = " ".join([value, *continuation]).strip()
        fields[label] = (index, value)
    return fields


def _has_substantive_infrastructure(section_text: str) -> bool:
    """Require usable Section 3.1 content beyond a heading or unavailable placeholder."""
    if _is_placeholder(section_text):
        return False

    fields = _version_fields(section_text)
    if fields and any(
        value.strip() and not _is_placeholder(value) and not _UNAVAILABLE_INFRA_VALUE_RE.fullmatch(value.strip())
        for _, value in fields.values()
    ):
        return True
    return bool(_INFRASTRUCTURE_DETAIL_RE.search(section_text))


def _version_evidence(section_text: str) -> tuple[list[str], list[str]]:
    bare_tbd = []
    advisory_gaps = []
    fields = _version_fields(section_text)
    unresolved_tbd, resolved_tbd = _tbd_field_states(section_text)
    unresolved_tbd = set(unresolved_tbd)
    resolved_tbd = set(resolved_tbd)

    for label in _VERSION_LABELS:
        field = fields.get(label)
        if field is None:
            advisory_gaps.append(label)
            continue
        _, value = field
        if not value:
            advisory_gaps.append(label)
            continue
        tbd = _TBD_RE.search(value)
        if tbd:
            # Use the same occurrence-aware classifier as Sections 3.2 and 3.3. This keeps
            # generic infrastructure TBDs and mixed entries subject to one policy.
            if label in unresolved_tbd:
                bare_tbd.append(label)
            elif label in resolved_tbd:
                advisory_gaps.append(label)
        elif _is_vague_version(value):
            advisory_gaps.append(label)
        elif _is_placeholder(value):
            advisory_gaps.append(label)

    return bare_tbd, advisory_gaps


def _markdown_tables(lines: list[str]) -> list[tuple[list[str], list[list[str]]]]:
    """Return table headers and rows from contiguous Markdown tables in a section."""
    tables = []
    index = 0
    while index < len(lines):
        if not (lines[index].strip().startswith("|") and lines[index].strip().endswith("|")):
            index += 1
            continue
        table_lines = []
        while index < len(lines):
            stripped = lines[index].strip()
            if not (stripped.startswith("|") and stripped.endswith("|")):
                break
            table_lines.append(stripped)
            index += 1
        if not table_lines:
            continue
        headers = [cell.strip() for cell in table_lines[0].strip("|").split("|")]
        tables.append((headers, parse_table_rows(table_lines)))
    return tables


def _example_candidates(value: str) -> list[str]:
    """Extract concrete-looking values from one explicitly marked example context."""
    candidates = [value]
    candidates.extend(_BACKTICKED_VALUE_RE.findall(value))
    candidates.extend(_STRUCTURED_EXAMPLE_RE.findall(value))
    candidates.extend(match.group("value") for match in _QUOTED_EXAMPLE_RE.finditer(value))
    candidates.extend(_URI_EXAMPLE_RE.findall(value))
    candidates.extend(match.group("value") for match in _MANIFEST_FIELD_RE.finditer(value))
    return candidates


def _actionability_for_test_data(section_text: str) -> bool:
    if _is_placeholder(section_text):
        return False

    lines = section_text.splitlines()
    format_values = [match.group("value") for match in _TEST_DATA_FORMAT_RE.finditer(section_text)]
    example_values = []
    table_format_values = []
    table_example_values = []
    table_has_format_column = False
    table_has_example_column = False

    for headers, rows in _markdown_tables(lines):
        normalized_headers = [re.sub(r"[*_`]", "", header).strip().casefold() for header in headers]
        format_columns = [index for index, header in enumerate(normalized_headers) if "format" in header]
        example_columns = [
            index
            for index, header in enumerate(normalized_headers)
            if re.search(r"\b(?:example|sample|fixture)", header)
        ]
        table_has_format_column |= bool(format_columns)
        table_has_example_column |= bool(example_columns)
        for row in rows:
            table_format_values.extend(row[index] for index in format_columns if index < len(row))
            for index in example_columns:
                if index < len(row):
                    candidates = _example_candidates(row[index])
                    table_example_values.extend(candidates)
                    example_values.extend(candidates)

    for match in _TEST_DATA_EXAMPLE_CLAUSE_RE.finditer(section_text):
        example_values.extend(_example_candidates(match.group("value")))
    for match in _TEST_DATA_EXAMPLE_LABEL_RE.finditer(section_text):
        example_values.extend(_example_candidates(match.group("value")))

    if format_values:
        # An explicit format field is authoritative: a placeholder there cannot be rescued by a
        # concrete example elsewhere in the section.
        has_format = all(_is_concrete_format(value) for value in format_values)
    elif table_has_format_column:
        has_format = bool(table_format_values) and all(_is_concrete_format(value) for value in table_format_values)
    else:
        # Without an explicit format field/table column, only concrete format vocabulary counts.
        # In particular, a bare word such as "token" is not a format declaration.
        has_format = bool(_TEST_DATA_FORMAT_WORD_RE.search(section_text))

    if table_has_example_column and not table_example_values:
        has_example = False
    else:
        has_example = any(_is_concrete_example(example) for example in example_values)
    return has_format and has_example


def _is_concrete_format(value: str) -> bool:
    if _is_placeholder(value) or _TBD_RE.search(value):
        return False
    normalized = re.sub(r"[*_`]", "", value).strip().casefold()
    if not normalized or normalized in {"unclear", "unknown", "unspecified", "various", "tbd"}:
        return False
    return bool(_TEST_DATA_FORMAT_WORD_RE.search(value))


def _is_concrete_example(value: str) -> bool:
    if _TBD_RE.search(value):
        return _has_tbd_resolution_path(value)
    if _is_placeholder(value):
        return False
    normalized = re.sub(r"[*_]", "", value).strip().strip("` \t.,:;()")
    if not normalized:
        return False
    if _BACKTICKED_VALUE_RE.search(value):
        return True
    if _STRUCTURED_EXAMPLE_RE.search(value) or _URI_EXAMPLE_RE.search(value):
        return True
    if re.search(r"['\"][^'\"]+['\"]", value):
        return True
    if re.search(r"\b(?:apiVersion|kind|metadata|spec)\s*:", value, re.IGNORECASE):
        return True
    if normalized.casefold() in _GENERIC_EXAMPLE_VALUES:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9][\w./:@+\- ]{0,}", normalized)) and not re.fullmatch(
        r"(?:a|an|the)?\s*(?:sample|example|test\s+data|identifier|manifest|uri|url|string)\s*", normalized, re.I
    )


def _actionability_for_users(section_text: str, lines: list[str]) -> bool:
    if _is_placeholder(section_text):
        return False
    if re.search(r"\bnot applicable\b", section_text, re.I):
        return len(section_text.split()) > 3
    table_has_rbac = False
    for index, line in enumerate(lines):
        header = line.strip()
        if not (header.startswith("|") and header.endswith("|")):
            continue
        headers = [cell.strip().casefold() for cell in header.strip("|").split("|")]
        role_columns = [
            i for i, cell in enumerate(headers) if any(name in cell for name in ("role", "user", "account"))
        ]
        permission_columns = [i for i, cell in enumerate(headers) if "permission" in cell]
        resource_columns = [
            i for i, cell in enumerate(headers) if any(name in cell for name in ("resource", "namespace", "project"))
        ]
        rows = parse_table_rows(lines[index:])
        for row in rows:
            if (
                role_columns
                and permission_columns
                and resource_columns
                and max(role_columns + permission_columns + resource_columns) < len(row)
                and not _is_placeholder(row[role_columns[0]])
                and _is_concrete_resource(row[resource_columns[0]])
                and _CONCRETE_PERMISSION_RE.search(row[permission_columns[0]])
            ):
                table_has_rbac = True
                break
        if table_has_rbac:
            break
    prose_has_rbac = bool(
        re.search(r"\b(?:role|users?|service account)\b", section_text, re.I)
        and _CONCRETE_PERMISSION_RE.search(section_text)
        and _has_concrete_prose_resource(section_text)
        and re.search(r"\b(?:can|may|allowed|permissions?)\b", section_text, re.I)
    )
    return table_has_rbac or prose_has_rbac


def _is_concrete_resource(value: str) -> bool:
    normalized = strip_markdown_presentation(value).strip()
    return (
        not _is_placeholder(value)
        and normalized.casefold() not in _GENERIC_RESOURCE_VALUES
        and not _is_broad_resource_collection(normalized)
    )


def _is_broad_resource_collection(value: str) -> bool:
    """Reject collection-wide and wildcard resource scopes in RBAC evidence."""
    normalized = re.sub(r"[-_/]+", " ", value.strip().casefold())
    return normalized in {"all", "any", "every"} or "*" in value or bool(_BROAD_PROSE_RESOURCE_RE.search(normalized))


def _has_concrete_prose_resource(value: str) -> bool:
    """Require a named resource kind and reject broad resource collections in prose RBAC."""
    normalized = strip_markdown_presentation(value)
    return not _is_broad_resource_collection(normalized) and bool(_CONCRETE_PROSE_RESOURCE_RE.search(normalized))


def validate_actionability_result(result: object, name: str = "actionability_result") -> None:
    """Fail closed on the structured actionability contract consumed by score gates.

    ``bare_tbd`` and ``missing_details`` are blocking evidence. ``advisory_gaps`` is retained
    for visibility but does not change ``valid`` or trigger a score cap.
    """
    if not isinstance(result, dict):
        raise ValueError(f"{name} must be a JSON object")
    if not isinstance(result.get("valid"), bool):
        raise ValueError(f"{name} must have a boolean 'valid' field")

    required_keys = {"valid", "bare_tbd", "missing_details", "advisory_gaps"}
    missing_keys = required_keys - result.keys()
    if missing_keys:
        raise ValueError(f"{name} is missing required fields: {', '.join(sorted(missing_keys))}")
    unknown_keys = set(result) - required_keys
    if unknown_keys:
        raise ValueError(f"{name} contains unknown fields: {', '.join(sorted(unknown_keys))}")

    for key in ("bare_tbd", "missing_details", "advisory_gaps"):
        entries = result.get(key)
        if not isinstance(entries, list) or any(not isinstance(entry, str) or not entry.strip() for entry in entries):
            raise ValueError(f"{name}.{key} must be a list of non-empty strings")

    has_blocking_gaps = bool(result["bare_tbd"] or result["missing_details"])
    if result["valid"] == has_blocking_gaps:
        raise ValueError(f"{name}.valid does not agree with its blocking evidence")


def validate_actionability(testplan_path: str) -> dict:
    """Check blocking operational evidence and retain advisory gaps for review visibility."""
    path = Path(testplan_path)
    if not path.exists():
        return {
            "valid": False,
            "bare_tbd": [],
            "missing_details": ["environment versions and configuration", "RBAC roles and permissions"],
            "advisory_gaps": [*_VERSION_LABELS, ACTIONABILITY_TEST_DATA_GAP],
        }

    content = path.read_text()
    infra_text, _ = _section_text(content, "3.1")
    data_text, _ = _section_text(content, "3.2")
    users_text, users_lines = _section_text(content, "3.3")

    tbd_states = {
        "3.1": _tbd_field_states(infra_text),
        "3.2": _tbd_field_states(data_text),
        "3.3": _tbd_field_states(users_text),
    }
    unresolved_tbd = {section: states[0] for section, states in tbd_states.items()}
    resolved_tbd = {section: states[1] for section, states in tbd_states.items()}
    bare_tbd, advisory_gaps = _version_evidence(infra_text)
    bare_tbd.extend(label for label in unresolved_tbd["3.1"] if label not in bare_tbd)
    advisory_gaps.extend(label for label in resolved_tbd["3.1"] if label not in advisory_gaps)
    if resolved_tbd["3.2"]:
        advisory_gaps.append(ACTIONABILITY_TEST_DATA_GAP)
    if resolved_tbd["3.3"]:
        advisory_gaps.append("RBAC roles and permissions")
    missing_details = []
    if not _has_substantive_infrastructure(infra_text):
        missing_details.append("environment versions and configuration")
    if unresolved_tbd["3.2"]:
        missing_details.append(ACTIONABILITY_TEST_DATA_GAP)
    elif not _actionability_for_test_data(data_text):
        advisory_gaps.append(ACTIONABILITY_TEST_DATA_GAP)
    if unresolved_tbd["3.3"] or not _actionability_for_users(users_text, users_lines):
        missing_details.append("RBAC roles and permissions")

    # Preserve order while avoiding duplicate diagnostics when a section is both absent and
    # missing a specific field.
    missing_details = list(dict.fromkeys(missing_details))
    blocking = set(bare_tbd) | set(missing_details)
    advisory_gaps = [gap for gap in dict.fromkeys(advisory_gaps) if gap not in blocking]
    return {
        "valid": not bare_tbd and not missing_details,
        "bare_tbd": bare_tbd,
        "missing_details": missing_details,
        "advisory_gaps": advisory_gaps,
    }
