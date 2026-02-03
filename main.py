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
import os
import platform
import time
import subprocess



pdfmetrics.registerFont(TTFont("DejaVu", "DejaVuSans.ttf"))

# ==============
# SESSION STATE
# ==============
if "open_asset_inputs" not in st.session_state: 
    st.session_state.open_asset_inputs = False

# =======================
# WEEKLY TREND VISIBILITY
# =======================
if "show_weekly_trend" not in st.session_state:
    st.session_state.show_weekly_trend = True

if "show_inv_delete_manager" not in st.session_state:
    st.session_state.show_inv_delete_manager = False

# ==============
# FLASH MESSAGE
# ==============
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
    initial_sidebar_state="expanded"
)

# ==============
# DATABASE MODELS
# ==============
DATABASE_URL = st.secrets.get(
    "DATABASE_URL",
    "sqlite:///expense.db"
)

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
# CREATE TABLES
# ==============
if "data_refresh" not in st.session_state:
    st.session_state.data_refresh = 0
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

st.markdown(
    """
    <style>
    /* ===============================
       BASIC DARK THEME (SAFE)
    =============================== */

    .stApp {
        background-color: #000000;
        color: #ffffff;
    }

    header[data-testid="stHeader"] {
        background: transparent;
    }

    div[data-testid="stToolbar"] {
        background: #000000;
    }

    /* ===============================
       SIDEBAR
    =============================== */
    section[data-testid="stSidebar"] {
        background-color: #000000;
        border-right: 1px solid #111111;
    }

    /* ===============================
       INPUTS
    =============================== */
    input, textarea, select {
        background-color: #000000;
        color: #ffffff;
        border: 1px solid #222222;
    }

    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div,
    div[data-baseweb="datepicker"] > div {
        background-color: #000000;
        border: 1px solid #222222;
    }

    /* ===============================
       BUTTONS
    =============================== */
    button {
        background-color: #000000;
        color: #ffffff;
        border: 1px solid #333333;
        transition: transform 0.08s ease;
    }

    button:hover {
        background-color: #111111;
    }

    button:active {
        transform: scale(0.97);
    }

    /* ===============================
       METRICS (POP-IN ANIMATION)
    =============================== */
    div[data-testid="metric-container"] {
        background-color: #000000;
        border: 1px solid #222222;
        border-radius: 12px;
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
    details[open] {
        border-left: 3px solid #4da3ff;
        padding-left: 8px;
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
def section(title, desc):
    st.subheader(title)
    st.caption(desc)

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

        st.plotly_chart(fig, use_container_width=True)
    

def advanced_analytics(period_df):

    if period_df.empty:
        st.info("No data available for selected period")
        return

    df = period_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    # now call charts
    cumulative_spend_chart(df)

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

def black_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(colors.black)
    canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], stroke=0, fill=1)
    canvas.restoreState()

def is_edit_mode(aid):
    return st.session_state.get(f"edit_mode_{aid}", False)


# ==============
# ADD EXPENSE
# ==============
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
        if st.button("Add Expense"):
            if amt > 0:
                db.add(Expense(
                    category_id=cat.id,
                    subcategory_id=sub.id,
                    date=d,
                    amount=amt
                ))
                db.commit()
                st.session_state.data_refresh += 1
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
            .order_by(Income.date.desc(), Income.id.desc())
            .all(),
            columns=["id", "date", "amount", "category", "subcategory"]
        )
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
                st.plotly_chart(fig_cat, use_container_width=True)

        with col2:
            st.markdown("**By Subcategory**")
            sub_pie = period_df.groupby("subcategory", as_index=False)["amount"].sum()
            if not sub_pie.empty:
                fig_sub = px.pie(sub_pie, names="subcategory", values="amount", hole=0.4)
                fig_sub.update_layout(paper_bgcolor="#000", font=dict(color="#fff"))
                fig_sub.update_traces(marker=dict(line=dict(color="black", width=2)))
                st.plotly_chart(fig_sub, use_container_width=True)

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
                edited_df = st.data_editor(
                    filtered_df,
                    use_container_width=True,
                    disabled=["id"],
                    column_config={
                        "date": st.column_config.DateColumn("Date"),
                        "amount": st.column_config.NumberColumn("Amount", min_value=0),
                        "category": st.column_config.SelectboxColumn("Category", options=all_cats),
                        "subcategory": st.column_config.SelectboxColumn("Subcategory", options=all_subs),
                    }
                )
                if st.button("💾 Save Income Changes"):
                    with db.no_autoflush:
                        for _, row in edited_df.iterrows():
                            inc = db.get(Income, int(row["id"]))
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
        st.divider()
        with st.expander("⚙️ Advanced (Income Category Management)"):
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

            # ====================================
            # RENAME INCOME CATEGORY / SUBCATEGORY
            # ====================================
            st.divider()
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
            # =========================
            # RENAME INCOME SUBCATEGORY
            # ========================
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
            # ====================================
            # DELETE INCOME CATEGORY / SUBCATEGORY
            # ====================================
            st.divider()
            st.subheader("🗑 Delete Income Subcategory")
            st.warning("Deletes ALL income under this subcategory")
            if income_subs:
                del_sub_name = st.selectbox(
                    "Select Subcategory to Delete",
                    [s.name for s in income_subs],
                    key="adv_delete_income_sub_select"
                )
                del_sub = db.query(IncomeSubCategory).filter_by(
                    name=del_sub_name,
                    category_id=sel_cat.id
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
            # ======================
            # DELETE INCOME CATEGORY
            # ======================
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
        st.divider()

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
def manage_categories():
    st.title("📂 Manage Categories")
    with SessionLocal() as db:
        # =================
        # ADD NEW CATEGORY
        # =================
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
        # =================
        # MANAGE EXISTING
        # =================
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
        st.divider()
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
        st.divider()
        # =================     
        # ADD SUBCATEGORY
        # =================
        st.subheader("📄 Subcategories")
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
            return
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
        # =================
        # MOVE SUBCATEGORY
        # =================
        st.subheader("🔀 Move Subcategory")
        sub_to_move = st.selectbox(
            "Subcategory to Move",
            [s.name for s in subs],
            key="move_sub"
        )
        target_cat_name = st.selectbox(
            "Move To Category",
            [c.name for c in cats if c.id != cat.id],
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
        st.divider()
        # ===========================
        # DELETE CATEGORY/SUBCATEGORY
        # ===========================
        with st.expander("⚠️ Danger Zone (Delete)"):
            st.warning("These actions are irreversible")
            st.subheader("🗑 Delete Subcategory")
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
            # ==================
            # DELETE CATEGORY
            # ==================
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
            edited_df = st.data_editor(
                df,
                use_container_width=True,
                disabled=["id"],
                column_config={
                    "date": st.column_config.DateColumn("Date"),
                    "category": st.column_config.SelectboxColumn("Category", options=all_cats),
                    "subcategory": st.column_config.SelectboxColumn("Subcategory", options=all_subs),
                    "amount": st.column_config.NumberColumn("Amount", min_value=0)
                }
            )
            if st.button("💾 Save Changes"):
                with db.no_autoflush:
                    for _, row in edited_df.iterrows():
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
                        
# =================
# EXPENSE DASHBOARD
# =================
def dashboard():
    st.title("📊 Dashboard")

    # ============================
    # STATE SAFETY
    # ============================
    if "data_refresh" not in st.session_state:
        st.session_state.data_refresh = 0

    if "show_weekly_trend" not in st.session_state:
        st.session_state.show_weekly_trend = True

    # ============================
    # LOAD DATA (CACHED – FOR CHARTS)
    # ============================
    df = load_expense_data(st.session_state.data_refresh)

    if df.empty:
        st.info("No data available")
        return

    df["date"] = pd.to_datetime(df["date"])

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
            label_visibility="collapsed"
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
    # PERIOD FILTER (CHARTS)
    # ============================
    st.divider()
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

            st.plotly_chart(fig_cat, use_container_width=True)

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

                    st.plotly_chart(fig_sub, use_container_width=True)

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
                    st.plotly_chart(fig_bar, use_container_width=True)
                
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
                        "Calendar Heatmap (Weekday × Week of Month)",
                        "Waterfall (Month-over-Month Change)",
                        "Distribution (Box Plot by Category)"
                    ],
                    key="advv_variant"
                )

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
                        st.plotly_chart(fig, use_container_width=True)

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
                        st.plotly_chart(fig, use_container_width=True)

                elif variant == "Calendar Heatmap (Weekday × Week of Month)":
                    if metric_mode == "Transaction Count":
                        daily = adv_df.groupby("date").size().reset_index(name="value")
                    elif metric_mode == "Average Spend":
                        daily = adv_df.groupby("date")["amount"].mean().reset_index(name="value")
                    else:
                        daily = adv_df.groupby("date")["amount"].sum().reset_index(name="value")

                    if daily.empty:
                        st.info("No daily data for heatmap.")
                    else:
                        daily["weekday"] = daily["date"].dt.day_name().str[:3]
                        daily["week_of_month"] = ((daily["date"].dt.day - 1) // 7) + 1
                        weekday_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                        pivot = daily.pivot_table(
                            index="weekday",
                            columns="week_of_month",
                            values="value",
                            aggfunc="sum"
                        ).reindex(weekday_order)

                        fig = px.imshow(
                            pivot,
                            color_continuous_scale="Inferno",
                            labels=dict(color="Value", x="Week of Month", y="Weekday")
                        )
                        fig.update_layout(
                            paper_bgcolor="#000",
                            plot_bgcolor="#000",
                            font=dict(color="#fff"),
                            margin=dict(l=30, r=30, t=40, b=30)
                        )
                        st.plotly_chart(fig, use_container_width=True)

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
                        st.plotly_chart(fig, use_container_width=True)

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
                        st.plotly_chart(fig, use_container_width=True)

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
def insights():
    st.title("📈 Insights")
    # ============================
    # AVERAGE SPEND & HIGHEST MONTH
    # ============================
    df = load_expense_data(st.session_state.data_refresh)
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
        st.plotly_chart(fig, use_container_width=True)

    # ============================
# EXPENSE PDF EXPORT SECTION
# ===========================
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
                st.dataframe(df, use_container_width=True)
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
                use_container_width=True
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
                st.dataframe(df_sum, use_container_width=True)

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
                st.dataframe(cat_total_df, use_container_width=True)

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
            st.plotly_chart(fig1, use_container_width=True)

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
            st.plotly_chart(fig2, use_container_width=True)

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
                edited = st.data_editor(df, disabled=["id"])
                if st.button("💾 Save Metal Changes"):
                    for _, r in edited.iterrows():
                        a = db.get(MetalAsset, int(r["id"]))
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
                edited = st.data_editor(land_tbl, disabled=["id"])
                if st.button("💾 Save Land Changes"):
                    for _, r in edited.iterrows():
                        l = db.get(LandAsset, int(r["id"]))
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
            tenure_type = st.radio(
                "Tenure Type",
                ["Years", "Months", "Days"],
                horizontal=True
            )

            tenure_value = st.number_input(
                f"Tenure ({tenure_type})",
                min_value=1,
                step=1
            )

            # Convert everything to days
            if tenure_type == "Years":
                tenure_days = tenure_value * 365
            elif tenure_type == "Months":
                tenure_days = tenure_value * 30
            else:
                tenure_days = tenure_value

            deposit_date = st.date_input("Deposit Date")

            maturity_date = deposit_date + timedelta(days=tenure_days)
            tenure_months = max(1, round(tenure_days / 30))
            maturity_amt = fd_maturity_value(principal, rate, tenure_months)

            c1, c2 = st.columns(2)
            c1.metric("Maturity Amount (₹)", f"{maturity_amt:,.2f}")
            c2.metric("Maturity Date", maturity_date.strftime("%d-%m-%Y"))

            if st.button("💾 Save FD"):
                if fd_name and principal > 0 and rate > 0:
                    db.add(FixedDeposit(
                        name=fd_name,
                        principal=principal,
                        rate=rate,
                        tenure_months=tenure_months,
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
                    "Tenure (Months)": fd.tenure_months,
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

                edited_df = st.data_editor(
                    active_df,
                    disabled=["id", "Current Value (₹)", "Maturity Date"],
                    use_container_width=True,
                    column_config={
                        "Name": st.column_config.TextColumn("FD Name"),
                        "Principal": st.column_config.NumberColumn("Principal (₹)", min_value=0),
                        "Rate (%)": st.column_config.NumberColumn("Rate (%)", min_value=0),
                        "Deposit Date": st.column_config.DateColumn("Deposit Date"),
                        "Tenure (Months)": st.column_config.NumberColumn(
                            "Tenure (Months)", min_value=1
                        )
                    }
                )


                if st.button("💾 Save Active FD Changes"):
                    for _, row in edited_df.iterrows():
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
                    "Tenure (Months)": fd.tenure_months,
                    "Deposit Date": fd.deposit_date,
                    "Maturity Date": fd.maturity_date,
                    "Maturity Amount (₹)": fd_maturity_value(
                        fd.principal, fd.rate, fd.tenure_months
                    )
                } for fd in matured_fds])
                matured_df["Maturity Date"] = pd.to_datetime(matured_df["Maturity Date"])
                matured_df = matured_df.sort_values(
                    ["Maturity Date", "id"],
                    ascending=[False, False]
                ).reset_index(drop=True)

                st.dataframe(matured_df, use_container_width=True)

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
                            new_mat = new_dep + relativedelta(
                                months=old.tenure_months
                            )

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
                edited = st.data_editor(
                    lic_df,
                    disabled=["id"],
                    use_container_width=True
                )

                if st.button("💾 Save LIC Changes"):
                    for _, r in edited.iterrows():
                        p = db.get(LICPolicy, int(r["id"]))
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
                            SELECT name, principal, rate, tenure_months, deposit_date
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
                            "",        # months
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

            st.plotly_chart(fig, use_container_width=True)

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
    "📤 Export Expenses",
    "🔌 Appliances Data",
    "💰 Income",
    "🏦 Assets",
    "📈 Insights",
    ],
    index =0
)       
# ======================
# PAGE ROUTING
# ======================

PAGE_ORDER = {
    "📊 Expense Dashboard": 0,
    "➕ Add Expense": 1,
    "📤 Export Expenses": 2,
    "🔌 Appliances Data": 3,
    "💰 Income": 4,
    "🏦 Assets": 5,
    "📈 Insights": 6
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
elif page == "💰 Income":
    income_section()
elif page == "🏦 Assets":
    assets_page()
elif page == "📈 Insights":
    insights()
elif page == "🔌 Appliances Data":
    appliances_page()
elif page == "📤 Export Expenses":
    export_data()
