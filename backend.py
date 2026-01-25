import datetime
from datetime import date, timedelta
import pandas as pd
import io
from io import BytesIO
import json
import re
import os, time, platform, subprocess

from sqlalchemy import (
    DateTime, create_engine, Column, Integer, String,
    Float, Date, ForeignKey, UniqueConstraint, func, text
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from dateutil.relativedelta import relativedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
pdfmetrics.registerFont(TTFont("DejaVu", "DejaVuSans.ttf"))


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///expense.db")
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False
)

def get_db():
    return SessionLocal()

def fetch_expense_dataframe():
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

# ==============
# MODELS
# ==============
Base = declarative_base()                               
class Category(Base):                                   
    __tablename__ = "categories"                         
    id = Column(Integer, primary_key=True)               
    name = Column(String, unique=True, nullable=False)  
# ==============
# SUBCATEGORY
# ==============
class SubCategory(Base):                                                
    __tablename__ = "subcategories"                              
    id = Column(Integer, primary_key=True)                        
    name = Column(String, nullable=False)                         
    category_id = Column(Integer, ForeignKey("categories.id"))    
    __table_args__ = (UniqueConstraint("name", "category_id"),)   
# ==============
# EXPENSE
# ==============
class Expense(Base):                                                       
    __tablename__ = "expenses"                                                  
    id = Column(Integer, primary_key=True)                                      
    category_id = Column(Integer, ForeignKey("categories.id"), index=True)      
    subcategory_id = Column(Integer, ForeignKey("subcategories.id"), index=True)
    date = Column(Date, nullable=False, index=True)                                
    amount = Column(Float, nullable=False)                                     
# ==============
# INCOME MODELS
# ==============
class IncomeCategory(Base):                                           
    __tablename__ = "income_categories"                                
    id = Column(Integer, primary_key=True)                             
    name = Column(String, unique=True, nullable=False)                 
# ==================
# INCOME SUBCATEGORY
# ==================
class IncomeSubCategory(Base):                                         
    __tablename__ = "income_subcategories"                             
    id = Column(Integer, primary_key=True)                             
    name = Column(String, nullable=False)                              
    category_id = Column(Integer, ForeignKey("income_categories.id"))  
    __table_args__ = (UniqueConstraint("name", "category_id"),)        
# =======
# INCOME
# =======
class Income(Base):                                 
    __tablename__ = "income"                       
    id = Column(Integer, primary_key=True)        
    category_id = Column(Integer, ForeignKey("income_categories.id"), index=True)        
    subcategory_id = Column(Integer, ForeignKey("income_subcategories.id"), index=True)  
    date = Column(Date, nullable=False, index=True)
    amount = Column(Float, nullable=False)          

# ============
# ASSET MODELS
# ============
#----METAL ASSETS----
class MetalAsset(Base):                         
    __tablename__ = "metal_assets"                
    id = Column(Integer, primary_key=True)       
    metal_type = Column(String, nullable=False)   
    weight_grams = Column(Float, nullable=False)  
    entry_date = Column(Date, nullable=False)     
    created_at = Column(DateTime, default=datetime.datetime.utcnow) 
#----LAND ASSETS----
class LandAsset(Base):
    __tablename__ = "land_assets"
    id = Column(Integer, primary_key=True)           
    asset_id = Column(Integer, nullable=True)        
    location = Column(String, nullable=False)        
    area_unit = Column(String, nullable=False)      
    area_size = Column(Float, nullable=False)        
    price_per_unit = Column(Float, nullable=True)    
# ----ASSET PRICES----
class AssetPrice(Base):
    __tablename__ = "asset_prices"          
    key = Column(String, primary_key=True)  
    value = Column(Float, nullable=False)    
# ----FIXED DEPOSITS----
class FixedDeposit(Base):                              
    __tablename__ = "fixed_deposits"                  
    id = Column(Integer, primary_key=True)            
    name = Column(String, nullable=False)             
    principal = Column(Float, nullable=False)         
    rate = Column(Float, nullable=False)              
    tenure_months = Column(Integer, nullable=False)         
    deposit_date = Column(Date, nullable=False)       
    maturity_date = Column(Date, nullable=False)      
    status = Column(String, default="active")        
    created_at = Column(DateTime, default=datetime.datetime.utcnow) 
