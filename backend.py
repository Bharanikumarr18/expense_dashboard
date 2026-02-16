import os
import json
import sqlite3
import tempfile
import datetime
from datetime import date, timedelta
import io
import shutil
from io import BytesIO
import pandas as pd
import smtplib
from email.message import EmailMessage

from sqlalchemy import (
    DateTime, create_engine, Column, Integer, String,
    Float, Date, ForeignKey, UniqueConstraint, func, text
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

pdfmetrics.registerFont(TTFont("DejaVu", "DejaVuSans.ttf"))


# ======================
# CONFIGURATION
# ======================
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///expense.db")

# Normalize sqlite path to avoid FileNotFoundError on missing directories.
if DATABASE_URL.startswith("sqlite"):
    db_path = None
    if DATABASE_URL.startswith("sqlite:///"):
        db_path = DATABASE_URL.replace("sqlite:///", "")
    elif DATABASE_URL.startswith("sqlite:////"):
        db_path = DATABASE_URL.replace("sqlite:////", "/")

    if db_path:
        if not os.path.isabs(db_path):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.abspath(os.path.join(base_dir, db_path))
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        DATABASE_URL = f"sqlite:///{db_path}"

engine_args = {}
if DATABASE_URL.startswith("sqlite"):
    engine_args["connect_args"] = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    **engine_args
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False
)


# ======================
# DB HELPERS
# ======================
def get_db():
    return SessionLocal()


# ======================
# MODELS
# ======================
Base = declarative_base()

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

class SubCategory(Base):
    __tablename__ = "subcategories"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"))
    __table_args__ = (UniqueConstraint("name", "category_id"),)

class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"), index=True)
    subcategory_id = Column(Integer, ForeignKey("subcategories.id"), index=True)
    date = Column(Date, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    travel = Column(Integer, default=0)
    trip_name = Column(String, nullable=True)
    trip_start = Column(Date, nullable=True)
    trip_end = Column(Date, nullable=True)

class IncomeCategory(Base):
    __tablename__ = "income_categories"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

class IncomeSubCategory(Base):
    __tablename__ = "income_subcategories"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("income_categories.id"))
    __table_args__ = (UniqueConstraint("name", "category_id"),)

class Income(Base):
    __tablename__ = "income"
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("income_categories.id"))
    subcategory_id = Column(Integer, ForeignKey("income_subcategories.id"))
    date = Column(Date, nullable=False)
    amount = Column(Float, nullable=False)

class AssetPrice(Base):
    __tablename__ = "asset_prices"
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(Float, nullable=False)

class MetalAsset(Base):
    __tablename__ = "metal_assets"
    id = Column(Integer, primary_key=True)
    metal = Column(String, nullable=False)
    weight_grams = Column(Float, nullable=False)
    buy_price = Column(Float, nullable=False)
    buy_date = Column(Date, nullable=False)

class LandAsset(Base):
    __tablename__ = "land_assets"
    id = Column(Integer, primary_key=True)
    location = Column(String, nullable=False)
    size_sqft = Column(Float, nullable=False)
    buy_price = Column(Float, nullable=False)
    buy_date = Column(Date, nullable=False)

class FixedDeposit(Base):
    __tablename__ = "fixed_deposits"
    id = Column(Integer, primary_key=True)
    bank = Column(String, nullable=False)
    principal = Column(Float, nullable=False)
    rate = Column(Float, nullable=False)
    deposit_date = Column(Date, nullable=False)
    maturity_date = Column(Date, nullable=False)
    maturity_amount = Column(Float, nullable=False)

class Appliance(Base):
    __tablename__ = "appliances"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    brand = Column(String, nullable=False)
    model = Column(String, nullable=False)
    purchase_date = Column(Date, nullable=False)
    warranty_years = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    image_path = Column(String, nullable=True)

class LICPolicy(Base):
    __tablename__ = "lic_policies"
    id = Column(Integer, primary_key=True)
    policy_name = Column(String, nullable=False)
    policy_number = Column(String, nullable=False)
    premium_amount = Column(Float, nullable=False)
    premium_frequency = Column(String, nullable=False)
    start_date = Column(Date, nullable=False)
    maturity_date = Column(Date, nullable=False)
    maturity_amount = Column(Float, nullable=False)

class InvestmentCategory(Base):
    __tablename__ = "investment_categories"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

