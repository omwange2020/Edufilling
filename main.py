from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import json
import io
from p9_extractor import extract_p9_data, extract_wht_data
from xml_generator import generate_itr_zip

app = FastAPI(title="EduFiling iTax API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/extract-p9")
async def extract_p9(file: UploadFile = File(...)):
    """
    Accepts a P9 form (PDF or image).
    Returns extracted tax values as JSON.
    """
    contents = await file.read()
    filename = file.filename or ""
    content_type = file.content_type or ""

    try:
        data = await extract_p9_data(contents, filename, content_type)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/api/extract-wht")
async def extract_wht(file: UploadFile = File(...)):
    """
    Accepts a Withholding Tax certificate (PDF or image).
    Returns extracted gross amount and tax withheld.
    """
    contents = await file.read()
    filename = file.filename or ""
    content_type = file.content_type or ""

    try:
        data = await extract_wht_data(contents, filename, content_type)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/api/generate-zip")
async def generate_zip(payload: str = Form(...)):
    """
    Accepts the full return data as JSON string.
    Generates the KRA-compatible XML, zips it, and returns the ZIP file.
    """
    try:
        data = json.loads(payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    try:
        zip_bytes, zip_filename = generate_itr_zip(data)
        return StreamingResponse(
            io.BytesIO(zip_bytes),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
