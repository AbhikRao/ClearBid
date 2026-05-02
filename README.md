# ClearBid — AI Procurement Auditor
### AI for Bharat Hackathon · Theme 3: CRPF Tender Evaluation

---

## What This Is
ClearBid evaluates government tender bidders using AI — criterion by criterion, with evidence citations, confidence scores, and a human review queue for ambiguous cases.

## Setup (2 minutes)

### 1. Add your API key
Open `backend/.env` and replace:
```
ANTHROPIC_API_KEY=your_api_key_here
```
Get a key at: https://console.anthropic.com

### 2. Run the app
```bash
chmod +x start.sh
./start.sh
```

### 3. Open the UI
Open `frontend/index.html` in Chrome or Safari.

---

## Demo Flow (for judges)

1. **Upload Tender** → use `synthetic_data/crpf_tender.txt`
2. **Review Criteria** → AI extracts 6 eligibility criteria
3. **Upload Bidders** → upload all 5 files from `synthetic_data/bidders/`
   - Bidder 1 (Sharma Security): Fully eligible ✅
   - Bidder 2 (Kapoor Infra): Fails turnover criterion ❌
   - Bidder 3 (Redfort Tech): Fails GST + ISO (both cancelled/expired) ❌
   - Bidder 4 (Bajaj Defence): Ambiguous — scan quality issues ⚠️
   - Bidder 5 (Sunrise Electronics): Ambiguous — only 1 similar work ⚠️
4. **Evaluate** → click Run Evaluation
5. **Results** → criterion-level table with evidence, confidence bars
6. **Export** → download PDF audit report

---

## Requirements
- Python 3.9+
- Anthropic API key (Claude Sonnet)
- Modern browser (Chrome recommended)

## Tech Stack
- Backend: FastAPI + Python
- LLM: Claude claude-sonnet-4-5 (Anthropic)
- Document parsing: pdfplumber
- Report generation: ReportLab
- Frontend: Vanilla HTML/CSS/JS (no build step)