class InvestmentEntry(Base):
    __tablename__ = "investment_entries"
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("investment_categories.id"), nullable=False)
    units = Column(Float, nullable=False)
    buy_price = Column(Float, nullable=False)
    buy_date = Column(Date, nullable=False)
    category = relationship("InvestmentCategory")

Base.metadata.create_all(bind=engine)


# ======================
# DB MIGRATIONS
# ======================
def migrate_expense_travel():
    try:
        with engine.connect() as conn:
            cols = conn.execute(text("PRAGMA table_info(expenses)")).fetchall()
            col_names = {c[1] for c in cols}
            if "travel" not in col_names:
                conn.execute(text("ALTER TABLE expenses ADD COLUMN travel INTEGER DEFAULT 0"))
            if "trip_name" not in col_names:
                conn.execute(text("ALTER TABLE expenses ADD COLUMN trip_name VARCHAR"))
            if "trip_start" not in col_names:
                conn.execute(text("ALTER TABLE expenses ADD COLUMN trip_start DATE"))
            if "trip_end" not in col_names:
                conn.execute(text("ALTER TABLE expenses ADD COLUMN trip_end DATE"))
    except Exception:
        pass

migrate_expense_travel()


# ======================
# BACKUP + STATE HELPERS
# ======================
GDRIVE_BACKUP_DIR = os.getenv(
    "GDRIVE_BACKUP_DIR",
    "/run/user/1000/gvfs/google-drive:host=gmail.com,user=bharanikumarr18/0AD1AeGLeY7L2Uk9PVA/1N9g1kGDrxiZpVq73wtodNM_ithFp5sl1"
)
BACKUP_FILENAME = "expense.db"
BACKUP_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".last_gdrive_backup.txt")
BACKUP_META_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".last_gdrive_backup_meta.json")
DB_MAINT_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".last_db_maintenance.txt")
SECRETS_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".streamlit", "secrets.toml")
AUTOMATION_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".automation_log.json")
WEEKLY_EMAIL_STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    ".last_weekly_email.txt"
)
MONTHLY_EMAIL_STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    ".last_monthly_email.txt"
)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_TO = os.getenv("SMTP_TO", "")


def read_state_value(path):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except Exception:
        return ""


def write_state_value(path, value):
    try:
        with open(path, "w") as f:
            f.write(value)
    except Exception:
        pass


