import os, json, datetime
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import pdfplumber
from groq import Groq
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
from dotenv import load_dotenv

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))

app = FastAPI(title="ClearBid API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STATE = {"tender_text": "", "criteria": [], "bidders": [], "evaluations": []}

def llm(prompt: str) -> str:
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=2000,
    )
    return response.choices[0].message.content.strip()

def clean_json(raw: str) -> str:
    import re
    raw = raw.strip()
    # Strip markdown fences
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    raw = raw.strip()
    # Extract first JSON object or array if there's surrounding text
    match = re.search(r'(\{.*\}|\[.*\])', raw, re.DOTALL)
    if match:
        raw = match.group(1)
    return raw.strip()

def extract_text_from_pdf(file_bytes: bytes) -> str:
    import io
    text = ""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            t = page.extract_text()
            if t:
                text += f"\n[PAGE {i+1}]\n{t}"
    return text.strip()

def parse_document(file_bytes: bytes, filename: str) -> str:
    if filename.lower().endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    return file_bytes.decode("utf-8", errors="ignore")


@app.post("/upload-tender")
async def upload_tender(file: UploadFile = File(...)):
    content = await file.read()
    text = parse_document(content, file.filename)
    STATE["tender_text"] = text
    STATE["criteria"] = []
    STATE["bidders"] = []
    STATE["evaluations"] = []

    prompt = f"""You are a government procurement expert. Extract ALL eligibility criteria from this tender document.
Return ONLY a JSON array. Each item must have:
- id: string like "CRIT_01"
- category: "financial" | "technical" | "compliance" | "document"
- description: clear one-line description
- mandatory: true or false
- threshold: the specific value or requirement
- source_clause: clause reference if visible, else ""

TENDER DOCUMENT:
{text[:6000]}

Return only the JSON array, no explanation, no markdown fences."""

    raw = llm(prompt)
    criteria = json.loads(clean_json(raw))
    STATE["criteria"] = criteria
    return {"status": "ok", "criteria": criteria, "tender_preview": text[:300]}


@app.post("/upload-bidder")
async def upload_bidder(file: UploadFile = File(...), name: str = ""):
    content = await file.read()
    text = parse_document(content, file.filename)
    bidder_id = f"BIDDER_{len(STATE['bidders']) + 1:02d}"
    bidder = {"id": bidder_id, "name": name or file.filename, "text": text, "filename": file.filename}
    STATE["bidders"].append(bidder)
    return {"status": "ok", "bidder_id": bidder_id, "name": bidder["name"], "preview": text[:200]}


@app.post("/evaluate")
async def evaluate():
    if not STATE["criteria"]:
        raise HTTPException(400, "No tender uploaded yet")
    if not STATE["bidders"]:
        raise HTTPException(400, "No bidders uploaded yet")

    results = []
    for bidder in STATE["bidders"]:
        bidder_results = {"bidder_id": bidder["id"], "name": bidder["name"], "criteria_results": []}

        for crit in STATE["criteria"]:
            prompt = f"""You are a strict government procurement evaluator.

CRITERION:
ID: {crit['id']}
Description: {crit['description']}
Threshold: {crit.get('threshold', 'See description')}
Mandatory: {crit['mandatory']}

BIDDER DOCUMENT:
{bidder['text'][:4000]}

Return ONLY a JSON object with:
- verdict: "ELIGIBLE" | "NOT_ELIGIBLE" | "NEEDS_REVIEW"
- confidence: number 0.0 to 1.0
- evidence: exact text/value found, or "Not found"
- page_reference: page or section, or "N/A"
- reasoning: one sentence explanation

Use NEEDS_REVIEW if evidence is ambiguous or unclear. Never guess.
Return only JSON, no markdown, no explanation."""

            raw = llm(prompt)
            try:
                result = json.loads(clean_json(raw))
            except Exception:
                result = {"verdict": "NEEDS_REVIEW", "confidence": 0.5,
                          "evidence": "Parse error", "page_reference": "N/A",
                          "reasoning": "Could not parse — flagged for manual review."}

            result["criterion_id"]   = crit["id"]
            result["criterion_desc"] = crit["description"]
            result["mandatory"]      = crit["mandatory"]
            bidder_results["criteria_results"].append(result)

        mandatory = [r for r in bidder_results["criteria_results"] if r["mandatory"]]
        if any(r["verdict"] == "NOT_ELIGIBLE" for r in mandatory):
            bidder_results["overall"] = "NOT_ELIGIBLE"
        elif any(r["verdict"] == "NEEDS_REVIEW" for r in mandatory):
            bidder_results["overall"] = "NEEDS_REVIEW"
        else:
            bidder_results["overall"] = "ELIGIBLE"

        avg_conf = sum(r["confidence"] for r in bidder_results["criteria_results"]) / len(bidder_results["criteria_results"])
        bidder_results["avg_confidence"] = round(avg_conf, 2)
        results.append(bidder_results)

    STATE["evaluations"] = results
    return {"status": "ok", "evaluations": results}


