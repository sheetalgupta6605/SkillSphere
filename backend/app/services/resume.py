import os
import re
import shutil
from pathlib import Path

SKILL_ALIASES = {
    "js": "javascript", "javascript": "javascript", "react": "react.js",
    "reactjs": "react.js", "react.js": "react.js", "py": "python",
    "python programming": "python", "node": "node.js", "nodejs": "node.js",
    "postgres": "postgresql", "postgresql": "postgresql", "mongo": "mongodb",
}

SECTION_HEADERS = {
    "education": ("education", "academic background", "qualifications"),
    "experience": ("experience", "work experience", "employment", "work history", "professional experience"),
}


def normalize_skill(value: str) -> str:
    compact = re.sub(r"\s+", " ", value.strip().lower())
    return SKILL_ALIASES.get(compact, compact)


def _contains_term(text: str, term: str) -> bool:
    escaped = re.escape(term.strip())
    return bool(re.search(r"(?<![\w.+#-])" + escaped + r"(?![\w.+#-])", text, re.IGNORECASE))


def extract_skills(text: str, known_skills: list[str]) -> list[str]:
    found = {normalize_skill(skill) for skill in known_skills if skill and _contains_term(text, skill)}
    return sorted(found)


def _section_lines(lines: list[str], headers: tuple[str, ...]) -> list[str] | None:
    collected = []
    inside = False
    known_headers = tuple(word for values in SECTION_HEADERS.values() for word in values)
    for line in lines:
        normalized = re.sub(r"[^a-z ]", "", line.lower()).strip()
        if any(normalized == header for header in headers):
            inside = True
            continue
        if inside and any(normalized == header for header in known_headers):
            break
        if inside:
            collected.append(line[:300])
            if len(collected) >= 12:
                break
    return collected or None


def parse_resume_text(text: str, known_skills: list[str]) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    phone_match = re.search(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)", text)
    name = None
    for line in lines[:8]:
        if "@" in line or re.search(r"\d", line) or "://" in line:
            continue
        words = re.findall(r"[A-Za-z][A-Za-z.'-]*", line)
        if 2 <= len(words) <= 4 and len(words) == len(line.split()):
            name = line[:120]
            break
    return {
        "name": name,
        "email": email_match.group(0) if email_match else None,
        "phone": phone_match.group(0).strip() if phone_match else None,
        "education": _section_lines(lines, SECTION_HEADERS["education"]),
        "experience": _section_lines(lines, SECTION_HEADERS["experience"]),
        "skills": extract_skills(text, known_skills),
        "raw_text": text[:30000],
    }


def _preprocess_image(image):
    from PIL import ImageEnhance, ImageFilter, ImageOps

    image = image.convert("L")
    image = ImageOps.autocontrast(image)
    image = image.filter(ImageFilter.MedianFilter(size=3))
    image = ImageEnhance.Contrast(image).enhance(1.6)
    return image.point(lambda pixel: 255 if pixel > 165 else 0)


def _ocr_image(image) -> str:
    import pytesseract

    tesseract_path = os.getenv("TESSERACT_CMD")
    if tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
    elif not shutil.which("tesseract"):
        raise RuntimeError("Tesseract OCR is not installed. Install Tesseract or set TESSERACT_CMD.")
    return pytesseract.image_to_string(_preprocess_image(image), config="--oem 3 --psm 6")


def extract_pages_from_file(path: Path, content_type: str) -> list[str]:
    if content_type == "application/pdf":
        import pymupdf as fitz
        from PIL import Image
        import io

        try:
            document = fitz.open(str(path))
        except Exception as exc:
            raise ValueError("The PDF is damaged or cannot be opened.") from exc
        try:
            if document.needs_pass:
                raise ValueError("Password-protected PDFs are not supported.")
            if not document.page_count:
                raise ValueError("The PDF contains no pages.")
            if document.page_count > 20:
                raise ValueError("PDFs are limited to 20 pages.")
            pages = [page.get_text("text") or "" for page in document]
            if not any(len(page.strip()) >= 30 for page in pages):
                for index, page in enumerate(document):
                    longest_edge = max(page.rect.width, page.rect.height, 1)
                    scale = min(2.0, 1800 / longest_edge)
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                    image = Image.open(io.BytesIO(pixmap.tobytes("png")))
                    pages[index] = _ocr_image(image)
            if not any(page.strip() for page in pages):
                raise ValueError("No readable text was found in this PDF.")
            return pages
        finally:
            document.close()

    raise ValueError("Unsupported resume file type")


def extract_text_from_file(path: Path, content_type: str) -> str:
    return "\n\n".join(extract_pages_from_file(path, content_type))