def read_backup_meta():
    try:
        with open(BACKUP_META_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return None


def write_backup_meta(meta):
    try:
        with open(BACKUP_META_FILE, "w") as f:
            json.dump(meta, f)
    except Exception:
        pass


def update_automation_log(task, status, message):
    entry = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "message": message
    }
    try:
        if os.path.exists(AUTOMATION_LOG_FILE):
            with open(AUTOMATION_LOG_FILE, "r") as f:
                data = json.load(f)
        else:
            data = {}
        data[task] = entry
        with open(AUTOMATION_LOG_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def create_sqlite_backup(src_path):
    try:
        tmp = tempfile.NamedTemporaryFile(prefix="tracker_backup_", suffix=".db", delete=False)
        tmp_path = tmp.name
        tmp.close()
        with sqlite3.connect(src_path) as src, sqlite3.connect(tmp_path) as dst:
            src.backup(dst)
        return tmp_path, None
    except Exception as exc:
        try:
            if "tmp_path" in locals() and tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass
        return None, str(exc)


def resolve_gdrive_backup_dir():
    if os.path.isdir(GDRIVE_BACKUP_DIR):
        return GDRIVE_BACKUP_DIR, None

    gvfs_base = os.path.join("/run/user", str(os.getuid()), "gvfs")
    if not os.path.isdir(gvfs_base):
        return None, "Google Drive is not mounted. Open Files and click Google Drive."

    candidates = [
        os.path.join(gvfs_base, name)
        for name in os.listdir(gvfs_base)
        if name.startswith("google-drive:")
    ]

    if len(candidates) == 1 and os.path.isdir(candidates[0]):
        return candidates[0], None

    if len(candidates) == 0:
        return None, "Google Drive mount not found. Open Files and click Google Drive."

    return None, "Multiple Google Drive mounts found. Set GDRIVE_BACKUP_DIR explicitly."


def resolve_db_path():
    if not DATABASE_URL.startswith("sqlite"):
        return None, "Database URL is not SQLite; file backup is not supported."

    db_path = "expense.db"
    if DATABASE_URL.startswith("sqlite:///"):
        db_path = DATABASE_URL.replace("sqlite:///", "")
    elif DATABASE_URL.startswith("sqlite:////"):
        db_path = DATABASE_URL.replace("sqlite:////", "/")

    if not os.path.isabs(db_path):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.abspath(os.path.join(base_dir, db_path))

    return db_path, None


def backup_db_to_gdrive():
    backup_dir, err = resolve_gdrive_backup_dir()
    if err:
        return False, err

    db_path, err = resolve_db_path()
    if err:
        return False, err

    if not db_path or not os.path.exists(db_path):
        return False, "expense.db not found."

    tmp_path = None
    src_path = db_path
    tmp_path, tmp_err = create_sqlite_backup(db_path)
    if tmp_path:
        src_path = tmp_path

    dest = os.path.join(backup_dir, BACKUP_FILENAME)
    last_exc = None
    try:
        shutil.copy2(src_path, dest)
    except OSError:
        try:
            shutil.copyfile(src_path, dest)
        except Exception as exc:
            last_exc = exc

    if last_exc:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return False, f"Backup failed: {last_exc}"

    try:
        expected_size = os.path.getsize(src_path)
        dest_size = os.path.getsize(dest)
        if dest_size <= 0 or dest_size != expected_size:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            return False, "Backup verification failed: size mismatch."
    except Exception as exc:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return False, f"Backup verification failed: {exc}"

    if tmp_path and os.path.exists(tmp_path):
        os.unlink(tmp_path)

    ts = datetime.datetime.now().isoformat(timespec="seconds")
    write_state_value(BACKUP_STATE_FILE, ts)
    write_backup_meta({
        "timestamp": ts,
        "dest": dest,
        "size": dest_size,
        "source": db_path
    })

    return True, "Database backed up to Google Drive."


def verify_gdrive_backup():
    meta = read_backup_meta() or {}
    backup_dir, err = resolve_gdrive_backup_dir()
    if err:
        return False, err

    dest = meta.get("dest") or os.path.join(backup_dir, BACKUP_FILENAME)
    if not os.path.exists(dest):
        fallback_dest = os.path.join(backup_dir, BACKUP_FILENAME)
        if not os.path.exists(fallback_dest):
            return False, "Backup file not found in Google Drive."
        dest = fallback_dest

    try:
        dest_size = os.path.getsize(dest)
    except Exception as exc:
        return False, f"Could not read backup file: {exc}"

    if dest_size <= 0:
        return False, "Backup verification failed: empty file."

    expected_size = meta.get("size")
    if expected_size is None:
        return True, "Backup exists (no metadata to verify size)."

    if dest_size != expected_size:
        return False, "Backup verification failed: size mismatch."

    return True, "Backup verified."


def run_db_maintenance():
    db_path, err = resolve_db_path()
    if err:
        return False, err
    if not db_path or not os.path.exists(db_path):
        return False, "expense.db not found."
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("PRAGMA optimize;")
            conn.execute("VACUUM;")
            conn.execute("ANALYZE;")
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        write_state_value(DB_MAINT_STATE_FILE, ts)
        return True, "Database maintenance completed."
    except Exception as exc:
        return False, f"Maintenance failed: {exc}"


def format_state_value(value):
    if not value:
        return "Never"
    try:
        if "T" in value:
            dt = datetime.datetime.fromisoformat(value)
            return dt.strftime("%d %b %Y %H:%M")
        dt = datetime.datetime.strptime(value, "%Y-%m-%d")
        return dt.strftime("%d %b %Y")
    except Exception:
        return value


def format_bytes(num):
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024


def get_db_size():
    db_path, err = resolve_db_path()
    if err:
        return None, err
    if not db_path or not os.path.exists(db_path):
        return None, "expense.db not found."
    try:
        return os.path.getsize(db_path), None
    except Exception as exc:
        return None, str(exc)


# ======================
# DATA ACCESS HELPERS
# ======================
def load_expense_data(refresh_key):
    with SessionLocal() as db:
        q = (
            db.query(
                Expense.date,
                Expense.amount,
                Category.name.label("category"),
                SubCategory.name.label("subcategory")
            )
            .join(Category, Expense.category_id == Category.id)
            .join(SubCategory, Expense.subcategory_id == SubCategory.id)
        )
        return pd.DataFrame(
            q.all(),
            columns=["date", "amount", "category", "subcategory"]
        )


def load_income_data(refresh_key):
    with SessionLocal() as db:
        q = (
            db.query(
                Income.id,
                Income.date,
                Income.amount,
                IncomeCategory.name.label("category"),
                IncomeSubCategory.name.label("subcategory")
            )
            .join(IncomeCategory, Income.category_id == IncomeCategory.id)
            .join(IncomeSubCategory, Income.subcategory_id == IncomeSubCategory.id)
            .order_by(Income.date.desc(), Income.id.desc())
        )
        return pd.DataFrame(
            q.all(),
            columns=["id", "date", "amount", "category", "subcategory"]
        )


def load_events_data(refresh_key):
    with SessionLocal() as db:
        q = (
            db.query(
                Expense.date,
                Category.name.label("category"),
                SubCategory.name.label("subcategory"),
                Expense.amount,
                Expense.trip_name,
                Expense.trip_start,
                Expense.trip_end
            )
            .join(Category, Expense.category_id == Category.id)
            .join(SubCategory, Expense.subcategory_id == SubCategory.id)
            .filter(Expense.travel == 1)
            .order_by(Expense.date.desc(), Expense.id.desc())
        )
        return pd.DataFrame(
            q.all(),
            columns=["date", "category", "subcategory", "amount", "trip_name", "trip_start", "trip_end"]
        )


def load_event_list(refresh_key):
    with SessionLocal() as db:
        return (
            db.query(Expense.trip_name, Expense.trip_start, Expense.trip_end)
            .filter(Expense.travel == 1)
            .filter(Expense.trip_name.isnot(None))
            .distinct()
            .order_by(Expense.trip_start.desc(), Expense.trip_end.desc())
            .all()
        )


# ======================
# BUSINESS RULES
# ======================
def add_months(start_date, months):
    total = (start_date.year * 12 + (start_date.month - 1)) + months
    year = total // 12
    month = (total % 12) + 1
    return date(year, month, 1)


def get_month_options(months_back=24):
    with SessionLocal() as db:
        rows = db.query(Expense.date).all()
    if not rows:
        return []
    month_counts = {}
    for (d,) in rows:
        if not d:
            continue
        month_start = date(d.year, d.month, 1)
        month_counts[month_start] = month_counts.get(month_start, 0) + 1
    options = [
        (month.strftime("%b %Y"), month)
        for month in sorted(month_counts.keys(), reverse=True)
        if month_counts.get(month, 0) > 0
    ]
    return options


def filter_expenses_for_dashboard(
    df,
    start_date,
    end_date,
    categories,
    subcategories,
    min_amount,
    max_amount
):
    if df.empty:
        return df

    out = df.copy()
    out["date"] = pd.to_datetime(out["date"])

    out = out[out["date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))]

    if categories:
        out = out[out["category"].isin(categories)]

    if subcategories:
        out = out[out["subcategory"].isin(subcategories)]

    out = out[out["amount"].between(min_amount, max_amount)]

    return out


def build_monthly_snapshots(df):
    if df.empty:
        return []

    d = df.copy()
    d["date"] = pd.to_datetime(d["date"])
    d["month"] = d["date"].dt.to_period("M")

    results = []
    for m, g in d.groupby("month"):
        total = float(g["amount"].sum())
        days = int(g["date"].dt.date.nunique())
        avg_day = total / days if days else 0.0
        tx = int(len(g))
        peak_row = g.groupby(g["date"].dt.date)["amount"].sum().sort_values(ascending=False)
        peak_day = peak_row.index[0] if not peak_row.empty else None
        peak_amt = float(peak_row.iloc[0]) if not peak_row.empty else 0.0

        top_cat = (
            g.groupby("category")["amount"]
            .sum()
            .sort_values(ascending=False)
        )
        top_sub = (
            g.groupby("subcategory")["amount"]
            .sum()
            .sort_values(ascending=False)
        )

        results.append({
            "period": m,
            "label": m.strftime("%b %Y"),
            "total": total,
            "avg_day": avg_day,
            "tx": tx,
            "peak_day": peak_day,
            "peak_amt": peak_amt,
            "top_cat": top_cat.index[0] if not top_cat.empty else "—",
            "top_sub": top_sub.index[0] if not top_sub.empty else "—",
        })

    results.sort(key=lambda x: x["period"], reverse=True)
    return results


# ======================
# FINANCIAL FORMULAS
# ======================
def get_price(db, key, default=0.0):
    row = db.query(AssetPrice).filter(AssetPrice.key == key).first()
    return row.value if row else default


def set_price(db, key, value):
    row = db.query(AssetPrice).filter(AssetPrice.key == key).first()
    if row:
        row.value = value
    else:
        db.add(AssetPrice(key=key, value=value))
    db.commit()


def fd_current_value(principal, rate, deposit_date):
    days = (date.today() - deposit_date).days
    years = max(days, 0) / 365
    return principal * ((1 + rate / 100) ** years)


def fd_maturity_value(principal, rate, tenure_months):
    years = tenure_months / 12
    return principal * ((1 + rate / 100) ** years)


# ======================
# PDF / REPORT HELPERS
# ======================
def black_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(colors.black)
    canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], stroke=0, fill=1)
    canvas.restoreState()


def generate_weekly_expense_pdf(start_date, end_date):
    with SessionLocal() as db:
        rows = (
            db.query(
                Expense.date,
                Category.name.label("category"),
                SubCategory.name.label("subcategory"),
                Expense.amount
            )
            .join(Category, Expense.category_id == Category.id)
            .join(SubCategory, Expense.subcategory_id == SubCategory.id)
            .filter(Expense.date.between(start_date, end_date))
            .order_by(Expense.date.desc(), Expense.id.desc())
            .all()
        )

    df = pd.DataFrame(rows, columns=["date", "category", "subcategory", "amount"])
    total = float(df["amount"].sum()) if not df.empty else 0.0
    count = int(len(df))
    avg = (total / count) if count else 0.0

    cat_summary = (
        df.groupby("category")["amount"].sum()
        .sort_values(ascending=False)
    ) if not df.empty else pd.Series(dtype=float)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="TitleBig",
        fontName="DejaVu",
        fontSize=18,
        leading=22,
        spaceAfter=10
    ))
    styles.add(ParagraphStyle(
        name="SectionHeader",
        fontName="DejaVu",
        fontSize=12,
        leading=16,
        spaceBefore=10,
        spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        name="BodySmall",
        fontName="DejaVu",
        fontSize=9,
        leading=11
    ))
    table_header = ParagraphStyle(
        name="TableHeader",
        fontName="DejaVu",
        fontSize=9,
        leading=11
    )
    table_body = ParagraphStyle(
        name="TableBody",
        fontName="DejaVu",
        fontSize=8,
        leading=10,
        wordWrap="CJK"
    )

    story = []
    story.append(Paragraph("Weekly Expense Report", styles["TitleBig"]))
    story.append(Paragraph(
        f"Period: {start_date.strftime('%d %b %Y')} → {end_date.strftime('%d %b %Y')}",
        styles["BodySmall"]
    ))
    story.append(Paragraph(
        f"Generated: {date.today().strftime('%d %b %Y')}",
        styles["BodySmall"]
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Summary", styles["SectionHeader"]))
    summary_data = [
        ["Total Expense (₹)", f"{total:,.2f}"],
        ["Transactions", f"{count}"],
        ["Average per Transaction (₹)", f"{avg:,.2f}"],
    ]
    summary_table = Table(summary_data, colWidths=[300, 110], hAlign="LEFT")
    summary_table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "DejaVu"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Category Totals", styles["SectionHeader"]))
    if cat_summary.empty:
        story.append(Paragraph("No expenses recorded in this period.", styles["BodySmall"]))
    else:
        cat_rows = [[
            Paragraph("Category", table_header),
            Paragraph("Total (₹)", table_header)
        ]]
        for cat, amt in cat_summary.items():
            cat_rows.append([
                Paragraph(str(cat), table_body),
                Paragraph(f"{amt:,.2f}", table_body)
            ])
        cat_table = Table(cat_rows, colWidths=[320, 110], hAlign="LEFT", repeatRows=1)
        cat_table.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), "DejaVu"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(cat_table)
    story.append(Spacer(1, 10))

    doc.build(story)
    return buffer.getvalue()


def generate_monthly_expense_pdf(start_date, end_date):
    with SessionLocal() as db:
        rows = (
            db.query(
                Expense.date,
                Category.name.label("category"),
                SubCategory.name.label("subcategory"),
                Expense.amount
            )
            .join(Category, Expense.category_id == Category.id)
            .join(SubCategory, Expense.subcategory_id == SubCategory.id)
            .filter(Expense.date.between(start_date, end_date))
            .order_by(Expense.date.desc(), Expense.id.desc())
            .all()
        )

    df = pd.DataFrame(rows, columns=["date", "category", "subcategory", "amount"])
    total = float(df["amount"].sum()) if not df.empty else 0.0
    count = int(len(df))
    avg = (total / count) if count else 0.0

    cat_summary = (
        df.groupby("category")["amount"].sum()
        .sort_values(ascending=False)
    ) if not df.empty else pd.Series(dtype=float)

    subcat_summary = (
        df.groupby("subcategory")["amount"].sum()
        .sort_values(ascending=False)
    ) if not df.empty else pd.Series(dtype=float)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="TitleBig",
        fontName="DejaVu",
        fontSize=18,
        leading=22,
        spaceAfter=10
    ))
    styles.add(ParagraphStyle(
        name="SectionHeader",
        fontName="DejaVu",
        fontSize=12,
        leading=16,
        spaceBefore=10,
        spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        name="BodySmall",
        fontName="DejaVu",
        fontSize=9,
        leading=11
    ))
    table_header = ParagraphStyle(
        name="TableHeader",
        fontName="DejaVu",
        fontSize=9,
        leading=11
    )
    table_body = ParagraphStyle(
        name="TableBody",
        fontName="DejaVu",
        fontSize=8,
        leading=10,
        wordWrap="CJK"
    )

    story = []
    story.append(Paragraph("Monthly Expense Report", styles["TitleBig"]))
    story.append(Paragraph(
        f"Period: {start_date.strftime('%d %b %Y')} → {end_date.strftime('%d %b %Y')}",
        styles["BodySmall"]
    ))
    story.append(Paragraph(
        f"Generated: {date.today().strftime('%d %b %Y')}",
        styles["BodySmall"]
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Summary", styles["SectionHeader"]))
    summary_data = [
        ["Total Expense (₹)", f"{total:,.2f}"],
        ["Transactions", f"{count}"],
        ["Average per Transaction (₹)", f"{avg:,.2f}"],
    ]
    summary_table = Table(summary_data, colWidths=[300, 110], hAlign="LEFT")
    summary_table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "DejaVu"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Category Totals", styles["SectionHeader"]))
    if cat_summary.empty:
        story.append(Paragraph("No expenses recorded in this period.", styles["BodySmall"]))
    else:
        cat_rows = [[
            Paragraph("Category", table_header),
            Paragraph("Total (₹)", table_header)
        ]]
        for cat, amt in cat_summary.items():
            cat_rows.append([
                Paragraph(str(cat), table_body),
                Paragraph(f"{amt:,.2f}", table_body)
            ])
        cat_table = Table(cat_rows, colWidths=[320, 110], hAlign="LEFT", repeatRows=1)
        cat_table.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), "DejaVu"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(cat_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Subcategory Totals", styles["SectionHeader"]))
    if subcat_summary.empty:
        story.append(Paragraph("No subcategory data for this period.", styles["BodySmall"]))
    else:
        subcat_rows = [[
            Paragraph("Subcategory", table_header),
            Paragraph("Total (₹)", table_header)
        ]]
        for subcat, amt in subcat_summary.items():
            subcat_rows.append([
                Paragraph(str(subcat), table_body),
                Paragraph(f"{amt:,.2f}", table_body)
            ])
        subcat_table = Table(
            subcat_rows,
            colWidths=[320, 110],
            hAlign="LEFT",
            repeatRows=1
        )
        subcat_table.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), "DejaVu"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(subcat_table)
    story.append(Spacer(1, 12))

    doc.build(story)
    return buffer.getvalue()


# ======================
# EMAIL LOGIC
# ======================
def send_weekly_email_report_core():
    today = date.today()
    if today.weekday() != 6:
        return False, "Not Sunday"

    last = read_state_value(WEEKLY_EMAIL_STATE_FILE)
    if last == today.isoformat():
        return False, "Already sent today"

    if not SMTP_USER or not SMTP_PASS or not SMTP_TO:
        return False, "SMTP credentials not configured"

    end_date = today - timedelta(days=1)
    start_date = end_date - timedelta(days=6)
    pdf_bytes = generate_weekly_expense_pdf(start_date, end_date)

    msg = EmailMessage()
    msg["Subject"] = f"Weekly Expense Report ({start_date} to {end_date})"
    msg["From"] = SMTP_USER
    msg["To"] = SMTP_TO
    msg.set_content(
        "Hello,\n\n"
        "Attached is your weekly expense report.\n\n"
        "Regards,\n"
        "Expense Tracker"
    )
    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=f"expense_report_{start_date}_{end_date}.pdf"
    )

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        write_state_value(WEEKLY_EMAIL_STATE_FILE, today.isoformat())
        return True, "Weekly email report sent."
    except Exception as e:
        return False, f"Weekly email failed: {e}"


