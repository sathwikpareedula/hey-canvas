"""One-off diagnostic: Braitenberg document status (local only)."""
from pathlib import Path

from sqlalchemy import create_engine, text

root = Path(__file__).resolve().parents[2]
for rel in ("backend/data/uta_academic_copilot.db", "data/uta_academic_copilot.db"):
    db = root / rel
    if db.exists():
        break
else:
    raise SystemExit("database not found")

engine = create_engine(f"sqlite:///{db}")
with engine.connect() as conn:
    rows = conn.execute(
        text(
            """
            SELECT cf.canvas_file_id, cf.display_name, ad.status,
                   (SELECT COUNT(*) FROM document_units du WHERE du.document_id = ad.id) AS units
            FROM academic_documents ad
            JOIN canvas_files cf ON cf.canvas_file_id = ad.canvas_file_id
            WHERE cf.display_name LIKE '%Braitenberg%' OR cf.filename LIKE '%Braitenberg%'
            """
        )
    ).fetchall()
    print("braitenberg:", rows)
    rows2 = conn.execute(
        text(
            """
            SELECT ad.status, COUNT(*)
            FROM academic_documents ad
            JOIN canvas_files cf ON cf.canvas_file_id = ad.canvas_file_id
            WHERE cf.canvas_course_id = '278791'
            GROUP BY ad.status
            """
        )
    ).fetchall()
    print("course 278791:", rows2)