@app.get("/state")
async def get_state():
    return {
        "has_tender": bool(STATE["tender_text"]),
        "criteria_count": len(STATE["criteria"]),
        "bidder_count": len(STATE["bidders"]),
        "evaluation_count": len(STATE["evaluations"]),
        "criteria": STATE["criteria"],
        "bidders": [{"id": b["id"], "name": b["name"]} for b in STATE["bidders"]],
        "evaluations": STATE["evaluations"],
    }


@app.get("/export-report")
async def export_report():
    if not STATE["evaluations"]:
        raise HTTPException(400, "No evaluations to export")

    path = "/tmp/clearbid_report.pdf"
    from reportlab.lib.colors import HexColor
    NAVY  = HexColor("#1B2A4A"); STEEL = HexColor("#2C4A7C")
    LIGHT = HexColor("#F7F9FC"); GRAY  = HexColor("#4A5568")

    small_s = ParagraphStyle("s", fontName="Helvetica",      fontSize=7.5, textColor=GRAY,  leading=11)
    head_s  = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=11,  textColor=STEEL, leading=14, spaceBefore=12)
    title_s = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=16,  textColor=NAVY,  leading=20)

    doc = SimpleDocTemplate(path, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
    W = A4[0] - 40*mm
    story = []
    story.append(Paragraph("ClearBid — Procurement Evaluation Report", title_s))
    story.append(Paragraph(f"Generated: {datetime.datetime.now().strftime('%d %B %Y, %H:%M')}", small_s))
    story.append(Spacer(1, 5*mm))

    for ev in STATE["evaluations"]:
        story.append(Paragraph(
            f"Bidder: {ev['name']}  |  Overall: {ev['overall']}  |  Avg Confidence: {ev['avg_confidence']}",
            head_s))
        story.append(Spacer(1, 2*mm))
        table_data = [[
            Paragraph("<b>Criterion</b>", small_s), Paragraph("<b>Verdict</b>", small_s),
            Paragraph("<b>Conf.</b>",     small_s), Paragraph("<b>Evidence</b>", small_s),
            Paragraph("<b>Source</b>",    small_s),
        ]]
        for r in ev["criteria_results"]:
            table_data.append([
                Paragraph(r["criterion_desc"][:60],       small_s),
                Paragraph(r["verdict"].replace("_", " "), small_s),
                Paragraph(str(r["confidence"]),           small_s),
                Paragraph(str(r["evidence"])[:80],        small_s),
                Paragraph(str(r["page_reference"]),       small_s),
            ])
        cws = [0.28*W, 0.14*W, 0.08*W, 0.35*W, 0.15*W]
        tbl = Table(table_data, colWidths=cws)
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,0),  NAVY),
            ("TEXTCOLOR",     (0,0),(-1,0),  colors.white),
            ("ROWBACKGROUNDS",(0,1),(-1,-1), [LIGHT, colors.white]),
            ("GRID",          (0,0),(-1,-1), 0.3, HexColor("#D1D9E6")),
            ("TOPPADDING",    (0,0),(-1,-1), 4),
            ("BOTTOMPADDING", (0,0),(-1,-1), 4),
            ("LEFTPADDING",   (0,0),(-1,-1), 5),
            ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 6*mm))

    story.append(Paragraph(
        "All verdicts are advisory. Final decisions remain with the designated procurement officer.",
        ParagraphStyle("d", fontName="Helvetica-Oblique", fontSize=7.5, textColor=GRAY, leading=11)))
    doc.build(story)
    return FileResponse(path, filename="ClearBid_Report.pdf", media_type="application/pdf")


@app.delete("/reset")
async def reset():
    STATE.update({"tender_text": "", "criteria": [], "bidders": [], "evaluations": []})
    return {"status": "reset"}