# ----APPLIANCES----
class Appliance(Base):                                  
    __tablename__ = "appliances"                      
    id = Column(Integer, primary_key=True)             
    name = Column(String, nullable=False)                     
    price = Column(Float, nullable=False)                
    purchase_date = Column(Date, nullable=False)        
    warranty_expiry = Column(Date, nullable=True)       
    depreciation_years = Column(Integer, nullable=True)  
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
    frequency = Column(String, nullable=False) 
    last_premium_date = Column(Date, nullable=True)
    maturity_date = Column(Date, nullable=False)
    maturity_amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


# ======================
# INVESTMENTS (STOCK / MF / ETF)
# ======================
class Investment(Base):
    __tablename__ = "investments"

    id = Column(Integer, primary_key=True)
    instrument = Column(String, nullable=False)      
    name = Column(String, nullable=False)            
    units = Column(Float, nullable=False)
    buy_price = Column(Float, nullable=False)
    buy_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

Base.metadata.create_all(bind=engine)  

def migrate_appliances_schema():                         
    with engine.connect() as conn:                      
        existing_cols = conn.execute(                    
            text("PRAGMA table_info(appliances)")        
        ).fetchall()
        existing_cols = {c[1] for c in existing_cols}   

        if "warranty_expiry" not in existing_cols:         
            conn.execute(
                text("ALTER TABLE appliances ADD COLUMN warranty_expiry DATE")
            )
        if "depreciation_years" not in existing_cols:    
            conn.execute(
                text("ALTER TABLE appliances ADD COLUMN depreciation_years INTEGER") 
            )
migrate_appliances_schema()

def load_expense_data():
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

APPLIANCE_IMG_DIR = "appliance_images"
os.makedirs(APPLIANCE_IMG_DIR, exist_ok=True)

def black_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(colors.black)
    canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], stroke=0, fill=1)
    canvas.restoreState()

# =============
# EXPENSE FUNCTIONS
# =============
def create_expense(db, category_name, subcategory_name, date_value, amount):
    if amount <= 0:
        raise ValueError("Amount must be greater than 0")

    cat = db.query(Category).filter_by(name=category_name).first()
    if not cat:
        raise ValueError("Invalid category")

    sub = db.query(SubCategory).filter_by(
        name=subcategory_name,
        category_id=cat.id
    ).first()
    if not sub:
        raise ValueError("Invalid subcategory")

    expense = Expense(
        category_id=cat.id,
        subcategory_id=sub.id,
        date=date_value,
        amount=amount
    )
    db.add(expense)
    db.commit()
    return expense.id
# ------ CATEGORY FUNCTIONS ------
def create_category(db, name):
    name = name.strip()
    if not name:
        raise ValueError("Category name cannot be empty")
    if db.query(Category).filter_by(name=name).first():
        raise ValueError("Category already exists")
    db.add(Category(name=name))
    db.commit()
# ------ RENAME CATEGORY ------
def rename_category(db, category_id, new_name):
    new_name = new_name.strip()
    if not new_name:
        raise ValueError("Category name cannot be empty")
    exists = db.query(Category).filter_by(name=new_name).first()
    if exists and exists.id != category_id:
        raise ValueError("Category name already exists")
    cat = db.get(Category, category_id)
    cat.name = new_name
    db.commit()
# ------ SUBCATEGORY FUNCTIONS ------
def create_subcategory(db, category_id, name):
    name = name.strip()
    if not name:
        raise ValueError("Subcategory name cannot be empty")
    if db.query(SubCategory).filter_by(
        name=name, category_id=category_id
    ).first():
        raise ValueError("Subcategory already exists in this category")
    db.add(SubCategory(name=name, category_id=category_id))
    db.commit()

#------ RENAME SUBCATEGORY ------
def rename_subcategory(db, subcategory_id, new_name):
    new_name = new_name.strip()
    if not new_name:
        raise ValueError("Subcategory name cannot be empty")
    sub = db.get(SubCategory, subcategory_id)
    exists = db.query(SubCategory).filter_by(
        name=new_name, category_id=sub.category_id
    ).first()
    if exists and exists.id != subcategory_id:
        raise ValueError("Subcategory already exists in this category")
    sub.name = new_name
    db.commit()
