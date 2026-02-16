import streamlit as st
import pandas as pd
import datetime
from datetime import date, timedelta
from sqlalchemy.orm import relationship
from sqlalchemy.orm import joinedload
from sqlalchemy import text
from sqlalchemy import (
    DateTime, create_engine, Column, Integer, String,
    Float, Date, ForeignKey, UniqueConstraint, func
)
from sqlalchemy.orm import declarative_base, sessionmaker
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
import plotly.express as px
import plotly.graph_objects as go
import io
from io import BytesIO
import json
import re
from difflib import SequenceMatcher
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import requests
import matplotlib.pyplot as plt
from dateutil.relativedelta import relativedelta
import calendar
import os
import platform
import time
import subprocess
import shutil
import smtplib
from email.message import EmailMessage
import sqlite3
import tempfile
import zipfile
import pytesseract
from PIL import Image
import cv2
import numpy as np

def get_config(key, default=None):
    value = os.getenv(key)
    if value is None or value == "":
        return st.secrets.get(key, default)
    return value

pdfmetrics.registerFont(TTFont("DejaVu", "DejaVuSans.ttf"))

# ==============
# SESSION STATE
# ==============
def init_session_state():
    defaults = {
        "open_asset_inputs": False,
        "show_weekly_trend": True,
        "show_inv_delete_manager": False,
        "data_refresh": 0
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

init_session_state()

# ==============
# FLASH MESSAGE
# ==============
# Handle flash.
def flash(message, kind="success"):
    st.session_state.setdefault("flash_msgs", [])
    st.session_state.flash_msgs.append({
        "msg": message,
        "type": kind
    })

# ==============
# DB SETUP
# ==============
st.set_page_config(
    page_title="Tracker",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==============
# DATABASE MODELS
# ==============
DATABASE_URL = get_config(
    "DATABASE_URL",
    "sqlite:///expense.db"
)

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


# Get DB.
def get_db():
    return SessionLocal()

# ==============
# MODELS
# ==============
Base = declarative_base()                                # base model
class Category(Base):                                    # expense categories
    __tablename__ = "categories"                         # categories table
    id = Column(Integer, primary_key=True)               # unique category id
    name = Column(String, unique=True, nullable=False)   # category name
# ==============
# SUBCATEGORY
# ==============
class SubCategory(Base):                                          # subcategories          
    __tablename__ = "subcategories"                               # subcategory table
    id = Column(Integer, primary_key=True)                        # unique subcategory id
    name = Column(String, nullable=False)                         # subcategory name
    category_id = Column(Integer, ForeignKey("categories.id"))    # category id
    __table_args__ = (UniqueConstraint("name", "category_id"),)   # unique constraint on (name, category_id)
# ==============
# EXPENSE
# ==============
class Expense(Base):                                                             # expense entries
    __tablename__ = "expenses"                                                   # expense table
    id = Column(Integer, primary_key=True)                                       # unique expense id
    category_id = Column(Integer, ForeignKey("categories.id"), index=True)       # category id
    subcategory_id = Column(Integer, ForeignKey("subcategories.id"), index=True) # subcategory id
    date = Column(Date, nullable=False, index=True)                              # date of expense        
    amount = Column(Float, nullable=False)                                       # expense amount
    travel = Column(Integer, default=0)                                          # 1 = travel expense
    trip_name = Column(String, nullable=True)                                    # travel trip name
    trip_start = Column(Date, nullable=True)                                     # trip start date
    trip_end = Column(Date, nullable=True)                                       # trip end date
# ==============
# INCOME MODELS
# ==============
class IncomeCategory(Base):                                            # income categories
    __tablename__ = "income_categories"                                # income category table
    id = Column(Integer, primary_key=True)                             # unique category id
    name = Column(String, unique=True, nullable=False)                 # income category name
# ==================
# INCOME SUBCATEGORY
# ==================
class IncomeSubCategory(Base):                                         # income subcategories
    __tablename__ = "income_subcategories"                             # income subcategory table
    id = Column(Integer, primary_key=True)                             # unique subcategory id
    name = Column(String, nullable=False)                              # subcategory name
    category_id = Column(Integer, ForeignKey("income_categories.id"))  # income category id
    __table_args__ = (UniqueConstraint("name", "category_id"),)        # unique constraint on (name, category_id)
# =======
# INCOME
# =======
class Income(Base):                                 # income entries
    __tablename__ = "income"                        # income table
    id = Column(Integer, primary_key=True)          # unique income id
    category_id = Column(Integer, ForeignKey("income_categories.id"), index=True)        # income category id   
    subcategory_id = Column(Integer, ForeignKey("income_subcategories.id"), index=True)  # income subcategory id
    date = Column(Date, nullable=False, index=True) # date of income
    amount = Column(Float, nullable=False)          # income amount

# ============
# ASSET MODELS
# ============
#----METAL ASSETS----
class MetalAsset(Base):                          # metal assets
    __tablename__ = "metal_assets"                # unique metal asset id
    id = Column(Integer, primary_key=True)        # optional 
    metal_type = Column(String, nullable=False)   # Gold / Silver
    weight_grams = Column(Float, nullable=False)  # weight in grams
    entry_date = Column(Date, nullable=False)     # date of purchase
    created_at = Column(DateTime, default=datetime.datetime.utcnow) # created timestamp
#----LAND ASSETS----
class LandAsset(Base):
    __tablename__ = "land_assets"
    id = Column(Integer, primary_key=True)           # unique land asset id 
    asset_id = Column(Integer, nullable=True)        # optional   
    location = Column(String, nullable=False)        # "Area, City"
    area_unit = Column(String, nullable=False)       # always "sqft"
    area_size = Column(Float, nullable=False)        # sqft value
    price_per_unit = Column(Float, nullable=True)    # optional
# ----ASSET PRICES----
class AssetPrice(Base):
    __tablename__ = "asset_prices"           # asset prices
    key = Column(String, primary_key=True)   # e.g. gold_price, land:Chennai
    value = Column(Float, nullable=False)    # price value
# ----FIXED DEPOSITS----
class FixedDeposit(Base):                             # fixed deposit assets  
    __tablename__ = "fixed_deposits"                  # unique FD table
    id = Column(Integer, primary_key=True)            # unique FD id
    name = Column(String, nullable=False)             # e.g. Bank Name / FD Scheme
    principal = Column(Float, nullable=False)         # amount deposited
    rate = Column(Float, nullable=False)              # annual %
    tenure_months = Column(Integer, nullable=False)   # tenure in months      
    tenure_days = Column(Integer, nullable=True)      # tenure in days
    deposit_date = Column(Date, nullable=False)       # date of deposit
    maturity_date = Column(Date, nullable=False)      # date of maturity
    status = Column(String, default="active")         # active | matured
    created_at = Column(DateTime, default=datetime.datetime.utcnow) # created timestamp
# ----APPLIANCES----
class Appliance(Base):                                   # appliance assets      
    __tablename__ = "appliances"                         # unique appliance id
    id = Column(Integer, primary_key=True)               # optional
    name = Column(String, nullable=False)                # e.g. Refrigerator        
    price = Column(Float, nullable=False)                # purchase price
    purchase_date = Column(Date, nullable=False)         # date of purchase
    warranty_expiry = Column(Date, nullable=True)        # warranty expiry date
    depreciation_years = Column(Integer, nullable=True)  # useful life in years
# ----APPLIANCE IMAGES----
class ApplianceImage(Base):                                   
    __tablename__ = "appliance_images"                      
    id = Column(Integer, primary_key=True)                  
    appliance_id = Column(Integer, ForeignKey("appliances.id", ondelete="CASCADE")) 
    image_path = Column(String, nullable=False)              
    appliance = relationship("Appliance", backref="images")  
# ======================
# LIC POLICIES (SIMPLE)
# ======================
class LICPolicy(Base):
    __tablename__ = "lic_policies"

    id = Column(Integer, primary_key=True)
    policy_name = Column(String, nullable=False)
    premium_amount = Column(Float, nullable=False)
    premium_frequency = Column(String, nullable=False)
    last_premium_date = Column(Date, nullable=True)
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

# ==============
# DB MIGRATIONS
# ==============
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


def migrate_fixed_deposit_tenure_days():
    try:
        with engine.begin() as conn:
            cols = conn.execute(text("PRAGMA table_info(fixed_deposits)")).fetchall()
            col_names = {c[1] for c in cols}
            if "tenure_days" not in col_names:
                conn.execute(text("ALTER TABLE fixed_deposits ADD COLUMN tenure_days INTEGER"))
    except Exception:
        pass


migrate_fixed_deposit_tenure_days()

# ==============
# WEEKLY BACKUP (SUNDAYS)
# ==============
GDRIVE_BACKUP_DIR = get_config(
    "GDRIVE_BACKUP_DIR",
    "/run/user/1000/gvfs/google-drive:host=gmail.com,user=bharanikumarr18/0AD1AeGLeY7L2Uk9PVA/1N9g1kGDrxiZpVq73wtodNM_ithFp5sl1"
)
LOCAL_IMPORT_DIR = os.path.expanduser(
    get_config("LOCAL_IMPORT_DIR", "~/Documents/Tracker Imports")
)
try:
    os.makedirs(LOCAL_IMPORT_DIR, exist_ok=True)
except Exception:
    pass
BACKUP_FILENAME = "expense.db"
BACKUP_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".last_gdrive_backup.txt")
BACKUP_META_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".last_gdrive_backup_meta.json")
DB_MAINT_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".last_db_maintenance.txt")
DAY_MERGE_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".last_day_subcategory_merge.txt")
SECRETS_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".streamlit", "secrets.toml")

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


# Resolve the SQLite db path from DATABASE_URL.
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
    if not os.path.isdir(GDRIVE_BACKUP_DIR):
        return False, "Google Drive folder not available."

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

    dest = os.path.join(GDRIVE_BACKUP_DIR, BACKUP_FILENAME)
    last_exc = None
    try:
        shutil.copy2(src_path, dest)
    except OSError:
        # GVFS often fails on copystat; fallback to plain copy.
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
    dest = meta.get("dest") or os.path.join(GDRIVE_BACKUP_DIR, BACKUP_FILENAME)
    if not os.path.exists(dest):
        return False, "Backup file not found in Google Drive."

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


def _find_first_matching_expense(
    db,
    entry_date,
    category_id,
    subcategory_id,
    travel,
    trip_name=None,
    trip_start=None,
    trip_end=None
):
    q = (
        db.query(Expense)
        .filter(Expense.date == entry_date)
        .filter(Expense.category_id == category_id)
        .filter(Expense.subcategory_id == subcategory_id)
        .filter(Expense.travel == int(travel))
    )
    if int(travel) == 1:
        q = (
            q.filter(Expense.trip_name == trip_name)
            .filter(Expense.trip_start == trip_start)
            .filter(Expense.trip_end == trip_end)
        )
    else:
        q = (
            q.filter(Expense.trip_name.is_(None))
            .filter(Expense.trip_start.is_(None))
            .filter(Expense.trip_end.is_(None))
        )
    return q.order_by(Expense.id.asc()).first()


def _add_or_merge_expense(
    db,
    category_id,
    subcategory_id,
    entry_date,
    amount,
    travel=0,
    trip_name=None,
    trip_start=None,
    trip_end=None
):
    existing = _find_first_matching_expense(
        db=db,
        entry_date=entry_date,
        category_id=category_id,
        subcategory_id=subcategory_id,
        travel=travel,
        trip_name=trip_name,
        trip_start=trip_start,
        trip_end=trip_end
    )
    if existing:
        existing.amount = float(existing.amount) + float(amount)
        return "merged", existing

    obj = Expense(
        category_id=category_id,
        subcategory_id=subcategory_id,
        date=entry_date,
        amount=float(amount),
        travel=int(travel),
        trip_name=trip_name if int(travel) == 1 else None,
        trip_start=trip_start if int(travel) == 1 else None,
        trip_end=trip_end if int(travel) == 1 else None
    )
    db.add(obj)
    return "inserted", obj


def _create_local_db_snapshot(prefix="expense_before_day_merge"):
    db_path, err = resolve_db_path()
    if err:
        return None, err
    if not db_path or not os.path.exists(db_path):
        return None, "expense.db not found."

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{prefix}_{ts}.db"
    backup_path = os.path.join(os.path.dirname(db_path), backup_name)
    try:
        shutil.copy2(db_path, backup_path)
    except Exception as exc:
        return None, f"Could not create safety backup: {exc}"
    return backup_path, None


def merge_same_day_subcategory_entries(days=None):
    try:
        backup_path, backup_err = _create_local_db_snapshot()
        if backup_err:
            return False, backup_err, 0, 0, None

        with SessionLocal() as db:
            q = db.query(Expense).order_by(Expense.id.asc())
            if days is not None:
                cutoff = date.today() - timedelta(days=int(days))
                q = q.filter(Expense.date >= cutoff)
            rows = q.all()

            grouped = {}
            for exp in rows:
                travel_flag = int(exp.travel or 0)
                trip_name = _clean_import_text(exp.trip_name) if travel_flag else None
                trip_start = exp.trip_start if travel_flag else None
                trip_end = exp.trip_end if travel_flag else None
                if trip_start and not trip_end:
                    trip_end = trip_start
                if trip_end and not trip_start:
                    trip_start = trip_end

                key = (
                    exp.date,
                    int(exp.category_id),
                    int(exp.subcategory_id),
                    travel_flag,
                    trip_name or None,
                    trip_start,
                    trip_end,
                )
                grouped.setdefault(key, []).append(exp)

            merged_rows = 0
            affected_groups = 0
            for items in grouped.values():
                if len(items) <= 1:
                    continue
                keeper = items[0]
                total_amt = sum(float(i.amount or 0.0) for i in items)
                keeper.amount = float(total_amt)
                for extra in items[1:]:
                    db.delete(extra)
                    merged_rows += 1
                affected_groups += 1

            if merged_rows > 0:
                db.commit()

        write_state_value(DAY_MERGE_STATE_FILE, datetime.datetime.now().isoformat(timespec="seconds"))
        return True, "Merge completed.", affected_groups, merged_rows, backup_path
    except Exception as exc:
        return False, f"Merge failed: {exc}", 0, 0, None


def run_db_integrity_check():
    db_path, err = resolve_db_path()
    if err:
        return False, err
    if not db_path or not os.path.exists(db_path):
        return False, "expense.db not found."
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute("PRAGMA integrity_check;").fetchone()
        result = str(row[0]).strip() if row and row[0] is not None else ""
        if result.lower() == "ok":
            return True, "Integrity check passed."
        return False, f"Integrity check failed: {result or 'unknown'}"
    except Exception as exc:
        return False, f"Integrity check failed: {exc}"


def _parse_state_datetime(value):
    if not value:
        return None
    try:
        if "T" in value:
            return datetime.datetime.fromisoformat(value)
        return datetime.datetime.strptime(value, "%Y-%m-%d")
    except Exception:
        return None


def _build_safety_snapshot_zip():
    tables = [
        "expenses",
        "categories",
        "subcategories",
        "income",
        "income_categories",
        "income_subcategories",
    ]

    out = BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for table in tables:
            try:
                df = pd.read_sql_query(f"SELECT * FROM {table}", engine)
            except Exception:
                continue
            zf.writestr(f"{table}.csv", df.to_csv(index=False))

        if os.path.exists("requirements.txt"):
            try:
                with open("requirements.txt", "r", encoding="utf-8") as f:
                    zf.writestr("requirements.txt", f.read())
            except Exception:
                pass

    out.seek(0)
    return out.getvalue()


def render_system_status_panel():
    with st.sidebar.expander("🛠 System Status", expanded=False):
        st.write(f"Last backup: {format_state_value(read_state_value(BACKUP_STATE_FILE))}")
        st.write(f"Last weekly email: {format_state_value(read_state_value(WEEKLY_EMAIL_STATE_FILE))}")
        st.write(f"Last monthly email: {format_state_value(read_state_value(MONTHLY_EMAIL_STATE_FILE))}")
        st.write(f"Last DB maintenance: {format_state_value(read_state_value(DB_MAINT_STATE_FILE))}")
        st.write(f"Last day+subcategory merge: {format_state_value(read_state_value(DAY_MERGE_STATE_FILE))}")

        db_size, size_err = get_db_size()
        if db_size is not None:
            st.write(f"DB size: {format_bytes(db_size)}")
        else:
            st.write(f"DB size: {size_err}")

        if os.path.exists(SECRETS_FILE_PATH):
            st.caption("Secrets file detected in project. Consider moving credentials to environment variables.")

        if st.button("Verify Backup", key="verify_backup_btn"):
            ok, msg = verify_gdrive_backup()
            if ok:
                st.success(msg)
            else:
                st.error(msg)

        if st.button("Run DB Maintenance", key="run_db_maint_btn"):
            with st.spinner("Running DB maintenance..."):
                ok, msg = run_db_maintenance()
            if ok:
                st.success(msg)
            else:
                st.error(msg)

        if st.button("Merge All Past Entries", key="merge_day_subcategory_btn"):
            with st.spinner("Merging same day + subcategory entries across all history..."):
                ok, msg, groups, rows, backup_path = merge_same_day_subcategory_entries(days=None)
            if ok:
                st.success(f"{msg} Groups merged: {groups}, rows removed: {rows}.")
                if backup_path:
                    st.caption(f"Safety backup: {backup_path}")
                st.session_state.data_refresh += 1
            else:
                st.error(msg)


# Handle weekly Google Drive backup.
def weekly_gdrive_backup():
    if st.session_state.get("weekly_backup_checked"):
        return
    st.session_state.weekly_backup_checked = True

    today = date.today()
    if today.weekday() != 6:  # Sunday
        return

    last = read_state_value(BACKUP_STATE_FILE)
    if last:
        last_date = last.split("T")[0]
        if last_date == today.isoformat():
            return

    ok, msg = backup_db_to_gdrive()
    if not ok:
        if not st.session_state.get("weekly_backup_warned"):
            st.session_state.weekly_backup_warned = True
            st.warning(f"Weekly backup skipped: {msg}")
        return

    flash("Weekly backup saved to Google Drive.", "info")

weekly_gdrive_backup()

# ==============
# WEEKLY EMAIL REPORT (SUNDAYS)
# ==============
SMTP_HOST = get_config("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(get_config("SMTP_PORT", "587"))
SMTP_USER = get_config("SMTP_USER", "")
SMTP_PASS = get_config("SMTP_PASS", "")
SMTP_TO = get_config("SMTP_TO", "bharanikumarr18@gmail.com")
WEEKLY_EMAIL_STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    ".last_weekly_email.txt"
)
MONTHLY_EMAIL_STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    ".last_monthly_email.txt"
)

# Generate weekly expense PDF.
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
        leading=12
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

    # Summary block
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

    # Category breakdown
    story.append(Paragraph("Category Breakdown", styles["SectionHeader"]))
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
    story.append(Spacer(1, 12))

    # Detailed transactions
    story.append(Paragraph("Transactions", styles["SectionHeader"]))
    if df.empty:
        story.append(Paragraph("No transactions found for this week.", styles["BodySmall"]))
    else:
        tx_rows = [[
            Paragraph("Date", table_header),
            Paragraph("Category", table_header),
            Paragraph("Subcategory", table_header),
            Paragraph("Amount (₹)", table_header)
        ]]
        for _, row in df.iterrows():
            tx_rows.append([
                Paragraph(row["date"].strftime("%Y-%m-%d"), table_body),
                Paragraph(str(row["category"]), table_body),
                Paragraph(str(row["subcategory"]), table_body),
                Paragraph(f"{row['amount']:,.2f}", table_body)
            ])
        tx_table = Table(
            tx_rows,
            colWidths=[70, 160, 190, 80],
            hAlign="LEFT",
            repeatRows=1
        )
        tx_table.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), "DejaVu"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("ALIGN", (3, 1), (3, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tx_table)

    doc.build(story)
    return buffer.getvalue()

# Generate monthly expense PDF.
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
        leading=12
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

    # Summary block
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

    # Category totals
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

    # Subcategory totals
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

# Send weekly email report.
def send_weekly_email_report():
    if st.session_state.get("weekly_email_checked"):
        return
    st.session_state.weekly_email_checked = True

    today = date.today()
    if today.weekday() != 6:  # Sunday
        return

    try:
        if os.path.exists(WEEKLY_EMAIL_STATE_FILE):
            last = open(WEEKLY_EMAIL_STATE_FILE, "r").read().strip()
            if last == today.isoformat():
                return
    except Exception:
        pass

    if not SMTP_USER or not SMTP_PASS or not SMTP_TO:
        if not st.session_state.get("weekly_email_warned"):
            st.session_state.weekly_email_warned = True
            st.warning("Weekly email skipped: SMTP credentials not configured.")
        return

    end_date = today - timedelta(days=1)  # Saturday
    start_date = end_date - timedelta(days=6)  # Sunday

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
        with open(WEEKLY_EMAIL_STATE_FILE, "w") as f:
            f.write(today.isoformat())
        flash("Weekly email report sent.", "info")
    except Exception as e:
        st.warning(f"Weekly email failed: {e}")

# Send test email report.
def send_test_email_report():
    if not SMTP_USER or not SMTP_PASS or not SMTP_TO:
        st.warning("SMTP credentials not configured. Add them in secrets.toml first.")
        return

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
        st.success("Test email sent successfully.")
    except Exception as e:
        st.error(f"Test email failed: {e}")

# Send monthly email report.
def send_monthly_email_report():
    if st.session_state.get("monthly_email_checked"):
        return
    st.session_state.monthly_email_checked = True

    today = date.today()
    if today.day != 3:
        return

    try:
        if os.path.exists(MONTHLY_EMAIL_STATE_FILE):
            last = open(MONTHLY_EMAIL_STATE_FILE, "r").read().strip()
            if last == today.isoformat():
                return
    except Exception:
        pass

    if not SMTP_USER or not SMTP_PASS or not SMTP_TO:
        if not st.session_state.get("monthly_email_warned"):
            st.session_state.monthly_email_warned = True
            st.warning("Monthly email skipped: SMTP credentials not configured.")
        return

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
        with open(MONTHLY_EMAIL_STATE_FILE, "w") as f:
            f.write(today.isoformat())
        flash("Monthly email report sent.", "info")
    except Exception as e:
        st.warning(f"Monthly email failed: {e}")

# Send test monthly email report.
def send_test_monthly_email_report():
    if not SMTP_USER or not SMTP_PASS or not SMTP_TO:
        st.warning("SMTP credentials not configured. Add them in secrets.toml first.")
        return

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
        st.success("Monthly test email sent successfully.")
    except Exception as e:
        st.error(f"Monthly test email failed: {e}")

# Add months.
def add_months(start_date, months):
    total = (start_date.year * 12 + (start_date.month - 1)) + months
    year = total // 12
    month = (total % 12) + 1
    return date(year, month, 1)

# Get month options.
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

# Send custom monthly report.
def send_custom_monthly_report(month_start, target_email):
    if not SMTP_USER or not SMTP_PASS:
        st.warning("SMTP credentials not configured. Add them in secrets.toml first.")
        return
    if not target_email or "@" not in target_email:
        st.warning("Please enter a valid email address.")
        return

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
        st.success("Monthly report sent successfully.")
    except Exception as e:
        st.error(f"Monthly report failed: {e}")

send_weekly_email_report()
send_monthly_email_report()

# ==============
# CREATE TABLES
# ==============
# Load expense data.
@st.cache_data(show_spinner=False)
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

# Load income data.
@st.cache_data(show_spinner=False)
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

# Load events data.
@st.cache_data(show_spinner=False)
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

# Load distinct event list (name + date range).
@st.cache_data(show_spinner=False)
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
# EXPENSE CSV IMPORT
# ======================
def _norm_lookup_text(value):
    text_val = str(value or "").strip().lower()
    return re.sub(r"[^a-z0-9]+", "", text_val)


def _is_blank_import_value(value):
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except Exception:
        pass
    if isinstance(value, str):
        txt = value.strip().lower()
        if txt in {"", "nan", "none", "nat", "null"}:
            return True
    return False


def _clean_import_text(value):
    if _is_blank_import_value(value):
        return ""
    return str(value).strip()


def _best_fuzzy_match(raw_value, candidates, min_score=0.78):
    raw_norm = _norm_lookup_text(raw_value)
    if not raw_norm or not candidates:
        return None, 0.0

    best_item = None
    best_score = 0.0
    for candidate in candidates:
        score = SequenceMatcher(None, raw_norm, _norm_lookup_text(candidate)).ratio()
        if score > best_score:
            best_item = candidate
            best_score = score

    if best_item and best_score >= min_score:
        return best_item, best_score
    return None, best_score


def _parse_import_date(value):
    if value is None or str(value).strip() == "":
        return None
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=False)
    if pd.isna(parsed):
        parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return None
    return parsed.date()


def _parse_import_amount(value):
    if value is None:
        return None
    txt = str(value).strip().replace(",", "")
    amt = pd.to_numeric(txt, errors="coerce")
    if pd.isna(amt):
        return None
    return float(amt)


def _read_expense_import_file(file_obj_or_path, source_name=None):
    file_name = str(source_name or getattr(file_obj_or_path, "name", "") or file_obj_or_path or "").lower()
    try:
        if file_name.endswith(".csv"):
            return pd.read_csv(file_obj_or_path), None
        if file_name.endswith(".xlsx"):
            return pd.read_excel(file_obj_or_path, engine="openpyxl"), None
        if file_name.endswith(".ods"):
            try:
                return pd.read_excel(file_obj_or_path, engine="odf"), None
            except ImportError:
                return None, "ODS import needs `odfpy`. Install with: `pip install odfpy`"
        return None, "Unsupported file format. Use .csv, .xlsx, or .ods"
    except Exception as exc:
        return None, f"Could not read file: {exc}"


def _list_local_import_files(folder_path):
    if not folder_path:
        return [], "Local import folder is not configured."
    if not os.path.isdir(folder_path):
        return [], f"Local import folder not found: {folder_path}"

    rows = []
    supported_ext = (".csv", ".xlsx", ".ods")
    try:
        with os.scandir(folder_path) as entries:
            for entry in entries:
                if not entry.is_file():
                    continue
                if not entry.name.lower().endswith(supported_ext):
                    continue
                stat = entry.stat()
                rows.append({
                    "name": entry.name,
                    "path": entry.path,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                })
    except Exception as exc:
        return [], f"Could not read local import folder: {exc}"

    rows.sort(key=lambda x: x["mtime"], reverse=True)
    return rows, None


def _fmt_import_file_size(num_bytes):
    size = float(num_bytes or 0)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024 or unit == "GB":
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024.0
    return "0 B"


def _get_expense_catalog(db):
    cats = db.query(Category).order_by(Category.name.asc()).all()
    subs = (
        db.query(SubCategory.name, Category.name)
        .join(Category, SubCategory.category_id == Category.id)
        .order_by(Category.name.asc(), SubCategory.name.asc())
        .all()
    )

    cat_to_subs = {c.name: [] for c in cats}
    sub_to_cats = {}
    for sub_name, cat_name in subs:
        cat_to_subs.setdefault(cat_name, []).append(sub_name)
        sub_to_cats.setdefault(sub_name, []).append(cat_name)

    for cat_name in list(cat_to_subs.keys()):
        cat_to_subs[cat_name] = sorted(set(cat_to_subs[cat_name]))
    for sub_name in list(sub_to_cats.keys()):
        sub_to_cats[sub_name] = sorted(set(sub_to_cats[sub_name]))

    return cat_to_subs, sub_to_cats