def send_test_email_report_core():
    if not SMTP_USER or not SMTP_PASS or not SMTP_TO:
        return False, "SMTP credentials not configured"

    end_date = date.today()
    start_date = end_date - timedelta(days=6)
    pdf_bytes = generate_weekly_expense_pdf(start_date, end_date)

    msg = EmailMessage()
    msg["Subject"] = f"Test Expense Report ({start_date} to {end_date})"
    msg["From"] = SMTP_USER
    msg["To"] = SMTP_TO
    msg.set_content(
        "Hello,\n\n"
        "This is a test email from your Expense Tracker.\n"
        "Attached is a sample report for the last 7 days.\n\n"
        "Regards,\n"
        "Expense Tracker"
    )
    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=f"expense_report_test_{start_date}_{end_date}.pdf"
    )

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True, "Test email sent successfully."
    except Exception as e:
        return False, f"Test email failed: {e}"


def send_monthly_email_report_core():
    today = date.today()
    if today.day != 3:
        return False, "Not scheduled day"

    last = read_state_value(MONTHLY_EMAIL_STATE_FILE)
    if last == today.isoformat():
        return False, "Already sent today"

    if not SMTP_USER or not SMTP_PASS or not SMTP_TO:
        return False, "SMTP credentials not configured"

    current_month_start = date(today.year, today.month, 1)
    end_date = current_month_start - timedelta(days=1)
    start_date = date(end_date.year, end_date.month, 1)
    pdf_bytes = generate_monthly_expense_pdf(start_date, end_date)

    msg = EmailMessage()
    msg["Subject"] = f"Monthly Expense Report ({start_date} to {end_date})"
    msg["From"] = SMTP_USER
    msg["To"] = SMTP_TO
    msg.set_content(
        "Hello,\n\n"
        "Attached is your monthly expense report.\n\n"
        "Regards,\n"
        "Expense Tracker"
    )
    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=f"expense_report_{start_date}_{end_date}.pdf"
    )

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        write_state_value(MONTHLY_EMAIL_STATE_FILE, today.isoformat())
        return True, "Monthly email report sent."
    except Exception as e:
        return False, f"Monthly email failed: {e}"


