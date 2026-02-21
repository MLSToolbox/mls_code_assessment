from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union
from urllib.parse import urlparse
import re


_HEADING_PATTERN = re.compile(r"^\s*===\s*(.*?)\s*===\s*$")
_STEP_PATTERN = re.compile(r"^\s*(step\s+\d+[:.]?|\d+[.)])\s*(.+)$", re.IGNORECASE)


@dataclass(frozen=True)
class MetricReference:
    label: str
    url: str

    def to_dict(self) -> Dict[str, str]:
        return {"label": self.label, "url": self.url}


@dataclass(frozen=True)
class MetricInterpretationItem:
    range: str
    description: str
    severity: str = "info"
    label: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "range": self.range,
            "description": self.description,
            "severity": self.severity,
        }
        if self.label:
            data["label"] = self.label
        return data


@dataclass(frozen=True)
class MetricDocSection:
    id: str
    title: str
    type: str
    content: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "content": self.content,
        }


@dataclass(frozen=True)
class MetricDocumentation:
    summary: str
    ideal_range: Dict[str, Any] = field(default_factory=dict)
    sections: List[MetricDocSection] = field(default_factory=list)
    interpretation: List[MetricInterpretationItem] = field(default_factory=list)
    references: List[MetricReference] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "ideal_range": self.ideal_range,
            "sections": [section.to_dict() for section in self.sections],
            "interpretation": [item.to_dict() for item in self.interpretation],
            "references": [reference.to_dict() for reference in self.references],
        }