# ----- MOVE SUBCATEGORY ------
def move_subcategory(db, subcategory_id, target_category_id):
    sub = db.get(SubCategory, subcategory_id)
    exists = db.query(SubCategory).filter_by(
        name=sub.name,
        category_id=target_category_id
    ).first()
    if exists:
        raise ValueError("Subcategory already exists in target category")

    sub.category_id = target_category_id

    db.query(Expense).filter(
        Expense.subcategory_id == sub.id
    ).update(
        {"category_id": target_category_id},
        synchronize_session=False
    )
    db.commit()
# ----- DELETE SUBCATEGORY / CATEGORY ------
def delete_subcategory(db, subcategory_id):
    db.query(Expense).filter_by(subcategory_id=subcategory_id).delete()
    sub = db.get(SubCategory, subcategory_id)
    db.delete(sub)
    db.commit()

#----- DELETE CATEGORY ------
def delete_category(db, category_id):
    db.query(Expense).filter_by(category_id=category_id).delete()
    db.query(SubCategory).filter_by(category_id=category_id).delete()
    cat = db.get(Category, category_id)
    db.delete(cat)
    db.commit()
#---- FETCH EXPENSES ------
def fetch_expenses(
    db,
    start_date,
    end_date,
    category_name=None,
    subcategory_name=None,
):
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
        .filter(Expense.date.between(start_date, end_date))
    )

    if category_name and category_name != "All":
        q = q.filter(Category.name == category_name)

    if subcategory_name and subcategory_name != "All":
        q = q.filter(SubCategory.name == subcategory_name)

    return pd.DataFrame(
        q.all(),
        columns=["id", "date", "category", "subcategory", "amount"]
    )
# ---- UPDATE EXPENSES BULK ------
def update_expenses_bulk(db, rows):
    """
    rows = list of dicts:
    {
        id, date, category, subcategory, amount
    }
    """
    with db.no_autoflush:
        for row in rows:
            exp = db.get(Expense, int(row["id"]))
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
#---- DELETE EXPENSES BY IDS ------
def delete_expenses_by_ids(db, expense_ids):
    for eid in expense_ids:
        exp = db.get(Expense, int(eid))
        if exp:
            db.delete(exp)
    db.commit()
#---- DELETE EXPENSES BULK ------
def delete_expenses_bulk(db, expense_ids):
    db.query(Expense).filter(
        Expense.id.in_(expense_ids)
    ).delete(synchronize_session=False)
    db.commit()
#--- MONTH SUMMARY ------
def get_month_summary(db, start_date, end_date):
    total_income = (
        db.query(func.sum(Income.amount))
        .filter(Income.date.between(start_date, end_date))
        .scalar()
    ) or 0

    total_expense = (
        db.query(func.sum(Expense.amount))
        .filter(Expense.date.between(start_date, end_date))
        .scalar()
    ) or 0

    return {
        "income": total_income,
        "expense": total_expense,
        "net": total_income - total_expense,
    }
# --- DAILY EXPENSE BREAKDOWN ------
def get_daily_expense_breakdown(db, target_date):
    rows = (
        db.query(
            SubCategory.name.label("subcategory"),
            func.sum(Expense.amount).label("amount")
        )
        .join(SubCategory, Expense.subcategory_id == SubCategory.id)
        .filter(Expense.date == target_date)
        .group_by(SubCategory.name)
        .order_by(func.sum(Expense.amount).desc())
        .all()
    )

    total = (
        db.query(func.sum(Expense.amount))
        .filter(Expense.date == target_date)
        .scalar()
    ) or 0

    return {
        "items": [{"subcategory": r.subcategory, "amount": r.amount} for r in rows],
        "total": total,
    }
# ---- TOTAL EXPENSE BETWEEN ------
def get_total_expense_between(db, start_date, end_date):
    return (
        db.query(func.sum(Expense.amount))
        .filter(Expense.date.between(start_date, end_date))
        .scalar()
    ) or 0
#--- AGGREGATE BY CATEGORY / SUBCATEGORY ------
def aggregate_by_category(df):
    return (
        df.groupby("category", as_index=False)["amount"]
        .sum()
        .sort_values("amount", ascending=False)
    )
# --- AGGREGATE BY SUBCATEGORY ------
def aggregate_by_subcategory(df, category_name):
    return (
        df[df["category"] == category_name]
        .groupby("subcategory", as_index=False)["amount"]
        .sum()
        .sort_values("amount", ascending=False)
    )
