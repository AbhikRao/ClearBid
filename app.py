import streamlit as st
import json, os, datetime, io, re

from groq import Groq
import pdfplumber
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ClearBid — Procurement Auditor",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Styling ── Midnight Tech palette ─────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Fraunces:ital,wght@0,700;1,400&display=swap');

  /* ── Global ── */
  html, body, [data-testid="stAppViewContainer"] {
    background: #020617 !important;
    font-family: 'Inter', sans-serif;
    color: #cbd5e1;
  }

  /* ── Sidebar ── */
  [data-testid="stSidebar"] {
    background: #0f172a !important;
    border-right: 1px solid #1e293b;
  }
  [data-testid="stSidebar"] * { color: #94a3b8 !important; }
  [data-testid="stSidebar"] h2,
  [data-testid="stSidebar"] strong { color: #f1f5f9 !important; }
  [data-testid="stSidebar"] .stRadio label { color: #94a3b8 !important; font-size: 13px; }
  [data-testid="stSidebar"] hr { border-color: #1e293b !important; }

  /* ── Main area ── */
  [data-testid="stMain"] { background: #020617 !important; }
  .block-container { padding-top: 2rem !important; }

  /* ── Header ── */
  .cb-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    border: 1px solid #1e293b;
    border-left: 4px solid #38bdf8;
    border-radius: 12px;
    padding: 28px 32px;
    margin-bottom: 32px;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.4), 0 2px 4px -2px rgba(0,0,0,0.3);
  }
  .cb-header h1 {
    font-family: 'Fraunces', serif;
    font-size: 28px;
    letter-spacing: -0.02em;
    color: #f1f5f9;
    margin: 0 0 6px;
  }
  .cb-header p { color: #64748b; font-size: 13px; margin: 0; font-weight: 400; }
  .cb-header .tag {
    display: inline-block;
    background: rgba(56,189,248,0.1);
    color: #38bdf8;
    border: 1px solid rgba(56,189,248,0.2);
    font-size: 11px; font-weight: 600;
    padding: 3px 10px; border-radius: 4px;
    margin-right: 6px; margin-top: 10px;
    letter-spacing: 0.04em; text-transform: uppercase;
  }

  /* ── Cards ── */
  .cb-card {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 20px 22px;
    margin-bottom: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.3), 0 1px 2px rgba(0,0,0,0.2);
    transition: box-shadow 0.2s, transform 0.2s;
  }
  .cb-card:hover {
    box-shadow: 0 10px 15px -3px rgba(0,0,0,0.4), 0 4px 6px -4px rgba(0,0,0,0.3);
    transform: translateY(-1px);
  }
  .cb-card-accent { border-left: 3px solid #38bdf8; }
  .crit-id {
    font-size: 10px; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase; color: #38bdf8; margin-bottom: 4px;
  }
  .crit-desc { font-size: 14px; font-weight: 500; color: #e2e8f0; margin: 4px 0; }
  .crit-meta { font-size: 12px; color: #64748b; margin-top: 6px; }

  /* ── Verdict chips ── */
  .eligible {
    background: rgba(34,197,94,0.1); color: #4ade80;
    border: 1px solid rgba(34,197,94,0.2);
    padding: 3px 12px; border-radius: 4px; font-weight: 600; font-size: 11px;
    letter-spacing: 0.06em; text-transform: uppercase;
  }
  .not-eligible {
    background: rgba(239,68,68,0.1); color: #f87171;
    border: 1px solid rgba(239,68,68,0.2);
    padding: 3px 12px; border-radius: 4px; font-weight: 600; font-size: 11px;
    letter-spacing: 0.06em; text-transform: uppercase;
  }
  .needs-review {
    background: rgba(245,158,11,0.1); color: #fbbf24;
    border: 1px solid rgba(245,158,11,0.2);
    padding: 3px 12px; border-radius: 4px; font-weight: 600; font-size: 11px;
    letter-spacing: 0.06em; text-transform: uppercase;
  }

  /* ── Bidder result header ── */
  .bidder-hdr {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-bottom: none;
    border-radius: 10px 10px 0 0;
    padding: 16px 20px;
    margin-top: 28px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .bidder-hdr-name {
    font-family: 'Fraunces', serif;
    font-size: 17px;
    color: #f1f5f9;
    letter-spacing: -0.01em;
  }
  .bidder-hdr-id { font-size: 11px; color: #475569; margin-left: 10px; }

  /* ── Metric overrides ── */
  div[data-testid="stMetric"] {
    background: #0f172a !important;
    border: 1px solid #1e293b !important;
    border-radius: 10px !important;
    padding: 20px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.3) !important;
  }
  div[data-testid="stMetric"] label { color: #64748b !important; font-size: 11px !important; text-transform: uppercase; letter-spacing: 0.05em; }
  div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: #f1f5f9 !important; font-size: 30px !important; font-weight: 700 !important; }

  /* ── Buttons ── */
  .stButton > button {
    background: #38bdf8 !important;
    color: #020617 !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    padding: 10px 20px !important;
    transition: transform 0.15s, box-shadow 0.15s !important;
    box-shadow: 0 0 0 0 rgba(56,189,248,0.4) !important;
  }
  .stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 0 20px rgba(56,189,248,0.3) !important;
  }

  /* ── File uploader ── */
  [data-testid="stFileUploader"] {
    background: #0f172a !important;
    border: 2px dashed #1e293b !important;
    border-radius: 10px !important;
  }
  [data-testid="stFileUploader"]:hover { border-color: #38bdf8 !important; }

  /* ── Dataframe ── */
  [data-testid="stDataFrame"] {
    border: 1px solid #1e293b !important;
    border-radius: 10px !important;
    overflow: hidden;
  }

  /* ── Section headings ── */
  h2, h3 {
    font-family: 'Fraunces', serif !important;
    letter-spacing: -0.02em !important;
    color: #f1f5f9 !important;
  }
  h3 { font-size: 20px !important; margin-bottom: 4px !important; }
  p, li { color: #94a3b8; }

  /* ── Divider ── */
  hr { border-color: #1e293b !important; }

  /* ── Expander ── */
  [data-testid="stExpander"] {
    background: #0f172a !important;
    border: 1px solid #1e293b !important;
    border-radius: 8px !important;
  }

  /* ── Progress bar ── */
  [data-testid="stProgressBar"] > div { background: #38bdf8 !important; }

  /* ── Info / success / warning boxes ── */
  [data-testid="stAlert"] {
    background: #0f172a !important;
    border-radius: 8px !important;
    border: 1px solid #1e293b !important;
    color: #94a3b8 !important;
  }

  /* ── Download button ── */
  .stDownloadButton > button {
    background: transparent !important;
    color: #38bdf8 !important;
    border: 1px solid #38bdf8 !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: transform 0.15s, background 0.15s !important;
  }
  .stDownloadButton > button:hover {
    background: rgba(56,189,248,0.1) !important;
    transform: translateY(-2px) !important;
  }

  /* ── Hide Streamlit branding ── */
  #MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Init state ────────────────────────────────────────────────────────────────
for key, val in [("criteria",[]), ("bidders",[]), ("evaluations",[]), ("tender_text","")]:
    if key not in st.session_state:
        st.session_state[key] = val

# ── Helpers ───────────────────────────────────────────────────────────────────
def get_groq():
    key = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY", ""))
    if not key:
        st.error("GROQ_API_KEY not found. Add it to .streamlit/secrets.toml or your environment.")
        st.stop()
    return Groq(api_key=key)

def llm(prompt: str) -> str:
    client = get_groq()
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1, max_tokens=2000,
    )
    return resp.choices[0].message.content.strip()

def clean_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    raw = raw.strip()
    m = re.search(r'(\{.*\}|\[.*\])', raw, re.DOTALL)
    return m.group(1) if m else raw

def read_pdf(file_bytes: bytes) -> str:
    text = ""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            t = page.extract_text()
            if t:
                text += f"\n[PAGE {i+1}]\n{t}"
    return text.strip()

def parse_doc(file) -> str:
    b = file.read()
    if file.name.lower().endswith(".pdf"):
        return read_pdf(b)
    return b.decode("utf-8", errors="ignore")

def verdict_badge(v: str) -> str:
    cls = {"ELIGIBLE":"eligible","NOT_ELIGIBLE":"not-eligible","NEEDS_REVIEW":"needs-review"}.get(v,"needs-review")
    label = v.replace("_"," ")
    return f'<span class="{cls}">{label}</span>'

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ClearBid")
    st.markdown("**Procurement Auditor**")
    st.markdown("---")
    st.markdown("**Pipeline Status**")
    st.markdown(f"{'— Tender uploaded' if st.session_state.tender_text else '· Awaiting tender'}")
    st.markdown(f"{'— ' + str(len(st.session_state.criteria)) + ' criteria extracted' if st.session_state.criteria else '· Criteria pending'}")
    st.markdown(f"{'— ' + str(len(st.session_state.bidders)) + ' bidder(s) loaded' if st.session_state.bidders else '· No bidders yet'}")
    st.markdown(f"{'— Evaluation complete' if st.session_state.evaluations else '· Not evaluated'}")
    st.markdown("---")
    page = st.radio("Navigate", ["1. Upload Tender","2. Review Criteria","3. Upload Bidders","4. Evaluate","5. Results & Report"], label_visibility="collapsed")
    st.markdown("---")
    if st.button("Reset Everything", use_container_width=True):
        for k in ["criteria","bidders","evaluations","tender_text"]:
            st.session_state[k] = [] if k != "tender_text" else ""
        st.rerun()
    st.markdown("---")
    st.markdown('<p style="font-size:11px;color:#475569">AI for Bharat · Theme 3<br>GFR 2017 Compliant · NIC Ready</p>', unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="cb-header">
  <h1>ClearBid</h1>
  <p>Explainable AI for Government Tender Evaluation &nbsp;·&nbsp; AI for Bharat &nbsp;·&nbsp; Theme 3: CRPF Procurement</p>
  <span class="tag">GFR 2017</span>
  <span class="tag">NIC Ready</span>
  <span class="tag">Zero Silent Rejection</span>
</div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# PAGE 1: UPLOAD TENDER
# ════════════════════════════════════════════════════════════════════════════
if page == "1. Upload Tender":
    st.markdown("### Upload Tender Document")
    st.markdown("Upload the CRPF tender PDF or TXT. The system will extract and structure all eligibility criteria.")
    uploaded = st.file_uploader("Tender document", type=["pdf","txt"], key="tender_upload")

    if uploaded:
        if st.button("Extract Criteria", type="primary", use_container_width=True):
            with st.spinner("Parsing tender and extracting eligibility criteria..."):
                text = parse_doc(uploaded)
                st.session_state.tender_text = text

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

                try:
                    raw = llm(prompt)
                    criteria = json.loads(clean_json(raw))
                    st.session_state.criteria = criteria
                    st.success(f"✅ {len(criteria)} eligibility criteria extracted successfully!")
                    st.info("Go to **2. Review Criteria** in the sidebar to see them.")
                except Exception as e:
                    st.error(f"Error extracting criteria: {e}")

    if st.session_state.tender_text:
        with st.expander("Tender text preview"):
            st.text(st.session_state.tender_text[:1000] + "...")

# ════════════════════════════════════════════════════════════════════════════
# PAGE 2: REVIEW CRITERIA
# ════════════════════════════════════════════════════════════════════════════
elif page == "2. Review Criteria":
    st.markdown("### Extracted Eligibility Criteria")
    if not st.session_state.criteria:
        st.warning("No criteria yet. Upload a tender first.")
    else:
        mandatory = [c for c in st.session_state.criteria if c.get("mandatory")]
        optional  = [c for c in st.session_state.criteria if not c.get("mandatory")]
        st.markdown(f"**{len(st.session_state.criteria)} criteria extracted** · {len(mandatory)} mandatory · {len(optional)} optional")
        st.markdown("---")


        for c in st.session_state.criteria:
            col1, col2 = st.columns([3,1])
            with col1:
                st.markdown(f"""
                <div class="cb-card cb-card-accent">
                  <div class="crit-id">{c['id']} · {c['category'].upper()}</div>
                  <div class="crit-desc">{c['description']}</div>
                  <div style="font-size:12px;color:#4A5568;margin-top:6px">
                    Threshold: <b>{c.get('threshold','—')}</b>
                    {f"&nbsp;·&nbsp; Clause: {c['source_clause']}" if c.get('source_clause') else ""}
                  </div>
                </div>""", unsafe_allow_html=True)
            with col2:
                if c.get("mandatory"):
                    st.markdown('<div style="background:#FCECEC;color:#8B1A1A;padding:6px 12px;border-radius:8px;text-align:center;font-weight:700;font-size:12px;margin-top:14px">MANDATORY</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div style="background:#EEF2F8;color:#4A5568;padding:6px 12px;border-radius:8px;text-align:center;font-weight:700;font-size:12px;margin-top:14px">OPTIONAL</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# PAGE 3: UPLOAD BIDDERS
# ════════════════════════════════════════════════════════════════════════════
elif page == "3. Upload Bidders":
    st.markdown("### Upload Bidder Submissions")
    st.markdown("Upload documents for each bidder. You can upload multiple files at once.")

    if not st.session_state.criteria:
        st.warning("Please upload a tender and extract criteria first.")
    else:
        files = st.file_uploader("Upload bidder documents", type=["pdf","txt"],
                                  accept_multiple_files=True, key="bidder_upload")

        if files and st.button("Load Bidders", type="primary"):
            existing_names = [b["name"] for b in st.session_state.bidders]
            added = 0
            for f in files:
                name = f.name.replace(".txt","").replace(".pdf","")
                if name not in existing_names:
                    text = parse_doc(f)
                    bid_id = f"BIDDER_{len(st.session_state.bidders)+1:02d}"
                    st.session_state.bidders.append({"id": bid_id, "name": name, "text": text})
                    added += 1
            if added:
                st.success(f"✅ {added} bidder(s) loaded. Total: {len(st.session_state.bidders)}")
            else:
                st.info("All uploaded bidders already loaded.")

        if st.session_state.bidders:
            st.markdown("---")
            st.markdown(f"**{len(st.session_state.bidders)} bidder(s) ready for evaluation:**")
            for b in st.session_state.bidders:
                st.markdown(f"**{b['name']}** — {b['id']}")

# ════════════════════════════════════════════════════════════════════════════
# PAGE 4: EVALUATE
# ════════════════════════════════════════════════════════════════════════════
elif page == "4. Evaluate":
    st.markdown("### Run Evaluation")

    if not st.session_state.criteria:
        st.warning("Upload a tender first.")
    elif not st.session_state.bidders:
        st.warning("Upload at least one bidder first.")
    else:
        st.markdown(f"Ready to evaluate **{len(st.session_state.bidders)} bidder(s)** against **{len(st.session_state.criteria)} criteria**.")
        total_calls = len(st.session_state.bidders) * len(st.session_state.criteria)
        st.info(f"This will make {total_calls} AI calls. Takes about {total_calls * 3} seconds.")

        if st.button("Run Full Evaluation", type="primary", use_container_width=True):
            results = []
            overall_progress = st.progress(0)
            status_text = st.empty()
            total = len(st.session_state.bidders) * len(st.session_state.criteria)
            done = 0

            for bidder in st.session_state.bidders:
                status_text.markdown(f"**Evaluating {bidder['name']}...**")
                bidder_results = {"bidder_id": bidder["id"], "name": bidder["name"], "criteria_results": []}

                for crit in st.session_state.criteria:
                    prompt = f"""You are a strict government procurement evaluator.

CRITERION:
ID: {crit['id']}
Description: {crit['description']}
Threshold: {crit.get('threshold','See description')}
Mandatory: {crit['mandatory']}

BIDDER DOCUMENT:
{bidder['text'][:4000]}

Return ONLY a JSON object with:
- verdict: "ELIGIBLE" | "NOT_ELIGIBLE" | "NEEDS_REVIEW"
- confidence: number 0.0 to 1.0
- evidence: exact text/value found, or "Not found"
- page_reference: page or section, or "N/A"
- reasoning: one sentence explanation

Use NEEDS_REVIEW if evidence is ambiguous. Never guess. Return only JSON, no markdown."""

                    try:
                        raw = llm(prompt)
                        result = json.loads(clean_json(raw))
                    except Exception:
                        result = {"verdict":"NEEDS_REVIEW","confidence":0.5,
                                  "evidence":"Parse error","page_reference":"N/A",
                                  "reasoning":"Could not parse — flagged for manual review."}

                    result["criterion_id"]   = crit["id"]
                    result["criterion_desc"] = crit["description"]
                    result["mandatory"]      = crit["mandatory"]
                    bidder_results["criteria_results"].append(result)
                    done += 1
                    overall_progress.progress(done / total)

                mandatory = [r for r in bidder_results["criteria_results"] if r["mandatory"]]
                if any(r["verdict"] == "NOT_ELIGIBLE" for r in mandatory):
                    bidder_results["overall"] = "NOT_ELIGIBLE"
                elif any(r["verdict"] == "NEEDS_REVIEW" for r in mandatory):
                    bidder_results["overall"] = "NEEDS_REVIEW"
                else:
                    bidder_results["overall"] = "ELIGIBLE"

                avg = sum(r["confidence"] for r in bidder_results["criteria_results"]) / len(bidder_results["criteria_results"])
                bidder_results["avg_confidence"] = round(avg, 2)
                results.append(bidder_results)

            st.session_state.evaluations = results
            overall_progress.progress(1.0)
            status_text.markdown("✅ **Evaluation complete!**")
            st.success(f"Done! Navigate to **5. Results & Report** to see the full breakdown.")

# ════════════════════════════════════════════════════════════════════════════
# PAGE 5: RESULTS & REPORT
# ════════════════════════════════════════════════════════════════════════════
elif page == "5. Results & Report":
    st.markdown("### Evaluation Results")

    if not st.session_state.evaluations:
        st.warning("No evaluations yet. Run the evaluation first.")
    else:
        evs = st.session_state.evaluations
        eligible     = sum(1 for e in evs if e["overall"] == "ELIGIBLE")
        not_eligible = sum(1 for e in evs if e["overall"] == "NOT_ELIGIBLE")
        review       = sum(1 for e in evs if e["overall"] == "NEEDS_REVIEW")

        # Summary metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Bidders",  len(evs))
        c2.metric("✅ Eligible",     eligible)
        c3.metric("❌ Not Eligible", not_eligible)
        c4.metric("⚠️ Needs Review", review)

        st.markdown("---")

        # PDF Export
        def make_pdf(evaluations):
            buf = io.BytesIO()
            NAVY=HexColor("#1B2A4A"); STEEL=HexColor("#2C4A7C")
            LIGHT=HexColor("#F7F9FC"); GRAY=HexColor("#4A5568")
            small = ParagraphStyle("s", fontName="Helvetica",      fontSize=7.5, textColor=GRAY,  leading=11)
            head  = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=11,  textColor=STEEL, leading=14, spaceBefore=10)
            title = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=16,  textColor=NAVY,  leading=20)
            doc = SimpleDocTemplate(buf, pagesize=A4,
                leftMargin=20*mm, rightMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
            W = A4[0] - 40*mm
            story = []
            story.append(Paragraph("ClearBid — Procurement Evaluation Report", title))
            story.append(Paragraph(f"Generated: {datetime.datetime.now().strftime('%d %B %Y, %H:%M')}", small))
            story.append(Spacer(1, 5*mm))
            for ev in evaluations:
                story.append(Paragraph(
                    f"Bidder: {ev['name']}  |  Overall: {ev['overall']}  |  Avg Confidence: {ev['avg_confidence']}", head))
                story.append(Spacer(1, 2*mm))
                rows = [[Paragraph(f"<b>{h}</b>", small) for h in ["Criterion","Verdict","Conf.","Evidence","Source"]]]
                for r in ev["criteria_results"]:
                    rows.append([
                        Paragraph(r["criterion_desc"][:55], small),
                        Paragraph(r["verdict"].replace("_"," "), small),
                        Paragraph(str(r["confidence"]), small),
                        Paragraph(str(r["evidence"])[:75], small),
                        Paragraph(str(r["page_reference"]), small),
                    ])
                cws = [0.28*W,0.14*W,0.08*W,0.35*W,0.15*W]
                tbl = Table(rows, colWidths=cws)
                tbl.setStyle(TableStyle([
                    ("BACKGROUND",(0,0),(-1,0),NAVY),("TEXTCOLOR",(0,0),(-1,0),colors.white),
                    ("ROWBACKGROUNDS",(0,1),(-1,-1),[LIGHT,colors.white]),
                    ("GRID",(0,0),(-1,-1),0.3,HexColor("#D1D9E6")),
                    ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
                    ("LEFTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP"),
                ]))
                story.append(tbl)
                story.append(Spacer(1, 6*mm))
            story.append(Paragraph(
                "All verdicts are advisory. Final decisions remain with the designated procurement officer.",
                ParagraphStyle("d", fontName="Helvetica-Oblique", fontSize=7.5, textColor=GRAY, leading=11)))
            doc.build(story)
            return buf.getvalue()

        pdf_bytes = make_pdf(evs)
        st.download_button("Download PDF Audit Report", data=pdf_bytes,
            file_name="ClearBid_Report.pdf", mime="application/pdf",
            use_container_width=True, type="primary")

        st.markdown("---")

        # Per-bidder results
        for ev in evs:
            overall = ev["overall"]
            color = {"ELIGIBLE":"#1E6B3C","NOT_ELIGIBLE":"#8B1A1A","NEEDS_REVIEW":"#8B5A00"}.get(overall,"#4A5568")
            bg    = {"ELIGIBLE":"#EBF5EC","NOT_ELIGIBLE":"#FCECEC","NEEDS_REVIEW":"#FDF6E3"}.get(overall,"#F7F9FC")

            st.markdown(f"""
            <div style="background:#1B2A4A;color:white;padding:14px 18px;border-radius:10px 10px 0 0;
                        display:flex;justify-content:space-between;align-items:center;margin-top:20px">
              <span class="bidder-hdr-name">{ev['name']} <span class="bidder-hdr-id">{ev['bidder_id']}</span></span>
              <span style="background:{bg};color:{color};padding:4px 14px;border-radius:20px;font-weight:700;font-size:12px">
                {overall.replace("_"," ")}
              </span>
            </div>""", unsafe_allow_html=True)

            rows = []
            for r in ev["criteria_results"]:
                rows.append({
                    "Criterion": r["criterion_desc"],
                    "Verdict":   r["verdict"].replace("_"," "),
                    "Confidence": r["confidence"],
                    "Evidence":  r["evidence"],
                    "Source":    r["page_reference"],
                    "Reasoning": r["reasoning"],
                    "Mandatory": "Yes" if r["mandatory"] else "No",
                })
            import pandas as pd
            df = pd.DataFrame(rows)

            def color_verdict(val):
                if "NOT ELIGIBLE" in val: return "background-color:#FCECEC;color:#8B1A1A;font-weight:700"
                if "NEEDS REVIEW" in val: return "background-color:#FDF6E3;color:#8B5A00;font-weight:700"
                if "ELIGIBLE"     in val: return "background-color:#EBF5EC;color:#1E6B3C;font-weight:700"
                return ""

            styled = df.style.applymap(color_verdict, subset=["Verdict"])
            st.dataframe(styled, use_container_width=True, hide_index=True)
            st.markdown(f"*Avg confidence: {ev['avg_confidence']}*")
