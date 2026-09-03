import numpy as np
import cv2
from fastapi import APIRouter
from app.services.student_import import get_ocr_engine, extract_text_from_image

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
    Diagnostic endpoint to verify lightweight PaddleOCR (RapidOCR ONNX) installation and operation:
    - Pure pip package
    - No Docker / apt-get required
    - Executes an end-to-end OCR test on an in-memory generated image
    """
    engine = get_ocr_engine()
    if engine is None:
        return {
            "status": "error",
            "ocr": "unavailable",
            "engine": "PaddleOCR (RapidOCR ONNX)",
            "pip_only": True,
            "no_docker_required": True,
            "test_passed": False,
            "message": "RapidOCR engine is not installed. Run `pip install rapidocr-onnxruntime onnxruntime`.",
        }

    # Generate quick in-memory test image
    test_img = np.ones((60, 240, 3), dtype=np.uint8) * 255
    cv2.putText(test_img, "PADDLE OCR OK", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

    extracted = ""
    test_passed = False
    test_message = ""

    try:
        extracted = extract_text_from_image(test_img).strip()
        test_passed = bool(extracted and len(extracted) > 0)
        test_message = f"PaddleOCR ONNX engine responded successfully. Sample extracted: '{extracted}'"
    except Exception as exc:
        test_message = f"OCR engine test execution error: {exc}"

    return {
        "status": "ok" if test_passed else "error",
        "ocr": "available" if test_passed else "unavailable",
        "engine": "PaddleOCR (RapidOCR ONNX)",
        "pip_only": True,
        "no_docker_required": True,
        "test_passed": test_passed,
        "sample_extracted": extracted,
        "message": test_message,
    }
