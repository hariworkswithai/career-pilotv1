"""Resume parsing: text extraction from PDF and DOCX uploads."""

from __future__ import annotations

import io

from app.schemas.resumes import AnalysisFinding, ResumeAnalysis


class ParseError(ValueError):
    pass


def extract_pdf(file_bytes: bytes) -> str:
    """Extract plain text from a PDF. pypdf first, pdfplumber as fallback."""
    text = _pypdf_text(file_bytes)
    if text.strip():
        return text
    text = _pdfplumber_text(file_bytes)
    if text.strip():
        return text
    raise ParseError("No extractable text found in the PDF. It may be a scanned image.")


def _pypdf_text(file_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(file_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:  # noqa: BLE001 - parser fallback chain
        return ""


def _pdfplumber_text(file_bytes: bytes) -> str:
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:  # noqa: BLE001 - parser fallback chain
        return ""


def extract_docx(file_bytes: bytes) -> str:
    """Extract paragraphs and table text from a DOCX."""
    try:
        from docx import Document

        doc = Document(io.BytesIO(file_bytes))
        parts: list[str] = [p.text for p in doc.paragraphs if p.text]
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    parts.append(" | ".join(cells))
        text = "\n".join(parts)
        if not text.strip():
            raise ParseError("No extractable text found in the DOCX.")
        return text
    except ParseError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ParseError(f"Could not read DOCX: {exc}") from exc


def extract_resume(file_bytes: bytes, file_type: str) -> str:
    if file_type == "pdf":
        return extract_pdf(file_bytes)
    if file_type == "docx":
        return extract_docx(file_bytes)
    raise ParseError(f"Unsupported file type: {file_type}")


def analyze_resume(text: str) -> ResumeAnalysis:
    """Heuristic resume completeness analysis (no LLM dependency at analysis time)."""
    findings: list[AnalysisFinding] = []
    content = text or ""
    low = content.lower()

    has_summary = any(k in low for k in ("summary", "objective", "about me", "profile"))
    has_experience = any(k in low for k in ("experience", "work history", "employment"))
    has_education = any(k in low for k in ("education", "bachelor", "master", "b.tech", "m.tech", "degree", "college", "university"))
    has_skills = any(k in low for k in ("skills", "technologies", "tech stack", "proficiencies"))

    findings.append(
        AnalysisFinding(
            category="summary", status="good" if has_summary else "needs_improvement",
            message="Professional summary present" if has_summary else "No professional summary found",
            suggestion="Add a 2-3 line headline stating your role focus and top skills.",
        )
    )
    findings.append(
        AnalysisFinding(
            category="experience", status="good" if has_experience else "needs_improvement",
            message="Work experience section found" if has_experience else "Work experience section not found",
            suggestion="List roles with company, dates, and quantified achievements.",
        )
    )
    findings.append(
        AnalysisFinding(
            category="education", status="good" if has_education else "needs_improvement",
            message="Education section found" if has_education else "Education section not found",
            suggestion="Add highest qualification and institution.",
        )
    )
    findings.append(
        AnalysisFinding(
            category="skills", status="good" if has_skills else "needs_improvement",
            message="Skills section found" if has_skills else "Skills section not found",
            suggestion="List 8-12 relevant technical and soft skills.",
        )
    )

    changes_needed = sum(1 for f in findings if f.status == "needs_improvement")
    overall = "improved" if changes_needed == 0 else ("needs_improvement" if changes_needed <= 2 else "incomplete")
    return ResumeAnalysis(findings=findings, summary=f"{len(content.split())} words across {len(findings)} sections.", overall=overall)