def _get_existing_events(db):
    return (
        db.query(Expense.trip_name, Expense.trip_start, Expense.trip_end)
        .filter(Expense.travel == 1)
        .filter(Expense.trip_name.isnot(None))
        .distinct()
        .order_by(Expense.trip_start.desc(), Expense.trip_end.desc())
        .all()
    )


def _build_existing_event_maps(existing_events):
    label_to_trip = {}
    norm_label_to_trip = {}
    name_norm_to_trips = {}

    for trip_name, trip_start, trip_end in existing_events:
        if not trip_name:
            continue
        start = _parse_import_date(trip_start) if not isinstance(trip_start, date) else trip_start
        end = _parse_import_date(trip_end) if not isinstance(trip_end, date) else trip_end
        if not start and end:
            start = end
        if not end and start:
            end = start
        if not start or not end:
            continue

        name_txt = str(trip_name).strip()
        label = f"{name_txt} | {start} -> {end}"
        trip = (name_txt, start, end)
        label_to_trip[label] = trip
        norm_label_to_trip[_norm_lookup_text(label)] = trip
        name_norm_to_trips.setdefault(_norm_lookup_text(name_txt), []).append(trip)

    return label_to_trip, norm_label_to_trip, name_norm_to_trips


def _resolve_event_fields(raw_mode, raw_existing_event, raw_new_event_name, raw_start, raw_end, existing_events):
    notes = []
    errors = []

    label_to_trip, norm_label_to_trip, name_norm_to_trips = _build_existing_event_maps(existing_events)

    mode_text = _clean_import_text(raw_mode)
    mode_norm = _norm_lookup_text(mode_text)
    existing_event_text = _clean_import_text(raw_existing_event)
    new_event_name_text = _clean_import_text(raw_new_event_name)
    # Backward compatibility: old template had a single "event" field.
    if mode_norm in {"createnew", "new", "create"} and not new_event_name_text and existing_event_text:
        new_event_name_text = existing_event_text
    if mode_norm in {"useexisting", "existing", "use"} and not existing_event_text and new_event_name_text:
        existing_event_text = new_event_name_text

    start_provided = not _is_blank_import_value(raw_start)
    end_provided = not _is_blank_import_value(raw_end)
    start_date = _parse_import_date(raw_start)
    end_date = _parse_import_date(raw_end)

    mode = ""
    if mode_norm in {"useexisting", "existing", "use"}:
        mode = "Use Existing"
    elif mode_norm in {"createnew", "new", "create"}:
        mode = "Create New"
    elif mode_norm == "":
        if existing_event_text or new_event_name_text or start_provided or end_provided:
            mode = "Create New"
            notes.append("Event mode inferred as Create New")
        else:
            return {
                "Event Mode": "",
                "Existing Event": "",
                "New Event Name": "",
                "Event Start": None,
                "Event End": None,
                "travel": 0,
                "trip_name": None,
                "trip_start": None,
                "trip_end": None,
                "notes": notes,
                "errors": errors,
            }
    else:
        errors.append("Invalid event mode")
        mode = mode_text

    if mode == "Use Existing":
        if not existing_event_text:
            errors.append("Select an existing event")
        else:
            trip = label_to_trip.get(existing_event_text)
            if not trip:
                trip = norm_label_to_trip.get(_norm_lookup_text(existing_event_text))
            if not trip:
                name_candidates = name_norm_to_trips.get(_norm_lookup_text(existing_event_text), [])
                if len(name_candidates) == 1:
                    trip = name_candidates[0]
                    notes.append("Resolved existing event by name")
                elif len(name_candidates) > 1:
                    errors.append("Multiple events share this name; use full event label")
            if not trip:
                errors.append("Existing event not found")
            else:
                trip_name, trip_start, trip_end = trip
                return {
                    "Event Mode": "Use Existing",
                    "Existing Event": f"{trip_name} | {trip_start} -> {trip_end}",
                    "New Event Name": "",
                    "Event Start": trip_start,
                    "Event End": trip_end,
                    "travel": 1,
                    "trip_name": trip_name,
                    "trip_start": trip_start,
                    "trip_end": trip_end,
                    "notes": notes,
                    "errors": errors,
                }

    if mode == "Create New":
        if not new_event_name_text:
            errors.append("Event name required for Create New")
        if not start_provided and not end_provided:
            errors.append("Event date required for Create New")
        if start_provided and start_date is None:
            errors.append("Invalid event start date")
        if end_provided and end_date is None:
            errors.append("Invalid event end date")
        if start_date and not end_date:
            end_date = start_date
        if end_date and not start_date:
            start_date = end_date
        if start_date and end_date and end_date < start_date:
            errors.append("Event end date is before start date")

        return {
            "Event Mode": "Create New",
            "Existing Event": existing_event_text,
            "New Event Name": new_event_name_text,
            "Event Start": start_date,
            "Event End": end_date,
            "travel": 0 if errors else 1,
            "trip_name": new_event_name_text if new_event_name_text else None,
            "trip_start": start_date,
            "trip_end": end_date,
            "notes": notes,
            "errors": errors,
        }

    return {
        "Event Mode": mode_text or mode,
        "Existing Event": existing_event_text,
        "New Event Name": new_event_name_text,
        "Event Start": start_date,
        "Event End": end_date,
        "travel": 0,
        "trip_name": None,
        "trip_start": None,
        "trip_end": None,
        "notes": notes,
        "errors": errors,
    }


def _safe_named_range(name):
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", str(name).strip())
    if not cleaned:
        cleaned = "CAT"
    if cleaned[0].isdigit():
        cleaned = f"C_{cleaned}"
    return cleaned[:180]


def _build_expense_template_xlsx(cat_to_subs, existing_events=None):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment
        from openpyxl.utils import get_column_letter
        from openpyxl.worksheet.datavalidation import DataValidation
        from openpyxl.workbook.defined_name import DefinedName
    except Exception:
        return None, "openpyxl is required for smart template export. Install with: `pip install openpyxl`"

    wb = Workbook()
    ws = wb.active
    ws.title = "Expenses"
    list_ws = wb.create_sheet("Lists")

    ws["A1"] = "event_mode"
    ws["B1"] = "existing_event"
    ws["C1"] = "new_event_name"
    ws["D1"] = "event_start"
    ws["E1"] = "event_end"
    ws["F1"] = "date"
    ws["G1"] = "category"
    ws["H1"] = "subcategory"
    ws["I1"] = "price"
    ws["J1"] = "helper"
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 34
    ws.column_dimensions["C"].width = 24
    ws.column_dimensions["D"].width = 16
    ws.column_dimensions["E"].width = 16
    ws.column_dimensions["F"].width = 16
    ws.column_dimensions["G"].width = 24
    ws.column_dimensions["H"].width = 28
    ws.column_dimensions["I"].width = 14
    ws.column_dimensions["J"].hidden = True
    ws.freeze_panes = "A2"

    list_ws["A1"] = "category"
    list_ws["B1"] = "range_name"

    categories = sorted(cat_to_subs.keys())
    used_names = set()

    def add_name(name_obj):
        try:
            wb.defined_names.add(name_obj)
        except Exception:
            wb.defined_names.append(name_obj)

    if categories:
        for idx, cat_name in enumerate(categories, start=2):
            base = _safe_named_range(cat_name)
            candidate = base
            suffix = 1
            while candidate in used_names:
                suffix += 1
                candidate = f"{base}_{suffix}"
            range_name = candidate
            used_names.add(range_name)

            list_ws.cell(row=idx, column=1, value=cat_name)
            list_ws.cell(row=idx, column=2, value=range_name)

            col_idx = idx + 1  # C onward
            col_letter = get_column_letter(col_idx)
            subs = sorted(cat_to_subs.get(cat_name, []))
            last_sub_row = 2
            for sub_row, sub_name in enumerate(subs, start=2):
                list_ws.cell(row=sub_row, column=col_idx, value=sub_name)
                last_sub_row = sub_row

            add_name(DefinedName(
                name=range_name,
                attr_text=f"Lists!${col_letter}$2:${col_letter}${max(last_sub_row, 2)}"
            ))

        cat_end = len(categories) + 1
        add_name(DefinedName(
            name="Categories",
            attr_text=f"Lists!$A$2:$A${cat_end}"
        ))

        for row in range(2, 1001):
            ws[f"J{row}"] = f'=IFERROR(VLOOKUP(G{row},Lists!$A$2:$B${cat_end},2,FALSE),"")'
            ws[f"D{row}"].number_format = "yyyy-mm-dd"
            ws[f"E{row}"].number_format = "yyyy-mm-dd"
            ws[f"F{row}"].number_format = "yyyy-mm-dd"
            ws[f"I{row}"].number_format = "0.00"

        dv_category = DataValidation(type="list", formula1="=Categories", allow_blank=False)
        dv_category.errorTitle = "Invalid Category"
        dv_category.error = "Choose from the category dropdown."
        ws.add_data_validation(dv_category)
        dv_category.add("G2:G1000")

        dv_subcategory = DataValidation(type="list", formula1="=INDIRECT($J2)", allow_blank=False)
        dv_subcategory.errorTitle = "Invalid Subcategory"
        dv_subcategory.error = "Choose a valid subcategory for the selected category."
        ws.add_data_validation(dv_subcategory)
        dv_subcategory.add("H2:H1000")

    event_rows = existing_events or []
    ev_label_col_idx = 200
    ev_name_col_idx = 201
    ev_start_col_idx = 202
    ev_end_col_idx = 203
    ev_label_col = get_column_letter(ev_label_col_idx)
    ev_name_col = get_column_letter(ev_name_col_idx)
    ev_start_col = get_column_letter(ev_start_col_idx)
    ev_end_col = get_column_letter(ev_end_col_idx)

    list_ws[f"{ev_label_col}1"] = "event_label"
    list_ws[f"{ev_name_col}1"] = "event_name"
    list_ws[f"{ev_start_col}1"] = "event_start"
    list_ws[f"{ev_end_col}1"] = "event_end"

    event_end_row = 2
    if event_rows:
        for idx, (trip_name, trip_start, trip_end) in enumerate(event_rows, start=2):
            start = _parse_import_date(trip_start) if not isinstance(trip_start, date) else trip_start
            end = _parse_import_date(trip_end) if not isinstance(trip_end, date) else trip_end
            if not start and end:
                start = end
            if not end and start:
                end = start
            if not trip_name or not start or not end:
                continue
            name_txt = str(trip_name).strip()
            label_txt = f"{name_txt} | {start} -> {end}"
            list_ws.cell(row=idx, column=ev_label_col_idx, value=label_txt)
            list_ws.cell(row=idx, column=ev_name_col_idx, value=name_txt)
            list_ws.cell(row=idx, column=ev_start_col_idx, value=start)
            list_ws.cell(row=idx, column=ev_end_col_idx, value=end)
            list_ws.cell(row=idx, column=ev_start_col_idx).number_format = "yyyy-mm-dd"
            list_ws.cell(row=idx, column=ev_end_col_idx).number_format = "yyyy-mm-dd"
            event_end_row = idx

        add_name(DefinedName(
            name="ExistingEvents",
            attr_text=f"Lists!${ev_label_col}$2:${ev_label_col}${event_end_row}"
        ))

    for row in range(2, 1001):
        ws[f"D{row}"] = (
            f'=IF($A{row}="Use Existing",'
            f'IFERROR(VLOOKUP($B{row},Lists!${ev_label_col}$2:${ev_end_col}${event_end_row},3,FALSE),""),'
            f'""'
            f')'
        )
        ws[f"E{row}"] = (
            f'=IF($A{row}="Use Existing",'
            f'IFERROR(VLOOKUP($B{row},Lists!${ev_label_col}$2:${ev_end_col}${event_end_row},4,FALSE),""),'
            f'""'
            f')'
        )

    dv_event_mode = DataValidation(type="list", formula1='"Use Existing,Create New"', allow_blank=True)
    dv_event_mode.errorTitle = "Invalid Event Mode"
    dv_event_mode.error = "Choose Use Existing or Create New."
    ws.add_data_validation(dv_event_mode)
    dv_event_mode.add("A2:A1000")

    if event_rows:
        # Keep dropdown visible for existing events, but allow manual typing
        # for Create New mode (validation is enforced again during import).
        dv_event_list = DataValidation(type="list", formula1="=ExistingEvents", allow_blank=True)
        dv_event_list.errorStyle = "warning"
        dv_event_list.errorTitle = "Event not in existing list"
        dv_event_list.error = "For Create New, you can type a new event name and continue."
        dv_event_list.showErrorMessage = True
        ws.add_data_validation(dv_event_list)
        dv_event_list.add("B2:B1000")

    dv_event_date = DataValidation(
        type="date",
        operator="between",
        formula1="DATE(2000,1,1)",
        formula2="DATE(2100,12,31)",
        allow_blank=True
    )
    ws.add_data_validation(dv_event_date)
    dv_event_date.add("D2:D1000")
    dv_event_date.add("E2:E1000")

    dv_date = DataValidation(
        type="date",
        operator="between",
        formula1="DATE(2000,1,1)",
        formula2="DATE(2100,12,31)",
        allow_blank=False
    )
    ws.add_data_validation(dv_date)
    dv_date.add("F2:F1000")

    dv_price = DataValidation(type="decimal", operator="greaterThan", formula1="0", allow_blank=False)
    ws.add_data_validation(dv_price)
    dv_price.add("I2:I1000")

    list_ws.sheet_state = "hidden"

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue(), None


def _resolve_import_row(
    raw_date,
    raw_category,
    raw_subcategory,
    raw_amount,
    raw_event_mode,
    raw_existing_event,
    raw_new_event_name,
    raw_event_start,
    raw_event_end,
    cat_to_subs,
    sub_to_cats,
    existing_events
):
    categories = list(cat_to_subs.keys())
    all_subs = list(sub_to_cats.keys())
    notes = []

    parsed_date = _parse_import_date(raw_date)
    parsed_amount = _parse_import_amount(raw_amount)

    category = _clean_import_text(raw_category)
    subcategory = _clean_import_text(raw_subcategory)

    if parsed_date is None:
        notes.append("Invalid date")
    if parsed_amount is None or parsed_amount <= 0:
        notes.append("Invalid price")

    cat_norm_map = {_norm_lookup_text(c): c for c in categories}
    sub_norm_map = {_norm_lookup_text(s): s for s in all_subs}

    resolved_cat = cat_norm_map.get(_norm_lookup_text(category))
    if not resolved_cat and category:
        resolved_cat, cat_score = _best_fuzzy_match(category, categories, min_score=0.76)
        if resolved_cat:
            notes.append(f"Category fuzzy match ({cat_score:.2f})")

    resolved_sub = None
    if resolved_cat:
        sub_candidates = cat_to_subs.get(resolved_cat, [])
        sub_local_norm = {_norm_lookup_text(s): s for s in sub_candidates}
        resolved_sub = sub_local_norm.get(_norm_lookup_text(subcategory))
        if not resolved_sub and subcategory:
            resolved_sub, sub_score = _best_fuzzy_match(subcategory, sub_candidates, min_score=0.76)
            if resolved_sub:
                notes.append(f"Subcategory fuzzy match ({sub_score:.2f})")

    if not resolved_cat or not resolved_sub:
        global_sub = sub_norm_map.get(_norm_lookup_text(subcategory))
        if not global_sub and subcategory:
            global_sub, g_score = _best_fuzzy_match(subcategory, all_subs, min_score=0.82)
            if global_sub:
                notes.append(f"Global subcategory fuzzy match ({g_score:.2f})")
        if global_sub:
            linked_cats = sub_to_cats.get(global_sub, [])
            if len(linked_cats) == 1:
                inferred_cat = linked_cats[0]
                if not resolved_cat:
                    resolved_cat = inferred_cat
                    notes.append("Category inferred from subcategory")
                if resolved_cat == inferred_cat and not resolved_sub:
                    resolved_sub = global_sub

    final_cat = resolved_cat or category
    final_sub = resolved_sub or subcategory

    if not final_cat:
        notes.append("Missing category")
    if not final_sub:
        notes.append("Missing subcategory")
    if final_cat and final_sub and final_cat in cat_to_subs and final_sub not in cat_to_subs[final_cat]:
        notes.append("Subcategory does not belong to category")

    event_resolved = _resolve_event_fields(
        raw_event_mode,
        raw_existing_event,
        raw_new_event_name,
        raw_event_start,
        raw_event_end,
        existing_events
    )
    notes.extend(event_resolved.get("notes", []))
    notes.extend(event_resolved.get("errors", []))

    status = "OK" if not notes else "Needs Review"
    return {
        "Event Mode": event_resolved.get("Event Mode", ""),
        "Existing Event": event_resolved.get("Existing Event", ""),
        "New Event Name": event_resolved.get("New Event Name", ""),
        "Event Start": event_resolved.get("Event Start"),
        "Event End": event_resolved.get("Event End"),
        "Date": parsed_date,
        "Category": final_cat,
        "Subcategory": final_sub,
        "Price": parsed_amount if parsed_amount is not None else raw_amount,
        "Status": status,
        "Notes": " | ".join(notes) if notes else "Ready",
    }


def _prepare_expense_import_preview(raw_df, cat_to_subs, sub_to_cats, existing_events):
    cols = {str(c).strip().lower(): c for c in raw_df.columns}

    def pick_col(names):
        for n in names:
            if n in cols:
                return cols[n]
        return None

    date_col = pick_col(["date"])
    cat_col = pick_col(["category"])
    sub_col = pick_col(["subcategory", "sub_category", "sub category"])
    amt_col = pick_col(["price", "amount", "amt"])
    event_mode_col = pick_col(["event_mode", "event mode"])
    existing_event_col = pick_col(["existing_event", "existing event", "event", "select event", "select_event"])
    new_event_col = pick_col(["new_event_name", "new event name", "event_name", "event name", "trip_name", "trip name"])
    event_start_col = pick_col(["event_start", "event start", "trip_start", "trip start"])
    event_end_col = pick_col(["event_end", "event end", "trip_end", "trip end"])

    missing = []
    if not date_col:
        missing.append("date")
    if not cat_col:
        missing.append("category")
    if not sub_col:
        missing.append("subcategory")
    if not amt_col:
        missing.append("price")
    if missing:
        return None, f"Missing required columns: {', '.join(missing)}"

    required_cols = [date_col, cat_col, sub_col, amt_col]
    optional_cols = [c for c in [event_mode_col, existing_event_col, new_event_col, event_start_col, event_end_col] if c]
    working_df = raw_df[required_cols + optional_cols].copy()
    working_df = working_df[
        working_df.apply(
            lambda r: any(not _is_blank_import_value(r.get(c)) for c in required_cols),
            axis=1
        )
    ]

    if working_df.empty:
        return None, "No non-empty rows found in CSV."

    parsed_rows = []
    for _, row in working_df.iterrows():
        parsed_rows.append(
            _resolve_import_row(
                row.get(date_col),
                row.get(cat_col),
                row.get(sub_col),
                row.get(amt_col),
                row.get(event_mode_col) if event_mode_col else None,
                row.get(existing_event_col) if existing_event_col else None,
                row.get(new_event_col) if new_event_col else None,
                row.get(event_start_col) if event_start_col else None,
                row.get(event_end_col) if event_end_col else None,
                cat_to_subs,
                sub_to_cats,
                existing_events
            )
        )

    preview_df = pd.DataFrame(
        parsed_rows,
        columns=[
            "Event Mode",
            "Existing Event",
            "New Event Name",
            "Event Start",
            "Event End",
            "Date",
            "Category",
            "Subcategory",
            "Price",
            "Status",
            "Notes",
        ]
    )
    if preview_df.empty:
        return None, "No rows found in CSV."
    return preview_df, None


def _normalize_event_columns_for_mode(df):
    if df is None or df.empty:
        return df, 0
    if "Event Mode" not in df.columns:
        return df, 0

    out_df = df.copy()
    fixed_count = 0

    for idx, row in out_df.iterrows():
        mode_norm = _norm_lookup_text(row.get("Event Mode"))
        if mode_norm in {"useexisting", "existing", "use"}:
            if "New Event Name" in out_df.columns and not _is_blank_import_value(row.get("New Event Name")):
                out_df.at[idx, "New Event Name"] = ""
                fixed_count += 1
        elif mode_norm in {"createnew", "new", "create"}:
            if "Existing Event" in out_df.columns and not _is_blank_import_value(row.get("Existing Event")):
                out_df.at[idx, "Existing Event"] = ""
                fixed_count += 1

    return out_df, fixed_count


def _build_event_mode_guard_errors(df):
    if df is None or df.empty:
        return pd.DataFrame()

    guard_errors = []
    for idx, row in df.iterrows():
        row_no = int(idx) + 1
        mode_norm = _norm_lookup_text(row.get("Event Mode"))
        existing_event = _clean_import_text(row.get("Existing Event"))
        new_event_name = _clean_import_text(row.get("New Event Name"))

        if mode_norm in {"useexisting", "existing", "use"} and not existing_event:
            guard_errors.append({
                "Row": row_no,
                "Issue": "Event Mode is Use Existing but Existing Event is empty."
            })
        elif mode_norm in {"createnew", "new", "create"} and not new_event_name:
            guard_errors.append({
                "Row": row_no,
                "Issue": "Event Mode is Create New but New Event Name is empty."
            })
        elif mode_norm and mode_norm not in {"useexisting", "existing", "use", "createnew", "new", "create"}:
            guard_errors.append({
                "Row": row_no,
                "Issue": "Invalid Event Mode. Use 'Use Existing' or 'Create New'."
            })

    return pd.DataFrame(guard_errors)


def _validate_and_insert_expense_import(db, edited_df):
    cat_objs = db.query(Category).all()
    sub_objs = db.query(SubCategory).all()
    cat_by_id = {c.id: c for c in cat_objs}

    cat_by_norm = {_norm_lookup_text(c.name): c for c in cat_objs}
    sub_by_pair = {}
    for s in sub_objs:
        parent = cat_by_id.get(s.category_id)
        if parent:
            sub_by_pair[(parent.id, _norm_lookup_text(s.name))] = s

    existing_events = _get_existing_events(db)
    existing_event_name_map = {}
    for ev_name, ev_start, ev_end in existing_events:
        name_txt = _clean_import_text(ev_name)
        if not name_txt:
            continue
        norm_name = _norm_lookup_text(name_txt)
        if norm_name and norm_name not in existing_event_name_map:
            start = _parse_import_date(ev_start) if not isinstance(ev_start, date) else ev_start
            end = _parse_import_date(ev_end) if not isinstance(ev_end, date) else ev_end
            if start and not end:
                end = start
            if end and not start:
                start = end
            if start and end:
                existing_event_name_map[norm_name] = (name_txt, start, end)

    pending_entries = {}
    errors = []
    merged_count = 0
    batch_new_event_name_map = {}

    for idx, row in edited_df.iterrows():
        row_no = int(idx) + 1
        if all(_is_blank_import_value(row.get(col)) for col in ["Date", "Category", "Subcategory", "Price"]):
            continue

        parsed_date = _parse_import_date(row.get("Date"))
        parsed_amt = _parse_import_amount(row.get("Price"))
        cat_raw = _clean_import_text(row.get("Category"))
        sub_raw = _clean_import_text(row.get("Subcategory"))
        event_mode_raw = _clean_import_text(row.get("Event Mode"))
        existing_event_raw = _clean_import_text(row.get("Existing Event"))
        new_event_name_raw = _clean_import_text(row.get("New Event Name"))
        event_start_raw = row.get("Event Start")
        event_end_raw = row.get("Event End")

        row_errors = []
        if not parsed_date:
            row_errors.append("Invalid date")
        if parsed_amt is None or parsed_amt <= 0:
            row_errors.append("Invalid price")

        cat_obj = cat_by_norm.get(_norm_lookup_text(cat_raw))
        if not cat_obj:
            row_errors.append("Category not found")
            sub_obj = None
        else:
            sub_obj = sub_by_pair.get((cat_obj.id, _norm_lookup_text(sub_raw)))
            if not sub_obj:
                row_errors.append("Subcategory not found under selected category")

        event_resolved = _resolve_event_fields(
            event_mode_raw,
            existing_event_raw,
            new_event_name_raw,
            event_start_raw,
            event_end_raw,
            existing_events
        )
        event_errors = event_resolved.get("errors", [])
        if event_errors:
            row_errors.extend(event_errors)
        else:
            # If same "Create New" event name appears multiple times, anchor all rows
            # to one event range (existing first, else first seen in this batch).
            if event_resolved.get("Event Mode") == "Create New":
                ev_name_norm = _norm_lookup_text(event_resolved.get("trip_name"))
                if ev_name_norm:
                    anchor = (
                        batch_new_event_name_map.get(ev_name_norm)
                        or existing_event_name_map.get(ev_name_norm)
                    )
                    if anchor:
                        a_name, a_start, a_end = anchor
                        event_resolved["travel"] = 1
                        event_resolved["trip_name"] = a_name
                        event_resolved["trip_start"] = a_start
                        event_resolved["trip_end"] = a_end
                    else:
                        batch_new_event_name_map[ev_name_norm] = (
                            event_resolved.get("trip_name"),
                            event_resolved.get("trip_start"),
                            event_resolved.get("trip_end")
                        )

        if row_errors:
            errors.append({
                "Row": row_no,
                "Category": cat_raw,
                "Subcategory": sub_raw,
                "Issue": " | ".join(row_errors)
            })
            continue

        key = (
            parsed_date,
            int(cat_obj.id),
            int(sub_obj.id),
            int(event_resolved.get("travel", 0)),
            _clean_import_text(event_resolved.get("trip_name")) or None,
            event_resolved.get("trip_start"),
            event_resolved.get("trip_end"),
        )
        if key not in pending_entries:
            pending_entries[key] = {
                "date": parsed_date,
                "category_id": int(cat_obj.id),
                "subcategory_id": int(sub_obj.id),
                "travel": int(event_resolved.get("travel", 0)),
                "trip_name": event_resolved.get("trip_name"),
                "trip_start": event_resolved.get("trip_start"),
                "trip_end": event_resolved.get("trip_end"),
                "amount": 0.0,
            }
        pending_entries[key]["amount"] += float(parsed_amt)

    if errors:
        return 0, merged_count, pd.DataFrame(errors)

    inserted_count = 0
    for item in pending_entries.values():
        existing = _find_first_matching_expense(
            db=db,
            entry_date=item["date"],
            category_id=item["category_id"],
            subcategory_id=item["subcategory_id"],
            travel=item["travel"],
            trip_name=item["trip_name"] if item["travel"] == 1 else None,
            trip_start=item["trip_start"] if item["travel"] == 1 else None,
            trip_end=item["trip_end"] if item["travel"] == 1 else None
        )
        if existing:
            existing.amount = float(existing.amount) + float(item["amount"])
            merged_count += 1
        else:
            db.add(Expense(
                category_id=item["category_id"],
                subcategory_id=item["subcategory_id"],
                date=item["date"],
                amount=float(item["amount"]),
                travel=item["travel"],
                trip_name=item["trip_name"] if item["travel"] == 1 else None,
                trip_start=item["trip_start"] if item["travel"] == 1 else None,
                trip_end=item["trip_end"] if item["travel"] == 1 else None
            ))
            inserted_count += 1

    if inserted_count > 0 or merged_count > 0:
        db.commit()
    return inserted_count, merged_count, pd.DataFrame()