def send_test_monthly_email_report_core():
    if not SMTP_USER or not SMTP_PASS or not SMTP_TO:
        return False, "SMTP credentials not configured"

    today = date.today()
    current_month_start = date(today.year, today.month, 1)
    end_date = current_month_start - timedelta(days=1)
    start_date = date(end_date.year, end_date.month, 1)

    pdf_bytes = generate_monthly_expense_pdf(start_date, end_date)

    msg = EmailMessage()
    msg["Subject"] = f"Test Monthly Report ({start_date} to {end_date})"
    msg["From"] = SMTP_USER
    msg["To"] = SMTP_TO
    msg.set_content(
        "Hello,\n\n"
        "This is a test monthly report from your Expense Tracker.\n\n"
        "Regards,\n"
        "Expense Tracker"
    )
    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=f"expense_report_test_{start_date}_{end_date}.pdf"
    )

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True, "Monthly test email sent successfully."
    except Exception as e:
        return False, f"Monthly test email failed: {e}"


def send_custom_monthly_report_core(month_start, target_email):
    if not SMTP_USER or not SMTP_PASS:
        return False, "SMTP credentials not configured"
    if not target_email or "@" not in target_email:
        return False, "Please enter a valid email address."

    end_date = add_months(month_start, 1) - timedelta(days=1)
    pdf_bytes = generate_monthly_expense_pdf(month_start, end_date)

    msg = EmailMessage()
    msg["Subject"] = f"Monthly Expense Report ({month_start} to {end_date})"
    msg["From"] = SMTP_USER
    msg["To"] = target_email
    msg.set_content(
        "Hello,\n\n"
        f"Attached is the monthly expense report for {month_start.strftime('%b %Y')}.\n"
        "It includes category totals and subcategory totals.\n\n"
        "Regards,\n"
        "Expense Tracker"
    )
    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=f"expense_report_{month_start}_{end_date}.pdf"
    )

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True, "Monthly report sent successfully."
    except Exception as e:
        return False, f"Monthly report failed: {e}"