# ---- EXPORT PDF ------
def export_pdf(df, footer_text=""):
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

    # Do NOT auto-add TOTAL if already present
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
        data.append(["", "", "TOTAL", f"{total_amount:.2f}"])

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

    doc.build(
        [table],
        onFirstPage=lambda c, d: (black_page(c, d), draw_footer(c, d)),
        onLaterPages=lambda c, d: (black_page(c, d), draw_footer(c, d))
    )

    buffer.seek(0)
    return buffer

def fetch_expenses_for_export(db, start_date, end_date, category="All", subcategory="All"):
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
            Expense.date.between(start_date, end_date)
        )
    )

    if category != "All":
        q = q.filter(Category.name == category)

    if subcategory != "All":
        q = q.filter(SubCategory.name == subcategory)

    return pd.DataFrame(q.all())

def fetch_expense_summary(
    db,
    start_date,
    end_date,
    categories,
    subcategory_ids=None
):
    q = (
        db.query(
            Category.name.label("Category"),
            SubCategory.name.label("Subcategory"),
            func.sum(Expense.amount).label("Total Amount")
        )
        .join(Category, Expense.category_id == Category.id)
        .join(SubCategory, Expense.subcategory_id == SubCategory.id)
        .filter(
            Expense.date.between(start_date, end_date),
            Category.name.in_(categories)
        )
    )

    if subcategory_ids:
        q = q.filter(SubCategory.id.in_(subcategory_ids))

    return pd.DataFrame(
        q.group_by(Category.name, SubCategory.name).all()
    )

def compute_category_totals(df):
    cat_total_df = (
        df.groupby("Category", as_index=False)["Total Amount"]
        .sum()
    )

    total_value = cat_total_df["Total Amount"].sum()

    total_row = pd.DataFrame([{
        "Category": "TOTAL",
        "Total Amount": total_value
    }])

    return pd.concat([cat_total_df, total_row], ignore_index=True)


# =============
# INCOME FUNCTIONS
# =============
def create_income(db, category_name, subcategory_name, date_value, amount):
    if amount <= 0:
        raise ValueError("Amount must be greater than 0")

    cat = db.query(IncomeCategory).filter_by(name=category_name).first()
    if not cat:
        raise ValueError("Invalid income category")

    sub = db.query(IncomeSubCategory).filter_by(
        name=subcategory_name,
        category_id=cat.id
    ).first()
    if not sub:
        raise ValueError("Invalid income subcategory")

    inc = Income(
        category_id=cat.id,
        subcategory_id=sub.id,
        date=date_value,
        amount=amount
    )
    db.add(inc)
    db.commit()
    return inc.id

def fetch_income(db):
    return pd.DataFrame(
        db.query(
            Income.id,
            Income.date,
            Income.amount,
            IncomeCategory.name.label("category"),
            IncomeSubCategory.name.label("subcategory")
        )
        .join(IncomeCategory, Income.category_id == IncomeCategory.id)
        .join(IncomeSubCategory, Income.subcategory_id == IncomeSubCategory.id)
        .all(),
        columns=["id", "date", "amount", "category", "subcategory"]
    )

def filter_income_by_period(df, start_date, end_date):
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    return df[df["date"].between(start_date, end_date)]

def get_income_expense_summary(db, start_date, end_date):
    total_income = (
        db.query(func.sum(Income.amount))
        .filter(Income.date.between(start_date, end_date))
        .scalar()
    ) or 0

    total_expense = (
        db.query(func.sum(Expense.amount))
        .filter(Expense.date.between(start_date, end_date))
        .scalar()
    ) or 0

    return {
        "income": total_income,
        "expense": total_expense,
        "net": total_income - total_expense,
    }

def filter_income_entries(df, category=None, subcategory=None):
    filtered = df.copy()

    if category and category != "All":
        filtered = filtered[filtered["category"] == category]

    if subcategory and subcategory != "All":
        filtered = filtered[filtered["subcategory"] == subcategory]

    return filtered

def update_income_bulk(db, rows):
    """
    rows: list of dicts with keys
    id, date, amount, category, subcategory
    """
    with db.no_autoflush:
        for row in rows:
            inc = db.get(Income, int(row["id"]))
            if not inc:
                continue

            inc.date = pd.to_datetime(row["date"]).date()
            inc.amount = float(row["amount"])

            cat = db.query(IncomeCategory).filter_by(
                name=row["category"]
            ).first()
            if not cat:
                continue

            sub = db.query(IncomeSubCategory).filter_by(
                name=row["subcategory"],
                category_id=cat.id
            ).first()
            if not sub:
                continue

            inc.category_id = cat.id
            inc.subcategory_id = sub.id

    db.commit()

