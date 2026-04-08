import base64
import json
import re
import httpx

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-20250514"


def _is_pdf(content_type: str, filename: str) -> bool:
    return "pdf" in content_type.lower() or filename.lower().endswith(".pdf")


def _image_media_type(content_type: str, filename: str) -> str:
    fn = filename.lower()
    if "png" in content_type or fn.endswith(".png"):
        return "image/png"
    if "gif" in content_type or fn.endswith(".gif"):
        return "image/gif"
    if "webp" in content_type or fn.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


def _build_document_block(contents: bytes, content_type: str, filename: str) -> dict:
    """Build the appropriate content block for Claude — PDF or image."""
    b64 = base64.standard_b64encode(contents).decode("utf-8")
    if _is_pdf(content_type, filename):
        return {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": b64,
            }
        }
    else:
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": _image_media_type(content_type, filename),
                "data": b64,
            }
        }


def _parse_json_response(text: str) -> dict:
    """Strip markdown fences and parse JSON from Claude's response."""
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    text = text.strip()
    return json.loads(text)


async def extract_p9_data(contents: bytes, filename: str, content_type: str) -> dict:
    """
    Send P9 form to Claude and extract the required tax fields.
    Returns a dict with keys matching the iTax XML fields.
    """
    doc_block = _build_document_block(contents, content_type, filename)

    prompt = """You are reading a Kenya Government P9 form (IPPD End of Year Tax Returns) 
issued by the Teachers Service Commission.

Extract ONLY the following values from the TOTALS / SUBTOTALS row at the bottom of the table:

1. employerPin       — Employer Tax-PIN (e.g. P051098084N)
2. employerName      — Always "Teachers Service Commission"
3. taxYear           — Tax Year (e.g. 2025)
4. taxpayerName      — Tax Payer's Name
5. taxablePay        — Taxable Pay (KES) TOTALS value (numeric only, no commas)
6. pension           — Pension (KES) TOTALS value (numeric only, no commas)
7. payeAuto          — PAYE auto (KES) TOTALS value (numeric only, no commas)
8. mprValue          — MPR value (KES) TOTALS value (numeric only, no commas)

Return ONLY a valid JSON object with these exact keys and numeric string values.
Do NOT include any explanation, markdown, or extra text. Example:
{"employerPin":"P051098084N","employerName":"Teachers Service Commission","taxYear":"2025",
"taxpayerName":"John Doe","taxablePay":"578404","pension":"38580.3",
"payeAuto":"61876.5","mprValue":"28800"}"""

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            ANTHROPIC_API_URL,
            headers={"Content-Type": "application/json"},
            json={
                "model": MODEL,
                "max_tokens": 1000,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            doc_block,
                            {"type": "text", "text": prompt}
                        ]
                    }
                ]
            }
        )
        response.raise_for_status()
        result = response.json()

    text = "".join(
        block.get("text", "")
        for block in result.get("content", [])
        if block.get("type") == "text"
    )

    data = _parse_json_response(text)

    # Ensure all required keys exist
    required = ["employerPin", "employerName", "taxYear", "taxpayerName",
                "taxablePay", "pension", "payeAuto", "mprValue"]
    for key in required:
        if key not in data:
            raise ValueError(f"Claude did not return field: {key}")

    return data


async def extract_wht_data(contents: bytes, filename: str, content_type: str) -> dict:
    """
    Send Withholding Tax certificate to Claude and extract:
    - grossAmount  (Gross Amount of Transaction / Consultancy Fees)
    - taxWithheld  (Amount of Tax Withheld)
    """
    doc_block = _build_document_block(contents, content_type, filename)

    prompt = """You are reading a Kenya Revenue Authority Withholding Tax Certificate.

Extract ONLY these two values:
1. grossAmount  — Gross Amount of Transaction (numeric only, no commas, no currency symbol)
2. taxWithheld  — Amount of Tax Withheld (numeric only, no commas, no currency symbol)

Return ONLY a valid JSON object. No explanation, no markdown. Example:
{"grossAmount":"50000","taxWithheld":"5000"}"""

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            ANTHROPIC_API_URL,
            headers={"Content-Type": "application/json"},
            json={
                "model": MODEL,
                "max_tokens": 500,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            doc_block,
                            {"type": "text", "text": prompt}
                        ]
                    }
                ]
            }
        )
        response.raise_for_status()
        result = response.json()

    text = "".join(
        block.get("text", "")
        for block in result.get("content", [])
        if block.get("type") == "text"
    )

    data = _parse_json_response(text)

    for key in ["grossAmount", "taxWithheld"]:
        if key not in data:
            raise ValueError(f"Claude did not return field: {key}")

    return data
