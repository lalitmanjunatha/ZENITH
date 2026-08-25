import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    import whisper
    WHISPER_AVAILABLE = False
except ImportError:
    WHISPER_AVAILABLE = False


class ContentExtractor:
    def __init__(self):
        self.extracted_count = 0
        self.failed_count = 0

    def extract(self, file_path: str) -> Dict[str, Any]:
        path = Path(file_path)
        ext = path.suffix.lower()

        result = {
            "file_path": str(file_path),
            "file_name": path.name,
            "extension": ext,
            "content": "",
            "metadata": {
                "size_bytes": path.stat().st_size if path.exists() else 0,
                "modified_time": datetime.fromtimestamp(path.stat().st_mtime).isoformat() if path.exists() else "",
                "extraction_method": "",
                "extraction_success": False,
            },
        }

        extractors = {
            ".txt": self._extract_text,
            ".csv": self._extract_text,
            ".json": self._extract_text,
            ".md": self._extract_text,
            ".py": self._extract_text,
            ".js": self._extract_text,
            ".html": self._extract_html,
            ".pdf": self._extract_pdf,
            ".docx": self._extract_docx,
            ".xlsx": self._extract_excel,
            ".xls": self._extract_excel,
            ".jpg": self._extract_image_ocr,
            ".jpeg": self._extract_image_ocr,
            ".png": self._extract_image_ocr,
            ".bmp": self._extract_image_ocr,
            ".mp3": self._extract_audio_whisper,
            ".wav": self._extract_audio_whisper,
        }

        extractor = extractors.get(ext, self._extract_text)
        try:
            content = extractor(str(path))
            result["content"] = content
            result["metadata"]["extraction_success"] = True
            result["metadata"]["extraction_method"] = extractor.__name__
            self.extracted_count += 1
        except Exception as e:
            logger.error(f"Failed to extract {file_path}: {e}")
            result["content"] = ""
            result["metadata"]["extraction_error"] = str(e)
            self.failed_count += 1

        return result

    def _extract_text(self, file_path: str) -> str:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except UnicodeDecodeError:
            with open(file_path, "r", encoding="latin-1", errors="replace") as f:
                return f.read()

    def _extract_html(self, file_path: str) -> str:
        if not BS4_AVAILABLE:
            return self._extract_text(file_path)
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
        return soup.get_text(separator="\n", strip=True)

    def _extract_pdf(self, file_path: str) -> str:
        text_parts = []

        if PDFPLUMBER_AVAILABLE:
            try:
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)
                if text_parts:
                    return "\n".join(text_parts)
            except Exception as e:
                logger.warning(f"pdfplumber failed for {file_path}: {e}")

        if PDF_AVAILABLE:
            try:
                with open(file_path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)
                if text_parts:
                    return "\n".join(text_parts)
            except Exception as e:
                logger.warning(f"PyPDF2 failed for {file_path}: {e}")

        return self._extract_text(file_path)

    def _extract_docx(self, file_path: str) -> str:
        if not DOCX_AVAILABLE:
            return self._extract_text(file_path)
        try:
            doc = docx.Document(file_path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(paragraphs)
        except Exception as e:
            logger.warning(f"python-docx failed for {file_path}: {e}")
            return self._extract_text(file_path)

    def _extract_excel(self, file_path: str) -> str:
        if not OPENPYXL_AVAILABLE:
            return self._extract_text(file_path)
        try:
            import pandas as pd
            df = pd.read_excel(file_path, engine="openpyxl")
            return df.to_string()
        except Exception as e:
            logger.warning(f"openpyxl failed for {file_path}: {e}")
            return self._extract_text(file_path)

    def _extract_image_ocr(self, file_path: str) -> str:
        if not OCR_AVAILABLE:
            return f"[Image file: {Path(file_path).name}]"
        try:
            img = Image.open(file_path)
            text = self._ocr_preprocess(img)
            return text.strip() if text.strip() else f"[Image: {Path(file_path).name} - no text detected]"
        except Exception as e:
            logger.warning(f"OCR failed for {file_path}: {e}")
            return f"[Image file: {Path(file_path).name}]"

    def _ocr_preprocess(self, img) -> str:
        """Run OCR with optional preprocessing for better digit/identity reading.

        Preprocessing auto-up: grayscale -> upscale -> adaptive threshold.
        Enabled via ZENITH_OCR_PREPROCESS (auto/on) and ZENITH_OCR_UPSCALE.
        """
        import os
        import numpy as np

        run = os.getenv("ZENITH_OCR_PREPROCESS", "auto").lower() in ("auto", "on", "1", "true", "yes")
        if not run:
            return pytesseract.image_to_string(img)

        try:
            from PIL import ImageOps

            gray = ImageOps.grayscale(img)
            try:
                scale = int(float(os.getenv("ZENITH_OCR_UPSCALE", "2")))
            except ValueError:
                scale = 2
            scale = max(1, min(scale, 4))
            if scale > 1:
                gray = gray.resize(
                    (gray.width * scale, gray.height * scale),
                    resample=Image.LANCZOS,
                )
            arr = np.array(gray)
            if arr.size:
                # Simple binary threshold for cleaner digit extraction
                try:
                    arr = np.where(arr > 128, 255, 0).astype(np.uint8)
                except Exception:
                    pass
            text = pytesseract.image_to_string(arr)
            return text
        except Exception as e:
            logger.warning(f"OCR preprocessing failed ({e}); falling back to plain OCR")
            return pytesseract.image_to_string(img)

    def _extract_audio_whisper(self, file_path: str) -> str:
        if not WHISPER_AVAILABLE:
            return f"[Audio file: {Path(file_path).name} - whisper not installed]"
        try:
            model = whisper.load_model("base")
            result = model.transcribe(file_path)
            return result["text"]
        except Exception as e:
            logger.warning(f"Whisper failed for {file_path}: {e}")
            return f"[Audio file: {Path(file_path).name}]"

    def get_stats(self) -> Dict[str, int]:
        return {
            "extracted": self.extracted_count,
            "failed": self.failed_count,
        }