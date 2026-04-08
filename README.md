# EduFiling — iTax Teacher Returns Backend

## What This Does
This FastAPI backend:
1. Accepts a P9 form (PDF or image) → uses Claude AI to extract tax values
2. Accepts a Withholding Tax certificate (optional) → extracts gross amount and tax withheld
3. Generates the **exact KRA iTax XML** file (reverse-engineered from real submissions)
4. Packages it into a ZIP file with the correct filename format
5. Returns the ZIP for the teacher to download and upload directly to iTax

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/extract-p9` | Upload P9 form → returns extracted JSON |
| POST | `/api/extract-wht` | Upload WHT certificate → returns extracted JSON |
| POST | `/api/generate-zip` | Submit all return data → returns ZIP file |

## Running Locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API will be available at: http://localhost:8000
Swagger docs at: http://localhost:8000/docs

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | YES | Your Anthropic API key for P9/WHT extraction |

Set it before running:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
uvicorn main:app --reload
```

## Deploying to Railway

1. Create a new project on railway.app
2. Connect your GitHub repo (push this backend folder)
3. Add environment variable: `ANTHROPIC_API_KEY`
4. Railway auto-detects Python and deploys
5. Copy the Railway URL → update frontend API base URL

## Frontend Integration

In the frontend (`itax-teacher-app.html`), replace the simulation functions:

```javascript
// Replace simulateP9Extraction() with:
async function extractP9FromBackend(file) {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch('https://YOUR-RAILWAY-URL/api/extract-p9', {
    method: 'POST',
    body: formData
  });
  const json = await res.json();
  return json.data;
}

// Replace the download button handler with:
async function generateAndDownloadZip(returnData) {
  const formData = new FormData();
  formData.append('payload', JSON.stringify(returnData));
  const res = await fetch('https://YOUR-RAILWAY-URL/api/generate-zip', {
    method: 'POST',
    body: formData
  });
  const blob = await res.blob();
  const filename = res.headers.get('Content-Disposition')
    .split('filename=')[1].replace(/"/g, '');
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
}
```

## ZIP Output Format

The generated ZIP matches the exact format KRA iTax expects:
- **ZIP filename**: `DD-MM-YYYY_HH-MM-SS_PIN_ITR.zip`
- **XML inside**: `DD-MM-YYYY_HH-MM-SS_PIN_ITR.xml`
- **Format**: KRA proprietary `field%V_@value@P_@` encoding
- **SheetCode**: `ITR_RET`

## Project Structure

```
itax-backend/
├── main.py           — FastAPI app + routes
├── p9_extractor.py   — Claude AI vision extraction for P9 and WHT
├── xml_generator.py  — KRA XML builder + ZIP packager
├── requirements.txt  — Python dependencies
└── README.md         — This file
```