@dataclass(frozen=True, init=False)
class MetricMetadata:
    metric_id: str
    name: str
    category: str
    documentation: MetricDocumentation

    def __init__(
        self,
        metric_id: str,
        name: str,
        category: str = "general",
        documentation: Optional[MetricDocumentation] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        formula: Optional[str] = None,
        ideal_range: Optional[Dict[str, Any]] = None,
        interpretation: Optional[
            Union[
                Dict[str, str],
                List[Dict[str, Any]],
                List[MetricInterpretationItem],
            ]
        ] = None,
        references: Optional[
            Union[List[str], List[Dict[str, str]], List[MetricReference]]
        ] = None,
    ):
        object.__setattr__(self, "metric_id", metric_id)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "category", category)

        if documentation is None:
            documentation = self._build_documentation(
                summary=summary or description or "",
                formula=formula,
                ideal_range=ideal_range or {},
                interpretation=interpretation,
                references=references,
            )
        object.__setattr__(self, "documentation", documentation)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "name": self.name,
            "category": self.category,
            **self.documentation.to_dict(),
        }

    def _build_documentation(
        self,
        summary: str,
        formula: Optional[str],
        ideal_range: Dict[str, Any],
        interpretation: Optional[
            Union[
                Dict[str, str],
                List[Dict[str, Any]],
                List[MetricInterpretationItem],
            ]
        ],
        references: Optional[
            Union[List[str], List[Dict[str, str]], List[MetricReference]]
        ],
    ) -> MetricDocumentation:
        return MetricDocumentation(
            summary=summary.strip(),
            ideal_range=ideal_range,
            sections=self._build_sections(formula),
            interpretation=self._normalize_interpretation(interpretation),
            references=self._normalize_references(references),
        )

    def _build_sections(self, formula: Optional[str]) -> List[MetricDocSection]:
        if not formula:
            return []

        segments = self._split_legacy_sections(formula)
        sections: List[MetricDocSection] = []

        for index, (title, body) in enumerate(segments):
            normalized_body = body.strip()
            if not normalized_body:
                continue

            section_id = f"section_{index + 1}"
            section_type = self._detect_section_type(title, normalized_body)

            if section_type == "table":
                table = self._parse_table(normalized_body)
                if table:
                    sections.append(
                        MetricDocSection(
                            id=section_id,
                            title=title,
                            type="table",
                            content=table,
                        )
                    )
                    continue
                section_type = "text"

            if section_type == "steps":
                steps = self._parse_steps(normalized_body)
                sections.append(
                    MetricDocSection(
                        id=section_id,
                        title=title,
                        type="steps",
                        content={"items": steps},
                    )
                )
                continue

            if section_type == "list":
                items = self._parse_list(normalized_body)
                sections.append(
                    MetricDocSection(
                        id=section_id,
                        title=title,
                        type="list",
                        content={"items": items},
                    )
                )
                continue

            if section_type == "formula":
                sections.append(
                    MetricDocSection(
                        id=section_id,
                        title=title,
                        type="formula",
                        content={"expression": normalized_body},
                    )
                )
                continue

            paragraphs = self._parse_paragraphs(normalized_body)
            sections.append(
                MetricDocSection(
                    id=section_id,
                    title=title,
                    type="text",
                    content={"paragraphs": paragraphs},
                )
            )

        return sections

    def _split_legacy_sections(self, formula: str) -> List[tuple[str, str]]:
        lines = formula.splitlines()
        segments: List[tuple[str, str]] = []

        current_title = "Formula"
        current_lines: List[str] = []
        has_heading = False

        for line in lines:
            match = _HEADING_PATTERN.match(line.strip())
            if match:
                has_heading = True
                if current_lines:
                    segments.append((current_title, "\n".join(current_lines).strip()))
                current_title = match.group(1).strip().title()
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            segments.append((current_title, "\n".join(current_lines).strip()))

        if not has_heading:
            return [("Formula", formula.strip())]

        return [segment for segment in segments if segment[1]]

    def _detect_section_type(self, title: str, body: str) -> str:
        title_lower = title.lower()
        lines = [line for line in body.splitlines() if line.strip()]

        if "formula" in title_lower:
            return "formula"
        if self._parse_table(body):
            return "table"
        if any(_STEP_PATTERN.match(line) for line in lines):
            return "steps"
        if any(self._is_bullet(line) for line in lines):
            return "list"
        return "text"

    def _parse_table(self, body: str) -> Optional[Dict[str, Any]]:
        lines = [line.strip() for line in body.splitlines() if "|" in line]
        if len(lines) < 2:
            return None

        rows = [self._split_pipe_line(line) for line in lines]
        rows = [row for row in rows if len(row) >= 2]
        if len(rows) < 2:
            return None

        columns = rows[0]
        data_rows: List[List[str]] = []

        for row in rows[1:]:
            if all(re.match(r"^[-= ]+$", cell) for cell in row):
                continue
            normalized = row[: len(columns)] + [""] * max(0, len(columns) - len(row))
            data_rows.append(normalized[: len(columns)])

        if not data_rows:
            return None

        return {"columns": columns, "rows": data_rows}

    def _split_pipe_line(self, line: str) -> List[str]:
        raw_cells = [cell.strip() for cell in line.split("|")]
        if raw_cells and raw_cells[0] == "":
            raw_cells = raw_cells[1:]
        if raw_cells and raw_cells[-1] == "":
            raw_cells = raw_cells[:-1]
        return raw_cells

    def _parse_steps(self, body: str) -> List[str]:
        items: List[str] = []
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            match = _STEP_PATTERN.match(line)
            if match:
                items.append(match.group(2).strip())
            elif self._is_bullet(line):
                items.append(self._strip_bullet_prefix(line))
        return items

    def _parse_list(self, body: str) -> List[str]:
        items: List[str] = []
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if self._is_bullet(line):
                items.append(self._strip_bullet_prefix(line))
            else:
                items.append(line)
        return items

    def _parse_paragraphs(self, body: str) -> List[str]:
        chunks = re.split(r"\n\s*\n", body.strip())
        paragraphs = [re.sub(r"\s+", " ", chunk).strip() for chunk in chunks]
        return [paragraph for paragraph in paragraphs if paragraph]

    def _is_bullet(self, line: str) -> bool:
        return line.startswith("•") or line.startswith("- ") or line.startswith("* ")

    def _strip_bullet_prefix(self, line: str) -> str:
        if line.startswith("•"):
            return line[1:].strip()
        if line.startswith("- ") or line.startswith("* "):
            return line[2:].strip()
        return line

    def _normalize_interpretation(
        self,
        interpretation: Optional[
            Union[
                Dict[str, str],
                List[Dict[str, Any]],
                List[MetricInterpretationItem],
            ]
        ],
    ) -> List[MetricInterpretationItem]:
        if not interpretation:
            return []

        if isinstance(interpretation, list):
            normalized_items: List[MetricInterpretationItem] = []
            for item in interpretation:
                if isinstance(item, MetricInterpretationItem):
                    normalized_items.append(item)
                    continue
                if isinstance(item, dict):
                    range_value = str(item.get("range", "")).strip()
                    description = str(item.get("description", "")).strip()
                    if not range_value or not description:
                        continue
                    severity = str(item.get("severity", "")).strip() or self._derive_severity(
                        range_value, description
                    )
                    label = str(item.get("label", "")).strip() or None
                    normalized_items.append(
                        MetricInterpretationItem(
                            range=range_value,
                            description=description,
                            severity=severity,
                            label=label,
                        )
                    )
            return normalized_items

        items: List[MetricInterpretationItem] = []
        for range_value, description in interpretation.items():
            text = str(description).strip()
            if not text:
                continue
            items.append(
                MetricInterpretationItem(
                    range=str(range_value),
                    description=text,
                    severity=self._derive_severity(str(range_value), text),
                )
            )
        return items

    def _derive_severity(self, range_value: str, description: str) -> str:
        full_text = f"{range_value} {description}".lower()
        if any(token in full_text for token in ["critical", "very_low", "very low", "poor"]):
            return "error"
        if any(token in full_text for token in ["warning", "low", "needs refactoring"]):
            return "warning"
        if any(token in full_text for token in ["moderate", "medium", "acceptable"]):
            return "info"
        return "success"

    def _normalize_references(
        self,
        references: Optional[
            Union[List[str], List[Dict[str, str]], List[MetricReference]]
        ],
    ) -> List[MetricReference]:
        if not references:
            return []

        normalized: List[MetricReference] = []

        for reference in references:
            if isinstance(reference, MetricReference):
                normalized.append(reference)
                continue

            if isinstance(reference, dict):
                label = str(reference.get("label", "")).strip()
                url = str(reference.get("url", "")).strip()
                if not label and url:
                    label = self._derive_reference_label(url)
                if label and url:
                    normalized.append(MetricReference(label=label, url=url))
                continue

            value = str(reference).strip()
            if not value:
                continue
            normalized.append(
                MetricReference(
                    label=self._derive_reference_label(value),
                    url=value,
                )
            )

        return normalized

    def _derive_reference_label(self, reference: str) -> str:
        parsed = urlparse(reference)
        if parsed.scheme and parsed.netloc:
            return parsed.netloc + (parsed.path or "")
        return reference