def export_pdf(df, footer_text=""):
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20,
        leftMargin=20,
        topMargin=30,
        bottomMargin=30
    )
    data = [df.columns.tolist()] + df.values.tolist()
    if "Category" in df.columns and "TOTAL" in df["Category"].values:
        total_amount = None
    else:
        if "Amount" in df.columns:
            total_amount = df["Amount"].sum()
        elif "Total Amount" in df.columns:
            total_amount = df["Total Amount"].sum()
        else:
            total_amount = None

    if total_amount is not None:
        row = [""] * (len(df.columns) - 2) + ["TOTAL", f"{total_amount:.2f}"]
        data.append(row)

    table = Table(data, repeatRows=1, hAlign="CENTER")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.black),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONT", (0, 0), (-1, 0), "DejaVu"),
        ("BACKGROUND", (0, 1), (-1, -1), colors.black),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    styles = getSampleStyleSheet()

    title_style = styles["Title"]
    title_style.textColor = colors.white
    title_style.alignment = 1

    meta_style = styles["Normal"]
    meta_style.textColor = colors.white
    meta_style.leading = 14

    def draw_footer(canvas, doc):
        canvas.saveState()
        footer_style = ParagraphStyle(
            name="FooterStyle",
            fontSize=8,
            textColor=colors.grey,
            leading=10
        )
        footer_para = Paragraph(footer_text, footer_style)
        page_width, _ = doc.pagesize
        footer_para.wrap(page_width - 40, 50)
        footer_para.drawOn(canvas, 20, 20)
        canvas.restoreState()

    def header_block(text):
        return Table(
            [[Paragraph(text.replace(" | ", "<br/>"), meta_style)]],
            colWidths=[doc.width],
            style=[
                ("BACKGROUND", (0, 0), (-1, -1), colors.black),
                ("LEFTPADDING", (0, 0), (-1, -1), 16),
                ("RIGHTPADDING", (0, 0), (-1, -1), 16),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ]
        )

    story = []
    story.append(Paragraph("EXPENSES REPORT", title_style))
    story.append(header_block(footer_text))
    story.append(Spacer(1, 16))

    story.append(Table(
        [[""]],
        colWidths=[doc.width],
        style=[
            ("LINEBELOW", (0, 0), (-1, -1), 1, colors.white),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]
    ))

    story.append(table)

    doc.build(
        story,
        onFirstPage=lambda c, d: (black_page(c, d), draw_footer(c, d)),
        onLaterPages=lambda c, d: (black_page(c, d), draw_footer(c, d))
    )

    buffer.seek(0)
    return buffer


