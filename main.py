import streamlit as st
import pandas as pd
from datetime import date, timedelta
from sqlalchemy import (
    create_engine, Column, Integer, String,
    Float, Date, ForeignKey, UniqueConstraint, func
)
from sqlalchemy.orm import declarative_base, sessionmaker
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
import plotly.express as px
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
import io
import subprocess
import json
import re
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle


if "show_weekly_trend" not in st.session_state:
    st.session_state.show_weekly_trend = True

# ==============
# DB SETUP
# ==============
st.set_page_config(
    page_title="Tracker",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.markdown(
    """
    <link href="https://fonts.googleapis.com/css2?family=Ubuntu:wght@300;400;500;700&display=swap" rel="stylesheet">
    """,
    unsafe_allow_html=True
)

# ==============
# DATABASE MODELS
# ==============
engine = create_engine(
    "sqlite:///expense.db",
    connect_args={
        "check_same_thread": False,
        "timeout": 30
    },
    pool_pre_ping=True
)
# ==============
# SESSION LOCAL
# ==============
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
# ==============
# INCOME SUBCATEGORY
# ==============
class IncomeSubCategory(Base):
    __tablename__ = "income_subcategories"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("income_categories.id"))
    __table_args__ = (UniqueConstraint("name", "category_id"),)
# ==============
# INCOME
# ==============
class Income(Base):
    __tablename__ = "income"
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("income_categories.id"), index=True)
    subcategory_id = Column(Integer, ForeignKey("income_subcategories.id"), index=True)
    date = Column(Date, nullable=False, index=True)
    amount = Column(Float, nullable=False)
# ==============
# DAILY HEALTH
# ==============
class DailyHealth(Base):
    __tablename__ = "daily_health"

    date = Column(Date, primary_key=True)
    water = Column(Integer, default=0)        # Litres
    sleep = Column(Float, default=0.0)         # hours
    weight = Column(Float, default=0.0)        # kg
# ==============
# WORKOUT       
# ==============
class Workout(Base):
    __tablename__ = "workouts"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    exercise = Column(String, nullable=False)
    sets = Column(Integer, nullable=True)
    reps = Column(Integer, nullable=True)
    duration_min = Column(Float, nullable=True)


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
    