def delete_income_by_ids(db, income_ids):
    for iid in income_ids:
        inc = db.get(Income, int(iid))
        if inc:
            db.delete(inc)
    db.commit()

def create_income_category(db, name):
    name = name.strip()
    if not name:
        raise ValueError("Category name cannot be empty")
    if db.query(IncomeCategory).filter_by(name=name).first():
        raise ValueError("Income category already exists")
    db.add(IncomeCategory(name=name))
    db.commit()

def create_income_subcategory(db, category_id, name):
    name = name.strip()
    if not name:
        raise ValueError("Subcategory name cannot be empty")
    if db.query(IncomeSubCategory).filter_by(
        name=name,
        category_id=category_id
    ).first():
        raise ValueError("Income subcategory already exists in this category")

    db.add(
        IncomeSubCategory(
            name=name,
            category_id=category_id
        )
    )
    db.commit()

def rename_income_category(db, category_id, new_name):
    new_name = new_name.strip()
    if not new_name:
        raise ValueError("Category name cannot be empty")

    exists = db.query(IncomeCategory).filter_by(name=new_name).first()
    if exists and exists.id != category_id:
        raise ValueError("Income category already exists")

    cat = db.get(IncomeCategory, category_id)
    cat.name = new_name
    db.commit()

def rename_income_subcategory(db, subcategory_id, new_name):
    new_name = new_name.strip()
    if not new_name:
        raise ValueError("Subcategory name cannot be empty")

    sub = db.get(IncomeSubCategory, subcategory_id)
    exists = db.query(IncomeSubCategory).filter_by(
        name=new_name,
        category_id=sub.category_id
    ).first()

    if exists and exists.id != subcategory_id:
        raise ValueError("Income subcategory already exists")

    sub.name = new_name
    db.commit()

def delete_income_subcategory(db, subcategory_id):
    db.query(Income).filter(
        Income.subcategory_id == subcategory_id
    ).delete()

    sub = db.get(IncomeSubCategory, subcategory_id)
    db.delete(sub)
    db.commit()

def delete_income_category(db, category_id):
    db.query(Income).filter(
        Income.category_id == category_id
    ).delete()

    db.query(IncomeSubCategory).filter(
        IncomeSubCategory.category_id == category_id
    ).delete()

    cat = db.get(IncomeCategory, category_id)
    db.delete(cat)
    db.commit()

def fetch_income_for_export(db):
    df = pd.DataFrame(
        db.query(
            Income.id,
            Income.date,
            Income.amount,
            IncomeCategory.name.label("category"),
            IncomeSubCategory.name.label("subcategory")
        )
        .join(IncomeCategory, Income.category_id == IncomeCategory.id)
        .join(IncomeSubCategory, Income.subcategory_id == IncomeSubCategory.id)
        .all(),
        columns=["NOs", "date", "amount", "category", "subcategory"]
    )

    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])

    return df

def filter_income_export(
    df,
    start_date,
    end_date,
    category="All",
    subcategory="All"
):
    fdf = df[df["date"].between(start_date, end_date)]

    if category != "All":
        fdf = fdf[fdf["category"] == category]

    if subcategory != "All":
        fdf = fdf[fdf["subcategory"] == subcategory]

    return fdf

def generate_income_pdf(df):
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

    story.append(Paragraph("Income Report", styles["WhiteTitle"]))
    story.append(Paragraph(
        f"Generated on: {datetime.date.today()}",
        styles["WhiteNormal"]
    ))
    story.append(Spacer(1, 12))

    df = df.copy()
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    df["amount"] = df["amount"].round(2)

    total_income = df["amount"].sum()

    table_data = [list(df.columns)] + df.values.tolist()
    table_data.append(["", "", "TOTAL", "", f"{total_income:,.2f}"])

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

    buffer.seek(0)
    return buffer.getvalue()