def import_expenses_page():
    st.title("🧾 Import Expenses")

    with SessionLocal() as db:
        cat_to_subs, sub_to_cats = _get_expense_catalog(db)
        existing_events = _get_existing_events(db)

    st.markdown("### Download Smart Template")
    template_bytes, template_err = _build_expense_template_xlsx(cat_to_subs, existing_events)
    if template_err:
        st.warning(template_err)
    else:
        st.download_button(
            "⬇️ Download Smart Import Template (.xlsx)",
            data=template_bytes,
            file_name="expense_import_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    st.markdown("### Import Source")
    source_mode = st.radio(
        "Source",
        ["Tracker Imports folder", "Upload from device"],
        horizontal=True,
        key="expense_import_source_mode"
    )

    raw_df = None
    read_err = None

    if source_mode == "Tracker Imports folder":
        st.caption(f"Folder: `{LOCAL_IMPORT_DIR}`")
        col_refresh, _ = st.columns([1, 5])
        with col_refresh:
            if st.button("Refresh Folder", key="refresh_local_import_folder"):
                st.rerun()

        local_files, local_err = _list_local_import_files(LOCAL_IMPORT_DIR)
        if local_err:
            st.warning(local_err)
            return
        if not local_files:
            st.info("No `.csv`, `.xlsx`, or `.ods` files found in local Tracker Imports folder.")
            return

        option_map = {}
        labels = []
        for f in local_files:
            modified_text = datetime.datetime.fromtimestamp(f["mtime"]).strftime("%Y-%m-%d %H:%M")
            label = f"{f['name']}  ({_fmt_import_file_size(f['size'])}, {modified_text})"
            option_map[label] = f
            labels.append(label)

        selected_labels = st.multiselect(
            "Select file(s) to import",
            labels,
            default=[labels[0]],
            key="local_import_file_pick"
        )
        if not selected_labels:
            return

        frames = []
        for label in selected_labels:
            file_meta = option_map[label]
            this_df, this_err = _read_expense_import_file(file_meta["path"], source_name=file_meta["name"])
            if this_err:
                st.error(f"{file_meta['name']}: {this_err}")
                return
            if isinstance(this_df, pd.DataFrame) and not this_df.empty:
                frames.append(this_df)

        if not frames:
            st.warning("Selected file(s) have no rows to import.")
            return

        raw_df = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
        st.caption(f"Loaded {len(selected_labels)} file(s) from local folder.")
    else:
        st.caption("Upload one file directly from your phone or laptop.")
        uploaded_file = st.file_uploader(
            "Upload expense file (.csv / .xlsx / .ods)",
            type=["csv", "xlsx", "ods"],
            key="expense_csv_upload",
            label_visibility="collapsed"
        )
        if uploaded_file is None:
            return
        raw_df, read_err = _read_expense_import_file(uploaded_file, source_name=uploaded_file.name)

    if read_err:
        st.error(read_err)
        return

    preview_df, preview_err = _prepare_expense_import_preview(raw_df, cat_to_subs, sub_to_cats, existing_events)
    if preview_err:
        st.error(preview_err)
        return

    st.markdown("### 3) Editable Preview")
    status_counts = preview_df["Status"].value_counts().to_dict()
    st.caption(
        f"Rows: {len(preview_df)} | OK: {status_counts.get('OK', 0)} | Needs Review: {status_counts.get('Needs Review', 0)}"
    )
    st.caption("For events: use `Existing Event` only with `Use Existing`, and `New Event Name` only with `Create New`.")

    all_categories = sorted(cat_to_subs.keys())
    all_subcategories = sorted({s for subs in cat_to_subs.values() for s in subs})
    edited_df = st.data_editor(
        preview_df,
        use_container_width=True,
        hide_index=True,
        disabled=["Status", "Notes"],
        column_config={
            "Event Mode": st.column_config.SelectboxColumn(
                "Event Mode",
                options=["", "Use Existing", "Create New"]
            ),
            "Existing Event": st.column_config.TextColumn("Existing Event"),
            "New Event Name": st.column_config.TextColumn("New Event Name"),
            "Event Start": st.column_config.DateColumn("Event Start"),
            "Event End": st.column_config.DateColumn("Event End"),
            "Date": st.column_config.DateColumn("Date"),
            "Category": st.column_config.SelectboxColumn("Category", options=all_categories),
            "Subcategory": st.column_config.SelectboxColumn("Subcategory", options=all_subcategories),
            "Price": st.column_config.NumberColumn("Price", min_value=0.0, step=1.0),
            "Status": st.column_config.TextColumn("Status"),
            "Notes": st.column_config.TextColumn("Notes"),
        }
    )
    normalized_df, fixed_rows = _normalize_event_columns_for_mode(edited_df)
    if fixed_rows > 0:
        st.caption("Auto-clean on save: fields are aligned by `Event Mode` (Use Existing vs Create New).")

    if st.button("💾 Save Import to Expenses"):
        guard_error_df = _build_event_mode_guard_errors(normalized_df)
        if not guard_error_df.empty:
            st.error("Event mode validation failed. Fix the rows below and try again.")
            st.dataframe(guard_error_df, use_container_width=True, hide_index=True)
            return

        with SessionLocal() as db:
            inserted, merged, error_df = _validate_and_insert_expense_import(db, normalized_df)
        if not error_df.empty:
            st.error("Some rows failed validation. Fix rows and try again.")
            st.dataframe(error_df, use_container_width=True, hide_index=True)
            return

        st.session_state.data_refresh += 1
        if inserted > 0:
            flash(f"Imported {inserted} expense row(s).")
        if merged > 0:
            flash(f"Merged {merged} row group(s) into existing same-day entries.", kind="info")
        st.rerun()

st.markdown(
    """
    <style>
    :root {
        --bg: #000000;
        --panel: #000000;
        --border: #000000;
        --accent: #ffffff;
        --text: #ffffff;
        --muted: #ffffff;
    }

    html, body, .stApp {
        font-family: "Fira Sans", "Noto Sans", "DejaVu Sans", sans-serif;
    }

    .block-container {
        padding-top: 2.2rem;
        padding-bottom: 1.5rem;
    }

    h1, h2, h3, h4 {
        letter-spacing: 0.2px;
    }

    /* ===============================
       BASIC DARK THEME (SAFE)
    =============================== */

    .stApp {
        background-color: #000000 !important;
        color: var(--text);
        background-image: none !important;
    }

    /* Flat panels (no chrome) */
    div[data-testid="metric-container"],
    details,
    section[data-testid="stSidebar"],
    div[data-testid="stDataFrame"],
    div[data-testid="stTable"] {
        background-color: var(--panel);
        border: 1px solid var(--border);
    }

    header[data-testid="stHeader"] {
        background: #000000 !important;
        box-shadow: none !important;
    }

    div[data-testid="stToolbar"] {
        background: #000000 !important;
    }

    /* ===============================
       SIDEBAR
    =============================== */
    section[data-testid="stSidebar"] {
        background-color: #000000;
        border-right: none;
    }
    /* Remove blue focus/selection lines in sidebar */
    section[data-testid="stSidebar"] *:focus,
    section[data-testid="stSidebar"] *:focus-visible {
        outline: none !important;
        box-shadow: none !important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label,
    section[data-testid="stSidebar"] div[role="radiogroup"] label div,
    section[data-testid="stSidebar"] div[data-baseweb="radio"] > div,
    section[data-testid="stSidebar"] div[role="radio"],
    section[data-testid="stSidebar"] div[role="radio"]::before {
        border-left: none !important;
        box-shadow: none !important;
        background: transparent !important;
    }

    /* ===============================
       INPUTS
    =============================== */
    input, textarea, select {
        color: #ffffff;
        border: 1px solid #000000;
        border-radius: 10px;
        background-color: #000000;
    }

    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div,
    div[data-baseweb="datepicker"] > div,
    div[data-baseweb="textarea"] > div,
    div[data-baseweb="multiselect"] > div {
        border: 1px solid #000000;
        border-radius: 10px;
        background-color: #000000;
    }

    input:focus, textarea:focus, select:focus,
    div[data-baseweb="select"] > div:focus-within,
    div[data-baseweb="input"] > div:focus-within,
    div[data-baseweb="datepicker"] > div:focus-within,
    div[data-baseweb="textarea"] > div:focus-within,
    div[data-baseweb="multiselect"] > div:focus-within {
        box-shadow: 0 0 0 2px rgba(111, 176, 255, 0.2);
        border-color: rgba(111, 176, 255, 0.5);
    }

    /* ===============================
       SURFACE PANELS
    =============================== */
    div[data-testid="metric-container"],
    div[data-testid="stDataFrame"],
    div[data-testid="stTable"],
    details,
    div[data-testid="stForm"],
    div[data-testid="stContainer"] {
        border: 1px solid #000000;
        border-radius: 12px;
        background-color: #000000;
        box-shadow: none;
    }

    /* Expander header (flat) */
    div[data-testid="stExpander"] details > summary,
    details > summary {
        border: 1px solid var(--border);
        border-radius: 10px;
        background-color: #0b0b0b;
    }

    /* Dropdown menu (flat) */
    div[data-baseweb="popover"] [role="listbox"],
    div[data-baseweb="popover"] [data-baseweb="menu"] {
        border: 1px solid var(--border);
        border-radius: 10px;
        background-color: #0b0b0b;
        box-shadow: 0 12px 26px rgba(0,0,0,0.6);
    }

    /* ===============================
       BUTTONS
    =============================== */
    button {
        background-color: #000000;
        color: #ffffff;
        border: 1px solid #333333;
        border-radius: 8px;
        padding: 0.35rem 0.85rem;
        transition: transform 0.08s ease, border-color 0.15s ease;
    }

    button:hover {
        background-color: #0b0b0b;
    }

    button:active {
        transform: scale(0.97);
    }

    /* ===============================
       METRICS (POP-IN ANIMATION)
    =============================== */
    div[data-testid="metric-container"] {
        background-color: #000000;
        border: 1px solid var(--border);
        border-radius: 12px;
        box-shadow: 0 6px 18px rgba(0,0,0,0.25);
        animation: metric-pop 0.35s ease-out;
    }

    @keyframes metric-pop {
        from {
            transform: scale(0.96);
            opacity: 0;
        }
        to {
            transform: scale(1);
            opacity: 1;
        }
    }

    /* ===============================
       TABLES / AGGRID
    =============================== */
    .ag-theme-streamlit,
    .ag-root-wrapper {
        background-color: #000000;
        color: #ffffff;
    }

    /* ===============================
       PLOTLY (FADE-IN)
    =============================== */
    .js-plotly-plot,
    .plotly {
        background: #000000;
        animation: fade-in 0.4s ease-in;
    }

    @keyframes fade-in {
        from { opacity: 0; }
        to { opacity: 1; }
    }

    /* ===============================
       EXPANDER OPEN HIGHLIGHT
    =============================== */
    details {
        background: var(--panel);
        padding: 0.25rem 0.25rem 0.5rem 0.25rem;
    }

    details[open] {
        border-left: 2px solid var(--accent);
        padding-left: 6px;
        transition: all 0.2s ease;
    }

    /* ===============================
       SIDEBAR DATE INPUT CLEANUP
    =============================== */
    section[data-testid="stSidebar"] .stDateInput label {
        display: none;
    }

    /* ===============================
       🔒 CRITICAL FIX
       Hide leaked Material icon text
    =============================== */
    section[data-testid="stSidebar"]
    span.material-symbols-outlined::before,
    section[data-testid="stSidebar"]
    span.material-icons::before {
        font-size: 18px !important;
    }

    section[data-testid="stSidebar"]
    span.material-symbols-outlined,
    section[data-testid="stSidebar"]
    span.material-icons {
        font-size: 0 !important;
    }
    /* ===============================
    PAGE TRANSITION (GLOBAL)
    =============================== */
    .stApp > div {
        animation: page-enter 0.35s ease-out;
    }

    @keyframes page-enter {
        from {
            opacity: 0;
            transform: translateY(6px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* ===============================
    SECTION / EXPANDER CONTENT REVEAL
    =============================== */
    details[open] > div {
        animation: reveal 0.25s ease-out;
    }

    @keyframes reveal {
        from {
            opacity: 0;
            transform: translateY(4px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* ===============================
    INPUTS (SELECTBOX / DROPDOWN / DATE)
    =============================== */
    div[data-baseweb="select"],
    div[data-baseweb="input"],
    div[data-baseweb="datepicker"] {
        animation: input-rise 0.25s ease-out;
    }

    @keyframes input-rise {
        from {
            opacity: 0;
            transform: translateY(3px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    /* ===============================
    DIRECTION-AWARE PAGE TRANSITION
    =============================== */

    html[data-nav-direction="right"] .stApp > div {
        animation: slide-from-right 0.35s ease-out;
    }

    html[data-nav-direction="left"] .stApp > div {
        animation: slide-from-left 0.35s ease-out;
    }

    @keyframes slide-from-right {
        from {
            opacity: 0;
            transform: translateX(12px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }

    @keyframes slide-from-left {
        from {
            opacity: 0;
            transform: translateX(-12px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }

    /* ===============================
    SWIPE-LIKE PAGE TRANSITION
    =============================== */
    html[data-nav-direction="right"] .stApp > div {
        animation: swipe-left 0.38s cubic-bezier(.22,.61,.36,1);
    }

    html[data-nav-direction="left"] .stApp > div {
        animation: swipe-right 0.38s cubic-bezier(.22,.61,.36,1);
    }

    @keyframes swipe-left {
        from {
            transform: translateX(100%);
            opacity: 0.6;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes swipe-right {
        from {
            transform: translateX(-100%);
            opacity: 0.6;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    /* ===============================
    ANIMATED BREADCRUMBS
    =============================== */
    .breadcrumb {
        font-size: 14px;
        color: #aaaaaa;
        margin-bottom: 10px;
        animation: crumb-slide 0.3s ease-out;
    }

    .breadcrumb span {
        margin: 0 6px;
        color: #555555;
    }

    @keyframes crumb-slide {
        from {
            opacity: 0;
            transform: translateX(-6px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }
    /* ===============================
    SAFE DROPDOWN ANIMATION (NO JUMP)
    =============================== */

    /* Target only the menu content, NOT the popover root */
    div[data-baseweb="popover"] > div {
        animation: dropdown-fade-slide 0.18s ease-out;
    }

    @keyframes dropdown-fade-slide {
        from {
            opacity: 0;
            transform: translateY(-4px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* ===============================
    JS-DRIVEN REVEAL ANIMATIONS
    =============================== */
    .js-reveal {
        opacity: 0;
        transform: translateY(6px) scale(0.99);
        transition: opacity 0.22s ease-out, transform 0.22s ease-out;
        will-change: opacity, transform;
    }

    .js-reveal.is-visible {
        opacity: 1;
        transform: translateY(0) scale(1);
    }

    .js-reveal[data-anim="pop"] {
        transform: translateY(4px) scale(0.97);
    }

    .js-reveal[data-anim="slide"] {
        transform: translateX(8px);
    }

    .js-reveal[data-anim="fade"] {
        transform: none;
    }

    /* ===============================
       EXTRA UI POLISH
    =============================== */
    .stApp {
        background-image: none !important;
    }

    /* Subtle hover lift for cards/expanders */
    details:hover,
    div[data-testid="metric-container"]:hover,
    div[data-testid="stDataFrame"]:hover,
    div[data-testid="stTable"]:hover {
        transform: translateY(-1px);
        transition: transform 0.12s ease;
    }

    /* Sidebar nav polish */
    section[data-testid="stSidebar"] label {
        padding: 6px 8px;
        border-radius: 8px;
    }
    section[data-testid="stSidebar"] label:hover {
        background: rgba(255,255,255,0.04);
    }

    /* Dataframe zebra striping */
    div[data-testid="stDataFrame"] table tbody tr:nth-child(odd) {
        background: #000000;
    }

    /* Scrollbar styling */
    *::-webkit-scrollbar {
        width: 10px;
        height: 10px;
    }
    *::-webkit-scrollbar-track {
        background: #0a0a0a;
    }
    *::-webkit-scrollbar-thumb {
        background: #2b2b2b;
        border-radius: 10px;
        border: 2px solid #0a0a0a;
    }

    /* Button glow on hover */
    button:hover {
        box-shadow: 0 6px 18px rgba(0,0,0,0.25);
        border-color: rgba(255,255,255,0.2);
    }

    /* Higher contrast text */
    p, li, label, span {
        color: var(--text);
    }

    /* Divider styling */
    hr {
        border: none;
        height: 1px;
        background: #000000;
    }

    /* Headings (no underline accents) */
    h1, h2 {
        position: relative;
        padding-bottom: 0.25rem;
        margin-bottom: 0.6rem;
    }
    h1::after, h2::after {
        content: none !important;
    }

    /* Expander summary styling */
    details > summary {
        font-weight: 600;
        letter-spacing: 0.2px;
        padding: 0.35rem 0.5rem;
        border-radius: 8px;
        background: #000000 !important;
    }
    details > summary:hover {
        background: #000000 !important;
    }

    /* Alerts (info/success/warn/error) */
    div[data-testid="stAlert"] {
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.08);
        background: rgba(255,255,255,0.03);
    }

    /* Caption tone */
    .stCaption, p.stCaption {
        color: var(--muted);
    }

    /* Checkbox/Radio spacing for cleaner layout */
    .stCheckbox, .stRadio {
        padding: 0.15rem 0.2rem;
    }

    /* Dataframe header polish */
    div[data-testid="stDataFrame"] thead tr th {
        background: rgba(255,255,255,0.03);
        color: var(--text);
        font-weight: 600;
        letter-spacing: 0.2px;
    }

    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <script>
    (function () {
      if (!window.__uiAnimObserver) {
        window.__uiAnimObserver = new IntersectionObserver(function(entries) {
          entries.forEach(function(entry) {
            if (entry.isIntersecting) {
              entry.target.classList.add("is-visible");
              window.__uiAnimObserver.unobserve(entry.target);
            }
          });
        }, { threshold: 0.12 });
      }

      const targets = [
        "button",
        "section[data-testid='stSidebar']",
        "div[data-testid='stMetric']",
        "div[data-testid='stMetricValue']",
        "div[data-testid='stDataFrame']",
        ".stDataFrame",
        ".stPlotlyChart",
        ".js-plotly-plot",
        ".stAlert",
        ".stExpander",
        ".stTabs",
        ".stForm",
        ".stDownloadButton",
        "div[data-baseweb='select']",
        "div[data-baseweb='input']",
        "div[data-baseweb='datepicker']",
        "div[data-baseweb='textarea']"
      ];

      function applyReveal() {
        const elements = document.querySelectorAll(targets.join(","));
        let idx = 0;
        elements.forEach(function(el) {
          if (el.dataset.animInit) return;
          el.dataset.animInit = "1";
          el.classList.add("js-reveal");

          const tag = el.tagName.toLowerCase();
          if (tag === "button") el.dataset.anim = "pop";
          else if (el.classList.contains("stPlotlyChart") || el.classList.contains("js-plotly-plot")) el.dataset.anim = "fade";
          else el.dataset.anim = "slide";

          const delay = Math.min(idx, 15) * 18;
          el.style.transitionDelay = delay + "ms";
          window.__uiAnimObserver.observe(el);
          idx += 1;
        });
      }

      applyReveal();

      if (!window.__uiAnimMO) {
        window.__uiAnimMO = new MutationObserver(function() {
          applyReveal();
        });
        window.__uiAnimMO.observe(document.body, { childList: true, subtree: true });
      }
    })();
    </script>
    """,
    unsafe_allow_html=True
)

if "flash_msgs" in st.session_state:
    for msg in st.session_state.flash_msgs:
        if msg["type"] == "success":
            st.success(msg["msg"])
        elif msg["type"] == "error":
            st.error(msg["msg"])
        elif msg["type"] == "info":
            st.info(msg["msg"])
    del st.session_state.flash_msgs

# ==============
# HELPER FUNCTIONS
# ==============
# Render a small section header with caption.
def section(title, desc):
    st.subheader(title)
    st.caption(desc)

# High-quality PNG export for Plotly charts.
def plotly_chart_hi_res(fig, use_container_width=True):
    config = {
        "displaylogo": False,
        "toImageButtonOptions": {
            "format": "png",
            "filename": "chart",
            "scale": 4,
        },
    }
    st.plotly_chart(fig, use_container_width=use_container_width, config=config)

# Render cumulative spend chart.
def cumulative_spend_chart(df):
    with st.expander("📈 Cumulative Spending Curve", expanded=False):
        st.caption(
            "Shows how your total expenses accumulate over time. Useful to detect spending acceleration."
        )

        mode = st.radio(
            "Aggregation Level",
            ["Daily", "Monthly"],
            horizontal=True,
            key="cum_agg"
        )

        data = df.copy()

        if mode == "Monthly":
            data["period"] = data["date"].dt.to_period("M").dt.to_timestamp()
            grp = data.groupby("period", as_index=False)["amount"].sum()
            x = "period"
        else:
            grp = data.groupby("date", as_index=False)["amount"].sum()
            x = "date"

        grp["cumulative"] = grp["amount"].cumsum()

        fig = px.line(grp, x=x, y="cumulative", markers=True)
        fig.update_layout(
            plot_bgcolor="#000000",
            paper_bgcolor="#000000",
            font=dict(color="white"),
            xaxis=dict(gridcolor="#222222"),
            yaxis=dict(gridcolor="#222222")
        )

        plotly_chart_hi_res(fig, use_container_width=True)
    

# Render a clean, aligned calendar view with filters and summary.
def render_calendar_view(df):
    if df.empty:
        st.info("No data available")
        return

    cal_df = df.copy()
    cal_df["date"] = pd.to_datetime(cal_df["date"])

    cal_df["month_start"] = cal_df["date"].dt.to_period("M").dt.to_timestamp()
    month_series = (
        cal_df["month_start"]
        .drop_duplicates()
        .sort_values(ascending=False)
    )
    month_labels = [m.strftime("%b %Y") for m in month_series]
    month_map = {m.strftime("%b %Y"): m for m in month_series}

    c1, c2, c3, c4, c5 = st.columns([2, 2, 3, 2, 2])
    selected_label = c1.selectbox("Month", month_labels, index=0)
    metric_mode = c2.selectbox(
        "Metric",
        ["Total Spend", "Transaction Count", "Average Spend"],
        index=0
    )
    selected_categories = c3.multiselect(
        "Category Filter",
        sorted(cal_df["category"].unique().tolist()),
        default=[]
    )
    week_start = c4.selectbox("Week Starts", ["Monday", "Sunday"], index=0)
    label_mode = c5.selectbox(
        "Labels",
        ["Day + Total", "Day + Total + Metric", "Total (Non-Zero)"],
        index=0
    )

    month_start = month_map[selected_label]
    month_end = (month_start + pd.offsets.MonthEnd(1)).normalize()
    month_mask = (cal_df["date"] >= month_start) & (cal_df["date"] <= month_end)
    month_df = cal_df.loc[month_mask].copy()
    if selected_categories:
        month_df = month_df[month_df["category"].isin(selected_categories)]

    daily = (
        month_df.groupby(month_df["date"].dt.date)["amount"]
        .agg(total="sum", count="size")
        .reset_index()
    )
    daily["avg"] = daily["total"] / daily["count"]
    daily_map = {
        row["date"]: {
            "total": float(row["total"]),
            "count": int(row["count"]),
            "avg": float(row["avg"])
        }
        for _, row in daily.iterrows()
    }

    # Summary metrics
    total_month = float(daily["total"].sum()) if not daily.empty else 0.0
    active_days = int(daily["date"].nunique()) if not daily.empty else 0
    avg_day = (total_month / active_days) if active_days else 0.0
    peak_day_amt = daily["total"].max() if not daily.empty else 0.0
    peak_day_date = daily.loc[daily["total"].idxmax(), "date"] if not daily.empty else None

    m1, m2, m3 = st.columns(3)
    m1.metric("Month Total", f"₹ {total_month:,.2f}")
    m2.metric("Avg Spend / Day", f"₹ {avg_day:,.2f}")
    m3.metric(
        "Peak Day",
        f"₹ {peak_day_amt:,.2f}",
        delta=peak_day_date.strftime("%d %b %Y") if peak_day_date else "—"
    )

    # Build calendar grid with numeric axes for perfect alignment
    firstweekday = 0 if week_start == "Monday" else 6
    cal = calendar.Calendar(firstweekday=firstweekday)
    weeks = cal.monthdayscalendar(month_start.year, month_start.month)

    z = []
    hover = []
    annotations = []
    for r, week in enumerate(weeks):
        row_z = []
        row_hover = []
        for c, day in enumerate(week):
            if day == 0:
                row_z.append(0)
                row_hover.append("")
                continue

            dt = date(month_start.year, month_start.month, day)
            stats = daily_map.get(dt, {"total": 0.0, "count": 0, "avg": 0.0})

            total_label = f"₹{stats['total']:,.0f}"
            if metric_mode == "Total Spend":
                value = stats["total"]
                metric_label = total_label
            elif metric_mode == "Transaction Count":
                value = stats["count"]
                metric_label = f"{int(value)} tx"
            else:
                value = stats["avg"] if stats["count"] else 0.0
                metric_label = f"₹{value:,.0f}"

            row_z.append(value)
            row_hover.append(
                f"{dt.strftime('%d %b %Y')}<br>"
                f"Total: ₹ {stats['total']:,.2f}<br>"
                f"Transactions: {stats['count']}<br>"
                f"Average: ₹ {stats['avg']:,.2f}"
            )

            label = f"{day}<br>{total_label}"
            if label_mode == "Day + Total + Metric" and metric_mode != "Total Spend":
                label = f"{day}<br>{total_label}<br>{metric_label}"
            elif label_mode == "Total (Non-Zero)" and stats["total"] <= 0:
                label = f"{day}"

            annotations.append(
                dict(
                    x=c,
                    y=r,
                    text=label,
                    showarrow=False,
                    font=dict(color="#ffffff", size=12)
                )
            )
        z.append(row_z)
        hover.append(row_hover)

    day_labels = (
        ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        if week_start == "Monday"
        else ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    )

    max_val = float(daily["total"].max()) if not daily.empty else 0.0
    if metric_mode == "Transaction Count" and not daily.empty:
        max_val = float(daily["count"].max())
    if metric_mode == "Average Spend" and not daily.empty:
        max_val = float(daily["avg"].max())
    if max_val <= 0:
        max_val = 1.0

    fig_cal = go.Figure(
        data=go.Heatmap(
            z=z,
            x=list(range(7)),
            y=list(range(len(weeks))),
            hovertext=hover,
            hoverinfo="text",
            hoverongaps=False,
            colorscale=[
                [0.0, "#000000"],
                [1.0, "#000000"],
            ],
            zmin=0,
            zmax=1,
            showscale=False
        )
    )

    fig_cal.update_layout(
        height=420,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(
            tickvals=list(range(7)),
            ticktext=day_labels,
            side="top",
            showgrid=False,
            zeroline=False,
            ticks="",
            showline=False,
            fixedrange=True,
            tickfont=dict(color="#ffffff")
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            ticks="",
            showline=False,
            autorange="reversed",
            fixedrange=True
        ),
        plot_bgcolor="#000000",
        paper_bgcolor="#000000",
        font=dict(color="white"),
        annotations=annotations,
        dragmode=False
    )
    fig_cal.update_traces(
        xgap=1,
        ygap=1,
        hoverlabel=dict(bgcolor="#0f1720", font=dict(color="#e6f2ff"))
    )

    # Improve label contrast on bright cells by adding a dark stroke
    fig_cal.update_annotations(font=dict(color="#ffffff"))

    # Premium layout: calendar + trend + top categories
    cal_left, cal_right = st.columns([2.2, 1.3])
    with cal_left:
        plotly_chart_hi_res(fig_cal, use_container_width=True)
    with cal_right:
        if daily.empty:
            st.info("No activity in this month.")
        else:
            trend = daily.sort_values("date")
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(
                x=trend["date"],
                y=trend["total"],
                mode="lines+markers",
                line=dict(color="#4da3ff", width=3),
                marker=dict(size=6, color="#9ad1ff"),
                name="Daily Spend"
            ))
            fig_trend.update_layout(
                height=200,
                margin=dict(l=10, r=10, t=10, b=10),
                plot_bgcolor="#000000",
                paper_bgcolor="#000000",
                font=dict(color="white"),
                xaxis=dict(title="", showgrid=False),
                yaxis=dict(title="", showgrid=True, gridcolor="#1a1a1a")
            )
            plotly_chart_hi_res(fig_trend, use_container_width=True)

            top_cats = (
                month_df.groupby("category")["amount"].sum()
                .sort_values(ascending=False)
                .head(6)
            )
            if not top_cats.empty:
                fig_top = go.Figure(go.Bar(
                    x=top_cats.values,
                    y=top_cats.index,
                    orientation="h",
                    marker=dict(color="#2c6fa0")
                ))
                fig_top.update_layout(
                    height=220,
                    margin=dict(l=10, r=10, t=10, b=10),
                    plot_bgcolor="#000000",
                    paper_bgcolor="#000000",
                    font=dict(color="white"),
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=False)
                )
                plotly_chart_hi_res(fig_top, use_container_width=True)

    with st.expander("Drilldown Day", expanded=False):
        day_options = sorted(daily["date"].tolist()) if not daily.empty else []
        if day_options:
            selected_day = st.selectbox(
                "Select date",
                day_options,
                format_func=lambda d: d.strftime("%d %b %Y")
            )
            day_rows = month_df[month_df["date"].dt.date == selected_day]
            if not day_rows.empty:
                day_rows = day_rows.sort_values("amount", ascending=False)
                st.dataframe(
                    day_rows[["date", "category", "subcategory", "amount"]],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No transactions for this day.")
        else:
            st.info("No daily data available for drilldown.")


# Handle advanced analytics.
def advanced_analytics(period_df):

    if period_df.empty:
        st.info("No data available for selected period")
        return

    df = period_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    # now call charts
    cumulative_spend_chart(df)


# ======================
# DASHBOARD HELPERS
# ======================
@st.cache_data(show_spinner=False)
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


@st.cache_data(show_spinner=False)
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

# Get price.
def get_price(db, key, default=0.0):
    row = db.query(AssetPrice).filter(AssetPrice.key == key).first()
    return row.value if row else default


# Set price.
def set_price(db, key, value):
    row = db.query(AssetPrice).filter(AssetPrice.key == key).first()
    if row:
        row.value = value
    else:
        db.add(AssetPrice(key=key, value=value))
    db.commit()

# Handle fd current value.
def fd_current_value(principal, rate, deposit_date):
    days = (date.today() - deposit_date).days
    years = max(days, 0) / 365
    return principal * ((1 + rate / 100) ** years)


# Handle fd maturity value.
def fd_maturity_value(principal, rate, tenure_days):
    years = max(float(tenure_days), 0.0) / 365
    return principal * ((1 + rate / 100) ** years)


def fd_get_tenure_days(fd):
    if getattr(fd, "tenure_days", None):
        return max(int(fd.tenure_days), 1)
    return max(int((fd.tenure_months or 1) * 30), 1)

APPLIANCE_IMG_DIR = "appliance_images"
os.makedirs(APPLIANCE_IMG_DIR, exist_ok=True)

# Handle open image.
def open_image(path):
    if not os.path.exists(path):
        st.warning("Image not found")
        return

    system = platform.system()
    if system == "Windows":
        os.startfile(path)
    elif system == "Darwin":
        subprocess.run(["open", path])
    else:
        subprocess.run(["xdg-open", path])

# Handle black page.
def black_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(colors.black)
    canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], stroke=0, fill=1)
    canvas.restoreState()

