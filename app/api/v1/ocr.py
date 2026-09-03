import io
import os
import shutil
from fastapi import APIRouter
from PIL import Image, ImageDraw
import pytesseract

from app.services.student_import import configure_tesseract, get_tesseract_cmd

router = APIRouter(
    prefix="/ocr",
    tags=["OCR Diagnostics"],
)


@router.get(
    "/health",
    summary="OCR Engine Health & Diagnostic Check",
)
def ocr_health():
    """
    Diagnostic endpoint to verify Tesseract OCR installation and operation on Linux/Render/Docker:
    - Verifies executable presence
    - Reads Tesseract version
    - Executes an end-to-end OCR test on a generated image
    """
    cmd = configure_tesseract()
    tesseract_exists = os.path.isfile(cmd) or bool(shutil.which(cmd))

    version_str = None
    test_passed = False
    test_message = ""
    extracted_sample = None

    try:
        version = pytesseract.get_tesseract_version()
        version_str = str(version)

        # Quick end-to-end in-memory OCR test
        test_img = Image.new("RGB", (180, 50), color=(255, 255, 255))
        draw = ImageDraw.Draw(test_img)
        draw.text((10, 15), "TEST OK", fill=(0, 0, 0))

        extracted = pytesseract.image_to_string(test_img, config="--psm 7").strip()
        extracted_sample = extracted
        test_passed = True
        test_message = f"OCR engine responded successfully. Sample text extracted: '{extracted}'"

    except pytesseract.TesseractNotFoundError as exc:
        test_message = (
            f"Tesseract executable not found or not accessible at '{cmd}'. "
            f"Details: {exc}"
        )
    except Exception as exc:
        test_message = f"OCR engine test execution error: {exc}"

    is_healthy = bool(tesseract_exists and version_str and test_passed)

    return {
        "status": "ok" if is_healthy else "error",
        "ocr": "available" if is_healthy else "unavailable",
        "tesseract_installed": tesseract_exists,
        "tesseract_version": version_str,
        "executable": cmd,
        "tessdata_prefix": os.getenv("TESSDATA_PREFIX", None),
        "test_passed": test_passed,
        "sample_extracted": extracted_sample,
        "message": test_message,
    }