# =============
# ASSET FUNCTIONS
# =============
def compute_asset_valuation(db):
    # Metals
    gold_grams = db.query(func.sum(MetalAsset.weight_grams))\
        .filter(MetalAsset.metal_type == "Gold").scalar() or 0
    silver_grams = db.query(func.sum(MetalAsset.weight_grams))\
        .filter(MetalAsset.metal_type == "Silver").scalar() or 0

    gold_price = get_price(db, "gold_price", 0.0)
    silver_price = get_price(db, "silver_price", 0.0)

    gold_value = gold_grams * gold_price
    silver_value = silver_grams * silver_price
    metal_total = gold_value + silver_value

    # Land
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

    # Fixed Deposits
    today = date.today()
    fd_total = 0.0
    fds = db.query(FixedDeposit).all()
    for fd in fds:
        if fd.status == "active":
            if today >= fd.maturity_date:
                fd.status = "matured"
            else:
                fd_total += fd_current_value(fd.principal, fd.rate, fd.deposit_date)
    db.commit()

    return {
        "gold": gold_value,
        "silver": silver_value,
        "metals_total": metal_total,
        "land_values": land_values,
        "land_total": land_total,
        "fd_total": fd_total,
        "grand_total": metal_total + land_total + fd_total,
    }

def create_metal_asset(db, metal_type, weight_grams, entry_date):
    if weight_grams <= 0:
        raise ValueError("Weight must be positive")
    db.add(MetalAsset(
        metal_type=metal_type,
        weight_grams=weight_grams,
        entry_date=entry_date
    ))
    db.commit()


def update_metal_assets(db, rows):
    for r in rows:
        a = db.get(MetalAsset, int(r["id"]))
        if a:
            a.metal_type = r["Metal"]
            a.weight_grams = float(r["Weight (g)"])
            a.entry_date = pd.to_datetime(r["Date"]).date()
    db.commit()


def delete_metal_assets(db, ids):
    for i in ids:
        a = db.get(MetalAsset, int(i))
        if a:
            db.delete(a)
    db.commit()

def create_land_asset(db, location, sqft):
    if not location or sqft <= 0:
        raise ValueError("Invalid land input")
    db.add(LandAsset(
        location=location,
        area_unit="sqft",
        area_size=sqft
    ))
    db.commit()


def update_land_assets(db, rows):
    for r in rows:
        l = db.get(LandAsset, int(r["id"]))
        if l:
            l.location = r["Place"]
            l.area_size = float(r["Sqft"])
    db.commit()


def delete_land_assets(db, ids):
    for i in ids:
        l = db.get(LandAsset, int(i))
        if l:
            db.delete(l)
    db.commit()

def create_fixed_deposit(
    db, name, principal, rate, tenure_months, deposit_date
):
    if not name or principal <= 0 or rate <= 0 or tenure_months < 1:
        raise ValueError("Invalid FD details")

    maturity_date = deposit_date + relativedelta(months=tenure_months)

    db.add(FixedDeposit(
        name=name,
        principal=principal,
        rate=rate,
        tenure_months=tenure_months,
        deposit_date=deposit_date,
        maturity_date=maturity_date,
        status="active"
    ))
    db.commit()


def update_active_fds(db, rows):
    for row in rows:
        fd = db.get(FixedDeposit, int(row["id"]))
        if fd:
            fd.name = row["Name"]
            fd.principal = float(row["Principal"])
            fd.rate = float(row["Rate (%)"])
            fd.deposit_date = pd.to_datetime(row["Deposit Date"]).date()
            fd.tenure_months = int(row["Tenure (Months)"])
            fd.maturity_date = fd.deposit_date + relativedelta(
                months=fd.tenure_months
            )
    db.commit()

def delete_fixed_deposits(db, ids):
    for i in ids:
        fd = db.get(FixedDeposit, int(i))
        if fd:
            db.delete(fd)
    db.commit()

def renew_fixed_deposit(db, fd_id):
    old = db.get(FixedDeposit, int(fd_id))
    if not old:
        return

    new_dep = date.today()
    new_mat = new_dep + relativedelta(months=old.tenure_months)

    db.add(FixedDeposit(
        name=f"{old.name} (Renewed)",
        principal=old.principal,
        rate=old.rate,
        tenure_months=old.tenure_months,
        deposit_date=new_dep,
        maturity_date=new_mat,
        status="active"
    ))
    db.commit()