# Handle is edit mode.
def is_edit_mode(aid):
    return st.session_state.get(f"edit_mode_{aid}", False)


# ==============
# ADD EXPENSE
# ==============
# Add expense.
def add_expense():
    st.markdown("## <span>➕</span> Add Expense", unsafe_allow_html=True)
    with SessionLocal() as db:
        # =================
        # ADD EXPENSE ENTRY
        # =================
        cats = db.query(Category).all()
        if not cats:
            st.warning("Please add categories first")
            return
        col1, col2 = st.columns(2)

        with col1:
            cat_name = st.selectbox(
                "Category",
                [c.name for c in cats],
                key="add_cat"
            )

        cat = db.query(Category).filter_by(name=cat_name).first()
        if not cat:
            st.warning("Invalid category")
            return

        subs = db.query(SubCategory).filter_by(category_id=cat.id).all()
        if not subs:
            st.info("Please add subcategories first")
            return

        with col2:
            sub_name = st.selectbox(
                "Subcategory",
                [s.name for s in subs],
                key="add_sub"
            )

        sub = db.query(SubCategory).filter_by(
            name=sub_name,
            category_id=cat.id
        ).first()
        d = st.date_input("Date", value=date.today())
        amt = st.number_input("Amount (₹)", min_value=0.0)
        is_travel = st.toggle("Events", value=False)
        trip_name = None
        trip_start = None
        trip_end = None
        if is_travel:
            existing_events = load_event_list(st.session_state.data_refresh)
            event_mode = st.radio(
                "Event",
                ["Use Existing", "Create New"],
                horizontal=True,
                index=0 if existing_events else 1
            )
            if event_mode == "Use Existing":
                if not existing_events:
                    st.info("No existing events found. Create a new one below.")
                    event_mode = "Create New"
                else:
                    event_labels = []
                    event_map = {}
                    for name, start, end in existing_events:
                        label = f"{name} | {start} → {end}"
                        event_labels.append(label)
                        event_map[label] = (name, start, end)
                    selected_event = st.selectbox("Select Event", event_labels)
                    trip_name, trip_start, trip_end = event_map[selected_event]
            if event_mode == "Create New":
                trip_name = st.text_input("Event Name", placeholder="")
                trip_mode = st.radio(
                    "Event Duration",
                    ["Single Day", "Multiple Days"],
                    horizontal=True,
                    index=0
                )
                if trip_mode == "Single Day":
                    single_day = st.date_input("Event Date", value=date.today())
                    trip_start, trip_end = single_day, single_day
                else:
                    trip_start, trip_end = st.date_input(
                        "Event Date Range",
                        value=[date.today(), date.today()]
                    )
        if st.button("Add Expense"):
            if amt > 0:
                if is_travel and (not trip_name or not trip_start or not trip_end):
                    st.error("Please enter event name and dates")
                    return
                action, _ = _add_or_merge_expense(
                    db=db,
                    category_id=cat.id,
                    subcategory_id=sub.id,
                    entry_date=d,
                    amount=amt,
                    travel=1 if is_travel else 0,
                    trip_name=trip_name if is_travel else None,
                    trip_start=trip_start if is_travel else None,
                    trip_end=trip_end if is_travel else None
                )
                db.commit()
                st.session_state.data_refresh += 1
                if action == "merged":
                    flash("Added to existing same-day entry ✅")
                else:
                    flash("Expense added ✅")
                st.rerun()
            else:
                st.error("Amount must be greater than 0")
        
    st.divider()
    with st.expander("🔍 Filter Expense Entries (Edit / Delete)"):
        manage_entries()
    with st.expander("⚙️ Advanced (Expense Category Management)"):
        manage_categories()



# ============
# ADD INCOME
# ============
# Handle income section.
def income_section():
    with SessionLocal() as db:
        # ================
        # ADD INCOME ENTRY
        # ================
        cats = db.query(IncomeCategory).all()
        if not cats:
            st.warning("No income categories found. Use Advanced section to add.")
            cats = []
        st.subheader("➕ Add Income")

        if cats:
            col1, col2 = st.columns(2)

            with col1:
                cat_name = st.selectbox(
                    "Select Income Category",
                    [c.name for c in cats],
                    key="add_income_cat"
                )

            cat = db.query(IncomeCategory).filter_by(name=cat_name).first()

            subs = db.query(IncomeSubCategory).filter_by(
                category_id=cat.id
            ).all()

            with col2:
                if not subs:
                    st.info("Add income subcategories first (Advanced section)")
                    sub = None
                else:
                    sub_name = st.selectbox(
                        "Select Income Subcategory",
                        [s.name for s in subs],
                        key="add_income_sub"
                    )
                    sub = db.query(IncomeSubCategory).filter_by(
                        name=sub_name,
                        category_id=cat.id
                    ).first()
        else:
            sub = None


   
        # ======    
        # INPUTS
        # ======
        d = st.date_input("Date", value=date.today())
        amt = st.number_input("Amount (₹)", min_value=0.0)
        if st.button("Add Income"):
            if not cats:
                st.error("Add an income category first")
            elif sub is None:
                st.error("Please select a subcategory")
            elif amt <= 0:
                st.error("Amount must be greater than 0")
            else:
                db.add(Income(
                    category_id=cat.id,
                    subcategory_id=sub.id,
                    date=d,
                    amount=amt
                ))
                db.commit()
                st.session_state.data_refresh += 1
                flash("Income added ✅")
                st.rerun()
        # =================
        # INCOME DASHBOARD
        # =================
        st.divider()
        df = load_income_data(st.session_state.data_refresh).copy()
        if df.empty:
            st.info("No income data available")
            return
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values(["date", "id"], ascending=[False, False]).reset_index(drop=True)
        # =================
        # PERIOD FILTER
        # =================
        st.subheader("📅 Period Filter")
        period_mode = st.radio(
            "Filter income by",
            ["Monthly", "Yearly", "Custom"],
            horizontal=True
        )
        today = pd.Timestamp.today().normalize()
        if period_mode == "Monthly":
            months = sorted(df["date"].dt.to_period("M").unique())
            labels = [m.strftime("%b %Y") for m in months]
            current_period = today.to_period("M")
            default_index = (
                months.index(current_period)
                if current_period in months
                else len(months) - 1
            )
            sel = st.selectbox(
                "Select Month",
                labels,
                index=default_index
            )
            sel_period = months[labels.index(sel)]
            start = sel_period.to_timestamp()
            end = (sel_period + 1).to_timestamp() - pd.Timedelta(seconds=1)
        elif period_mode == "Yearly":
            years = sorted(df["date"].dt.year.unique())
            year = st.selectbox("Select Year", years)
            start = pd.Timestamp(year=year, month=1, day=1)
            end = pd.Timestamp(year=year, month=12, day=31)
        else:
            start, end = st.date_input(
                "Select date range",
                [today.replace(day=1).date(), today.date()]
            )
            start = pd.to_datetime(start)
            end = pd.to_datetime(end)
        period_df = df[df["date"].between(start, end)]
        period_df = period_df.sort_values(["date", "id"], ascending=[False, False]).reset_index(drop=True)
        # ========================
        # INCOME SUMMARY + VISUALS
        # ========================
        st.subheader("📊 Income Summary")
        total_income = period_df["amount"].sum()
        total_expense = (
            db.query(func.sum(Expense.amount))
            .filter(Expense.date.between(
                start.date(), end.date()
            ))
            .scalar()
        ) or 0
        net_balance = total_income - total_expense
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Income", f"₹ {total_income:,.2f}")
        c2.metric("Total Expense", f"₹ {total_expense:,.2f}")
        c3.metric(
            "Net Balance",
            f"₹ {net_balance:,.2f}",
            delta="Surplus" if net_balance >= 0 else "Deficit"
        )
        # =====================
        # INCOME VISUALIZATIONS
        # =====================
        st.subheader("📈 Income Breakdown")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**By Category**")
            cat_pie = period_df.groupby("category", as_index=False)["amount"].sum()
            if not cat_pie.empty:
                fig_cat = px.pie(cat_pie, names="category", values="amount", hole=0.4)
                fig_cat.update_layout(paper_bgcolor="#000", font=dict(color="#fff"))
                fig_cat.update_traces(marker=dict(line=dict(color="black", width=2)))
                plotly_chart_hi_res(fig_cat, use_container_width=True)

        with col2:
            st.markdown("**By Subcategory**")
            sub_pie = period_df.groupby("subcategory", as_index=False)["amount"].sum()
            if not sub_pie.empty:
                fig_sub = px.pie(sub_pie, names="subcategory", values="amount", hole=0.4)
                fig_sub.update_layout(paper_bgcolor="#000", font=dict(color="#fff"))
                fig_sub.update_traces(marker=dict(line=dict(color="black", width=2)))
                plotly_chart_hi_res(fig_sub, use_container_width=True)

        # =====================
        # MANAGE INCOME ENTRIES
        # =====================
        st.divider()
        with st.expander("🔍 Filter Income Entries (Edit / Delete)"):
            f_cat = st.selectbox(
                "Filter by Category",
                ["All"] + sorted(period_df["category"].unique())
            )
            if f_cat != "All":
                f_sub_options = period_df[period_df["category"] == f_cat]["subcategory"].unique()
            else:
                f_sub_options = period_df["subcategory"].unique()
            f_sub = st.selectbox(
                "Filter by Subcategory",
                ["All"] + sorted(f_sub_options)
            )
            filtered_df = period_df.copy()
            if f_cat != "All":
                filtered_df = filtered_df[filtered_df["category"] == f_cat]
            if f_sub != "All":
                filtered_df = filtered_df[filtered_df["subcategory"] == f_sub]
            filtered_df = filtered_df.sort_values(["date", "id"], ascending=[False, False]).reset_index(drop=True)
            if filtered_df.empty:
                st.info("No income entries found")
                return
            action_mode = st.radio(
                "Action",
                ["Edit Income Entries", "Delete Income Entries"],
                horizontal=True
            )
            if action_mode == "Edit Income Entries":
                all_cats = [c.name for c in db.query(IncomeCategory).all()]
                all_subs = [s.name for s in db.query(IncomeSubCategory).all()]
                edit_df = filtered_df.set_index("id")
                edited_df = st.data_editor(
                    edit_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "date": st.column_config.DateColumn("Date"),
                        "amount": st.column_config.NumberColumn("Amount", min_value=0),
                        "category": st.column_config.SelectboxColumn("Category", options=all_cats),
                        "subcategory": st.column_config.SelectboxColumn("Subcategory", options=all_subs),
                    }
                )
                if st.button("💾 Save Income Changes"):
                    with db.no_autoflush:
                        for row_id, row in edited_df.iterrows():
                            inc = db.get(Income, int(row_id))
                            if not inc:
                                continue
                            inc.date = pd.to_datetime(row["date"]).date()
                            inc.amount = float(row["amount"])
                            cat_obj = db.query(IncomeCategory).filter_by(
                                name=row["category"]
                            ).first()
                            if not cat_obj:
                                continue
                            sub_obj = db.query(IncomeSubCategory).filter_by(
                                name=row["subcategory"],
                                category_id=cat_obj.id
                            ).first()
                            if not sub_obj:
                                st.warning(
                                    f"Subcategory '{row['subcategory']}' does not belong to '{row['category']}'"
                                )
                                continue
                            inc.category_id = cat_obj.id
                            inc.subcategory_id = sub_obj.id
                    db.commit()
                    st.session_state.data_refresh += 1
                    flash("Income entries updated successfully")
                    st.rerun()
            elif action_mode == "Delete Income Entries":
                del_df = filtered_df.copy()
                del_df["date"] = pd.to_datetime(del_df["date"]).dt.strftime("%Y-%m-%d")
                gb = GridOptionsBuilder.from_dataframe(del_df)
                gb.configure_column(
                    "date",
                    checkboxSelection=True,
                    headerCheckboxSelection=True,
                    sort="desc",
                    sortIndex=0
                )
                gb.configure_column("id", hide=True, sort="desc", sortIndex=1)
                gb.configure_grid_options(rowSelection="multiple", suppressRowClickSelection=True)
                grid = AgGrid(
                    del_df,
                    gridOptions=gb.build(),
                    update_mode=GridUpdateMode.MODEL_CHANGED,
                    fit_columns_on_grid_load=True
                )
                selected = pd.DataFrame(grid["selected_rows"])
                if not selected.empty:
                    st.warning(f"Selected rows: {len(selected)}")
                    if st.checkbox("Confirm delete selected income"):
                        if st.button("❌ Delete Selected Income"):
                            for _, row in selected.iterrows():
                                inc = db.get(Income, int(row["id"]))
                                if inc:
                                    db.delete(inc)
                            db.commit()
                            st.session_state.data_refresh += 1
                            flash("Selected income entries deleted")
                            st.rerun()
        # ===================================
        # ADVANCED INCOME CATEGORY MANAGEMENT
        # ===================================
        with st.expander("⚙️ Advanced (Income Category Management)"):
            st.caption("Use tabs below to navigate quickly.")

            st.subheader("➕ Add Income Category")
            new_cat = st.text_input(
                "New Income Category",
                placeholder="e.g. Salary, Freelance",
                key="adv_add_income_cat"
            )
            if st.button("Add Income Category", key="adv_add_income_cat_btn"):
                if not new_cat.strip():
                    st.error("Category name cannot be empty")
                elif db.query(IncomeCategory).filter_by(name=new_cat.strip()).first():
                    st.warning("Income category already exists")
                else:
                    db.add(IncomeCategory(name=new_cat.strip()))
                    db.commit()
                    st.session_state.data_refresh += 1
                    flash("Income category added")
                    st.rerun()
            income_cats = db.query(IncomeCategory).all()
            if not income_cats:
                st.info("No income categories available")
                st.stop()

            tab_add_sub, tab_rename, tab_delete = st.tabs([
                "➕ Add Subcategory",
                "✏️ Rename",
                "🗑 Delete"
            ])

            with tab_add_sub:
                st.subheader("➕ Add Income Subcategory")
                parent_cat_name = st.selectbox(
                    "Select Parent Category",
                    [c.name for c in income_cats],
                    key="adv_add_income_sub_parent"
                )
                parent_cat = db.query(IncomeCategory).filter_by(
                    name=parent_cat_name
                ).first()
                new_sub = st.text_input(
                    "New Income Subcategory",
                    placeholder="e.g. Monthly Salary, Bonus",
                    key="adv_add_income_sub"
                )
                if st.button("Add Income Subcategory", key="adv_add_income_sub_btn"):
                    if not new_sub.strip():
                        st.error("Subcategory name cannot be empty")
                    elif db.query(IncomeSubCategory).filter_by(
                        name=new_sub.strip(),
                        category_id=parent_cat.id
                    ).first():
                        st.warning("Subcategory already exists in this category")
                    else:
                        db.add(
                            IncomeSubCategory(
                                name=new_sub.strip(),
                                category_id=parent_cat.id
                            )
                        )
                        db.commit()
                        st.session_state.data_refresh += 1
                        flash("Income subcategory added")
                        st.rerun()

            with tab_rename:
                st.subheader("✏️ Rename Income Category")
                sel_cat_name = st.selectbox(
                    "Select Income Category",
                    [c.name for c in income_cats],
                    key="adv_rename_income_cat_select"
                )
                sel_cat = db.query(IncomeCategory).filter_by(name=sel_cat_name).first()
                new_cat_name = st.text_input(
                    "New Category Name",
                    value=sel_cat.name,
                    key="adv_rename_income_cat"
                )
                if st.button("Update Category Name", key="adv_rename_income_cat_btn"):
                    if new_cat_name.strip() and new_cat_name != sel_cat.name:
                        if db.query(IncomeCategory).filter_by(name=new_cat_name).first():
                            st.error("Category name already exists")
                        else:
                            sel_cat.name = new_cat_name.strip()
                            db.commit()
                            st.session_state.data_refresh += 1
                            flash("Income category renamed")
                            st.rerun()

                st.divider()
                st.subheader("✏️ Rename Income Subcategory")
                income_subs = db.query(IncomeSubCategory).filter_by(
                    category_id=sel_cat.id
                ).all()
                if income_subs:
                    sub_name = st.selectbox(
                        "Select Subcategory",
                        [s.name for s in income_subs],
                        key="adv_rename_income_sub_select"
                    )
                    sub_obj = db.query(IncomeSubCategory).filter_by(
                        name=sub_name,
                        category_id=sel_cat.id
                    ).first()
                    new_sub_name = st.text_input(
                        "New Subcategory Name",
                        value=sub_name,
                        key="adv_rename_income_sub"
                    )
                    if st.button("Update Subcategory Name", key="adv_rename_income_sub_btn"):
                        if db.query(IncomeSubCategory).filter_by(
                            name=new_sub_name,
                            category_id=sel_cat.id
                        ).first():
                            st.error("Subcategory already exists")
                        else:
                            sub_obj.name = new_sub_name.strip()
                            db.commit()
                            st.session_state.data_refresh += 1
                            flash("Income subcategory renamed")
                            st.rerun()
                else:
                    st.info("No subcategories available")

            with tab_delete:
                st.subheader("🗑 Delete Income Subcategory")
                st.warning("Deletes ALL income under this subcategory")
                del_parent_name = st.selectbox(
                    "Select Parent Category",
                    [c.name for c in income_cats],
                    key="adv_delete_income_sub_parent"
                )
                del_parent = db.query(IncomeCategory).filter_by(name=del_parent_name).first()
                del_income_subs = db.query(IncomeSubCategory).filter_by(
                    category_id=del_parent.id
                ).all()
                if del_income_subs:
                    del_sub_name = st.selectbox(
                        "Select Subcategory to Delete",
                        [s.name for s in del_income_subs],
                        key="adv_delete_income_sub_select"
                    )
                    del_sub = db.query(IncomeSubCategory).filter_by(
                        name=del_sub_name,
                        category_id=del_parent.id
                    ).first()
                    if st.checkbox("Confirm delete income subcategory", key="adv_confirm_del_sub"):
                        if st.button("❌ Delete Income Subcategory", key="adv_delete_income_sub_btn"):
                            db.query(Income).filter(
                                Income.subcategory_id == del_sub.id
                            ).delete()
                            db.delete(del_sub)
                            db.commit()
                            st.session_state.data_refresh += 1
                            flash("Income subcategory deleted")
                            st.rerun()
                else:
                    st.info("No subcategories available for this category")

                st.divider()
                st.subheader("🗑 Delete Income Category (Danger)")
                st.warning("Deletes ALL subcategories and ALL income under this category")
                del_cat_name = st.selectbox(
                    "Select Income Category to Delete",
                    [c.name for c in income_cats],
                    key="adv_delete_income_cat_select"
                )
                del_cat = db.query(IncomeCategory).filter_by(name=del_cat_name).first()
                st.info(f"You are about to delete: **{del_cat.name}**")
                if st.checkbox("I understand and want to delete this income category", key="adv_confirm_del_cat"):
                    if st.button("❌ Delete Income Category", key="adv_delete_income_cat_btn"):
                        db.query(Income).filter(
                            Income.category_id == del_cat.id
                        ).delete()
                        db.query(IncomeSubCategory).filter(
                            IncomeSubCategory.category_id == del_cat.id
                        ).delete()
                        db.delete(del_cat)
                        db.commit()
                        st.session_state.data_refresh += 1
                        flash(f"Income category '{del_cat.name}' deleted")
                        st.rerun()

        # =====================================================
        # 📄 INCOME PDF EXPORT (ADVANCED – BLACK THEME)
        # =====================================================
        with st.expander("⬇️ Export Income to PDF", expanded=False):

            # -------------------------------
            # LOAD FULL INCOME DATA
            # -------------------------------
            income_df = pd.DataFrame(
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
                .all(),
                columns=["ID", "date", "amount", "category", "subcategory"]
            )

            if income_df.empty:
                st.info("No income data available for export.")
                st.stop()

            income_df["date"] = pd.to_datetime(income_df["date"])

            # -------------------------------
            # FILTERS
            # -------------------------------
            st.markdown("### 🔍 Filters")

            c1, c2, c3 = st.columns(3)

            with c1:
                period_type = st.selectbox(
                    "Period Type",
                    ["All", "Monthly", "Yearly", "Custom Range"]
                )

            with c2:
                categories = ["All"] + sorted(income_df["category"].unique())
                sel_category = st.selectbox("Category", categories)

            with c3:
                if sel_category == "All":
                    subcats = ["All"]
                else:
                    subcats = ["All"] + sorted(
                        income_df[income_df["category"] == sel_category]["subcategory"].unique()
                    )
                sel_subcategory = st.selectbox("Subcategory", subcats)

            today = datetime.date.today()

            if period_type == "Monthly":
                months = sorted(income_df["date"].dt.to_period("M").unique())
                month_labels = [m.strftime("%b %Y") for m in months]
                sel_month = st.selectbox("Select Month", month_labels)
                period = months[month_labels.index(sel_month)]
                start_date = period.to_timestamp()
                end_date = (period + 1).to_timestamp() - pd.Timedelta(seconds=1)

            elif period_type == "Yearly":
                years = sorted(income_df["date"].dt.year.unique())
                sel_year = st.selectbox("Select Year", years)
                start_date = pd.Timestamp(sel_year, 1, 1)
                end_date = pd.Timestamp(sel_year, 12, 31)

            elif period_type == "Custom Range":
                start_date, end_date = st.date_input(
                    "Date Range",
                    [today.replace(day=1), today]
                )
                start_date = pd.to_datetime(start_date)
                end_date = pd.to_datetime(end_date)

            else:
                start_date = income_df["date"].min()
                end_date = income_df["date"].max()

            # -------------------------------
            # APPLY FILTERS
            # -------------------------------
            fdf = income_df[income_df["date"].between(start_date, end_date)]
            fdf = fdf.sort_values("date", ascending=False)

            if sel_category != "All":
                fdf = fdf[fdf["category"] == sel_category]

            if sel_subcategory != "All":
                fdf = fdf[fdf["subcategory"] == sel_subcategory]

            if fdf.empty:
                st.warning("No income found for selected filters.")
                st.stop()

            # -------------------------------
            # GENERATE PDF
            # -------------------------------
            if st.button("🧾 Generate Income PDF Report"):

                buffer = BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=A4)
                styles = getSampleStyleSheet()
                styles.add(ParagraphStyle(
                    name="WhiteNormal",
                    fontName="DejaVu",
                    fontSize=10,
                    textColor=colors.white
                ))
                styles.add(ParagraphStyle(
                    name="WhiteHeading",
                    fontName="DejaVu",
                    fontSize=14,
                    textColor=colors.white,
                    spaceAfter=10
                ))
                styles.add(ParagraphStyle(
                    name="WhiteTitle",
                    fontName="DejaVu",
                    fontSize=18,
                    textColor=colors.white,
                    spaceAfter=14
                ))

                story = []
                story.append(Paragraph(
                    f"""
                    Period: {start_date.date()} → {end_date.date()}<br/>
                    Category: {sel_category}<br/>
                    Subcategory: {sel_subcategory}
                    """,
                    styles["WhiteNormal"]
                ))
                story.append(Spacer(1, 12))

                # ---------- TITLE ----------
                story.append(Paragraph("Income Report", styles["WhiteTitle"]))
                story.append(Paragraph(
                    f"Generated on: {datetime.date.today()}",
                    styles["WhiteNormal"]
                ))
                story.append(Spacer(1, 12))

                # ---------- TABLE ----------
                fdf["date"] = fdf["date"].dt.strftime("%Y-%m-%d")
                fdf["amount"] = fdf["amount"].round(2)
                total_income = fdf["amount"].sum()
                table_data = [list(fdf.columns)] + fdf.values.tolist()
                table_data.append(["", "", "", "TOTAL", f"{total_income:,.2f}"])

                table = Table(table_data, repeatRows=1)
                table.setStyle(TableStyle([
                    ("FONT", (0,0), (-1,-1), "DejaVu"),
                    ("BACKGROUND", (0,0), (-1,0), colors.black),
                    ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                    ("BACKGROUND", (0,1), (-1,-2), colors.black),
                    ("TEXTCOLOR", (0,1), (-1,-1), colors.white),
                    ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                    ("BACKGROUND", (-2,-1), (-1,-1), colors.black),
                ]))

                story.append(table)
                story.append(Spacer(1, 20))
                story.append(Paragraph(
                    f"GRAND TOTAL INCOME: ₹ {total_income:,.2f}",
                    styles["WhiteHeading"]
                ))

                # ---------- BLACK PAGE BACKGROUND ----------
                def black_bg(canvas, doc):
                    canvas.saveState()
                    canvas.setFillColor(colors.black)
                    canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1)
                    canvas.restoreState()

                doc.build(
                    story,
                    onFirstPage=black_bg,
                    onLaterPages=black_bg
                )

                file_name = f"income_report_{start_date.date()}_{end_date.date()}.pdf"

                st.download_button(
                    "⬇️ Download Income PDF",
                    data=buffer.getvalue(),
                    file_name=file_name,
                    mime="application/pdf"
                )

                st.download_button(
                    "⬇️ Download CSV",
                    data=fdf.to_csv(index=False),
                    file_name="income_report.csv",
                    mime="text/csv"
                )