# ==============
# CUSTOM CSS
# ==============
st.markdown(
    """
    <style>
    /* ===============================
       GLOBAL RESET
    =============================== */
    * {
        box-shadow: none !important;
    }

    /* ===============================
       APP + HEADER
    =============================== */
    .stApp {
        background-color: #000000 !important;
        color: #ffffff !important;
    }

    header[data-testid="stHeader"] {
        background: transparent;
    }

    div[data-testid="stToolbar"] {
        background: #000000 !important;
    }

    /* ===============================
       SIDEBAR
    =============================== */
    section[data-testid="stSidebar"] {
        background-color: #000000 !important;
        border-right: 1px solid #111111;
    }

    /* ===============================
       ALL TEXT
    =============================== */
    html, body, [class*="css"] {
        color: #ffffff !important;
    }

    /* ===============================
       INPUTS / SELECT / DATE
    =============================== */
    input, textarea, select {
        background-color: #000000 !important;
        color: #ffffff !important;
        border: 1px solid #222222 !important;
    }

    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div,
    div[data-baseweb="datepicker"] > div {
        background-color: #000000 !important;
        border: 1px solid #222222 !important;
    }

    /* ===============================
       BUTTONS
    =============================== */
    button {
        background-color: #000000 !important;
        color: #ffffff !important;
        border: 1px solid #333333 !important;
    }

    button:hover {
        background-color: #111111 !important;
    }

    /* ===============================
       METRICS / CARDS
    =============================== */
    div[data-testid="metric-container"] {
        background-color: #000000 !important;
        border: 1px solid #222222 !important;
        border-radius: 12px;
    }

    /* ===============================
       DATAFRAMES / AGGRID
    =============================== */
    .ag-theme-streamlit,
    .ag-root-wrapper {
        background-color: #000000 !important;
        color: #ffffff !important;
    }

    /* ===============================
       PLOTLY
    =============================== */
    .js-plotly-plot,
    .plotly {
        background: #000000 !important;
    }

    /* ===============================
       🔥 SIDEBAR DATE INPUT – HARD FIX
    =============================== */
    /* ===============================
    FIX SIDEBAR NAV DISAPPEARING
    =============================== */

    /* Hide ONLY date_input label */
    section[data-testid="stSidebar"] .stDateInput label {
        display: none !important;
    }

    /* Tighten date input spacing */
    section[data-testid="stSidebar"] div[data-testid="stDateInput"] {
        margin-top: -10px !important;
    }

    /* Remove BaseWeb wrapper spacing */
    section[data-testid="stSidebar"] div[data-testid="stDateInput"] {
        padding-top: 0 !important;
        margin-top: -14px !important;
    }

    /* Tighten inner input container */
    section[data-testid="stSidebar"] div[data-baseweb="datepicker"] {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }

    /* Ensure full width */
    section[data-testid="stSidebar"] .stDateInput > div {
        width: 100% !important;
        margin-top: 0 !important;
    }

       /* ===============================
    GLOBAL RESET
    =============================== */
    * {
        box-shadow: none !important;
        font-family: 'Ubuntu', sans-serif !important;
    }

    html, body {
        font-family: 'Ubuntu', sans-serif !important;
    }

    h1, h2, h3, h4, h5, h6 {
        font-family: 'Ubuntu', sans-serif !important;
        font-weight: 700 !important;
    }

    section[data-testid="stSidebar"] * {
        font-family: 'Ubuntu', sans-serif !important;
    }

    div[data-testid="stDataFrame"] * {
        font-family: 'Ubuntu', sans-serif !important;
    }

    /* ---- KEEP ALL YOUR EXISTING DARK THEME CSS BELOW ---- */
    /* (no changes needed there) */
    p:has-text("keyboard_double_arrow_right") {
    display: none !important;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ==============
# ADD EXPENSE
# ==============
def add_expense():
    st.title("➕ Add Expense")
    with SessionLocal() as db:
        # =================
        # ADD EXPENSE ENTRY
        # =================
        cats = db.query(Category).all()
        if not cats:
            st.warning("Please add categories first")
            return
        cat_name = st.selectbox("Category", [c.name for c in cats])
        cat = db.query(Category).filter_by(name=cat_name).first()
        if not cat:
            st.warning("Invalid category")
            return
        subs = db.query(SubCategory).filter_by(category_id=cat.id).all()
        if not subs:
            st.info("Please add subcategories first")
            return
        sub_name = st.selectbox("Subcategory", [s.name for s in subs])
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
                st.success("Expense added ✅")
                st.rerun()
            else:
                st.error("Amount must be greater than 0")
        st.divider()

    with st.expander("📂 Manage Expense Categories"):
        manage_categories()

    with st.expander("🧾 Manage Expense Entries"):
        manage_entries()


# ============
# ADD INCOME
# ============
def income_section():
    st.title("💰 Income")
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
            cat_name = st.selectbox(
                "Select Income Category",
                [c.name for c in cats],
                key="add_income_cat_select"
            )
            cat = db.query(IncomeCategory).filter_by(name=cat_name).first()
            subs = db.query(IncomeSubCategory).filter_by(
                category_id=cat.id
            ).all()
            if not subs:
                st.info("Add income subcategories first (Advanced section)")
                sub = None
            else:
                sub_name = st.selectbox(
                    "Select Income Subcategory",
                    [s.name for s in subs],
                    key="add_income_sub_select"
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
                st.success("Income added ✅")
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
            .all(),
            columns=["id", "date", "amount", "category", "subcategory"]
        )
        if df.empty:
            st.info("No income data available")
            return
        df["date"] = pd.to_datetime(df["date"])
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
                st.plotly_chart(fig_cat, use_container_width=True)

        with col2:
            st.markdown("**By Subcategory**")
            sub_pie = period_df.groupby("subcategory", as_index=False)["amount"].sum()
            if not sub_pie.empty:
                fig_sub = px.pie(sub_pie, names="subcategory", values="amount", hole=0.4)
                fig_sub.update_layout(paper_bgcolor="#000", font=dict(color="#fff"))
                st.plotly_chart(fig_sub, use_container_width=True)

        # =====================
        # MANAGE INCOME ENTRIES
        # =====================
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
                    st.success("Income entries updated successfully")
                    st.rerun()
            elif action_mode == "Delete Income Entries":
                del_df = filtered_df.copy()
                del_df["date"] = pd.to_datetime(del_df["date"]).dt.strftime("%Y-%m-%d")
                gb = GridOptionsBuilder.from_dataframe(del_df)
                gb.configure_column("date", checkboxSelection=True, headerCheckboxSelection=True)
                gb.configure_column("id", hide=True)
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
                            st.success("Selected income entries deleted")
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
                    st.success("Income category added")
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
                    st.success("Income subcategory added")
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
                        st.success("Income category renamed")
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
                        st.success("Income subcategory renamed")
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
                        st.success("Income subcategory deleted")
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
                    st.success(f"Income category '{del_cat.name}' deleted")
                    st.rerun()


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
                st.success("Category added")
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
                st.success("Category renamed")
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
                st.success("Subcategory added")
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
                st.success("Subcategory renamed")
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
                st.success(
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
                    st.success("Subcategory deleted")
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
                    st.success("Category deleted")
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
        )
        if sel_cat != "All":
            q = q.filter(Category.name == sel_cat)
        if sel_sub != "All":
            q = q.filter(SubCategory.name == sel_sub)

        df = pd.DataFrame(q.all(), columns=["id", "date", "category", "subcategory", "amount"])
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
                st.success("Entries updated successfully")
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
                gb.configure_column("date", checkboxSelection=True, headerCheckboxSelection=True)
                gb.configure_column("id", hide=True)
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
                            st.success("Selected entries deleted")
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
                        st.success("All filtered entries deleted")
                        st.rerun()

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

        daily_total = (
            db.query(func.sum(Expense.amount))
            .filter(Expense.date == selected_date)
            .scalar()
        ) or 0

        st.sidebar.divider()
        st.sidebar.metric(
            f"Total · {selected_date.strftime('%d %b')}",
            f"₹ {daily_total:,.0f}"
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

        month_expense = (
            db.query(func.sum(Expense.amount))
            .filter(Expense.date.between(month_start_ts.date(), today_date))
            .scalar()
        ) or 0

        year_expense = (
            db.query(func.sum(Expense.amount))
            .filter(Expense.date.between(year_start_ts.date(), today_date))
            .scalar()
        ) or 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Last 7 Days", f"₹ {week_expense:,.2f}")
        c2.metric("This Month", f"₹ {month_expense:,.2f}")
        c3.metric("Year So Far", f"₹ {year_expense:,.2f}")

    # ============================
    # PERIOD FILTER (CHARTS)
    # ============================
    st.divider()
    st.subheader("📅 Period Filter")
     

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
                    hovertemplate="<b>%{label}</b><br>₹ %{value:,.0f}<br>%{customdata}%<extra></extra>"
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
        ][["date", "subcategory", "amount"]].sort_values("date")

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
    # SUBCATEGORY DETAILS TABLE
    # ============================
    st.divider()
    st.subheader("📋 Subcategory Details")

    # ---- Select subcategory (based on selected category)
    available_subs = sorted(
        period_df[period_df["category"] == selected_category]["subcategory"].unique()
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
        (df["category"] == selected_category) &
        (df["subcategory"] == selected_subcategory) &
        (df["date"].between(start_ts, end_ts))
    ][["date", "subcategory", "amount"]]

    if table_df.empty:
        st.warning("No records found for this selection")
    else:
        table_df = table_df.sort_values("date")

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


    # ============================
    # WEEKLY TREND (SMART & SCALABLE)
    # ============================

    # Prepare full daily trend
    trend_df = (
        df.assign(day=lambda x: x["date"].dt.date)
        .groupby("day", as_index=False)["amount"]
        .sum()
        .sort_values("day")
    )

    if trend_df.empty:
        st.caption("No data available")
        return

    # ----------------------------
    # Adaptive aggregation
    # ----------------------------
    days_span = (trend_df["day"].max() - trend_df["day"].min()).days

    if days_span <= 14:
        plot_df = trend_df
    elif days_span <= 90:
        plot_df = (
            trend_df
            .assign(week=lambda x: pd.to_datetime(x["day"]).dt.to_period("W").dt.start_time)
            .groupby("week", as_index=False)["amount"]
            .sum()
            .rename(columns={"week": "day"})
        )
    else:
        plot_df = (
            trend_df
            .assign(month=lambda x: pd.to_datetime(x["day"]).dt.to_period("M").dt.start_time)
            .groupby("month", as_index=False)["amount"]
            .sum()
            .rename(columns={"month": "day"})
        )

    # ----------------------------
    # UI container
    # ----------------------------
    st.markdown('<div class="weekly-trend-box">', unsafe_allow_html=True)

    header_col, btn_col = st.columns([6, 1])
    header_col.markdown("📈 **Spending Trend**")

    if btn_col.button(
        "➖" if st.session_state.show_weekly_trend else "➕",
        key="weekly_toggle"
    ):
        st.session_state.show_weekly_trend = not st.session_state.show_weekly_trend

    # ----------------------------
    # Plot
    # ----------------------------
    if st.session_state.show_weekly_trend:

        y_max = max(plot_df["amount"].max() * 1.1, 100)

        fig = px.line(
            plot_df,
            x="day",
            y="amount",
            markers=True
        )

        fig.update_layout(
            height=220,
            paper_bgcolor="#000",
            plot_bgcolor="#000",
            font=dict(color="#fff"),
            xaxis_title=None,
            yaxis_title=None,

            # Never allow negative Y
            yaxis=dict(
                range=[0, y_max],
                fixedrange=False
            ),

            # Allow horizontal pan
            xaxis=dict(
                type="date",
                fixedrange=False
            )
        )

        # Default focus → last 7 days
        fig.update_xaxes(
            range=[
                trend_df["day"].max() - pd.Timedelta(days=7),
                trend_df["day"].max()
            ]
        )

        st.plotly_chart(fig, use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)



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
        return
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
        return
    last_month = monthly_sub.iloc[-1]
    prev_month = monthly_sub.iloc[-2]
    diff = last_month - prev_month
    pct = (diff / prev_month) * 100 if prev_month != 0 else 0
    direction = "higher" if diff > 0 else "lower"
    arrow = "🔺" if diff > 0 else "🔻"
    st.success(
        f"""
        {arrow} You spent **₹ {abs(diff):,.2f} ({abs(pct):.1f}%)**
        **{direction}** on **{sel_cat} → {sel_sub}**
        compared to the previous month.
        """
    )

# ====================================================
# EXPORT
# ====================================================
# ===================
# PDF EXPORT FUNCTION
# ===================
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
        data.append(["", "", "TOTAL", f"{total_amount:.2f}"])

    table = Table(data, repeatRows=1, hAlign="CENTER")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.black),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 1), (-1, -1), colors.black),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
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

    doc.build(
        [table],
        onFirstPage=lambda c, d: (black_page(c, d), draw_footer(c, d)),
        onLaterPages=lambda c, d: (black_page(c, d), draw_footer(c, d))
    )
    buffer.seek(0)
    return buffer   
# ==========================
# Black background for pages
# ==========================
def black_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(colors.black)
    canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], stroke=0, fill=1)
    canvas.restoreState()


# ================
# EXPORT DATA
# ================
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
            )
            if sel_cat != "All":
                q = q.filter(Category.name == sel_cat)
            if sel_sub != "All":
                q = q.filter(SubCategory.name == sel_sub)
            df = pd.DataFrame(q.all())
            if df.empty:
                st.info("No data for selected filters")
            else:
                st.dataframe(df, use_container_width=True)
                footer_text = (
                    f"Exported on: {today.strftime('%Y-%m-%d')} | "
                    f"Period: {period} | "
                    f"Category: {sel_cat} | "
                    f"Subcategory: {sel_sub} | "
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
                        file_name=f"expenses_{today.strftime('%Y-%m-%d')}.pdf",
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



# ======================
# WORKOUT TRENDS DATAFRAME  
# ======================
def get_workout_trend_df(start, end):
    with SessionLocal() as db:
        df = pd.DataFrame(
            db.query(
                Workout.date,
                Workout.exercise,
                Workout.sets,
                Workout.reps,
                Workout.duration_min
            )
            .filter(Workout.date.between(start, end))
            .all(),
            columns=["date", "exercise", "sets", "reps", "duration"]
        )

    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"])

    # reps-based volume
    df["total_reps"] = (
        df["sets"].fillna(0) * df["reps"].fillna(0)
    )

    return df


# ======================
# HABIT SECTIONS
# ======================
def habit_dashboard():
    st.title("🧠 Habit Dashboard")

    today = pd.Timestamp.today().normalize()

    # =========================
    # DAILY HEALTH – TODAY
    # =========================
    st.subheader("📅 Today · Daily Health")

    with SessionLocal() as db:
        dh = db.get(DailyHealth, today.date())

    c1, c2, c3 = st.columns(3)

    if dh:
        c1.metric("💧 Water", f"{dh.water} glasses")
        c2.metric("😴 Sleep", f"{dh.sleep} hrs")
        c3.metric("⚖️ Weight", f"{dh.weight} kg")
    else:
        c1.metric("💧 Water", "—")
        c2.metric("😴 Sleep", "—")
        c3.metric("⚖️ Weight", "—")

    # =========================
    # WORKOUT SUMMARY
    # =========================
    # =========================
    # WORKOUT TRENDS
    # =========================
    st.divider()
    st.subheader("🏋️ Workout Trends")

    today = pd.Timestamp.today().normalize()

    # -------------------------
    # LOAD ALL WORKOUT DATA FIRST
    # -------------------------
    with SessionLocal() as db:
        df = pd.DataFrame(
            db.query(
                Workout.date,
                Workout.exercise,
                Workout.sets,
                Workout.reps,
                Workout.duration_min
            ).all(),
            columns=["date", "exercise", "sets", "reps", "duration"]
        )

    if df.empty:
        st.info("No workout data available")
        return

    df["date"] = pd.to_datetime(df["date"])
    df["total_reps"] = df["sets"].fillna(0) * df["reps"].fillna(0)

    # -------------------------
    # PERIOD FILTER
    # -------------------------
    period = st.radio(
        "Period",
        ["Weekly", "Monthly", "Custom"],
        horizontal=True,
        key="workout_trend_period"
    )

    if period == "Weekly":
        start = today - pd.Timedelta(days=6)
        end = today

    elif period == "Monthly":
        months = sorted(df["date"].dt.to_period("M").unique())
        month_labels = [m.strftime("%b %Y") for m in months]

        selected_label = st.selectbox(
            "Select Month",
            month_labels,
            key="workout_trend_month"
        )

        selected_period = months[month_labels.index(selected_label)]
        start = selected_period.to_timestamp()
        end = (selected_period + 1).to_timestamp() - pd.Timedelta(seconds=1)

    else:
        start, end = st.date_input(
            "Select date range",
            [today - pd.Timedelta(days=7), today],
            key="workout_trend_custom"
        )
        start = pd.Timestamp(start)
        end = pd.Timestamp(end)

    # -------------------------
    # APPLY DATE FILTER
    # -------------------------
    df = df[df["date"].between(start, end)]

    if df.empty:
        st.info("No workout data for selected period")
        return

    # -------------------------
    # SPLIT WORKOUT TYPES
    # -------------------------
    reps_exercises = [
        "Push-ups",
        "Squats",
        "Bicep Curls",
        "Tricep Pushbacks",
        "Handgrip"
    ]

    time_exercises = [
        "Walking",
        "Step Climbing",
        "Plank"
    ]

    # =========================
    # REPS-BASED TREND
    # =========================
    st.markdown("### 🔢 Reps-Based Workouts")

    reps_df = (
        df[df["exercise"].isin(reps_exercises)]
        .groupby(["date", "exercise"], as_index=False)["total_reps"]
        .sum()
    )

    if reps_df.empty:
        st.info("No reps-based workouts in this period")
    else:
        reps_df["date_only"] = reps_df["date"].dt.date

        fig = px.line(
            reps_df.assign(date_only=reps_df["date"].dt.date),
            x="date_only",
            y="total_reps",
            color="exercise",
            markers=True
        )

        fig.update_layout(
            height=320,
            paper_bgcolor="#000",
            plot_bgcolor="#000",
            font=dict(color="#fff"),
            yaxis_title="Total Reps",
            xaxis_title="Date",
            xaxis_tickformat="%d %b"
        )

        st.plotly_chart(fig, use_container_width=True)


    # =========================
    # TIME-BASED TREND
    # =========================
    st.markdown("### ⏱ Time-Based Workouts")

    time_df = (
        df[df["exercise"].isin(time_exercises)]
        .groupby(["date", "exercise"], as_index=False)["duration"]
        .sum()
    )

    if time_df.empty:
        st.info("No time-based workouts in this period")
    else:
        time_df["date_only"] = time_df["date"].dt.date

        fig = px.line(
            time_df.assign(date_only=time_df["date"].dt.date),
            x="date_only",
            y="duration",
            color="exercise",
            markers=True
        )

        fig.update_layout(
            height=320,
            paper_bgcolor="#000",
            plot_bgcolor="#000",
            font=dict(color="#fff"),
            yaxis_title="Minutes",
            xaxis_title="Date",
            xaxis_tickformat="%d %b"

        )

        st.plotly_chart(fig, use_container_width=True)
    # =========================
    # PER-WORKOUT MISSED DAYS
    # =========================
    st.divider()
    st.subheader("❌ Missed Days by Workout")

    # All days in selected range
    all_days = pd.date_range(start=start, end=end, freq="D")
    total_days = len(all_days)

    # Fixed workout list (important)
    all_exercises = [
        "Push-ups",
        "Squats",
        "Bicep Curls",
        "Tricep Pushbacks",
        "Handgrip",
        "Walking",
        "Step Climbing",
        "Plank"
    ]

    missed_data = []

    for exercise in all_exercises:
        done_days = (
            df[df["exercise"] == exercise]["date"]
            .dt.normalize()
            .nunique()
        )

        missed_days = total_days - done_days

        missed_data.append({
            "Workout": exercise,
            "Missed Days": missed_days
        })

    missed_df = pd.DataFrame(missed_data)

    # Optional: sort by most missed
    missed_df = missed_df.sort_values(
        by="Missed Days",
        ascending=False
    )

    # Display as simple table
    st.dataframe(
        missed_df,
        use_container_width=True,
        hide_index=True
    )

    st.divider()
    st.subheader("📈 Progressive Reps")

    exercise = st.selectbox(
        "Select Exercise",
        reps_exercises,
        key="progress_exercise"
    )

    ex_df = df[df["exercise"] == exercise].copy()

    if ex_df.empty:
        st.info("No data for selected exercise")
        return
    
    if period == "Weekly":
        st.markdown("### 🔁 Weekly Progressive Reps")

        # This week (Mon–Sun)
        this_week_start = today - pd.Timedelta(days=today.weekday())
        this_week_end = this_week_start + pd.Timedelta(days=6)

        # Last week (Mon–Sun)
        last_week_start = this_week_start - pd.Timedelta(days=7)
        last_week_end = this_week_start - pd.Timedelta(days=1)

        this_week_reps = ex_df[
            ex_df["date"].between(this_week_start, this_week_end)
        ]["total_reps"].sum()

        last_week_reps = ex_df[
            ex_df["date"].between(last_week_start, last_week_end)
        ]["total_reps"].sum()

        if last_week_reps == 0:
            st.info("Not enough data to compare with last week")
        else:
            progress = ((this_week_reps - last_week_reps) / last_week_reps) * 100

            st.metric(
                "Weekly Progress",
                f"{this_week_reps} reps",
                f"{progress:+.2f}%"
            )
    elif period == "Monthly":
        st.markdown("### 📅 Monthly Progressive Reps")

        # This month
        this_month_start = today.replace(day=1)

        # Last month
        last_month_end = this_month_start - pd.Timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)

        this_month_reps = ex_df[
            ex_df["date"].between(this_month_start, today)
        ]["total_reps"].sum()

        last_month_reps = ex_df[
            ex_df["date"].between(last_month_start, last_month_end)
        ]["total_reps"].sum()

        if last_month_reps == 0:
            st.info("Not enough data to compare with last month")
        else:
            progress = ((this_month_reps - last_month_reps) / last_month_reps) * 100

            st.metric(
                "Monthly Progress",
                f"{this_month_reps} reps",
                f"{progress:+.2f}%"
            )



    # ==================
    # FOOD (PLACEHOLDER)
    # ==================
    st.divider()
    st.subheader("🍽 Food")

    st.info("Food tracking summary will appear here")


# ===============
# WORKOUT SECTION
# ===============
def habit_workout():
    st.title("🏋️ Workout Tracker")

    exercises = [
        "Push-ups",
        "Squats",
        "Bicep Curls",
        "Tricep Pushbacks",
        "Handgrip",
        "Walking",
        "Step Climbing",
        "Plank"
    ]

    with SessionLocal() as db:
        # ============
        # ADD WORKOUT
        # ============
        st.subheader("➕ Add Workout")

        workout_date = st.date_input("Workout Date", value=date.today())
        exercise = st.selectbox("Exercise", exercises)

        is_time_based = exercise in ["Walking", "Step Climbing", "Plank"]

        col1, col2 = st.columns(2)

        if is_time_based:
            with col1:
                duration = st.number_input(
                    "Duration (minutes)",
                    min_value=0.0,
                    step=1.0
                )
            sets = reps = None
        else:
            with col1:
                sets = st.number_input("Sets", min_value=1, step=1)
            with col2:
                reps = st.number_input("Reps per set", min_value=1, step=1)
            duration = None

        if st.button("💾 Save Workout"):
            db.add(
                Workout(
                    date=workout_date,
                    exercise=exercise,
                    sets=sets,
                    reps=reps,
                    duration_min=duration
                )
            )
            db.commit()
            st.success("Workout saved ✅")
            st.rerun()

        # ========
        # FILTERS
        # ========
        st.divider()
        st.subheader("🔍 Filters")

        col1, col2 = st.columns(2)

        with col1:
            date_filter = st.radio(
                "Date Filter",
                ["Last 7 Days", "Monthly", "Yearly", "Custom"],
                horizontal=True
            )

        with col2:
            exercise_filter = st.selectbox(
                "Exercise Type",
                ["All"] + exercises
            )

        today = date.today()

        if date_filter == "Last 7 Days":
            start = today - timedelta(days=6)
            end = today

        elif date_filter == "Monthly":
            months = (
                db.query(func.strftime("%Y-%m", Workout.date))
                .distinct()
                .order_by(func.strftime("%Y-%m", Workout.date))
                .all()
            )

            if not months:
                st.info("No workout data available for monthly filter")
                return

            labels = [
                pd.to_datetime(m[0] + "-01").strftime("%b %Y")
                for m in months
            ]

            sel = st.selectbox("Select Month", labels)
            idx = labels.index(sel)

            start = pd.to_datetime(months[idx][0] + "-01").date()
            end = (pd.to_datetime(start) + pd.offsets.MonthEnd(1)).date()

        elif date_filter == "Yearly":
            years = sorted({
                int(y[0]) for y in
                db.query(func.strftime("%Y", Workout.date)).all()
            })

            if not years:
                st.info("No workout data available for yearly filter")
                return

            year = st.selectbox("Select Year", years)

            start = date(year, 1, 1)
            end = date(year, 12, 31)

        else:
            start, end = st.date_input(
                "Custom Date Range",
                [today.replace(day=1), today]
            )

        # ===================
        # LOAD FILTERED DATA
        # ===================
        q = (
            db.query(
                Workout.id,
                Workout.date,
                Workout.exercise,
                Workout.sets,
                Workout.reps,
                Workout.duration_min
            )
            .filter(Workout.date.between(start, end))
        )

        if exercise_filter != "All":
            q = q.filter(Workout.exercise == exercise_filter)

        df = pd.DataFrame(
            q.order_by(Workout.date.desc()).all(),
            columns=["id", "date", "exercise", "sets", "reps", "duration_min"]
        )

        if df.empty:
            st.info("No workouts found for selected filters")
            return

        df["date"] = pd.to_datetime(df["date"])

        # ===========
        # ACTION MODE
        # ===========
        st.divider()
        action = st.radio(
            "Action",
            ["Edit Entries", "Delete Entries"],
            horizontal=True
        )

        # =========
        # EDIT MODE
        # =========
        if action == "Edit Entries":
            edited_df = st.data_editor(
                df,
                use_container_width=True,
                disabled=["id"],
                column_config={
                    "date": st.column_config.DateColumn("Date"),
                    "exercise": st.column_config.SelectboxColumn(
                        "Exercise",
                        options=exercises
                    ),
                    "sets": st.column_config.NumberColumn("Sets", min_value=0),
                    "reps": st.column_config.NumberColumn("Reps", min_value=0),
                    "duration_min": st.column_config.NumberColumn(
                        "Duration (min)",
                        min_value=0.0
                    ),
                }
            )

            if st.button("💾 Save Changes"):
                with db.no_autoflush:
                    for _, row in edited_df.iterrows():
                        w = db.get(Workout, int(row["id"]))
                        if not w:
                            continue
                        w.date = pd.to_datetime(row["date"]).date()
                        w.exercise = row["exercise"]
                        w.sets = int(row["sets"]) if not pd.isna(row["sets"]) else None
                        w.reps = int(row["reps"]) if not pd.isna(row["reps"]) else None
                        w.duration_min = (
                            float(row["duration_min"])
                            if not pd.isna(row["duration_min"])
                            else None
                        )
                db.commit()
                st.success("Workout entries updated ✅")
                st.rerun()

        # ============
        # DELETE MODE
        # ============
        else:
            delete_mode = st.radio(
                "Delete Option",
                ["Delete selected rows", "Delete ALL filtered rows"],
                horizontal=True
            )

            df_del = df.copy()
            df_del["date"] = df_del["date"].dt.strftime("%Y-%m-%d")

            if delete_mode == "Delete selected rows":
                gb = GridOptionsBuilder.from_dataframe(df_del)
                gb.configure_column("date", checkboxSelection=True, headerCheckboxSelection=True)
                gb.configure_column("id", hide=True)
                gb.configure_grid_options(
                    rowSelection="multiple",
                    suppressRowClickSelection=True
                )

                grid = AgGrid(
                    df_del,
                    gridOptions=gb.build(),
                    update_mode=GridUpdateMode.MODEL_CHANGED,
                    fit_columns_on_grid_load=True
                )

                selected = pd.DataFrame(grid["selected_rows"])

                if not selected.empty:
                    st.warning(f"Selected rows: {len(selected)}")

                    if st.checkbox("Confirm delete selected workouts"):
                        if st.button("❌ Delete Selected"):
                            for _, row in selected.iterrows():
                                w = db.get(Workout, int(row["id"]))
                                if w:
                                    db.delete(w)
                            db.commit()
                            st.success("Selected workouts deleted")
                            st.rerun()

            else:
                st.warning(f"This will delete ALL {len(df)} filtered workouts")
                if st.checkbox("I understand this is permanent"):
                    if st.button("❌ Delete ALL Filtered"):
                        for _, row in df.iterrows():
                            w = db.get(Workout, int(row["id"]))
                            if w:
                                db.delete(w)
                        db.commit()
                        st.success("All filtered workouts deleted")
                        st.rerun()


def habit_water():
    st.title("💧 Water")
    st.info("Water intake tracking coming soon")

def habit_food():
    st.title("🍽 Food")
    st.info("Food tracking coming soon")


def habit_daily_health():
    st.title("💧😴⚖️ Daily Health")

    with SessionLocal() as db:
        date_selected = st.date_input("Date", value=date.today())

        existing = db.get(DailyHealth, date_selected)

        col1, col2, col3 = st.columns(3)

        with col1:
            water = st.number_input(
                "💧 Water (Litres)",
                min_value=0,
                max_value=30,
                step=1,
                value=existing.water if existing else 0
            )

        with col2:
            sleep_hours = st.number_input(
                "😴 Sleep (hours)",
                min_value=0.0,
                max_value=24.0,
                step=0.5,
                value=existing.sleep if existing else 0.0
            )

        with col3:
            weight = st.number_input(
                "⚖️ Weight (kg)",
                min_value=0.0,
                max_value=300.0,
                step=0.1,
                value=existing.weight if existing else 0.0
            )

        if st.button("💾 Save Daily Health"):
            if existing:
                existing.water = water
                existing.sleep = sleep_hours
                existing.weight = weight
            else:
                db.add(
                    DailyHealth(
                        date=date_selected,
                        water=water,
                        sleep=sleep_hours,
                        weight=weight
                    )
                )
            db.commit()
            st.success("Daily health saved ✅")
            st.rerun()


def habit_insights():
    st.title("📈 Habit Insights")
    st.info("Habit insights coming soon")

def habit_export():
    st.title("📤 Habit Export")
    st.info("Habit export coming soon")
# ================= SIDEBAR =================
tracker = st.sidebar.radio(
    "📌 Select Tracker",
    ["Finance", "Habit"]
)
if tracker == "Finance":
    page = st.sidebar.radio(
        "Finance Menu",
        [
            "Expense Dashboard",
            "Add Expense",
            "Income & Dashboard",
            "Insights",
            "Export Data",
        ]
    )
else:  
    page = st.sidebar.radio(
        "Habit Menu",
        [
            "Dashboard",
            "Workout",
            "Daily Health",
            "Food",
            "Insights",
            "Export Data",
        ]
    )



# ================= ROUTER =================
if tracker == "Finance":
    if page == "Expense Dashboard":
        dashboard()
    elif page == "Add Expense":
        add_expense() 
    elif page == "Income & Dashboard":
        income_section()
    elif page == "Insights":
        insights()
    elif page == "Export Data":
        export_data()
else:
    if page == "Dashboard":
        habit_dashboard()
    elif page == "Workout":
        habit_workout()
    elif page == "Daily Health":
        habit_daily_health()
    elif page == "Food":
        habit_food()
    elif page == "Insights":
        habit_insights()
    elif page == "Export Data":
        habit_export()
