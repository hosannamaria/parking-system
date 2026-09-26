"""
=============================================================
 MODERN PARKING SYSTEM - Full Stack (Flask + SQLite + JS)
 8 Modules: Display | Entry | Allocation | Duration
            | Fees | Payment | Barrier | Reports
=============================================================
"""
import sqlite3, heapq
from datetime import datetime
from collections import deque
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)
DB = "parking.db"
TOTAL_SLOTS = 40

# ---------------- Kenya tariff (KES) ----------------
BASE_FEE, HOURLY_RATE, DAILY_CAP, LOST_TICKET = 50, 30, 300, 500

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.execute("""CREATE TABLE IF NOT EXISTS tickets(
        ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
        plate TEXT NOT NULL, vehicle_type TEXT, slot_no INTEGER,
        entry_time TEXT, exit_time TEXT, duration_sec REAL,
        fee_paid REAL DEFAULT 0, status TEXT DEFAULT 'ACTIVE')""")
    conn.commit(); conn.close()

# =====================================================================
# MODULE 3: SLOT ALLOCATION  (min-heap)
# =====================================================================
class SlotAllocator:
    def __init__(self, n):
        self.total = n
        self.free = list(range(1, n + 1)); heapq.heapify(self.free)
        # rebuild heap from DB in case server restarted mid-day
        conn = db()
        for r in conn.execute("SELECT slot_no FROM tickets WHERE status='ACTIVE'"):
            if r["slot_no"] in self.free:
                self.free.remove(r["slot_no"])
        heapq.heapify(self.free); conn.close()

    def allocate(self):
        return heapq.heappop(self.free) if self.free else None
    def release(self, s): heapq.heappush(self.free, s)
    def occupied(self): return set(range(1, self.total + 1)) - set(self.free)

init_db()
ALLOC = SlotAllocator(TOTAL_SLOTS)
WAITING = deque()   # FIFO entrance queue (Module: overflow handling)

# =====================================================================
# MODULE 1: SLOT DISPLAY
# =====================================================================
def slot_status():
    occ = ALLOC.occupied()
    return [{"slot": i, "occupied": i in occ} for i in range(1, TOTAL_SLOTS + 1)]