# ====================
# MANAGE CATEGORIES
# ====================
# Handle manage categories.
def manage_categories():
    st.title("📂 Manage Categories")
    with SessionLocal() as db:
        st.subheader("➕ Add New Category")
        new_cat = st.text_input(
            "Category Name",
            placeholder="e.g. Transport"
        )
        if st.button("Add Category"):
            if not new_cat.strip():
                st.error("Category name cannot be empty")
            elif db.query(Category).filter_by(name=new_cat.strip()).first():
                st.warning("Category already exists")
            else:
                db.add(Category(name=new_cat.strip()))
                db.commit()
                st.session_state.data_refresh += 1
                flash("Category added")
                st.rerun()

        st.divider()
        cats = db.query(Category).all()
        if not cats:
            st.info("No categories available")
            return

        st.subheader("📁 Select Category")
        selected_cat_name = st.selectbox(
            "Choose a category to manage",
            [c.name for c in cats]
        )
        cat = db.query(Category).filter_by(name=selected_cat_name).first()
        subs = db.query(SubCategory).filter_by(category_id=cat.id).all()

        st.caption("Use tabs below to navigate quickly.")
        tab_category, tab_subcategory, tab_danger = st.tabs([
            "🏷️ Category",
            "🗂️ Subcategories",
            "⚠️ Danger Zone"
        ])

        with tab_category:
            st.subheader("✏️ Rename Category")
            new_cat_name = st.text_input(
                "New Category Name",
                value=cat.name
            )
            if st.button("Update Category Name"):
                if not new_cat_name.strip():
                    st.error("Category name cannot be empty")
                elif new_cat_name != cat.name and db.query(Category).filter_by(name=new_cat_name).first():
                    st.error("Category name already exists")
                else:
                    cat.name = new_cat_name.strip()
                    db.commit()
                    st.session_state.data_refresh += 1
                    flash("Category renamed")
                    st.rerun()

        with tab_subcategory:
            st.subheader("➕ Add Subcategory")
            new_sub = st.text_input(
                "Add New Subcategory",
                placeholder="e.g. Bus, Fuel"
            )
            if st.button("Add Subcategory"):
                if not new_sub.strip():
                    st.error("Subcategory name cannot be empty")
                elif db.query(SubCategory).filter_by(
                    name=new_sub.strip(),
                    category_id=cat.id
                ).first():
                    st.warning("Subcategory already exists in this category")
                else:
                    db.add(SubCategory(name=new_sub.strip(), category_id=cat.id))
                    db.commit()
                    st.session_state.data_refresh += 1
                    flash("Subcategory added")
                    st.rerun()

            if not subs:
                st.info("No subcategories available")
            else:
                st.divider()
                st.subheader("✏️ Rename Subcategory")
                sub_to_rename = st.selectbox(
                    "Select Subcategory",
                    [s.name for s in subs],
                    key="rename_sub"
                )
                sub_obj = db.query(SubCategory).filter_by(
                    name=sub_to_rename,
                    category_id=cat.id
                ).first()
                new_sub_name = st.text_input(
                    "New Subcategory Name",
                    value=sub_to_rename
                )
                if st.button("Update Subcategory Name"):
                    if not new_sub_name.strip():
                        st.error("Subcategory name cannot be empty")
                    elif db.query(SubCategory).filter_by(
                        name=new_sub_name,
                        category_id=cat.id
                    ).first():
                        st.error("Subcategory already exists in this category")
                    else:
                        sub_obj.name = new_sub_name.strip()
                        db.commit()
                        st.session_state.data_refresh += 1
                        flash("Subcategory renamed")
                        st.rerun()

                st.divider()
                st.subheader("🔀 Move Subcategory")
                sub_to_move = st.selectbox(
                    "Subcategory to Move",
                    [s.name for s in subs],
                    key="move_sub"
                )
                target_options = [c.name for c in cats if c.id != cat.id]
                if not target_options:
                    st.info("Create another category to enable moving subcategories.")
                else:
                    target_cat_name = st.selectbox(
                        "Move To Category",
                        target_options,
                        key="target_cat"
                    )
                    target_cat = db.query(Category).filter_by(name=target_cat_name).first()
                    sub_obj = db.query(SubCategory).filter_by(
                        name=sub_to_move,
                        category_id=cat.id
                    ).first()
                    if st.button("Move Subcategory"):
                        exists = db.query(SubCategory).filter_by(
                            name=sub_obj.name,
                            category_id=target_cat.id
                        ).first()
                        if exists:
                            st.error("Subcategory already exists in target category")
                        else:
                            sub_obj.category_id = target_cat.id
                            db.query(Expense).filter(
                                Expense.subcategory_id == sub_obj.id
                            ).update(
                                {"category_id": target_cat.id},
                                synchronize_session=False
                            )
                            db.commit()
                            st.session_state.data_refresh += 1
                            flash(
                                f"'{sub_obj.name}' moved to '{target_cat.name}' "
                                "and past expenses updated"
                            )
                            st.rerun()

        with tab_danger:
            st.warning("These actions are irreversible")
            st.subheader("🗑 Delete Subcategory")
            if not subs:
                st.info("No subcategories available")
            else:
                del_sub = st.selectbox(
                    "Subcategory to Delete",
                    [s.name for s in subs],
                    key="del_sub"
                )
                if st.checkbox("Confirm delete subcategory"):
                    if st.button("❌ Delete Subcategory"):
                        sub = db.query(SubCategory).filter_by(
                            name=del_sub,
                            category_id=cat.id
                        ).first()
                        db.query(Expense).filter_by(
                            subcategory_id=sub.id
                        ).delete()
                        db.delete(sub)
                        db.commit()
                        st.session_state.data_refresh += 1
                        flash("Subcategory deleted")
                        st.rerun()

            st.divider()
            st.subheader("🗑 Delete Category")
            st.info(f"Selected category: **{cat.name}**")
            if st.checkbox("I understand this will delete ALL related data"):
                if st.button("❌ Delete Category"):
                    db.query(Expense).filter_by(category_id=cat.id).delete()
                    db.query(SubCategory).filter_by(category_id=cat.id).delete()
                    db.delete(cat)
                    db.commit()
                    st.session_state.data_refresh += 1
                    flash("Category deleted")
                    st.rerun()

