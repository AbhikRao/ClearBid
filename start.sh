#!/bin/bash
echo "================================================"
echo "  ClearBid — AI Procurement Auditor"
echo "  AI for Bharat Hackathon · Theme 3: CRPF"
echo "================================================"
echo ""

cd "$(dirname "$0")/backend"

# Check API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
  if [ -f .env ]; then
    export $(cat .env | xargs)
  fi
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "ERROR: ANTHROPIC_API_KEY not set."
  echo "Create backend/.env with: ANTHROPIC_API_KEY=your_key_here"
  exit 1
fi

# Install dependencies if needed
echo "Checking dependencies..."
pip3 install -r requirements.txt -q

echo ""
echo "Starting ClearBid backend on http://localhost:8000"
echo "Open frontend/index.html in your browser"
echo ""
echo "DEMO DATA is in synthetic_data/ folder:"
echo "  1. Upload: synthetic_data/crpf_tender.txt"
echo "  2. Upload bidders from synthetic_data/bidders/"
echo ""
echo "Press Ctrl+C to stop"
echo "================================================"
echo ""

python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
