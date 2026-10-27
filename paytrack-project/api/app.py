import json
import os
import uuid
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import redis

engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
queue = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
app = Flask(__name__)

def init_db():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,
                customer_name VARCHAR(120) NOT NULL,
                amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
                currency VARCHAR(3) NOT NULL DEFAULT 'NGN',
                reference VARCHAR(80) NOT NULL UNIQUE,
                status VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'completed', 'failed')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))

@app.before_request
def prepare_schema():
    # Starter shortcut. Real projects should use versioned database migrations.
    init_db()

def to_dict(row):
    return {
        "id": row["id"], "customer_name": row["customer_name"],
        "amount": float(row["amount"]), "currency": row["currency"],
        "reference": row["reference"], "status": row["status"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None
    }

@app.get("/api/health/live")
def live():
    return jsonify(status="ok"), 200

@app.get("/api/health/ready")
def ready():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        queue.ping()
        return jsonify(status="ready", database="ok", redis="ok"), 200
    except Exception:
        return jsonify(status="not_ready"), 503

@app.get("/api/payments")
def list_payments():
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, customer_name, amount, currency, reference, status, created_at, updated_at
            FROM payments ORDER BY id DESC LIMIT 200
        """)).mappings().all()
    return jsonify([to_dict(r) for r in rows])

@app.post("/api/payments")
def create_payment():
    data = request.get_json(silent=True) or {}
    customer = str(data.get("customer_name", "")).strip()
    reference = str(data.get("reference", "")).strip()
    currency = str(data.get("currency", "NGN")).upper().strip()
    try:
        amount = float(data.get("amount", 0))
    except (TypeError, ValueError):
        return jsonify(error="amount must be a positive number"), 400
    if not customer or len(customer) > 120:
        return jsonify(error="customer_name is required (max 120 characters)"), 400
    if not reference or len(reference) > 80:
        return jsonify(error="reference is required (max 80 characters)"), 400
    if currency not in {"NGN", "USD", "GBP", "EUR"}:
        return jsonify(error="currency must be NGN, USD, GBP, or EUR"), 400
    if amount <= 0:
        return jsonify(error="amount must be positive"), 400
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO payments (customer_name, amount, currency, reference)
                VALUES (:customer, :amount, :currency, :reference)
                RETURNING id, customer_name, amount, currency, reference, status, created_at, updated_at
            """), {"customer": customer, "amount": amount, "currency": currency, "reference": reference})
            payment = to_dict(result.mappings().one())
    except SQLAlchemyError as exc:
        if "unique" in str(exc).lower():
            return jsonify(error="reference already exists"), 409
        app.logger.exception("Could not save payment")
        return jsonify(error="could not save payment"), 500
    return jsonify(payment), 201

@app.get("/api/payments/<int:payment_id>")
def get_payment(payment_id):
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT id, customer_name, amount, currency, reference, status, created_at, updated_at
            FROM payments WHERE id=:id
        """), {"id": payment_id}).mappings().first()
    if not row:
        return jsonify(error="payment not found"), 404
    return jsonify(to_dict(row))

@app.patch("/api/payments/<int:payment_id>/status")
def update_status(payment_id):
    data = request.get_json(silent=True) or {}
    status = str(data.get("status", "")).lower()
    if status not in {"pending", "completed", "failed"}:
        return jsonify(error="status must be pending, completed, or failed"), 400
    with engine.begin() as conn:
        result = conn.execute(text("""
            UPDATE payments SET status=:status, updated_at=NOW()
            WHERE id=:id
            RETURNING id, customer_name, amount, currency, reference, status, created_at, updated_at
        """), {"status": status, "id": payment_id})
        row = result.mappings().first()
    if not row:
        return jsonify(error="payment not found"), 404
    payment = to_dict(row)
    event = {
        "event_id": str(uuid.uuid4()), "type": "payment.status_changed",
        "payment_id": payment_id, "status": status,
        "occurred_at": datetime.now(timezone.utc).isoformat()
    }
    try:
        queue.lpush("paytrack:events", json.dumps(event))
    except Exception:
        app.logger.exception("Status saved but event could not be queued")
    return jsonify(payment), 200