# ===============
# MANAGE ENTRIES
# ===============
# Handle manage entries.
def manage_entries():
    st.title("🧾 Manage Entries")
    with SessionLocal() as db:
        cats = db.query(Category).all()
        cat_names = ["All"] + [c.name for c in cats]
        sel_cat = st.selectbox("Category", cat_names)
        sub_names = ["All"]
        if sel_cat != "All":
            cat_obj = db.query(Category).filter_by(name=sel_cat).first()
            sub_names += [
                s.name for s in db.query(SubCategory).filter_by(category_id=cat_obj.id)
            ]
        sel_sub = st.selectbox("Subcategory", sub_names)
        date_mode = st.radio(
            "Date filter",
            ["Weekly", "Monthly", "Yearly", "Custom"],
            horizontal=True
        )
        today = date.today()
        if date_mode == "Monthly":
            months = (
                db.query(func.strftime("%Y-%m", Expense.date))
                .distinct()
                .order_by(func.strftime("%Y-%m", Expense.date))
                .all()
            )
            if not months:
                st.info("No data available")
                return
            month_map = {
                pd.to_datetime(m[0] + "-01").strftime("%b %Y"):
                pd.to_datetime(m[0] + "-01")
                for m in months
            }
            label = st.selectbox("Select Month", list(month_map.keys()))
            start = month_map[label]
            end = start + pd.offsets.MonthEnd(1)
        elif date_mode == "Yearly":
            years = sorted({int(y[0]) for y in db.query(func.strftime("%Y", Expense.date)).all()})
            if not years:
                st.info("No data available")
                return
            year = st.selectbox("Select Year", years)
            start = pd.Timestamp(year=year, month=1, day=1)
            end = pd.Timestamp(year=year, month=12, day=31)
        elif date_mode == "Weekly":
            option = st.selectbox(
                "Select period",
                ["Last 1 Week", "Last 4 Weeks", "Last 8 Weeks", "Last 12 Weeks"]
            )
            days_map = {
                "Last 1 Week": 7,
                "Last 4 Weeks": 28,
                "Last 8 Weeks": 56,
                "Last 12 Weeks": 84
            }
            end = today
            start = end - timedelta(days=days_map[option])
        else:
            start, end = st.date_input(
                "Select date range",
                [today.replace(day=1), today]
            )
        q = (
            db.query(
                Expense.id,
                Expense.date,
                Category.name.label("category"),
                SubCategory.name.label("subcategory"),
                Expense.amount
            )
            .join(Category, Expense.category_id == Category.id)
            .join(SubCategory, Expense.subcategory_id == SubCategory.id)
            .filter(Expense.date.between(start, end))
            .order_by(Expense.date.desc(), Expense.id.desc())
        )
        if sel_cat != "All":
            q = q.filter(Category.name == sel_cat)
        if sel_sub != "All":
            q = q.filter(SubCategory.name == sel_sub)

        df = pd.DataFrame(q.all(), columns=["id", "date", "category", "subcategory", "amount"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values(["date", "id"], ascending=[False, False]).reset_index(drop=True)
        if df.empty:
            st.info("No entries found")
            return
        action_mode = st.radio(
            "Action",
            ["Edit Entries", "Delete Entries"],
            horizontal=True
        )
        if action_mode == "Edit Entries":
            all_cats = [c.name for c in db.query(Category).all()]
            all_subs = [s.name for s in db.query(SubCategory).all()]
            edit_df = df.set_index("id")
            edited_df = st.data_editor(
                edit_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "date": st.column_config.DateColumn("Date"),
                    "category": st.column_config.SelectboxColumn("Category", options=all_cats),
                    "subcategory": st.column_config.SelectboxColumn("Subcategory", options=all_subs),
                    "amount": st.column_config.NumberColumn("Amount", min_value=0)
                }
            )
            if st.button("💾 Save Changes"):
                with db.no_autoflush:
                    for row_id, row in edited_df.iterrows():
                        exp = db.get(Expense, int(row_id))
                        if not exp:
                            continue
                        exp.date = pd.to_datetime(row["date"]).date()
                        exp.amount = float(row["amount"])
                        cat = db.query(Category).filter_by(name=row["category"]).first()
                        if not cat:
                            continue
                        sub = db.query(SubCategory).filter_by(
                            name=row["subcategory"],
                            category_id=cat.id
                        ).first()
                        if sub:
                            exp.category_id = cat.id
                            exp.subcategory_id = sub.id
                db.commit()
                st.session_state.data_refresh += 1
                flash("Entries updated successfully")
                st.rerun()
        else:
            st.subheader("🗑 Delete Entries")
            delete_mode = st.radio(
                "Delete option",
                ["Delete selected rows", "Delete ALL filtered rows"],
                horizontal=True
            )
            df_del = df.copy()
            df_del["date"] = pd.to_datetime(df_del["date"]).dt.strftime("%Y-%m-%d")
            if delete_mode == "Delete selected rows":
                gb = GridOptionsBuilder.from_dataframe(df_del)
                gb.configure_column(
                    "date",
                    checkboxSelection=True,
                    headerCheckboxSelection=True,
                    sort="desc",
                    sortIndex=0
                )
                gb.configure_column("id", hide=True, sort="desc", sortIndex=1)
                gb.configure_grid_options(rowSelection="multiple", suppressRowClickSelection=True)
                grid = AgGrid(
                    df_del,
                    gridOptions=gb.build(),
                    update_mode=GridUpdateMode.MODEL_CHANGED,
                    fit_columns_on_grid_load=True
                )
                selected = pd.DataFrame(grid["selected_rows"])
                if not selected.empty:
                    st.warning(f"Selected rows: {len(selected)}")
                    if st.checkbox("Confirm delete selected entries"):
                        if st.button("❌ Delete Selected"):
                            for _, row in selected.iterrows():
                                exp = db.get(Expense, int(row["id"]))
                                if exp:
                                    db.delete(exp)
                            db.commit()
                            st.session_state.data_refresh += 1
                            flash("Selected entries deleted")
                            st.rerun()
            else:
                st.warning(f"This will delete ALL {len(df)} filtered entries")
                if st.checkbox("I understand this action is permanent"):
                    if st.button("❌ Delete ALL Filtered"):
                        for _, row in df.iterrows():
                            exp = db.get(Expense, int(row["id"]))
                            if exp:
                                db.delete(exp)
                        db.commit()
                        st.session_state.data_refresh += 1
                        flash("All filtered entries deleted")
                        st.rerun()

# ===============
# TRAVEL PAGE
# ===============
def events_page():
    st.title("🎫 Events")
    df = load_events_data(st.session_state.data_refresh).copy()
    if df.empty:
        st.info("No events found yet.")
        return

    df["trip_start"] = pd.to_datetime(df["trip_start"], errors="coerce")
    df["trip_end"] = pd.to_datetime(df["trip_end"], errors="coerce")

    grouped = df.groupby(["trip_name", "trip_start", "trip_end"], dropna=False)
    for (tname, tstart, tend), g in grouped:
        tname_label = str(tname).strip() if pd.notna(tname) and str(tname).strip() else "Untitled Event"
        start_label = tstart.strftime("%d %b %Y") if pd.notna(tstart) else "—"
        end_label = tend.strftime("%d %b %Y") if pd.notna(tend) else "—"
        total = float(g["amount"].sum())
        label = f"{tname_label} | {start_label} → {end_label} | ₹{total:,.2f}"
        with st.expander(label, expanded=False):
            g_view = g[["date", "category", "subcategory", "amount"]].copy()
            g_view["date"] = pd.to_datetime(g_view["date"]).dt.strftime("%Y-%m-%d")
            st.dataframe(g_view, use_container_width=True, hide_index=True)

            safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", str(tname_label)).strip("_") or "event"
            start_file = tstart.strftime("%Y-%m-%d") if pd.notna(tstart) else "start"
            end_file = tend.strftime("%Y-%m-%d") if pd.notna(tend) else "end"
            file_name = f"event_{safe_name}_{start_file}_to_{end_file}.pdf"

            if st.button("🧾 Generate Event PDF", key=f"event_pdf_btn_{safe_name}_{start_file}_{end_file}"):
                pdf_df = g_view.copy()
                st.session_state[f"event_pdf_{safe_name}_{start_file}_{end_file}"] = generate_event_pdf_black(
                    tname_label,
                    start_label,
                    end_label,
                    pdf_df
                )

            pdf_bytes = st.session_state.get(f"event_pdf_{safe_name}_{start_file}_{end_file}")
            if pdf_bytes:
                st.download_button(
                    "⬇️ Download Event PDF",
                    data=pdf_bytes,
                    file_name=file_name,
                    mime="application/pdf",
                    key=f"event_pdf_dl_{safe_name}_{start_file}_{end_file}"
                )

            st.divider()
            with st.expander("delete", expanded=False):
                c_del, c_unlink = st.columns(2)

                with c_del:
                    confirm_delete = st.checkbox(
                        "Confirm delete event + entries",
                        key=f"confirm_delete_event_rows_{safe_name}_{start_file}_{end_file}"
                    )
                    if st.button("🗑️ Delete Event + Entries", key=f"delete_event_rows_btn_{safe_name}_{start_file}_{end_file}"):
                        if not confirm_delete:
                            st.warning("Please confirm deletion first.")
                        else:
                            with SessionLocal() as db:
                                q = db.query(Expense).filter(Expense.travel == 1)
                                if pd.notna(tname):
                                    q = q.filter(Expense.trip_name == str(tname))
                                else:
                                    q = q.filter(Expense.trip_name.is_(None))
                                if pd.notna(tstart):
                                    q = q.filter(Expense.trip_start == tstart.date())
                                else:
                                    q = q.filter(Expense.trip_start.is_(None))
                                if pd.notna(tend):
                                    q = q.filter(Expense.trip_end == tend.date())
                                else:
                                    q = q.filter(Expense.trip_end.is_(None))

                                deleted_count = q.delete(synchronize_session=False)
                                db.commit()

                            st.session_state.data_refresh += 1
                            flash(f"Deleted event '{tname_label}' with {deleted_count} entry row(s).")
                            st.rerun()

                with c_unlink:
                    confirm_unlink = st.checkbox(
                        "Confirm remove event tag only",
                        key=f"confirm_unlink_event_{safe_name}_{start_file}_{end_file}"
                    )
                    if st.button("✂️ Remove Event Tag (Keep Entries)", key=f"unlink_event_btn_{safe_name}_{start_file}_{end_file}"):
                        if not confirm_unlink:
                            st.warning("Please confirm action first.")
                        else:
                            with SessionLocal() as db:
                                q = db.query(Expense).filter(Expense.travel == 1)
                                if pd.notna(tname):
                                    q = q.filter(Expense.trip_name == str(tname))
                                else:
                                    q = q.filter(Expense.trip_name.is_(None))
                                if pd.notna(tstart):
                                    q = q.filter(Expense.trip_start == tstart.date())
                                else:
                                    q = q.filter(Expense.trip_start.is_(None))
                                if pd.notna(tend):
                                    q = q.filter(Expense.trip_end == tend.date())
                                else:
                                    q = q.filter(Expense.trip_end.is_(None))

                                updated_count = q.update(
                                    {
                                        Expense.travel: 0,
                                        Expense.trip_name: None,
                                        Expense.trip_start: None,
                                        Expense.trip_end: None,
                                    },
                                    synchronize_session=False
                                )
                                db.commit()

                            st.session_state.data_refresh += 1
                            flash(f"Removed event tag from '{tname_label}' ({updated_count} entry row(s) kept).", kind="info")
                            st.rerun()

# =================
# EXPENSE DASHBOARD
# =================
# Handle dashboard.

# ============================
# DASHBOARD RIGHT PANEL
# ============================
def dashboard():
    st.title("📊 Dashboard")

    # ============================
    # LOAD DATA (CACHED – FOR CHARTS)
    # ============================
    df = load_expense_data(st.session_state.data_refresh).copy()

    if df.empty:
        st.info("No data available")
        return

    df["date"] = pd.to_datetime(df["date"])

    # ============================
    # MONTHLY SNAPSHOTS
    # ============================
    with st.expander("📌 Monthly Snapshot Cards", expanded=False):
        st.caption("Auto-updated monthly highlight cards.")

        if df.empty:
            st.info("No data available.")
        else:
            st.markdown(
                """
                <style>
                .snapshot-card {
                    background: #0b0b0b;
                    border: 1px solid #1f1f1f;
                    border-radius: 12px;
                    padding: 14px 16px;
                    margin-bottom: 14px;
                }
                .snapshot-title {
                    font-size: 16px;
                    font-weight: 700;
                    color: #ffffff;
                    margin-bottom: 6px;
                }
                .snapshot-row {
                    font-size: 13px;
                    color: #cfcfcf;
                    margin: 2px 0;
                }
                </style>
                """,
                unsafe_allow_html=True
            )

            snapshots = build_monthly_snapshots(df)
            for snap in snapshots:
                peak_label = snap["peak_day"].strftime("%d %b %Y") if snap["peak_day"] else "—"
                st.markdown(
                    f"""
                    <div class="snapshot-card">
                        <div class="snapshot-title">{snap["label"]}</div>
                        <div class="snapshot-row">Total: ₹ {snap["total"]:,.2f}</div>
                        <div class="snapshot-row">Average per day: ₹ {snap["avg_day"]:,.2f}</div>
                        <div class="snapshot-row">Transactions: {snap["tx"]}</div>
                        <div class="snapshot-row">Peak day: {peak_label} (₹ {snap["peak_amt"]:,.2f})</div>
                        <div class="snapshot-row">Top category: {snap["top_cat"]}</div>
                        <div class="snapshot-row">Top subcategory: {snap["top_sub"]}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

    # ============================
    # COMMON DATE ANCHORS
    # ============================
    today_ts = pd.Timestamp.today().normalize()
    week_start_ts = today_ts - pd.Timedelta(days=6)
    month_start_ts = today_ts.replace(day=1)
    year_start_ts = today_ts.replace(month=1, day=1)
    today_date = today_ts.date()

    # ============================
    # DB SESSION (ALL LIVE TOTALS)
    # ============================
    with SessionLocal() as db:

        # ========================
        # CURRENT MONTH SUMMARY
        # ========================
        st.subheader("Income & Expense Summary (Current Month)")

        total_income = (
            db.query(func.sum(Income.amount))
            .filter(Income.date.between(month_start_ts.date(), today_date))
            .scalar()
        ) or 0

        total_expense = (
            db.query(func.sum(Expense.amount))
            .filter(Expense.date.between(month_start_ts.date(), today_date))
            .scalar()
        ) or 0

        net_balance = total_income - total_expense

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Income", f"₹ {total_income:,.2f}")
        c2.metric("Total Expense", f"₹ {total_expense:,.2f}")
        c3.metric(
            "Net Balance",
            f"₹ {net_balance:,.2f}",
            delta="Surplus" if net_balance >= 0 else "Deficit"
        )

        # ========================
        # DAILY BUY (SIDEBAR)
        # ========================
        st.sidebar.divider()
        st.sidebar.subheader("🛒 Daily Buy")

        selected_date = st.sidebar.date_input(
            "",
            value=today_date,
            label_visibility="collapsed",
            key="daily_buy_date"
        )

        daily_df = pd.DataFrame(
            db.query(
                Expense.amount,
                SubCategory.name.label("subcategory")
            )
            .join(SubCategory, Expense.subcategory_id == SubCategory.id)
            .filter(Expense.date == selected_date)
            .all(),
            columns=["amount", "subcategory"]
        )

        if daily_df.empty:
            st.sidebar.caption(
                f"No entries on {selected_date.strftime('%d %b %Y')}"
            )
        else:
            grouped = (
                daily_df.groupby("subcategory", as_index=False)["amount"]
                .sum()
                .sort_values("amount", ascending=False)
            )

            for _, row in grouped.iterrows():
                st.sidebar.write(
                    f"• **{row['subcategory']}** — ₹ {row['amount']:,.0f}"
                )
            st.sidebar.markdown(
                f"<div style='font-size:16px; font-weight:700;'>Total — ₹ {grouped['amount'].sum():,.0f}</div>",
                unsafe_allow_html=True
            )

        # ========================
        # DATABASE ENTRY COUNT (LIVE)
        # ========================
        total_entries = sum((
            db.query(func.count(Expense.id)).scalar() or 0,
            db.query(func.count(Income.id)).scalar() or 0,
            db.query(func.count(MetalAsset.id)).scalar() or 0,
            db.query(func.count(LandAsset.id)).scalar() or 0,
            db.query(func.count(FixedDeposit.id)).scalar() or 0,
            db.query(func.count(Appliance.id)).scalar() or 0,
            db.query(func.count(LICPolicy.id)).scalar() or 0,
            db.query(func.count(InvestmentEntry.id)).scalar() or 0,
        ))

        st.sidebar.divider()
        st.sidebar.metric(
            "Total Entries So Far",
            f"{total_entries:,}"
        )

        # ========================
        # EXPENSE SUMMARY (LIVE)
        # ========================
        st.subheader("Expense Summary")

        week_expense = (
            db.query(func.sum(Expense.amount))
            .filter(Expense.date.between(week_start_ts.date(), today_date))
            .scalar()
        ) or 0


        year_expense = (
            db.query(func.sum(Expense.amount))
            .filter(Expense.date.between(year_start_ts.date(), today_date))
            .scalar()
        ) or 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Last 7 Days", f"₹ {week_expense:,.2f}")
        c2.metric("Year So Far", f"₹ {year_expense:,.2f}")

    # ============================
    # CALENDAR VIEW
    # ============================
    with st.expander("📅 Calendar View", expanded=False):
        render_calendar_view(df)

    # ============================
    # PERIOD FILTER (CHARTS)
    # ============================
    with st.expander("📅 Period Filter & Pie Charts", expanded=False):
    
        period_mode = st.radio(
            "Filter expenses by",
            ["Monthly", "Yearly", "Custom"],
            horizontal=True,
            key="dashboard_period_filter"
        )

        if period_mode == "Monthly":
            months = sorted(df["date"].dt.to_period("M").unique())
            labels = [m.strftime("%b %Y") for m in months]
            current_period = today_ts.to_period("M")
            default_index = months.index(current_period) if current_period in months else len(months) - 1

            sel = st.selectbox("Select Month", labels, index=default_index)
            sel_period = months[labels.index(sel)]
            start_ts = sel_period.to_timestamp()
            end_ts = (sel_period + 1).to_timestamp() - pd.Timedelta(seconds=1)

        elif period_mode == "Yearly":
            years = sorted(df["date"].dt.year.unique())
            year = st.selectbox("Select Year", years)
            start_ts = pd.Timestamp(year=year, month=1, day=1)
            end_ts = pd.Timestamp(year=year, month=12, day=31)

        else:
            start, end = st.date_input(
                "Select date range",
                [month_start_ts.date(), today_date]
            )
            start_ts = pd.Timestamp(start)
            end_ts = pd.Timestamp(end)

        period_df = df[df["date"].between(start_ts, end_ts)]

        with SessionLocal() as db:
            total_spend = (
                db.query(func.sum(Expense.amount))
                .filter(Expense.date.between(start_ts.date(), end_ts.date()))
                .scalar()
            ) or 0

        st.markdown(f"## 💰 Total for selected period: ₹ {total_spend:,.2f}")


        # ============================
        # SIDE-BY-SIDE CATEGORY / SUBCATEGORY CHARTS
        # ============================

        # ---- Chart view toggle
        chart_view = st.radio(
            "Chart View",
            ["Pie Chart", "Bar Chart"],
            horizontal=True,
            key="dashboard_chart_view"
        )

        # ---- Category aggregation
        cat_df = (
            period_df.groupby("category", as_index=False)["amount"]
            .sum()
            .sort_values("amount", ascending=False)
        )

        if cat_df.empty:
            st.info("No data for selected period")
            return

        col1, col2 = st.columns(2)

        # =====================
        # CATEGORY CHART
        # =====================
        with col1:
            st.subheader("By Category")

            cat_df["percent"] = (
                cat_df["amount"] / cat_df["amount"].sum() * 100
            ).round(1)

            fig_cat = px.pie(
                cat_df,
                names="category",
                values="amount",
                hole=0.4
            )

            fig_cat.update_traces(
                texttemplate="%{customdata}%",
                customdata=cat_df["percent"],
                hovertemplate="<b>%{label}</b><br>₹ %{value:,.0f}<br>%{customdata}%<extra></extra>"
            )

            fig_cat.update_layout(
                height=480,
                margin=dict(l=20, r=20, t=40, b=140),
                legend=dict(
                    orientation="h",
                    yanchor="top",
                    y=-0.35,
                    xanchor="center",
                    x=0.5
                ),
                legend_itemclick=False,
                legend_itemdoubleclick=False,
                paper_bgcolor="#000",
                font=dict(color="#fff")
            )
            fig_cat.update_traces(marker=dict(line=dict(color="black", width=2)))

            plotly_chart_hi_res(fig_cat, use_container_width=True)

        # =====================
        # SUBCATEGORY CHART
        # =====================
        with col2:
            st.subheader("By Subcategory")

            selected_category = st.selectbox(
                "Select Category",
                cat_df["category"].tolist(),
                key="subcategory_chart_category"
            )

            sub_df = (
                period_df[period_df["category"] == selected_category]
                .groupby("subcategory", as_index=False)["amount"]
                .sum()
                .sort_values("amount", ascending=False)
            )

            if sub_df.empty:
                st.info("No subcategory data")
            else:
                sub_df["percent"] = (
                    sub_df["amount"] / sub_df["amount"].sum() * 100
                ).round(1)

                if chart_view == "Pie Chart":
                    fig_sub = px.pie(
                        sub_df,
                        names="subcategory",
                        values="amount",
                        hole=0.4
                    )

                    fig_sub.update_traces(
                        texttemplate="%{customdata}%",
                        customdata=sub_df["percent"],
                        hovertemplate="<b>%{label}</b><br>₹ %{value:,.0f}<br>%{customdata}%<extra></extra>",
                    )

                    fig_sub.update_layout(
                        height=480,
                        margin=dict(l=20, r=20, t=40, b=140),
                        legend=dict(
                            orientation="h",
                            yanchor="top",
                            y=-0.35,
                            xanchor="center",
                            x=0.5
                        ),
                        legend_itemclick=False,
                        legend_itemdoubleclick=False,
                        paper_bgcolor="#000",
                        font=dict(color="#fff")
                    )
                    fig_sub.update_traces(marker=dict(line=dict(color="black", width=2)))

                    plotly_chart_hi_res(fig_sub, use_container_width=True)

                else:
                    fig_bar = px.bar(
                        sub_df,
                        x="subcategory",
                        y="amount",
                        text_auto=".2f"
                    )

                    fig_bar.update_layout(
                        height=420,
                        xaxis_title="Subcategory",
                        yaxis_title="Amount (₹)",
                        paper_bgcolor="#000",
                        plot_bgcolor="#000",
                        font=dict(color="#fff"),
                        xaxis=dict(tickangle=-45)
                    )
                    fig_bar.update_traces(marker=dict(line=dict(color="black", width=2)))
                    fig_bar.update_traces(marker=dict(line=dict(color="black", width=2)))
                    plotly_chart_hi_res(fig_bar, use_container_width=True)
                
        # ============================
        # BAR → TRANSACTION TABLE
        # ============================
    if chart_view == "Bar Chart" and not sub_df.empty:
        st.divider()
        st.subheader("📋 Transactions for Subcategory")

        selected_sub = st.selectbox(
            "Select Subcategory to View Transactions",
            sub_df["subcategory"].tolist(),
            key="bar_to_table_subcategory"
        )

        table_df = period_df[
            (period_df["category"] == selected_category) &
            (period_df["subcategory"] == selected_sub)
        ][["date", "subcategory", "amount"]].sort_values("date", ascending=False)

        if table_df.empty:
            st.info("No transactions found")
        else:
            table_df = table_df.rename(columns={
                "date": "Date",
                "subcategory": "Subcategory",
                "amount": "Amount (₹)"
            })

            st.dataframe(
                table_df,
                use_container_width=True,
                hide_index=True
            )

            st.metric(
                "Total",
                f"₹ {table_df['Amount (₹)'].sum():,.2f}"
            )

    # ============================
    # ✨ ADVANCED VISUAL CHARTS
    # ============================
    with st.expander("✨ Advanced Visual Charts", expanded=False):
        st.caption("High-impact chart variants with smart filters for deeper insights.")

        if period_df.empty:
            st.info("No data for advanced charts.")
        else:
            adv_df = period_df.copy()

            f1, f2, f3 = st.columns(3)
            all_cats = sorted(adv_df["category"].dropna().unique().tolist())
            sel_cats = f1.multiselect(
                "Categories",
                all_cats,
                default=all_cats,
                key="advv_cats"
            )
            if sel_cats:
                adv_df = adv_df[adv_df["category"].isin(sel_cats)]

            all_subs = sorted(adv_df["subcategory"].dropna().unique().tolist())
            sel_subs = f2.multiselect(
                "Subcategories",
                all_subs,
                default=all_subs,
                key="advv_subs"
            )
            if sel_subs:
                adv_df = adv_df[adv_df["subcategory"].isin(sel_subs)]

            metric_mode = f3.selectbox(
                "Metric",
                ["Total Spend", "Transaction Count", "Average Spend"],
                key="advv_metric"
            )

            if adv_df.empty:
                st.info("No data after filters.")
            else:
                variant = st.selectbox(
                    "Chart Variant",
                    [
                        "Treemap (Category → Subcategory)",
                        "Sunburst (Category → Subcategory)",
                        "Waterfall (Month-over-Month Change)",
                        "Distribution (Box Plot by Category)"
                    ],
                    key="advv_variant"
                )

                # Handle agg metric.
                def agg_metric(df, group_cols):
                    if metric_mode == "Transaction Count":
                        return df.groupby(group_cols).size().reset_index(name="value")
                    if metric_mode == "Average Spend":
                        return df.groupby(group_cols)["amount"].mean().reset_index(name="value")
                    return df.groupby(group_cols)["amount"].sum().reset_index(name="value")

                if variant == "Treemap (Category → Subcategory)":
                    agg = agg_metric(adv_df, ["category", "subcategory"])
                    if agg.empty:
                        st.info("No data for treemap.")
                    else:
                        max_items = len(agg)
                        if max_items > 1:
                            top_n = st.slider(
                                "Limit items",
                                min_value=1,
                                max_value=min(30, max_items),
                                value=min(15, max_items),
                                step=1,
                                key="advv_treemap_top"
                            )
                            agg = agg.sort_values("value", ascending=False).head(top_n)

                        fig = px.treemap(
                            agg,
                            path=["category", "subcategory"],
                            values="value",
                            color="value",
                            color_continuous_scale="Viridis"
                        )
                        fig.update_layout(
                            paper_bgcolor="#000",
                            font=dict(color="#fff"),
                            margin=dict(l=10, r=10, t=40, b=10)
                        )
                        plotly_chart_hi_res(fig, use_container_width=True)

                elif variant == "Sunburst (Category → Subcategory)":
                    agg = agg_metric(adv_df, ["category", "subcategory"])
                    if agg.empty:
                        st.info("No data for sunburst.")
                    else:
                        max_items = len(agg)
                        if max_items > 1:
                            top_n = st.slider(
                                "Limit items",
                                min_value=1,
                                max_value=min(30, max_items),
                                value=min(15, max_items),
                                step=1,
                                key="advv_sunburst_top"
                            )
                            agg = agg.sort_values("value", ascending=False).head(top_n)

                        fig = px.sunburst(
                            agg,
                            path=["category", "subcategory"],
                            values="value",
                            color="value",
                            color_continuous_scale="Plasma"
                        )
                        fig.update_layout(
                            paper_bgcolor="#000",
                            font=dict(color="#fff"),
                            margin=dict(l=10, r=10, t=40, b=10)
                        )
                        plotly_chart_hi_res(fig, use_container_width=True)

                elif variant == "Waterfall (Month-over-Month Change)":
                    monthly = agg_metric(
                        adv_df.assign(
                            period=adv_df["date"].dt.to_period("M").dt.to_timestamp()
                        ),
                        ["period"]
                    ).sort_values("period")

                    if monthly.empty or len(monthly) < 2:
                        st.info("Need at least 2 months of data for waterfall.")
                    else:
                        monthly["delta"] = monthly["value"].diff().fillna(monthly["value"])
                        fig = go.Figure(go.Waterfall(
                            x=monthly["period"].dt.strftime("%b %Y"),
                            y=monthly["delta"],
                            measure=["relative"] * len(monthly),
                            increasing={"marker": {"color": "#2ecc71"}},
                            decreasing={"marker": {"color": "#e74c3c"}},
                            connector={"line": {"color": "#555"}}
                        ))
                        fig.update_layout(
                            paper_bgcolor="#000",
                            plot_bgcolor="#000",
                            font=dict(color="#fff"),
                            xaxis_title="Month",
                            yaxis_title="Change",
                            margin=dict(l=20, r=20, t=40, b=40)
                        )
                        plotly_chart_hi_res(fig, use_container_width=True)

                else:  # Distribution (Box Plot by Category)
                    if adv_df.empty:
                        st.info("No data for distribution.")
                    else:
                        fig = px.box(
                            adv_df,
                            x="category",
                            y="amount",
                            points="outliers"
                        )
                        fig.update_layout(
                            paper_bgcolor="#000",
                            plot_bgcolor="#000",
                            font=dict(color="#fff"),
                            xaxis_title="Category",
                            yaxis_title="Amount (₹)",
                            margin=dict(l=20, r=20, t=40, b=40)
                        )
                        fig.update_traces(marker=dict(color="#4da3ff"))
                        plotly_chart_hi_res(fig, use_container_width=True)

    advanced_analytics(period_df)
    # ============================
    # SUBCATEGORY DETAILS TABLE
    # ============================
    with st.expander("🔎 View Subcategory Details Table", expanded=False):

        st.subheader("📋 Subcategory Details")

        # ---- Select category + subcategory (local to this section)
        available_categories = sorted(period_df["category"].dropna().unique())
        if not available_categories:
            st.info("No categories available")
            return

        table_category = st.selectbox(
            "Select Category",
            available_categories,
            key="subcategory_table_category"
        )

        available_subs = sorted(
            period_df[period_df["category"] == table_category]["subcategory"].unique()
        )

        if not available_subs:
            st.info("No subcategories available")
            return

        selected_subcategory = st.selectbox(
            "Select Subcategory",
            available_subs,
            key="subcategory_table_select"
        )

        # ---- Time filter
        time_filter = st.radio(
            "Filter by",
            ["Monthly", "Last 7 Days", "Custom"],
            horizontal=True,
            key="subcategory_time_filter"
        )

        today_ts = pd.Timestamp.today().normalize()

        if time_filter == "Monthly":
            months = sorted(df["date"].dt.to_period("M").unique())
            labels = [m.strftime("%b %Y") for m in months]

            current_period = today_ts.to_period("M")
            default_index = (
                months.index(current_period)
                if current_period in months
                else len(months) - 1
            )

            sel = st.selectbox(
                "Select Month",
                labels,
                index=default_index,
                key="subcategory_month_select"
            )

            sel_period = months[labels.index(sel)]
            start_ts = sel_period.to_timestamp()
            end_ts = (sel_period + 1).to_timestamp() - pd.Timedelta(seconds=1)

        elif time_filter == "Last 7 Days":
            end_ts = today_ts
            start_ts = today_ts - pd.Timedelta(days=6)

        else:
            start, end = st.date_input(
                "Select date range",
                [today_ts.date() - pd.Timedelta(days=7), today_ts.date()],
                key="subcategory_custom_range"
            )
            start_ts = pd.Timestamp(start)
            end_ts = pd.Timestamp(end)

        # ---- Filter data
        table_df = df[
            (df["category"] == table_category) &
            (df["subcategory"] == selected_subcategory) &
            (df["date"].between(start_ts, end_ts))
        ][["date", "subcategory", "amount"]]

        if table_df.empty:
            st.warning("No records found for this selection")
        else:
            table_df = table_df.sort_values("date", ascending=False)

            # Rename columns
            table_df = table_df.rename(columns={
                "date": "Date",
                "subcategory": "Subcategory",
                "amount": "Amount (₹)"
            })

            # Display table
            st.dataframe(
                table_df,
                use_container_width=True,
                hide_index=True
            )

            # Total
            total_value = table_df["Amount (₹)"].sum()
            st.metric(
                "Total",
                f"₹ {total_value:,.2f}"
            )


## ======================================
# INSIGHTS
# ======================================
# Handle insights.
def insights():
    st.title("📈 Insights")
    # ============================
    # AVERAGE SPEND & HIGHEST MONTH
    # ============================
    df = load_expense_data(st.session_state.data_refresh).copy()
    if df.empty:
        st.info("No data available")
        st.stop()

    df["date"] = pd.to_datetime(df["date"])
    avg_mode = st.radio(
        "Average Spend Period",
        ["Weekly", "Monthly", "Yearly"],
        horizontal=True
    )
    if avg_mode == "Weekly":
        avg_value = (
            df.groupby(df["date"].dt.to_period("W"))["amount"]
            .sum()
            .mean()
        )
        avg_label = "Avg Weekly Spend"
    elif avg_mode == "Monthly":
        avg_value = (
            df.groupby(df["date"].dt.to_period("M"))["amount"]
            .sum()
            .mean()
        )
        avg_label = "Avg Monthly Spend"
    else:
        avg_value = (
            df.groupby(df["date"].dt.to_period("Y"))["amount"]
            .sum()
            .mean()
        )
        avg_label = "Avg Yearly Spend"
    monthly = (
        df.groupby(df["date"].dt.to_period("M"))["amount"]
        .sum()
        .sort_values(ascending=False)
    )
    top_month = monthly.index[0].strftime("%b %Y")
    top_month_value = monthly.iloc[0]
    col1, col2 = st.columns(2)
    col1.metric(avg_label, f"₹ {avg_value:,.2f}")
    col2.metric(
        "Highest Spend Month",
        top_month,
        f"₹ {top_month_value:,.2f}"
    )
    # ============================
    # TOP 5 CATEGORY / SUBCATEGORY MONTHLY
    # ============================
    st.divider()
    st.subheader("🏷 Top 5/month")
    df["date"] = pd.to_datetime(df["date"])
    months = sorted(df["date"].dt.to_period("M").unique())
    month_labels = [m.strftime("%b %Y") for m in months]
    current_period = pd.Timestamp.today().to_period("M")
    default_index = months.index(current_period) if current_period in months else len(months) - 1
    selected_label = st.selectbox(
        "Select Month",
        month_labels,
        index=default_index,
        key="top5_month"
    )
    selected_period = months[month_labels.index(selected_label)]
    start = selected_period.to_timestamp()
    end = (selected_period + 1).to_timestamp() - pd.Timedelta(seconds=1)
    filtered_top_df = df[df["date"].between(start, end)]
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("Categories")
        top_categories = (
            filtered_top_df.groupby("category")["amount"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )
        if top_categories.empty:
            st.info("No data for selected month")
        else:
            for cat, amt in top_categories.items():
                st.write(f"**{cat}** — ₹ {amt:,.2f}")
    with col_right:
        st.subheader("Subcategories")
        top_subcategories = (
            filtered_top_df.groupby("subcategory")["amount"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )
        if top_subcategories.empty:
            st.info("No data for selected month")
        else:
            for sub, amt in top_subcategories.items():
                st.write(f"**{sub}** — ₹ {amt:,.2f}")

    # ============================
    # CATEGORY TREND COMPARISON
    # ============================
    st.divider()
    st.subheader("📊 Category Trend Comparison")
    sel_cat = st.selectbox(
        "Select Category",
        sorted(df["category"].unique())
    )
    sel_sub = st.selectbox(
        "Select Subcategory",
        sorted(
            df[df["category"] == sel_cat]["subcategory"].unique()
        )
    )
    sub_df = df[
        (df["category"] == sel_cat) &
        (df["subcategory"] == sel_sub)
    ]
    monthly_sub = (
        sub_df.groupby(sub_df["date"].dt.to_period("M"))["amount"]
        .sum()
        .sort_index()
    )

    if len(monthly_sub) < 2:
        st.info("Not enough data for comparison")
    else:
        last_month = monthly_sub.iloc[-1]
        prev_month = monthly_sub.iloc[-2]

        diff = last_month - prev_month

        if prev_month == 0:
            pct = 100.0
        else:
            pct = (diff / prev_month) * 100

        if diff > 0:
            direction = "higher"
            arrow = "🔺"
        elif diff < 0:
            direction = "lower"
            arrow = "🔻"
        else:
            direction = "the same"
            arrow = "➖"

        st.markdown(
                f"""
                ### {arrow} Spending Trend
                You spent **₹ {abs(diff):,.2f} ({abs(pct):.1f}%)**
                **{direction}** on **{sel_cat} → {sel_sub}**
                compared to the previous month.
                """
            )

    # ============================
    # 🧠 SPENDING ANOMALY DETECTOR
    # ============================
    st.divider()
    st.subheader("🧠 Spending Anomaly Detector")
    st.caption("Highlights unusual spikes or dips using a rolling median and MAD (robust z-score).")

    g1, g2, g3 = st.columns(3)
    granularity = g1.selectbox(
        "Granularity",
        ["Daily", "Weekly", "Monthly"],
        key="insights_anomaly_granularity"
    )
    window = g2.slider(
        "Rolling window",
        min_value=4,
        max_value=60,
        value=14,
        step=1,
        key="insights_anomaly_window"
    )
    threshold = g3.slider(
        "Sensitivity (z-score)",
        min_value=2.5,
        max_value=6.0,
        value=3.5,
        step=0.5,
        key="insights_anomaly_threshold"
    )

    if granularity == "Weekly":
        series = (
            df.groupby(df["date"].dt.to_period("W"))["amount"]
            .sum()
            .sort_index()
        )
        series.index = series.index.to_timestamp()
    elif granularity == "Monthly":
        series = (
            df.groupby(df["date"].dt.to_period("M"))["amount"]
            .sum()
            .sort_index()
        )
        series.index = series.index.to_timestamp()
    else:
        series = (
            df.groupby(df["date"])["amount"]
            .sum()
            .sort_index()
        )

    if len(series) < 4:
        st.info("Not enough data to detect anomalies.")
    else:
        min_periods = max(3, window // 2)
        roll_med = series.rolling(window, center=True, min_periods=min_periods).median()
        abs_dev = (series - roll_med).abs()
        mad = abs_dev.rolling(window, center=True, min_periods=min_periods).median()

        safe_mad = mad.replace(0, pd.NA)
        z = 0.6745 * (series - roll_med) / safe_mad
        z = z.fillna(0)
        anomalies = z.abs() > threshold

        a1, a2, a3 = st.columns(3)
        a1.metric("Anomalies Found", f"{int(anomalies.sum())}")
        a2.metric("Max Spike", f"₹ {series.max():,.0f}")
        a3.metric("Max Dip", f"₹ {series.min():,.0f}")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=series.index,
            y=series.values,
            mode="lines",
            name="Spend",
            line=dict(color="#4da3ff", width=2)
        ))
        fig.add_trace(go.Scatter(
            x=roll_med.index,
            y=roll_med.values,
            mode="lines",
            name="Rolling Median",
            line=dict(color="#aaaaaa", width=1, dash="dot")
        ))

        if anomalies.any():
            fig.add_trace(go.Scatter(
                x=series.index[anomalies],
                y=series[anomalies],
                mode="markers",
                name="Anomalies",
                marker=dict(color="#ff5c5c", size=9, line=dict(color="black", width=1))
            ))

            top_anom = (
                series[anomalies]
                .sort_values(ascending=False)
                .head(5)
                .reset_index()
            )
            top_anom.columns = ["Date", "Amount (₹)"]
            st.dataframe(top_anom, use_container_width=True, hide_index=True)

        fig.update_layout(
            paper_bgcolor="#000",
            plot_bgcolor="#000",
            font=dict(color="#fff"),
            xaxis_title="Date",
            yaxis_title="Amount (₹)",
            margin=dict(l=20, r=20, t=40, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
        )
        plotly_chart_hi_res(fig, use_container_width=True)

    # ============================
# EXPENSE PDF EXPORT SECTION
# ===========================
# Export PDF.
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
    # Do NOT auto-add TOTAL if it already exists as a row
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

    from reportlab.lib.styles import getSampleStyleSheet

    styles = getSampleStyleSheet()

    title_style = styles["Title"]
    title_style.textColor = colors.white
    title_style.alignment = 1  # CENTER

    meta_style = styles["Normal"]
    meta_style.textColor = colors.white
    meta_style.leading = 14

    # Footer function
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

        footer_para.wrap(
            page_width - 40,  # left + right margins
            50
        )

        footer_para.drawOn(canvas, 20, 20)

        canvas.restoreState()

    # Handle header block.
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

    # separator line
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

# Export a single event to a black-themed PDF.
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

# Export data.
def export_data():
    st.title("📤 Export")
    with SessionLocal() as db:
        col1, col2, col3 = st.columns(3)
        with col1:
            period = st.selectbox(
                "Period",
                ["Weekly", "Monthly", "Yearly", "Custom"]
            )
        with col2:
            cats = db.query(Category).all()
            cat_names = ["All"] + [c.name for c in cats]
            sel_cat = st.selectbox("Category", cat_names)
        with col3:
            if sel_cat == "All":
                sel_sub = "All"
                st.selectbox("Subcategory", ["All"], disabled=True)
            else:
                cat = db.query(Category).filter_by(name=sel_cat).first()
                subs = db.query(SubCategory).filter_by(category_id=cat.id).all()
                sel_sub = st.selectbox(
                    "Subcategory",
                    ["All"] + [s.name for s in subs]
                )
        today = date.today()
        if period == "Weekly":
            end = today
            start = end - timedelta(days=7)
        elif period == "Monthly":
            months = (
                db.query(func.strftime("%Y-%m", Expense.date))
                .distinct()
                .order_by(func.strftime("%Y-%m", Expense.date))
                .all()
            )
            if months:
                labels = [
                    pd.to_datetime(m[0] + "-01").strftime("%b %Y")
                    for m in months
                ]
                sel = st.selectbox("Select Month", labels)
                idx = labels.index(sel)
                start = pd.to_datetime(months[idx][0] + "-01").date()
                end = (pd.to_datetime(start) + pd.offsets.MonthEnd(1)).date()
            else:
                start = end = today
        elif period == "Yearly":
            years = (
                db.query(func.strftime("%Y", Expense.date))
                .distinct()
                .order_by(func.strftime("%Y", Expense.date))
                .all()
            )
            years = [int(y[0]) for y in years]
            if years:
                year = st.selectbox("Select Year", years)
                start = date(year, 1, 1)
                end = date(year, 12, 31)
            else:
                start = end = today
        else:
            start, end = st.date_input(
                "Custom Date Range",
                [today.replace(day=1), today]
            )
        # =========================
        # FETCH & DISPLAY DATA
        # =========================
        st.divider()
        if st.button("Apply Filters"):
            q = (
                db.query(
                    Expense.date.label("Date"),
                    Category.name.label("Category"),
                    SubCategory.name.label("Subcategory"),
                    Expense.amount.label("Amount")
                )
                .join(Category, Expense.category_id == Category.id)
                .join(SubCategory, Expense.subcategory_id == SubCategory.id)
                .filter(
                    Expense.date.between(
                        pd.to_datetime(start).date(),
                        pd.to_datetime(end).date()
                    )
                )
                .order_by(Expense.date.desc(), Expense.id.desc())
            )
            if sel_cat != "All":
                q = q.filter(Category.name == sel_cat)
            if sel_sub != "All":
                q = q.filter(SubCategory.name == sel_sub)
            df = pd.DataFrame(q.all())
            if "Date" in df.columns:
                df = df.sort_values("Date", ascending=False)
            if df.empty:
                st.info("No data for selected filters")
            else:
                df = df.sort_values("Date", ascending=False)
                top_row = df.groupby("Subcategory")["Amount"].sum().idxmax()
                top_amt = df.groupby("Subcategory")["Amount"].sum().max()
                st.dataframe(df, use_container_width=True, hide_index=True)
                footer_text = (
                    f"Exported on: {today.strftime('%Y-%m-%d')} | "
                    f"Period: {period} | "
                    f"Category: {sel_cat} | "
                    f"Subcategory: {sel_sub} | "
                    f"Top Spend: {top_row} (₹ {top_amt:,.0f}) | "
                    f"Range: {start} → {end}"
                )
                pdf_buf = export_pdf(df, footer_text)
                c1, c2 = st.columns(2)
                with c1:
                    st.download_button(
                        "⬇ CSV",
                        df.to_csv(index=False),
                        "expenses.csv"
                    )
                with c2:
                    st.download_button(
                        "⬇ PDF",
                        data=pdf_buf,
                        file_name=f"expenses_{period}_{start}_{end}.pdf",
                        mime="application/pdf"
                    )
        else:
            st.dataframe(
                pd.DataFrame(
                    columns=["Date", "Category", "Subcategory", "Amount"]
                ),
                use_container_width=True,
                hide_index=True
            )
        # =========================
        # SUMMARY / TOTALS EXPORT
        # =========================
        st.divider()
        st.subheader("📊 Summary / Totals Export")

        # --- SAME PERIOD FILTER (reuse start & end already computed above)

        # --- MULTI CATEGORY SELECT
        all_categories = db.query(Category).all()
        cat_map = {c.name: c.id for c in all_categories}

        sel_categories = st.multiselect(
            "Select Categories",
            options=list(cat_map.keys()),
            default=list(cat_map.keys())
        )

        if not sel_categories:
            st.info("Select at least one category")
            return

        # --- SUBCATEGORY MODE
        sub_mode = st.radio(
            "Subcategory Mode",
            ["All Subcategories", "Select Subcategories"],
            horizontal=True
        )

        selected_sub_ids = []

        if sub_mode == "Select Subcategories":
            sub_options = []
            sub_map = {}

            for cname in sel_categories:
                subs = (
                    db.query(SubCategory)
                    .filter(SubCategory.category_id == cat_map[cname])
                    .all()
                )
                for s in subs:
                    label = f"{cname} → {s.name}"
                    sub_options.append(label)
                    sub_map[label] = s.id

            selected_subs = st.multiselect(
                "Select Subcategories",
                sub_options
            )

            if not selected_subs:
                st.info("Select at least one subcategory")
                return

            selected_sub_ids = [sub_map[x] for x in selected_subs]

        # --- APPLY SUMMARY QUERY
        if st.button("Generate Summary"):
            q = (
                db.query(
                    Category.name.label("Category"),
                    SubCategory.name.label("Subcategory"),
                    func.sum(Expense.amount).label("Total Amount")
                )
                .join(Category, Expense.category_id == Category.id)
                .join(SubCategory, Expense.subcategory_id == SubCategory.id)
                .filter(
                    Expense.date.between(
                        pd.to_datetime(start).date(),
                        pd.to_datetime(end).date()
                    ),
                    Category.name.in_(sel_categories)
                )
            )

            if sub_mode == "Select Subcategories":
                q = q.filter(SubCategory.id.in_(selected_sub_ids))

            df_sum = pd.DataFrame(q.group_by(Category.name, SubCategory.name).all())

            if df_sum.empty:
                st.info("No data for selected filters")

            else:
                st.dataframe(df_sum, use_container_width=True, hide_index=True)

                # --- CATEGORY TOTAL VIEW
                cat_total_df = (
                    df_sum
                    .groupby("Category", as_index=False)["Total Amount"]
                    .sum()
                )
                total = cat_total_df["Total Amount"].sum()
                cat_total_df["Share %"] = (
                    cat_total_df["Total Amount"] / total * 100
                ).round(1)

                # --- ADD TOTAL ROW (FOR CSV + PDF)
                total_value = cat_total_df["Total Amount"].sum()

                total_row = pd.DataFrame([{
                    "Category": "TOTAL",
                    "Total Amount": total_value
                }])

                cat_total_df = pd.concat(
                    [cat_total_df, total_row],
                    ignore_index=True
                )


                st.subheader("📌 Category Totals")
                st.dataframe(cat_total_df, use_container_width=True, hide_index=True)

                # --- CSV EXPORT (CATEGORY TOTALS ONLY)
                st.download_button(
                    "⬇ Download Category Totals CSV",
                    cat_total_df.to_csv(index=False),
                    file_name="expense_category_totals.csv"
                )

                # --- HUMAN READABLE PERIOD LABEL
                if period == "Weekly":
                    period_label = f"{start.strftime('%d %b %Y')} – {end.strftime('%d %b %Y')}"

                elif period == "Monthly":
                    period_label = start.strftime("%b %Y")

                elif period == "Yearly":
                    period_label = start.strftime("%Y")

                else:  # Custom
                    period_label = f"{start.strftime('%d %b %Y')} – {end.strftime('%d %b %Y')}"

                # --- PDF EXPORT (CATEGORY TOTALS ONLY)
                summary_footer = (
                    f"Exported on: {today.strftime('%Y-%m-%d')} | "
                    f"Category Totals Summary | "
                    f"Period: {period_label} | "
                    f"Categories: {', '.join(sel_categories)} | "
                    f"Range: {start} → {end}"
                )

                summary_pdf_buf = export_pdf(cat_total_df, summary_footer)

                st.download_button(
                    "⬇ Download Category Totals PDF",
                    data=summary_pdf_buf,
                    file_name=f"expense_category_totals_{today.strftime('%Y-%m-%d')}.pdf",
                    mime="application/pdf"
                )

# ===========
# ASSETS PAGE
# ===========
# Handle assets page.
def assets_page():
    st.title("🏦 Assets")

    with SessionLocal() as db:
        st.markdown('<div id="asset-inputs"></div>', unsafe_allow_html=True)
        with st.expander("⚙️ Asset Valuation Inputs", expanded=False):

            # =====================================================
            # DASHBOARD – CALCULATIONS ONLY
            # =====================================================

            # ---------- METALS ----------
            gold_grams = db.query(func.sum(MetalAsset.weight_grams))\
                .filter(MetalAsset.metal_type == "Gold").scalar() or 0

            silver_grams = db.query(func.sum(MetalAsset.weight_grams))\
                .filter(MetalAsset.metal_type == "Silver").scalar() or 0

            gold_price = get_price(db, "gold_price", 0.0)
            silver_price = get_price(db, "silver_price", 0.0)

            gold_value = gold_grams * gold_price
            silver_value = silver_grams * silver_price
            metal_total = gold_value + silver_value

            # ---------- LAND ----------
            land_df = pd.read_sql(
                "SELECT location, SUM(area_size) AS sqft FROM land_assets GROUP BY location",
                engine
            )

            land_values = {}
            land_total = 0.0

            for _, r in land_df.iterrows():
                key = f"land:{r['location']}"
                price = get_price(db, key, 0.0)
                val = r["sqft"] * price
                land_values[r["location"]] = val
                land_total += val

            # ---------- FIXED DEPOSITS ----------
            today = date.today()
            fd_total = 0.0

            fds = db.query(FixedDeposit).all()
            for fd in fds:
                if fd.status == "active":
                    if today >= fd.maturity_date:
                        fd.status = "matured"
                    else:
                        fd_total += fd_current_value(
                            fd.principal, fd.rate, fd.deposit_date
                        )
            db.commit()
            
            # ---------- LIC ----------
            try:
                lic_total = db.query(func.sum(LICPolicy.maturity_amount)).scalar() or 0.0
            except Exception:
                lic_total = 0.0

            # =====================================================
            # PRICE INPUTS (PERSISTENT)
            # =====================================================
            st.subheader("💰 Valuation Inputs")

            c1, c2 = st.columns(2)
            with c1:
                gold_price = st.number_input("Gold ₹ / gram", value=gold_price, step=10.0)
                set_price(db, "gold_price", gold_price)

            with c2:
                silver_price = st.number_input("Silver ₹ / gram", value=silver_price, step=1.0)
                set_price(db, "silver_price", silver_price)

            st.markdown("### 🏞️ Land Prices (₹ / sqft)")
            for loc in land_values:
                key = f"land:{loc}"
                p = st.number_input(
                    loc,
                    value=get_price(db, key, 0.0),
                    step=100.0,
                    key=f"dash_{key}"
                )
                set_price(db, key, p)

        # =====================================================
        # DASHBOARD (PIES)
        # =====================================================
        st.subheader("📊 Asset Dashboard")
        col1, col2 = st.columns(2)

        with col1:
            df_main = pd.DataFrame({
            "Category": ["Metals", "Land", "FDs", "LIC"],
            "Value": [metal_total, land_total, fd_total, lic_total]
            })
            fig1 = px.pie(df_main, names="Category", values="Value", hole=0.4)
            fig1.update_layout(paper_bgcolor="#000", font=dict(color="white"))
            fig1.update_traces(marker=dict(line=dict(color="black", width=2)))
            plotly_chart_hi_res(fig1, use_container_width=True)

        with col2:
            # ---------- LIC SUB-BREAKDOWN ----------
            lic_rows = db.query(
                LICPolicy.policy_name,
                LICPolicy.maturity_amount
            ).all()

            lic_labels = [f"LIC – {r.policy_name}" for r in lic_rows]
            lic_values = [r.maturity_amount for r in lic_rows]


            # ---------- SUB PIE DATA ----------
            labels = (
                ["Gold", "Silver"]
                + list(land_values.keys())
                + ["FDs"]
                + lic_labels
            )

            values = (
                [gold_value, silver_value]
                + list(land_values.values())
                + [fd_total]
                + lic_values
            )

            df_sub = pd.DataFrame({"Asset": labels, "Value": values})
            fig2 = px.pie(df_sub, names="Asset", values="Value", hole=0.4)
            fig2.update_layout(paper_bgcolor="#000", font=dict(color="white"))
            fig2.update_traces(marker=dict(line=dict(color="black", width=2)))
            plotly_chart_hi_res(fig2, use_container_width=True)

        # =====================================================
        # VALUATION SUMMARY (NUMBERS BELOW PIE CHARTS)
        # =====================================================
        st.markdown("### 📌 Asset Valuation Summary")

        st.metric(
            "🪙 Metals Total",
            f"₹ {metal_total:,.2f}",
            help=f"Gold: ₹ {gold_value:,.2f} | Silver: ₹ {silver_value:,.2f}"
        )

        st.metric(
            "🏞️ Land Total",
            f"₹ {land_total:,.2f}",
            help="Based on sqft × price per location"
        )

        st.metric(
            "🏦 Fixed Deposits",
            f"₹ {fd_total:,.2f}",
            help="Current value of active FDs"
        )

        st.metric(
            "📜 LIC Policies",
            f"₹ {lic_total:,.2f}",
            help="Total maturity value of all LIC policies"
        )


        grand_total_assets = metal_total + land_total + fd_total + lic_total

        st.divider()

        st.metric(
            "💼 TOTAL ASSETS VALUE",
            f"₹ {grand_total_assets:,.2f}"
        )

        st.caption(
            'Valuations are indicative and based on user-entered prices and accrued interest as of today, so dont forget to input the current day\'s prices accordingly in the'
            '<a href="#asset-inputs">Asset Valuation Inputs</a> section.',
            unsafe_allow_html=True
        )

        st.divider()

        # =====================================================
        # METAL ASSETS – FULL CRUD
        # =====================================================
        with st.expander("🪙 Metal Assets", expanded=False):

            col1, col2 = st.columns(2)
            metal_type = col1.selectbox("Metal", ["Gold", "Silver"])
            weight = col2.number_input("Weight (g)", min_value=0.0, step=0.1)
            entry_date = st.date_input("Date", value=date.today())

            if st.button("➕ Add Metal"):
                if weight > 0:
                    db.add(MetalAsset(
                        metal_type=metal_type,
                        weight_grams=weight,
                        entry_date=entry_date
                    ))
                    db.commit()
                    st.rerun()

            df = pd.DataFrame(
                db.query(
                    MetalAsset.id,
                    MetalAsset.metal_type,
                    MetalAsset.weight_grams,
                    MetalAsset.entry_date
                ).all(),
                columns=["id", "Metal", "Weight (g)", "Date"]
            )
            if not df.empty:
                df["Date"] = pd.to_datetime(df["Date"])
                df = df.sort_values(["Date", "id"], ascending=[False, False]).reset_index(drop=True)

            if not df.empty:
                edit_df = df.set_index("id")
                edited = st.data_editor(edit_df, hide_index=True)
                if st.button("💾 Save Metal Changes"):
                    for row_id, r in edited.iterrows():
                        a = db.get(MetalAsset, int(row_id))
                        if a:
                            a.metal_type = r["Metal"]
                            a.weight_grams = r["Weight (g)"]
                            a.entry_date = pd.to_datetime(r["Date"]).date()
                    db.commit()
                    st.rerun()

                del_ids = st.multiselect(
                    "Delete Metal Entries",
                    df["id"].tolist(),
                    format_func=lambda x: f"Metal ID {x}"
                )

                if del_ids and st.button("❌ Delete Selected Metals"):
                    for i in del_ids:
                        a = db.get(MetalAsset, int(i))
                        if a:
                            db.delete(a)
                    db.commit()
                    st.rerun()

        # ========================
        # LAND ASSETS – FULL CRUD
        # ========================
        with st.expander("🏞️ Land Assets", expanded=False):

            col1, col2 = st.columns(2)
            area = col1.text_input("Area / Locality")
            city = col2.text_input("City")
            sqft = st.number_input("Sqft", min_value=0.0, step=10.0)

            if st.button("➕ Add Land"):
                if area and city and sqft > 0:
                    db.add(LandAsset(
                        location=f"{area}, {city}",
                        area_unit="sqft",
                        area_size=sqft
                    ))
                    db.commit()
                    st.rerun()

            land_tbl = pd.DataFrame(
                db.query(
                    LandAsset.id,
                    LandAsset.location,
                    LandAsset.area_size
                ).all(),
                columns=["id", "Place", "Sqft"]
            )
            if not land_tbl.empty:
                land_tbl = land_tbl.sort_values("id", ascending=False).reset_index(drop=True)

            if not land_tbl.empty:
                edit_tbl = land_tbl.set_index("id")
                edited = st.data_editor(edit_tbl, hide_index=True)
                if st.button("💾 Save Land Changes"):
                    for row_id, r in edited.iterrows():
                        l = db.get(LandAsset, int(row_id))
                        if l:
                            l.location = r["Place"]
                            l.area_size = r["Sqft"]
                    db.commit()
                    st.rerun()

                del_ids = st.multiselect(
                    "Delete Land Entries",
                    land_tbl["id"].tolist(),
                    format_func=lambda x: f"{x} – {land_tbl.loc[land_tbl.id==x,'Place'].values[0]}"
                )

                if del_ids and st.button("❌ Delete Selected Land"):
                    for i in del_ids:
                        l = db.get(LandAsset, int(i))
                        if l:
                            db.delete(l)
                    db.commit()
                    st.rerun()


        with st.expander("🏦 Fixed Deposits", expanded=False):

            # ==============
            # FIXED DEPOSITS
            # ==============
            st.subheader("➕ Add Fixed Deposit")

            fd_name = st.text_input("FD Name")
            principal = st.number_input("Principal (₹)", min_value=0.0, step=1000.0)
            rate = st.number_input("Interest Rate (%)", min_value=0.0, step=0.1)
            tenure_days = st.number_input("Tenure (Days)", min_value=1, step=1)

            deposit_date = st.date_input("Deposit Date")

            maturity_date = deposit_date + timedelta(days=tenure_days)
            tenure_months_legacy = max(1, round(tenure_days / 30))
            maturity_amt = fd_maturity_value(principal, rate, tenure_days)

            c1, c2 = st.columns(2)
            c1.metric("Maturity Amount (₹)", f"{maturity_amt:,.2f}")
            c2.metric("Maturity Date", maturity_date.strftime("%d-%m-%Y"))

            if st.button("💾 Save FD"):
                if fd_name and principal > 0 and rate > 0:
                    db.add(FixedDeposit(
                        name=fd_name,
                        principal=principal,
                        rate=rate,
                        tenure_months=tenure_months_legacy,
                        tenure_days=tenure_days,
                        deposit_date=deposit_date,
                        maturity_date=maturity_date,
                        status="active"
                    ))
                    db.commit()
                    flash("FD added successfully")
                    st.rerun()
                else:
                    st.error("Please fill all FD fields correctly")

            st.divider()

            # ===============================
            # ACTIVE FDs (EDIT / DELETE)
            # ===============================
            st.subheader("📋 Active Fixed Deposits")

            active_fds = db.query(FixedDeposit)\
                .filter(FixedDeposit.status == "active").all()

            if active_fds:
                active_df = pd.DataFrame([{
                    "id": fd.id,
                    "Name": fd.name,
                    "Principal": fd.principal,
                    "Rate (%)": fd.rate,
                    "Tenure (Days)": fd_get_tenure_days(fd),
                    "Deposit Date": fd.deposit_date,
                    "Maturity Date": fd.maturity_date,
                    "Current Value (₹)": fd_current_value(
                        fd.principal, fd.rate, fd.deposit_date
                    )
                } for fd in active_fds])
                active_df["Deposit Date"] = pd.to_datetime(active_df["Deposit Date"])
                active_df = active_df.sort_values(
                    ["Deposit Date", "id"],
                    ascending=[False, False]
                ).reset_index(drop=True)

                edit_active = active_df.set_index("id")
                edited_df = st.data_editor(
                    edit_active,
                    disabled=["Current Value (₹)", "Maturity Date"],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Name": st.column_config.TextColumn("FD Name"),
                        "Principal": st.column_config.NumberColumn("Principal (₹)", min_value=0),
                        "Rate (%)": st.column_config.NumberColumn("Rate (%)", min_value=0),
                        "Deposit Date": st.column_config.DateColumn("Deposit Date"),
                        "Tenure (Days)": st.column_config.NumberColumn(
                            "Tenure (Days)", min_value=1
                        )
                    }
                )


                if st.button("💾 Save Active FD Changes"):
                    for row_id, row in edited_df.iterrows():
                        fd = db.get(FixedDeposit, int(row_id))
                        if fd:
                            fd.name = row["Name"]
                            fd.principal = float(row["Principal"])
                            fd.rate = float(row["Rate (%)"])
                            fd.deposit_date = pd.to_datetime(row["Deposit Date"]).date()
                            fd.tenure_days = int(row["Tenure (Days)"])
                            fd.tenure_months = max(1, round(fd.tenure_days / 30))
                            fd.maturity_date = fd.deposit_date + timedelta(days=fd.tenure_days)
                    db.commit()
                    flash("Active FDs updated successfully")
                    st.rerun()


                delete_ids = st.multiselect(
                    "Delete Active FDs",
                    active_df["id"].tolist(),
                    format_func=lambda x:
                        active_df.loc[active_df.id == x, "Name"].values[0]
                )

                if delete_ids and st.button("❌ Delete Selected Active FDs"):
                    for i in delete_ids:
                        fd = db.get(FixedDeposit, int(i))
                        if fd:
                            db.delete(fd)
                    db.commit()
                    flash("Selected active FDs deleted")
                    st.rerun()
            else:
                st.info("No active fixed deposits")

            st.divider()

            # ===============================
            # MATURED FDs (DELETE / RENEW)
            # ===============================
            st.subheader("✅ Matured Fixed Deposits")

            matured_fds = db.query(FixedDeposit)\
                .filter(FixedDeposit.status == "matured").all()

            if matured_fds:
                matured_df = pd.DataFrame([{
                    "id": fd.id,
                    "Name": fd.name,
                    "Principal": fd.principal,
                    "Rate (%)": fd.rate,
                    "Tenure (Days)": fd_get_tenure_days(fd),
                    "Deposit Date": fd.deposit_date,
                    "Maturity Date": fd.maturity_date,
                    "Maturity Amount (₹)": fd_maturity_value(
                        fd.principal, fd.rate, fd_get_tenure_days(fd)
                    )
                } for fd in matured_fds])
                matured_df["Maturity Date"] = pd.to_datetime(matured_df["Maturity Date"])
                matured_df = matured_df.sort_values(
                    ["Maturity Date", "id"],
                    ascending=[False, False]
                ).reset_index(drop=True)

                matured_view = matured_df.drop(columns=["id"], errors="ignore")
                st.dataframe(matured_view, use_container_width=True, hide_index=True)

                col1, col2 = st.columns(2)

                with col1:
                    del_ids = st.multiselect(
                        "Delete Matured FDs",
                        matured_df["id"].tolist(),
                        format_func=lambda x:
                            matured_df.loc[matured_df.id == x, "Name"].values[0]
                    )

                    if del_ids and st.button("❌ Delete Selected Matured FDs"):
                        for i in del_ids:
                            fd = db.get(FixedDeposit, int(i))
                            if fd:
                                db.delete(fd)
                        db.commit()
                        flash("Matured FDs deleted")
                        st.rerun()

                with col2:
                    renew_id = st.selectbox(
                        "Renew FD",
                        options=[fd.id for fd in matured_fds],
                        format_func=lambda x:
                            matured_df.loc[matured_df.id == x, "Name"].values[0]
                    )

                    if st.button("🔁 Renew Selected FD"):
                        old = db.get(FixedDeposit, int(renew_id))
                        if old:
                            new_dep = date.today()
                            old_tenure_days = fd_get_tenure_days(old)
                            new_mat = new_dep + timedelta(days=old_tenure_days)

                            db.add(FixedDeposit(
                                name=f"{old.name} (Renewed)",
                                principal=old.principal,
                                rate=old.rate,
                                tenure_months=max(1, round(old_tenure_days / 30)),
                                tenure_days=old_tenure_days,
                                deposit_date=new_dep,
                                maturity_date=new_mat,
                                status="active"
                            ))
                            db.commit()
                            flash("FD renewed successfully")
                            st.rerun()
            else:
                st.info("No matured fixed deposits")

        # ===
        # LIC
        # ===
        with st.expander("📜 LIC Policies", expanded=False):

            st.subheader("➕ Add LIC Policy")

            policy_name = st.text_input("Policy Name")
            premium_amount = st.number_input("Premium Amount (₹)", min_value=0.0, step=100.0)
            premium_frequency = st.selectbox(
                "Premium Frequency",
                ["Monthly", "Quarterly", "Half-Yearly", "Yearly"]
            )
            last_premium_date = st.date_input(
                "Last Premium Date (optional)",
                value=date.today()
            )

            no_last_premium = st.checkbox("No last premium date")

            if no_last_premium:
                last_premium_date = None

            maturity_date = st.date_input("Maturity Date")
            maturity_amount = st.number_input("Maturity Amount (₹)", min_value=0.0, step=1000.0)

            if st.button("💾 Save LIC Policy"):
                if policy_name and premium_amount > 0 and maturity_amount > 0:
                    db.add(LICPolicy(
                        policy_name=policy_name,
                        premium_amount=premium_amount,
                        premium_frequency=premium_frequency,
                        last_premium_date=last_premium_date,
                        maturity_date=maturity_date,
                        maturity_amount=maturity_amount
                    ))
                    db.commit()
                    st.rerun()
                else:
                    st.error("Please fill all mandatory LIC fields")

            st.divider()

            st.subheader("📋 LIC Policies")

            try:
                lic_df = pd.DataFrame(
                    db.query(
                        LICPolicy.id,
                        LICPolicy.policy_name,
                        LICPolicy.premium_amount,
                        LICPolicy.premium_frequency,
                        LICPolicy.last_premium_date,
                        LICPolicy.maturity_date,
                        LICPolicy.maturity_amount
                    ).all(),
                    columns=[
                        "id",
                        "Policy Name",
                        "Premium Amount",
                        "Frequency",
                        "Last Premium Date",
                        "Maturity Date",
                        "Maturity Amount"
                    ]
                )
            except Exception:
                lic_df = pd.DataFrame()

            if not lic_df.empty:
                lic_df = lic_df.sort_values("id", ascending=False).reset_index(drop=True)
                edit_lic = lic_df.set_index("id")
                edited = st.data_editor(
                    edit_lic,
                    use_container_width=True,
                    hide_index=True
                )

                if st.button("💾 Save LIC Changes"):
                    for row_id, r in edited.iterrows():
                        p = db.get(LICPolicy, int(row_id))
                        if p:
                            p.policy_name = r["Policy Name"]
                            p.premium_amount = float(r["Premium Amount"])
                            p.premium_frequency = r["Frequency"]
                            p.last_premium_date = (
                                pd.to_datetime(r["Last Premium Date"]).date()
                                if pd.notna(r["Last Premium Date"]) else None
                            )
                            p.maturity_date = pd.to_datetime(r["Maturity Date"]).date()
                            p.maturity_amount = float(r["Maturity Amount"])
                    db.commit()
                    st.rerun()

                del_ids = st.multiselect(
                    "Delete LIC Policies",
                    lic_df["id"].tolist(),
                    format_func=lambda x:
                        lic_df.loc[lic_df.id == x, "Policy Name"].values[0]
                )

                if del_ids and st.button("❌ Delete Selected LIC Policies"):
                    for i in del_ids:
                        p = db.get(LICPolicy, int(i))
                        if p:
                            db.delete(p)
                    db.commit()
                    st.rerun()
            else:
                st.info("No LIC policies added yet")

            st.metric(
                "📜 Total LIC Value",
                f"₹ {lic_total:,.2f}"
            )


        # =====================================================
        # PDF EXPORT (ASSETS WITH TOTALS)
        # =====================================================
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        pdfmetrics.registerFont(TTFont("DejaVu", "DejaVuSans.ttf"))
        st.divider()
        with st.expander("⬇️ Export to PDF", expanded=False):

            export_sections = st.multiselect(
                "Select sections to include",
                ["Metals", "Land", "Fixed Deposits", "LIC"],
                default=["Metals", "Land", "Fixed Deposits", "LIC"]
            )

            if st.button("🧾 Generate PDF Report"):         
                from reportlab.lib.pagesizes import A4
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
                from reportlab.lib.styles import getSampleStyleSheet
                from reportlab.lib import colors
                from io import BytesIO
                import datetime

                buffer = BytesIO()
                doc = SimpleDocTemplate(
                    buffer,
                    pagesize=A4,
                    leftMargin=30,
                    rightMargin=20,
                    topMargin=30,
                    bottomMargin=30
                )
                styles = getSampleStyleSheet()
                from reportlab.lib.styles import ParagraphStyle

                styles.add(ParagraphStyle(
                    name="BlackNormal",
                    fontName="DejaVu",
                    fontSize=10,
                    textColor=colors.white
                ))

                styles.add(ParagraphStyle(
                    name="BlackTitle",
                    fontName="DejaVu",
                    fontSize=20,
                    textColor=colors.white,
                    spaceAfter=14
                ))

                styles.add(ParagraphStyle(
                    name="BlackHeading",
                    fontName="DejaVu",
                    fontSize=14,
                    textColor=colors.white,
                    spaceAfter=10
                ))

                story = []
                story.append(Paragraph("Assets Valuation Report", styles["BlackTitle"]))
                story.append(Paragraph(
                    f"Generated on: {datetime.date.today()}",
                    styles["BlackNormal"]
                ))
                story.append(Spacer(1, 14))


                GRAND_TOTAL = 0.0
                story.append(Spacer(1, 12))

                # =====================================================
                # METALS
                # =====================================================
                if "Metals" in export_sections:
                    gold_price = get_price(db, "gold_price")
                    silver_price = get_price(db, "silver_price")

                # =====================================================
                # METALS (GOLD & SILVER SIDE BY SIDE)
                # =====================================================
                gold_price = get_price(db, "gold_price")
                silver_price = get_price(db, "silver_price")

                metals_df = pd.read_sql("""
                    SELECT metal_type, weight_grams
                    FROM metal_assets
                """, engine)

                # ---- Split
                gold_df = metals_df[metals_df["metal_type"] == "Gold"].copy()
                silver_df = metals_df[metals_df["metal_type"] == "Silver"].copy()

                # ---- Values
                gold_df["Value (₹)"] = (gold_df["weight_grams"] * gold_price).round(2)
                silver_df["Value (₹)"] = (silver_df["weight_grams"] * silver_price).round(2)

                gold_total = gold_df["Value (₹)"].sum()
                silver_total = silver_df["Value (₹)"].sum()

                GRAND_TOTAL += (gold_total + silver_total)

                # ---- Heading
                story.append(Paragraph("<b>Metal Assets</b>", styles["BlackHeading"]))
                story.append(Paragraph(
                    f"Gold ₹/g: {gold_price} | Silver ₹/g: {silver_price}",
                    styles["BlackNormal"]
                ))
                story.append(Spacer(1, 8))

                # ---- GOLD TABLE
                gold_table_data = [["Gold (grams)", "Value (₹)"]]
                gold_table_data += gold_df[["weight_grams", "Value (₹)"]].values.tolist()
                gold_table_data.append(["TOTAL", f"{gold_total:,.2f}"])

                gold_table = Table(gold_table_data, colWidths=[80, 90])
                gold_table.setStyle(TableStyle([
                    ("FONT", (0,0), (-1,-1), "DejaVu"),
                    ("BACKGROUND", (0,0), (-1,0), colors.black),
                    ("BACKGROUND", (0,1), (-1,-1), colors.black),
                    ("TEXTCOLOR", (0,0), (-1,-1), colors.white),
                    ("GRID", (0,0), (-1,-1), 0.5, colors.white),
                    ("ALIGN", (0,0), (-1,-1), "CENTER"),
                ]))

                # ---- SILVER TABLE
                silver_table_data = [["Silver (grams)", "Value (₹)"]]
                silver_table_data += silver_df[["weight_grams", "Value (₹)"]].values.tolist()
                silver_table_data.append(["TOTAL", f"{silver_total:,.2f}"])

                silver_table = Table(silver_table_data, colWidths=[80, 90])
                silver_table.setStyle(TableStyle([
                    ("FONT", (0,0), (-1,-1), "DejaVu"),
                    ("BACKGROUND", (0,0), (-1,0), colors.black),
                    ("BACKGROUND", (0,1), (-1,-1), colors.black),
                    ("TEXTCOLOR", (0,0), (-1,-1), colors.white),
                    ("GRID", (0,0), (-1,-1), 0.5, colors.white),
                    ("ALIGN", (0,0), (-1,-1), "CENTER"),
                ]))

                # ---- SIDE BY SIDE WRAPPER
                wrapper = Table(
                    [[gold_table, silver_table]],
                    colWidths=[250, 250]
                )

                story.append(wrapper)
                story.append(Spacer(1, 14))


                # =====================================================
                # LAND
                # =====================================================
                if "Land" in export_sections:
                    land_df = pd.read_sql("""
                        SELECT location, area_size
                        FROM land_assets
                    """, engine)

                    land_df["Price ₹/sqft"] = land_df["location"].apply(
                        lambda loc: get_price(db, f"land:{loc}")
                    )
                    land_df["Value (₹)"] = land_df["area_size"] * land_df["Price ₹/sqft"]

                    total_land = land_df["Value (₹)"].sum()
                    GRAND_TOTAL += total_land

                    story.append(Paragraph("<b>Land Assets</b>", styles["BlackHeading"]))
                    story.append(Spacer(1, 6))

                    table_data = [list(land_df.columns)] + land_df.values.tolist()
                    table_data.append(["", "TOTAL", "", f"{total_land:,.2f}"])

                    table = Table(table_data, hAlign="LEFT")
                    table.setStyle(TableStyle([
                        ("FONT", (0,0), (-1,-1), "DejaVu"),
                        ("BACKGROUND", (0,0), (-1,0), colors.black),
                        ("BACKGROUND", (0,1), (-1,-1), colors.black),
                        ("TEXTCOLOR", (0,0), (-1,-1), colors.white),
                        ("GRID", (0,0), (-1,-1), 0.5, colors.white),
                        ("ALIGN", (0,0), (-1,-1), "LEFT"),
                        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                        ("LEFTPADDING", (0,0), (-1,-1), 6),
                        ("RIGHTPADDING", (0,0), (-1,-1), 6),
                    ]))


                    story.append(table)
                    story.append(Spacer(1, 14))

                # =====================================================
                # FIXED DEPOSITS
                # =====================================================
                if "Fixed Deposits" in export_sections:
                    try:
                        fd_df = pd.read_sql("""
                            SELECT
                                name,
                                principal,
                                rate,
                                COALESCE(tenure_days, tenure_months * 30) AS tenure_days,
                                deposit_date
                            FROM fixed_deposits
                        """, engine)

                        today = datetime.date.today()

                        fd_df["Current Value (₹)"] = fd_df.apply(
                            lambda r: round(
                                r["principal"] *
                                ((1 + r["rate"] / 100) **
                                ((today - pd.to_datetime(r["deposit_date"]).date()).days / 365)),
                                2
                            ),
                            axis=1
                        )

                        total_fd = fd_df["Current Value (₹)"].sum()
                        GRAND_TOTAL += total_fd

                        story.append(Paragraph("<b>Fixed Deposits</b>", styles["BlackHeading"]))
                        story.append(Spacer(1, 6))

                        table_data = [list(fd_df.columns)] + fd_df.values.tolist()
                        table_data.append([
                            "TOTAL",   # Deposit Account
                            "",        # principal
                            "",        # rate
                            "",        # tenure_days
                            "",        # deposit_date
                            f"{total_fd:,.2f}"  # Current Value
                        ])

                        table = Table(table_data, hAlign="LEFT")
                        table.setStyle(TableStyle([
                            ("FONT", (0,0), (-1,-1), "DejaVu"),
                            ("BACKGROUND", (0,0), (-1,0), colors.black),
                            ("BACKGROUND", (0,1), (-1,-1), colors.black),
                            ("TEXTCOLOR", (0,0), (-1,-1), colors.white),
                            ("GRID", (0,0), (-1,-1), 0.5, colors.white),
                            ("ALIGN", (0,0), (-1,-1), "LEFT"),
                            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                            ("LEFTPADDING", (0,0), (-1,-1), 6),
                            ("RIGHTPADDING", (0,0), (-1,-1), 6),
                        ]))

                        story.append(table)

                    except Exception:
                        story.append(Paragraph("Fixed Deposits not available.", styles["BlackNormal"]))

                # =====================================================
                # LIC POLICIES
                # =====================================================
                if "LIC" in export_sections:
                    lic_df = pd.read_sql("""
                        SELECT policy_name, premium_amount, premium_frequency,
                            last_premium_date, maturity_date, maturity_amount
                        FROM lic_policies
                    """, engine)

                    if not lic_df.empty:
                        total_lic = lic_df["maturity_amount"].sum()
                        GRAND_TOTAL += total_lic

                        story.append(Paragraph("<b>LIC Policies</b>", styles["BlackHeading"]))
                        story.append(Spacer(1, 6))

                        table_data = [list(lic_df.columns)] + lic_df.values.tolist()
                        table_data.append(["TOTAL", "", "", "", "", f"{total_lic:,.2f}"])

                        table = Table(table_data)
                        table.setStyle(TableStyle([
                            ("FONT", (0,0), (-1,-1), "DejaVu"),
                            ("BACKGROUND", (0,0), (-1,0), colors.black),
                            ("BACKGROUND", (0,1), (-1,-1), colors.black),
                            ("TEXTCOLOR", (0,0), (-1,-1), colors.white),
                            ("GRID", (0,0), (-1,-1), 0.5, colors.white),
                        ]))

                        story.append(table)
                        story.append(Spacer(1, 14))


                # ================= GRAND TOTAL =================
                story.append(Spacer(1, 24))

                story.append(Paragraph(
                    f"<b>GRAND TOTAL ASSETS VALUE</b>",
                    styles["BlackHeading"]
                ))

                story.append(Spacer(1, 6))

                story.append(Paragraph(
                    f"₹ {GRAND_TOTAL:,.2f}",
                    ParagraphStyle(
                        name="GrandTotalValue",
                        fontName="DejaVu",
                        fontSize=18,
                        textColor=colors.white,
                        leading=22
                    )
                ))

                from reportlab.lib import colors
                # Handle black page background.
                def black_page_background(canvas, doc):
                    canvas.saveState()
                    canvas.setFillColor(colors.black)
                    canvas.rect(
                        0,
                        0,
                        doc.pagesize[0],
                        doc.pagesize[1],
                        fill=1,
                        stroke=0
                    )
                    canvas.restoreState()

                doc.build(
                    story,
                    onFirstPage=black_page_background,
                    onLaterPages=black_page_background
                )

                st.download_button(
                    "⬇️ Download Assets PDF",
                    data=buffer.getvalue(),
                    file_name="assets_report.pdf",
                    mime="application/pdf"
                )

# ======================
# APPLIANCES PAGE   
# ======================
# Handle appliances page.
def appliances_page():
    st.header("🔌 Appliances")

    show_thumbnails = st.toggle("Show Thumbnails", value=False)

    with st.form("add_appliance"):
        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input("Appliance Name")

        with col2:
            price = st.number_input(
                "Price",
                min_value=0.0,
                step=100.0,
                format="%.2f"
            )

        col3, col4 = st.columns(2)

        with col3:
            purchase_date = st.date_input(
                "Purchase Date",
                value=date.today()
            )

        with col4:
            warranty_expiry = st.date_input(
                "Warranty Expiry",
                value=None
            )

        images = st.file_uploader(
            "Upload Appliance & Invoice Images",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True
        )

        submit = st.form_submit_button("Add Appliance")


        if submit and name:
            db = SessionLocal()
            appliance = Appliance(
                name=name,
                price=price,
                purchase_date=purchase_date,
                warranty_expiry=warranty_expiry,
            )
            db.add(appliance)
            db.commit()
            db.refresh(appliance)

            if images:
                for img in images:
                    safe = f"{int(time.time())}_{img.name}"
                    path = os.path.join(APPLIANCE_IMG_DIR, safe)
                    with open(path, "wb") as f:
                        f.write(img.getbuffer())

                    db.add(ApplianceImage(
                        appliance_id=appliance.id,
                        image_path=path
                    ))

            db.commit()
            db.close()
            flash("Appliance added")
            st.rerun()

    db = SessionLocal()
    appliances = (
        db.query(Appliance)
        .options(joinedload(Appliance.images))
        .order_by(Appliance.purchase_date.desc(), Appliance.id.desc())
        .all()
    )
    db.close()

    st.divider()
    if not appliances:
        st.info("No appliances added yet")
        return

    # ======================
    # APPLIANCES PIE CHARTS
    # ======================
    with st.expander("📊 Appliance Insights", expanded=False):
        chart_type = st.radio(
            "View",
            ["By Value", "By Purchase Year"],
            horizontal=True
        )

        if appliances:
            # ---------- BY VALUE ----------
            if chart_type == "By Value":
                df_pie = pd.DataFrame([{
                    "Appliance": a.name,
                    "Price": float(a.price)
                } for a in appliances])

                fig = px.pie(
                    df_pie,
                    names="Appliance",
                    values="Price",
                    hole=0.4
                )

            # ---------- BY YEAR ----------
            else:
                df_pie = pd.DataFrame([{
                    "Year": a.purchase_date.year
                } for a in appliances])

                df_pie = df_pie.value_counts().reset_index()
                df_pie.columns = ["Year", "Count"]

                fig = px.pie(
                    df_pie,
                    names="Year",
                    values="Count",
                    hole=0.4
                )

            # ---------- DARK THEME ----------
            fig.update_layout(
                paper_bgcolor="black",
                plot_bgcolor="black",
                font=dict(color="white"),
                legend=dict(font=dict(color="white"))
            )

            fig.update_traces(
                marker=dict(line=dict(color="black", width=2))
            )

            plotly_chart_hi_res(fig, use_container_width=True)

        else:
            st.info("No appliance data available to visualize.")

    for a in appliances:
        with st.expander(f"{a.name} | ₹{a.price:,.0f} | {a.purchase_date}"):

            # ======================
            # VIEW MODE
            # ======================
            if not is_edit_mode(a.id):
                c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
                c1.write(f"**Appliance**: {a.name}")
                c2.write(f"**Price**: ₹{a.price:,.2f}")
                c3.write(f"**Purchased**: {a.purchase_date}")
                c4.write(f"**Warranty**: {a.warranty_expiry or '—'}")

                # ---- IMAGE VIEW (LOCAL VIEWER)
                if a.images:
                    st.divider()
                    for img in a.images:
                        if show_thumbnails and os.path.exists(img.image_path):
                            st.image(img.image_path, width=200)

                        col_img1, col_img2, col_img3 = st.columns([4, 1, 1])

                        col_img1.write(os.path.basename(img.image_path))

                        if col_img2.button(
                            "📂 Open",
                            key="openimg_" + str(img.id)
                        ):
                            open_image(img.image_path)

                        if col_img3.button(
                            "❌ Delete",
                            key="delimg_" + str(img.id)
                        ):
                            st.session_state["confirm_img_" + str(img.id)] = True

                    for img in a.images:
                        key = "confirm_img_" + str(img.id)
                        if st.session_state.get(key):
                            st.warning("Delete this image permanently?")
                            y, n = st.columns(2)

                            if y.button("Yes", key="yesimg_" + str(img.id)):
                                db = SessionLocal()
                                img_db = db.get(ApplianceImage, img.id)

                                if img_db:
                                    if os.path.exists(img_db.image_path):
                                        os.remove(img_db.image_path)
                                    db.delete(img_db)
                                    db.commit()
                                    db.close()

                                del st.session_state[key]
                                st.rerun()

                            if n.button("Cancel", key="noimg_" + str(img.id)):
                                del st.session_state[key]

                st.divider()

                col_edit, col_delete = st.columns([1, 1])

                if col_edit.button("✏️ Edit", key="edit_" + str(a.id)):
                    st.session_state[f"edit_mode_{a.id}"] = True
                    st.rerun()

                if col_delete.button("❌ Delete Appliance", key="del_" + str(a.id)):
                    st.session_state["confirm_" + str(a.id)] = True

            # ======================
            # EDIT MODE
            # ======================
            else:
                with st.form("edit_form_" + str(a.id)):
                    col1, col2 = st.columns(2)
                    with col1:
                        edit_name = st.text_input(
                            "Appliance Name",
                            value=a.name
                        )
                    with col2:
                        edit_price = st.number_input(
                            "Price",
                            min_value=0.0,
                            step=100.0,
                            format="%.2f",
                            value=float(a.price)
                        )

                    col3, col4 = st.columns(2)
                    with col3:
                        edit_purchase_date = st.date_input(
                            "Purchase Date",
                            value=a.purchase_date
                        )
                    with col4:
                        edit_warranty = st.date_input(
                            "Warranty Expiry",
                            value=a.warranty_expiry
                        )

                    new_images = st.file_uploader(
                        "Add More Images",
                        type=["jpg", "jpeg", "png"],
                        accept_multiple_files=True
                    )

                    col_save, col_cancel = st.columns(2)
                    save = col_save.form_submit_button("💾 Save Changes")
                    cancel = col_cancel.form_submit_button("❌ Cancel")

                    if save:
                        db = SessionLocal()
                        appliance = db.get(Appliance, a.id)
                        appliance.name = edit_name
                        appliance.price = edit_price
                        appliance.purchase_date = edit_purchase_date
                        appliance.warranty_expiry = edit_warranty

                        if new_images:
                            for img in new_images:
                                safe = f"{int(time.time())}_{img.name}"
                                path = os.path.join(APPLIANCE_IMG_DIR, safe)
                                with open(path, "wb") as f:
                                    f.write(img.getbuffer())

                                db.add(ApplianceImage(
                                    appliance_id=appliance.id,
                                    image_path=path
                                ))

                        db.commit()
                        db.close()

                        st.session_state[f"edit_mode_{a.id}"] = False
                        flash("Appliance updated")
                        st.rerun()

                    if cancel:
                        st.session_state[f"edit_mode_{a.id}"] = False
                        st.rerun()

            # ======================
            # DELETE CONFIRMATION
            # ======================
            if st.session_state.get("confirm_" + str(a.id)):
                st.warning("This will permanently delete this appliance and all its images.")
                yes, no = st.columns(2)

                if yes.button("Yes, Delete", key="yes_" + str(a.id)):
                    db = SessionLocal()
                    appliance = db.get(Appliance, a.id)

                    for img in appliance.images:
                        if os.path.exists(img.image_path):
                            os.remove(img.image_path)

                    db.delete(appliance)
                    db.commit()
                    db.close()

                    del st.session_state["confirm_" + str(a.id)]
                    flash("Appliance deleted")
                    st.rerun()

                if no.button("Cancel", key="no_" + str(a.id)):
                    del st.session_state["confirm_" + str(a.id)]

# ======================
# APPLIANCES PDF EXPORT
# ======================
    st.divider()
    with st.expander("⬇️ Export Appliances Data as PDF", expanded=False):

                if st.button(
                        "🧾 Generate Appliances Data PDF",
                        key="appliances_pdf_export"
                    ):

                    from reportlab.platypus import (
                        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
                    )
                    from reportlab.lib.pagesizes import A4
                    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
                    from reportlab.lib import colors
                    from io import BytesIO
                    import datetime

                    buffer = BytesIO()

                    doc = SimpleDocTemplate(
                        buffer,
                        pagesize=A4,
                        leftMargin=30,
                        rightMargin=30,
                        topMargin=30,
                        bottomMargin=30
                    )

                    styles = getSampleStyleSheet()

                    styles.add(ParagraphStyle(
                        name="WhiteTitle",
                        fontName="DejaVu",
                        fontSize=20,
                        textColor=colors.white,
                        spaceAfter=14
                    ))

                    styles.add(ParagraphStyle(
                        name="WhiteNormal",
                        fontName="DejaVu",
                        fontSize=10,
                        textColor=colors.white,
                        spaceAfter=6
                    ))

                    styles.add(ParagraphStyle(
                        name="WhiteHeading",
                        fontName="DejaVu",
                        fontSize=14,
                        textColor=colors.white,
                        spaceAfter=10
                    ))

                    story = []

                    # -------- TITLE --------
                    story.append(Paragraph("Appliances Report", styles["WhiteTitle"]))
                    story.append(Paragraph(
                        f"Generated on: {datetime.date.today()}",
                        styles["WhiteNormal"]
                    ))
                    story.append(Spacer(1, 12))

                    # -------- FETCH DATA --------
                    db = SessionLocal()
                    appliances = (
                        db.query(Appliance)
                        .options(joinedload(Appliance.images))
                        .order_by(Appliance.purchase_date.desc(), Appliance.id.desc())
                        .all()
                    )
                    db.close()

                    if not appliances:
                        story.append(Paragraph(
                            "No appliance data available.",
                            styles["WhiteNormal"]
                        ))
                    else:
                        table_data = [
                                ["Name", "Price (₹)", "Purchase Date", "Warranty Expiry"]
                        ]

                        for ap in appliances:
                            table_data.append([
                                ap.name,
                                f"{ap.price:,.2f}",
                                ap.purchase_date.strftime("%Y-%m-%d"),
                                ap.warranty_expiry.strftime("%Y-%m-%d") if ap.warranty_expiry else "—"
                            ])

                        table = Table(
                            table_data,
                            colWidths=[160, 90, 100, 100],
                            hAlign="LEFT"
                        )

                        table.setStyle(TableStyle([
                            ("FONT", (0, 0), (-1, -1), "DejaVu"),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.black),
                            ("BACKGROUND", (0, 1), (-1, -1), colors.black),
                            ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.white),
                            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("TOPPADDING", (0, 0), (-1, -1), 6),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ]))

                        story.append(table)

                    # -------- BLACK PAGE BACKGROUND --------
                    def black_page(canvas, doc):
                        canvas.saveState()
                        canvas.setFillColor(colors.black)
                        canvas.rect(
                            0, 0,
                            doc.pagesize[0],
                            doc.pagesize[1],
                            fill=1,
                            stroke=0
                        )
                        canvas.restoreState()

                    doc.build(
                        story,
                        onFirstPage=black_page,
                        onLaterPages=black_page
                    )

                    st.download_button(
                        "⬇️ Download Appliances PDF",
                        data=buffer.getvalue(),
                        file_name="appliances_report.pdf",
                        mime="application/pdf"
                    )

# ======================
# CAPABILITIES PAGE
# ======================
def capabilities_page():
    st.title("🧭 Tracker Capabilites")
    st.caption("A clean map of what your tracker covers, grouped by purpose.")

    st.markdown("## ✅ Everyday Tracking")
    st.markdown(
        """
**Expenses**
- Add expenses with category and subcategory
- Edit and delete entries, including bulk actions
- Monthly, yearly, and custom period filters
- Daily buy sidebar drilldown

**Income**
- Add income with category and subcategory
- Period filters and income summaries
- Edit and delete income entries
- Breakdown charts by category and subcategory
        """
    )

    st.markdown("## 📊 Analytics & Insights")
    st.markdown(
        """
**Visual Analytics**
- Calendar view with daily totals and filters
- Cumulative spending curve
- Category and subcategory charts (pie or bar)
- Advanced visuals: treemap, sunburst, waterfall, distribution

**Insights**
- Average spend (weekly, monthly, yearly)
- Top 5 categories and subcategories per month
- Category trend comparison (month‑over‑month)
- Anomaly detection using rolling median and MAD
        """
    )

    st.markdown("## 🏦 Assets & Net Worth")
    st.markdown(
        """
**Assets**
- Metals (gold and silver) with weight-based valuation
- Land assets with location-based pricing
- Fixed deposits with maturity tracking and renewal
- LIC policies with maturity value tracking
- Asset dashboard totals and breakdowns
        """
    )

    st.markdown("## 🔌 Appliances")
    st.markdown(
        """
**Inventory**
- Appliance inventory with warranty tracking
- Image uploads (appliance and invoice)
- Appliance insights charts
- Appliance PDF report export
        """
    )

    st.markdown("## 📤 Exports & Reports")
    st.markdown(
        """
**Exports**
- Expense CSV and PDF exports by period and filters
- Category totals CSV and PDF summary
- Income PDF export
- Assets PDF export

**Reports**
- Weekly and monthly expense reports (PDF)
- Manual monthly report sender from sidebar
        """
    )

    st.markdown("## ⚙️ Automation & Storage")
    st.markdown(
        """
**Automation**
- Weekly Google Drive database backup (when available)
- Weekly and monthly email reports via SMTP

**Storage**
- Local SQLite database by default
- Fully offline unless email or Google Drive features are enabled
        """
    )


def longevity_check_page():
    st.title("🛡️ Longevity Check")
    st.caption("Local-first 10-year maintenance checklist for your tracker.")

    now_dt = datetime.datetime.now()
    backup_raw = read_state_value(BACKUP_STATE_FILE)
    maint_raw = read_state_value(DB_MAINT_STATE_FILE)
    weekly_raw = read_state_value(WEEKLY_EMAIL_STATE_FILE)
    monthly_raw = read_state_value(MONTHLY_EMAIL_STATE_FILE)

    backup_dt = _parse_state_datetime(backup_raw)
    maint_dt = _parse_state_datetime(maint_raw)

    backup_days = (now_dt - backup_dt).days if backup_dt else None
    maint_days = (now_dt - maint_dt).days if maint_dt else None

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Last Backup", format_state_value(backup_raw))
        st.caption("Target: once every 7 days")
    with c2:
        st.metric("Last DB Maintenance", format_state_value(maint_raw))
        st.caption("Target: once every 30 days")
    with c3:
        db_size, db_size_err = get_db_size()
        st.metric("DB Size", format_bytes(db_size) if db_size is not None else "N/A")
        if db_size is None:
            st.caption(db_size_err)

    st.markdown("### Checklist")
    st.write(f"{'✅' if backup_days is not None and backup_days <= 7 else '⚠️'} Weekly backup freshness (<= 7 days)")
    st.write(f"{'✅' if maint_days is not None and maint_days <= 30 else '⚠️'} DB maintenance freshness (<= 30 days)")
    st.write(f"{'✅' if os.path.exists('requirements.txt') else '⚠️'} `requirements.txt` present")
    st.write(f"{'⚠️' if os.path.exists(SECRETS_FILE_PATH) else '✅'} Secrets file location review")
    st.write(f"{'✅' if weekly_raw else '⚠️'} Weekly email status file present")
    st.write(f"{'✅' if monthly_raw else '⚠️'} Monthly email status file present")

    st.markdown("### Maintenance Actions")
    a1, a2, a3 = st.columns(3)
    with a1:
        if st.button("Run Integrity Check"):
            ok, msg = run_db_integrity_check()
            if ok:
                st.success(msg)
            else:
                st.error(msg)
    with a2:
        if st.button("Run DB Maintenance Now"):
            with st.spinner("Running DB maintenance..."):
                ok, msg = run_db_maintenance()
            if ok:
                st.success(msg)
            else:
                st.error(msg)
    with a3:
        if st.button("Verify Backup File"):
            ok, msg = verify_gdrive_backup()
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    st.markdown("### Safety Snapshot")
    st.caption("Download a portable local snapshot (CSV tables + requirements) for long-term recoverability.")
    snapshot_bytes = _build_safety_snapshot_zip()
    st.download_button(
        "⬇️ Download Safety Snapshot (.zip)",
        data=snapshot_bytes,
        file_name=f"tracker_safety_snapshot_{date.today().isoformat()}.zip",
        mime="application/zip"
    )


st.markdown('<div id="breadcrumbs"></div>', unsafe_allow_html=True)
# ======================
# SIDEBAR NAVIGATION
# ======================
st.sidebar.title("💰 Finance Tracker")
page = st.sidebar.radio(
    "Navigate",
    [
    "📊 Expense Dashboard",
    "➕ Add Expense",
    "🧾 Import Expenses",
    "🎫 Events",
    "📤 Export Expenses",
    "🔌 Appliances Data",
    "💰 Income",
    "🏦 Assets",
    "📈 Insights",
    "🛡️ Longevity Check",
    "🧭 Tracker Capabilites",
    ],
    index=1
)       
with st.sidebar.expander("📨 Send Monthly Report"):
    month_options = get_month_options(24)
    if not month_options:
        st.info("No monthly data found yet.")
    else:
        month_labels = [label for label, _ in month_options]
        selected_label = st.selectbox("Select month", month_labels, index=0)
        month_map = {label: dt for label, dt in month_options}
        target_email = st.text_input("Send to email", value=SMTP_TO)
        if st.button("Send Monthly Report"):
            with st.spinner("Sending monthly report..."):
                send_custom_monthly_report(month_map[selected_label], target_email)

if st.sidebar.button("Backup Database Now"):
    with st.sidebar.spinner("Backing up database..."):
        ok, msg = backup_db_to_gdrive()
    if ok:
        st.sidebar.success("Database backed up.")
    else:
        st.sidebar.error(msg)

render_system_status_panel()

# ======================
# PAGE ROUTING
# ======================
PAGE_ORDER = {
    "📊 Expense Dashboard": 0,
    "➕ Add Expense": 1,
    "🧾 Import Expenses": 2,
    "🎫 Events": 3,
    "📤 Export Expenses": 4,
    "🔌 Appliances Data": 5,
    "💰 Income": 6,
    "🏦 Assets": 7,
    "📈 Insights": 8,
    "🛡️ Longevity Check": 9,
    "🧭 Tracker Capabilites": 10
}

current_page = page                                                # whatever variable you use
prev_page = st.session_state.get("prev_page", current_page)        # get previous page from session state
direction = "right"                                                # default direction
if PAGE_ORDER.get(current_page, 0) < PAGE_ORDER.get(prev_page, 0): # if current_page != prev_page:
    direction = "left"                                             # determine direction
st.session_state.prev_page = current_page                          # update previous page
st.markdown(                                                       # inject direction attribute 
    f"""
    <script>
    document.documentElement.setAttribute(
        "data-nav-direction",
        "{direction}"
    );
    </script>
    """,    
    unsafe_allow_html=True
)                                                                 
# ======================
# BREADCRUMBS RENDERING
# ======================
def render_breadcrumbs(page):                             
    st.markdown(
        f"""
        <div class="breadcrumb">
            Home <span>›</span> {page}
        </div>
        """,
        unsafe_allow_html=True
    )
render_breadcrumbs(current_page)
# =============
# PAGE ROUTING
# =============
if page == "📊 Expense Dashboard":
    dashboard()
elif page == "➕ Add Expense":
    add_expense()
elif page == "🧾 Import Expenses":
    import_expenses_page()
elif page == "🎫 Events":
    events_page()
elif page == "💰 Income":
    income_section()
elif page == "🏦 Assets":
    assets_page()
elif page == "📈 Insights":
    insights()
elif page == "🛡️ Longevity Check":
    longevity_check_page()
elif page == "🔌 Appliances Data":
    appliances_page()
elif page == "📤 Export Expenses":
    export_data()
elif page == "🧭 Tracker Capabilites":
    capabilities_page()