def fetch_assets_for_pdf(db):
    # ---------- METALS ----------
    gold_price = get_price(db, "gold_price", 0.0)
    silver_price = get_price(db, "silver_price", 0.0)

    metals_df = pd.read_sql(
        "SELECT metal_type, weight_grams FROM metal_assets",
        engine
    )

    gold_df = metals_df[metals_df["metal_type"] == "Gold"].copy()
    silver_df = metals_df[metals_df["metal_type"] == "Silver"].copy()

    gold_df["Value (₹)"] = (gold_df["weight_grams"] * gold_price).round(2)
    silver_df["Value (₹)"] = (silver_df["weight_grams"] * silver_price).round(2)

    gold_total = gold_df["Value (₹)"].sum()
    silver_total = silver_df["Value (₹)"].sum()

    # ---------- LAND ----------
    land_df = pd.read_sql(
        "SELECT location, area_size FROM land_assets",
        engine
    )

    if not land_df.empty:
        land_df["Price ₹/sqft"] = land_df["location"].apply(
            lambda loc: get_price(db, f"land:{loc}", 0.0)
        )
        land_df["Value (₹)"] = land_df["area_size"] * land_df["Price ₹/sqft"]
        land_total = land_df["Value (₹)"].sum()
    else:
        land_total = 0.0

    # ---------- FIXED DEPOSITS ----------
    fd_df = pd.read_sql(
        "SELECT name, principal, rate, tenure_months, deposit_date FROM fixed_deposits",
        engine
    )

    today = date.today()
    if not fd_df.empty:
        fd_df["Current Value (₹)"] = fd_df.apply(
            lambda r: round(
                r["principal"]
                * ((1 + r["rate"] / 100) **
                   ((today - pd.to_datetime(r["deposit_date"]).date()).days / 365)),
                2
            ),
            axis=1
        )
        fd_total = fd_df["Current Value (₹)"].sum()
    else:
        fd_total = 0.0

    grand_total = gold_total + silver_total + land_total + fd_total

    return {
        "gold_df": gold_df,
        "silver_df": silver_df,
        "gold_price": gold_price,
        "silver_price": silver_price,
        "gold_total": gold_total,
        "silver_total": silver_total,
        "land_df": land_df,
        "land_total": land_total,
        "fd_df": fd_df,
        "fd_total": fd_total,
        "grand_total": grand_total,
    }

def generate_assets_pdf(data, sections):
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
        f"Generated on: {date.today()}",
        styles["BlackNormal"]
    ))
    story.append(Spacer(1, 14))

    GRAND_TOTAL = 0.0

    # ================= METALS =================
    if "Metals" in sections:
        story.append(Paragraph("<b>Metal Assets</b>", styles["BlackHeading"]))
        story.append(Paragraph(
            f"Gold ₹/g: {data['gold_price']} | Silver ₹/g: {data['silver_price']}",
            styles["BlackNormal"]
        ))
        story.append(Spacer(1, 8))

        def metal_table(df, title, total):
            tbl = [[title, "Value (₹)"]] + df[["weight_grams", "Value (₹)"]].values.tolist()
            tbl.append(["TOTAL", f"{total:,.2f}"])
            t = Table(tbl, colWidths=[100, 100])
            t.setStyle(TableStyle([
                ("FONT", (0,0), (-1,-1), "DejaVu"),
                ("BACKGROUND", (0,0), (-1,-1), colors.black),
                ("TEXTCOLOR", (0,0), (-1,-1), colors.white),
                ("GRID", (0,0), (-1,-1), 0.5, colors.white),
                ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ]))
            return t

        gold_tbl = metal_table(
            data["gold_df"], "Gold (grams)", data["gold_total"]
        )
        silver_tbl = metal_table(
            data["silver_df"], "Silver (grams)", data["silver_total"]
        )

        wrapper = Table([[gold_tbl, silver_tbl]], colWidths=[250, 250])
        story.append(wrapper)
        story.append(Spacer(1, 14))

        GRAND_TOTAL += data["gold_total"] + data["silver_total"]

    # ================= LAND =================
    if "Land" in sections and not data["land_df"].empty:
        story.append(Paragraph("<b>Land Assets</b>", styles["BlackHeading"]))
        tbl = [list(data["land_df"].columns)] + data["land_df"].values.tolist()
        tbl.append(["", "TOTAL", "", f"{data['land_total']:,.2f}"])
        t = Table(tbl)
        t.setStyle(TableStyle([
            ("FONT", (0,0), (-1,-1), "DejaVu"),
            ("BACKGROUND", (0,0), (-1,-1), colors.black),
            ("TEXTCOLOR", (0,0), (-1,-1), colors.white),
            ("GRID", (0,0), (-1,-1), 0.5, colors.white),
        ]))
        story.append(t)
        story.append(Spacer(1, 14))

        GRAND_TOTAL += data["land_total"]

    # ================= FIXED DEPOSITS =================
    if "Fixed Deposits" in sections and not data["fd_df"].empty:
        story.append(Paragraph("<b>Fixed Deposits</b>", styles["BlackHeading"]))
        tbl = [list(data["fd_df"].columns)] + data["fd_df"].values.tolist()
        tbl.append(["TOTAL", "", "", "", f"{data['fd_total']:,.2f}"])
        t = Table(tbl)
        t.setStyle(TableStyle([
            ("FONT", (0,0), (-1,-1), "DejaVu"),
            ("BACKGROUND", (0,0), (-1,-1), colors.black),
            ("TEXTCOLOR", (0,0), (-1,-1), colors.white),
            ("GRID", (0,0), (-1,-1), 0.5, colors.white),
        ]))
        story.append(t)

        GRAND_TOTAL += data["fd_total"]

    # ================= GRAND TOTAL =================
    story.append(Spacer(1, 24))
    story.append(Paragraph(
        "<b>GRAND TOTAL ASSETS VALUE</b>",
        styles["BlackHeading"]
    ))
    story.append(Paragraph(
        f"₹ {GRAND_TOTAL:,.2f}",
        ParagraphStyle(
            name="GrandTotalValue",
            fontName="DejaVu",
            fontSize=18,
            textColor=colors.white
        )
    ))

    def black_bg(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.black)
        canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1)
        canvas.restoreState()

    doc.build(story, onFirstPage=black_bg, onLaterPages=black_bg)
    buffer.seek(0)
    return buffer.getvalue()


