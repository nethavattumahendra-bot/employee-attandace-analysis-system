"""
Vercel Serverless Function entry point for AttendIQ Flask application.
"""

import sys
import os
import shutil

# Explicitly flag Vercel serverless environment
os.environ["VERCEL"] = "1"
os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib"
os.makedirs("/tmp/matplotlib", exist_ok=True)
os.makedirs("/tmp/reports", exist_ok=True)

# Ensure the root project directory is on sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Copy pre-generated reports to /tmp/reports if not present
try:
    bundled_reports = os.path.join(root_dir, "reports")
    if os.path.exists(bundled_reports):
        for fname in os.listdir(bundled_reports):
            src_f = os.path.join(bundled_reports, fname)
            dst_f = os.path.join("/tmp/reports", fname)
            if os.path.isfile(src_f) and not os.path.exists(dst_f):
                shutil.copy2(src_f, dst_f)
except Exception:
    pass

# Initialize database in serverless environment
from db import db
from seed_sample_data import SampleDataSeeder
from web_app import app

try:
    db.init_db()
    emp_count = db.execute_query("SELECT COUNT(*) as c FROM employees", fetch="one")
    if not emp_count or emp_count.get("c", 0) == 0:
        seeder = SampleDataSeeder(db_manager=db)
        seeder.seed_all()
except Exception as e:
    import logging
    logging.getLogger("vercel_entry").warning("Serverless initialization note: %s", e)

# Expose app for Vercel WSGI
application = app

if __name__ == "__main__":
    app.run()
