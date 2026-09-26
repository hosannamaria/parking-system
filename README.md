# Modern Parking System - Kenya

Full-stack parking automation system (Data Structures & Algorithms project).

## Stack

- **Frontend:** HTML + CSS + JavaScript (live slot grid, auto-refresh every 5s)
- **Backend:** Python Flask REST API (8 modules)
- **Database:** SQLite (auto-created on first run)

## The 8 Modules

| # | Module | Data Structure | Why |
| --- | --- | --- | --- |
| 1 | Slot Display | Array/list | O(1) index access for grid rendering |
| 2 | Vehicle Entry | SQLite INSERT | Persistent ticket record |
| 3 | Slot Allocation | Min-heap (`heapq`) | O(log n) allocate/release, lowest slot first |
| 4 | Duration Tracking | `datetime` arithmetic | O(1) elapsed-time computation |
| 5 | Fee Calculation | Formula (50 KES 1st hr, 30/hr, 300/day cap) | Deterministic tariff |
| 6 | Payment | Validation function | Blocks underpayment |
| 7 | Barrier Control | Access-control gate | Opens ONLY after confirmed payment |
| 8 | Records & Reporting | SQL queries | Search by plate, daily revenue |

## How to Run Locally

1. Install Python 3.10+ from python.org
2. Open terminal in this folder
3. `pip install -r requirements.txt`
4. `python app.py`
5. Open http://127.0.0.1:5000 in your browser

## API

- `GET /api/slots` - slot statuses
- `POST /api/arrival` `{plate, vehicle_type}`
- `GET /api/quote/<plate>` - automatic fee quote (duration + amount due)
- `POST /api/departure` `{plate, amount_paid, method}`
- `GET /api/search/<plate>`
- `GET /api/report/<YYYY-MM-DD>`

The frontend communicates with the backend via REST API calls(fetch) and the backend persists everything in SQLite.