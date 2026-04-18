"""Flask blueprint for the order-placement flow.

Endpoints:
- ``POST /orders/save_message`` — persist a chat/cube message.
- ``POST /orders/generate``     — extract + validate + write PDF.
- ``GET  /orders/pdf/<id>``     — serve the generated PDF inline.
- ``GET  /orders/export/<sid>`` — raw conversation JSON (debug).
- ``GET  /orders/draft/<id>``   — inspect the stored draft (debug).
"""

from __future__ import annotations

import os

from flask import Blueprint, abort, jsonify, request, send_file

from .extractor import OrderExtractionError, build_draft
from .pdf_generator import build_pdf
from .storage import (
    add_message,
    create_order,
    ensure_schema,
    export_session_json,
    get_messages,
    get_order,
    next_po_number,
)

orders_bp = Blueprint("orders", __name__, url_prefix="/orders")

PDF_DIR = os.path.join(os.path.dirname(__file__), "pdfs")


def _ensure_pdf_dir() -> None:
    os.makedirs(PDF_DIR, exist_ok=True)


# Make sure the schema exists when the blueprint is imported.
ensure_schema()
_ensure_pdf_dir()


@orders_bp.route("/save_message", methods=["POST"])
def save_message():
    data = request.get_json(force=True, silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    role = (data.get("role") or "").strip()
    content = data.get("content") or ""
    source = (data.get("source") or "chat").strip() or "chat"
    metadata = data.get("metadata")
    if not session_id or role not in {"user", "assistant", "system"} or not content:
        return (
            jsonify(
                {
                    "error": "session_id, role∈{user,assistant,system}, and content are required",
                }
            ),
            400,
        )
    message_id = add_message(
        session_id, role=role, content=content, source=source, metadata=metadata
    )
    return jsonify({"ok": True, "message_id": message_id})


@orders_bp.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True, silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    api_key = (
        data.get("api_key")
        or os.environ.get("OPENAI_API_KEY", "")
        or ""
    ).strip()
    if not session_id:
        return jsonify({"error": "session_id required"}), 400
    if not api_key:
        return (
            jsonify(
                {
                    "error": (
                        "No OpenAI API key available. Set OPENAI_API_KEY or "
                        "send api_key in the request body."
                    )
                }
            ),
            400,
        )

    messages = get_messages(session_id)
    if not messages:
        return jsonify({"error": "no messages saved for this session yet"}), 400

    try:
        draft = build_draft(messages, api_key=api_key)
    except OrderExtractionError as exc:
        return jsonify({"error": str(exc)}), 502

    po_number = next_po_number()
    safe_po = po_number.replace("/", "-")
    pdf_path = os.path.join(PDF_DIR, f"{safe_po}.pdf")
    build_pdf(pdf_path, po_number=po_number, draft=draft)

    order_id = create_order(
        session_id=session_id,
        po_number=po_number,
        draft=draft,
        pdf_path=pdf_path,
        grand_total=draft.get("grand_total"),
    )

    return jsonify(
        {
            "ok": True,
            "order_id": order_id,
            "po_number": po_number,
            "pdf_url": f"/orders/pdf/{order_id}",
            "draft": draft,
        }
    )


@orders_bp.route("/pdf/<int:order_id>")
def serve_pdf(order_id: int):
    order = get_order(order_id)
    if not order or not order.get("pdf_path"):
        abort(404)
    path = order["pdf_path"]
    if not os.path.isfile(path):
        abort(404)
    return send_file(
        path,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=f"{order['po_number']}.pdf",
    )


@orders_bp.route("/draft/<int:order_id>")
def serve_draft(order_id: int):
    order = get_order(order_id)
    if not order:
        abort(404)
    return jsonify(order)


@orders_bp.route("/export/<session_id>")
def export_session(session_id: str):
    return jsonify(export_session_json(session_id))