# =====================================================================
# MODULE 2: VEHICLE ENTRY
# =====================================================================
def register(plate, vtype, slot):
    conn = db()
    cur = conn.execute(
        "INSERT INTO tickets(plate,vehicle_type,slot_no,entry_time,status)"
        " VALUES(?,?,?,?,'ACTIVE')",
        (plate.upper(), vtype, slot, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit(); tid = cur.lastrowid; conn.close()
    return tid

# =====================================================================
# MODULE 4: DURATION TRACKING
# =====================================================================
def duration(entry_time):
    entry = datetime.strptime(entry_time, "%Y-%m-%d %H:%M:%S")
    secs = (datetime.now() - entry).total_seconds()
    return secs, f"{int(secs//3600)}h {int(secs%3600//60)}m"

# =====================================================================
# MODULE 5: FEE CALCULATION
# =====================================================================
def fee(secs):
    if secs <= 0: return 0
    hours = secs / 3600
    if hours <= 1: return BASE_FEE
    total = BASE_FEE + int(hours) * HOURLY_RATE
    return min(total, (int(hours // 24) + 1) * DAILY_CAP)

# =====================================================================
# MODULE 6: PAYMENT
# =====================================================================
def pay(due, paid):
    return (paid >= due), max(0, paid - due)

# =====================================================================
# MODULE 7: BARRIER CONTROL
# =====================================================================
def gate(ok):
    return "BARRIER OPEN - vehicle may pass" if ok else "ACCESS DENIED - pay first"

# =====================================================================
# MODULE 8: RECORDS & REPORTING
# =====================================================================
def search(plate):
    conn = db()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM tickets WHERE plate=? ORDER BY entry_time",
        (plate.upper(),))]
    conn.close(); return rows

def report(date_str):
    conn = db()
    rows = conn.execute(
        "SELECT * FROM tickets WHERE entry_time LIKE ? AND status='CLOSED'",
        (date_str + "%",)).fetchall()
    conn.close()
    return {"date": date_str, "vehicles": len(rows),
            "revenue": sum(r["fee_paid"] for r in rows)}

# ============================ ROUTES ================================
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/slots")
def api_slots():
    s = slot_status()
    return jsonify({"slots": s, "free": sum(1 for x in s if not x["occupied"]),
                    "waiting": list(WAITING)})

@app.route("/api/arrival", methods=["POST"])
def api_arrival():
    plate = request.json.get("plate", "").strip()
    vtype = request.json.get("vehicle_type", "Car")
    if not plate:
        return jsonify({"error": "Plate number required"}), 400
    if search_active(plate):
        return jsonify({"error": f"{plate} already inside the car park"}), 400
    slot = ALLOC.allocate()
    if slot is None:
        WAITING.append(plate)
        return jsonify({"queued": True, "message":
                        "CARPARK FULL - queued at entrance (FIFO)"})
    tid = register(plate, vtype, slot)
    return jsonify({"queued": False, "ticket_id": tid, "slot": slot,
                    "barrier": gate(True)})

def search_active(plate):
    conn = db()
    r = conn.execute("SELECT 1 FROM tickets WHERE plate=? AND status='ACTIVE'",
                     (plate.upper(),)).fetchone()
    conn.close(); return r is not None

@app.route("/api/departure", methods=["POST"])
def api_departure():
    plate = request.json.get("plate", "").strip()
    paid = float(request.json.get("amount_paid", 0))
    method = request.json.get("method", "M-Pesa")
    conn = db()
    t = conn.execute("SELECT * FROM tickets WHERE plate=? AND status='ACTIVE'",
                     (plate.upper(),)).fetchone()
    if not t:
        conn.close()
        return jsonify({"error": "No active ticket", "lost_ticket_fee": LOST_TICKET}), 404
    secs, hr = duration(t["entry_time"])
    amount = fee(secs)
    ok, change = pay(amount, paid)
    if not ok:
        conn.close()
        return jsonify({"error": "Insufficient payment", "due": amount,
                        "barrier": gate(False)}), 402
    conn.execute("""UPDATE tickets SET exit_time=?, duration_sec=?,
                 fee_paid=?, status='CLOSED' WHERE ticket_id=?""",
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                  secs, amount, t["ticket_id"]))
    conn.commit(); conn.close()
    ALLOC.release(t["slot_no"])
    msg = gate(True)
    nxt = None
    if WAITING:                       # admit next queued vehicle
        nxt = WAITING.popleft()
        slot = ALLOC.allocate()
        if slot is not None:
            register(nxt, "Car", slot)
            msg += f" | Admitted queued vehicle {nxt} -> Slot {slot}"
    return jsonify({"plate": plate.upper(), "duration": hr, "seconds": secs,
                    "fee": amount, "paid": paid, "change": change,
                    "method": method, "barrier": msg})

@app.route("/api/quote/<plate>")
def api_quote(plate):
    """Automatic fee quote: duration + amount due, WITHOUT closing the ticket."""
    conn = db()
    t = conn.execute("SELECT * FROM tickets WHERE plate=? AND status='ACTIVE'",
                     (plate.upper(),)).fetchone()
    conn.close()
    if not t:
        return jsonify({"error": "No active ticket for this plate",
                        "lost_ticket_fee": LOST_TICKET}), 404
    secs, hr = duration(t["entry_time"])
    return jsonify({"plate": plate.upper(), "entry_time": t["entry_time"],
                    "slot": t["slot_no"], "duration": hr, "fee": fee(secs)})

@app.route("/api/search/<plate>")
def api_search(plate):
    return jsonify({"tickets": search(plate)})

@app.route("/api/report/<date>")
def api_report(date):
    return jsonify(report(date))

if __name__ == "__main__":
    app.run(debug=True)