def generate_event_pdf_black(event_name, start_label, end_label, df):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=28,
        leftMargin=28,
        topMargin=28,
        bottomMargin=28
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name="EventTitleBlack",
        parent=styles["Title"],
        fontName="DejaVu",
        fontSize=18,
        textColor=colors.white,
        spaceAfter=10
    )
    meta_style = ParagraphStyle(
        name="EventMetaBlack",
        parent=styles["Normal"],
        fontName="DejaVu",
        fontSize=10,
        textColor=colors.white,
        leading=14
    )

    total = float(df["amount"].sum()) if not df.empty else 0.0

    story = []
    story.append(Paragraph(f"Event Report — {event_name}", title_style))
    story.append(Paragraph(f"Date range: {start_label} → {end_label}", meta_style))
    story.append(Paragraph(f"Total spend: ₹ {total:,.2f}", meta_style))
    story.append(Spacer(1, 12))

    table_rows = [["Date", "Category", "Subcategory", "Amount (₹)"]]
    for _, row in df.iterrows():
        table_rows.append([
            row["date"],
            row["category"],
            row["subcategory"],
            f"{float(row['amount']):,.2f}"
        ])

    col_widths = [
        doc.width * 0.22,
        doc.width * 0.28,
        doc.width * 0.32,
        doc.width * 0.18
    ]
    table = Table(table_rows, colWidths=col_widths, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "DejaVu"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.black),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, -1), colors.black),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ALIGN", (0, 0), (-2, -1), "LEFT"),
        ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    story.append(Spacer(1, 10))

    total_table = Table(
        [["TOTAL", f"₹ {total:,.2f}"]],
        colWidths=[doc.width - col_widths[-1], col_widths[-1]],
        hAlign="LEFT"
    )
    total_table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "DejaVu"),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("LINEABOVE", (0, 0), (-1, 0), 0.6, colors.white),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(total_table)

    def black_bg(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.black)
        canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1)
        canvas.restoreState()

    doc.build(story, onFirstPage=black_bg, onLaterPages=black_bg)
    buffer.seek(0)
    return buffer.getvalue()