# =============
# APPLIANCES FUNCTIONS
# =============
def create_appliance(db, name, price, purchase_date, warranty_expiry, images):
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

def fetch_appliances(db):
    return (
        db.query(Appliance)
        .options(joinedload(Appliance.images))
        .order_by(Appliance.purchase_date.desc())
        .all()
    )

def update_appliance(
    db,
    appliance_id,
    name,
    price,
    purchase_date,
    warranty_expiry,
    new_images
):
    appliance = db.get(Appliance, appliance_id)
    if not appliance:
        return

    appliance.name = name
    appliance.price = price
    appliance.purchase_date = purchase_date
    appliance.warranty_expiry = warranty_expiry

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

def delete_appliance(db, appliance_id):
    appliance = db.get(Appliance, appliance_id)
    if not appliance:
        return

    for img in appliance.images:
        if os.path.exists(img.image_path):
            os.remove(img.image_path)

    db.delete(appliance)
    db.commit()

def appliance_value_distribution(appliances):
    return pd.DataFrame([{
        "Appliance": a.name,
        "Price": float(a.price)
    } for a in appliances])


def appliance_year_distribution(appliances):
    df = pd.DataFrame([{
        "Year": a.purchase_date.year
    } for a in appliances])

    return df.value_counts().reset_index(
        name="Count"
    ).rename(columns={"Year": "Year"})

def fetch_appliances_for_pdf(db):
    return (
        db.query(Appliance)
        .options(joinedload(Appliance.images))
        .order_by(Appliance.purchase_date.desc())
        .all()
    )

def generate_appliances_pdf(appliances):
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

    story.append(Paragraph("Appliances Report", styles["WhiteTitle"]))
    story.append(Paragraph(
        f"Generated on: {date.today()}",
        styles["WhiteNormal"]
    ))
    story.append(Spacer(1, 12))

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
                ap.warranty_expiry.strftime("%Y-%m-%d")
                if ap.warranty_expiry else "—"
            ])

        table = Table(
            table_data,
            colWidths=[160, 90, 100, 100],
            hAlign="LEFT"
        )

        table.setStyle(TableStyle([
            ("FONT", (0,0), (-1,-1), "DejaVu"),
            ("BACKGROUND", (0,0), (-1,0), colors.black),
            ("BACKGROUND", (0,1), (-1,-1), colors.black),
            ("TEXTCOLOR", (0,0), (-1,-1), colors.white),
            ("GRID", (0,0), (-1,-1), 0.5, colors.white),
            ("ALIGN", (1,1), (-1,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING", (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ]))

        story.append(table)

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

    buffer.seek(0)
    return buffer.getvalue()
