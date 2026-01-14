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
# ==============
# DB SETUP
# ==============
st.set_page_config(
    page_title="Expense Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
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
            sel = st.selectbox("Select Month", labels)
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
        st.subheader("📈 Income by Category")
        cat_pie = period_df.groupby("category", as_index=False)["amount"].sum()
        if not cat_pie.empty:
            fig_cat = px.pie(cat_pie, names="category", values="amount", hole=0.4)
            fig_cat.update_layout(paper_bgcolor="#000", font=dict(color="#fff"))
            st.plotly_chart(fig_cat, use_container_width=True)
        st.subheader("📈 Income by Subcategory")
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

# ====================================================
# DASHBOARD
# ====================================================
def dashboard():
    st.title("📊 Dashboard")
    with SessionLocal() as db:
        st.subheader("Income & Expense Summary(Current Month)")
        today = pd.Timestamp.today().normalize()
        month_start = today.replace(day=1)
        total_income = (
            db.query(func.sum(Income.amount))
            .filter(Income.date.between(
                month_start.date(),
                today.date()
            ))
            .scalar()
        ) or 0
        total_expense = (
            db.query(func.sum(Expense.amount))
            .filter(Expense.date.between(
                month_start.date(),
                today.date()
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
        st.sidebar.divider()
        # ========================
        # DAILY BUY SIDEBAR
        # ========================
        st.sidebar.subheader("🛒 Daily Buy")

        selected_date = st.sidebar.date_input(
            "",
            value=date.today(),
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
            st.sidebar.caption(f"No entries on {selected_date.strftime('%d %b %Y')}")
        else:
            grouped = (
                daily_df
                .groupby("subcategory", as_index=False)["amount"]
                .sum()
                .sort_values("amount", ascending=False)
            )

            for _, row in grouped.iterrows():
                st.sidebar.write(
                    f"• **{row['subcategory']}** — ₹ {row['amount']:,.0f}"
                )

            st.sidebar.divider()

            st.sidebar.metric(
                f"Total · {selected_date.strftime('%d %b')}",
                f"₹ {daily_df['amount'].sum():,.0f}"
            )

            # ---------- SAFETY ----------
            if "data_refresh" not in st.session_state:
                st.session_state.data_refresh = 0

            # ---------- LOAD DATA (ALWAYS FIRST) ----------
            df = load_expense_data(st.session_state.data_refresh)

            # df EXISTS from this point onward
            if df.empty:
                st.info("No data available")
                return


    # ============================
    # EXPENSE SUMMARY METRICS
    # ============================
    df["date"] = pd.to_datetime(df["date"])
    today = pd.Timestamp.today().normalize()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)
    week_start = today - pd.Timedelta(days=6)
    st.subheader("Expense Summary")
    col1, col2, col3 = st.columns(3)
    col1.metric(
        "Last 7 Days",
        f"₹ {df[df['date'].between(week_start, today)]['amount'].sum():.2f}"
    )
    col2.metric(
        "This Month",
        f"₹ {df[df['date'].between(month_start, today)]['amount'].sum():.2f}"
    )
    col3.metric(
        "Year So Far",
        f"₹ {df[df['date'].between(year_start, today)]['amount'].sum():.2f}"
    )
    st.divider()  
    st.subheader("📅 Period Filter")
    period_mode = st.radio(
        "Filter expenses by",
        ["Monthly", "Yearly", "Custom"],
        horizontal=True
    )
    if period_mode == "Monthly":
        months = sorted(df["date"].dt.to_period("M").unique())
        if not months:
            st.info("No monthly data available")
            return
        labels = [m.strftime("%b %Y") for m in months]
        months = sorted(df["date"].dt.to_period("M").unique())
        labels = [m.strftime("%b %Y") for m in months]
        current_period = pd.Timestamp.today().to_period("M")
        if current_period in months:
            default_index = months.index(current_period)
        else:
            default_index = len(months) - 1  # fallback to latest
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
        current_year = pd.Timestamp.today().year
        if current_year in years:
            default_index = years.index(current_year)
        else:
            default_index = len(years) - 1  
        year = st.selectbox(
            "Select Year",
            years,
            index=default_index
        )
        start = pd.Timestamp(year=year, month=1, day=1)
        end = pd.Timestamp(year=year, month=12, day=31)
    else: 
        start, end = st.date_input(
            "Select date range",
            [month_start.date(), today.date()]
        )
        start = pd.to_datetime(start)
        end = pd.to_datetime(end)
    period_df = df[df["date"].between(start, end)]
    total_spend = period_df["amount"].sum()
    st.markdown(f"## 💰 Total for selected period: ₹ {total_spend:.2f}")
    cat_df = (
        period_df.groupby("category", as_index=False)["amount"]
        .sum()
        .sort_values("amount", ascending=False)
    )
    fig_cat = px.pie(
        cat_df,
        names="category",
        values="amount",
        title="Spending by Category",
        hole=0.4
    )
    fig_cat.update_layout(
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(color="#ffffff"),
        legend=dict(bgcolor="#000000")
    )
    st.plotly_chart(fig_cat, use_container_width=True)
    if not cat_df.empty:
        selected_category = st.selectbox(
            "Select Category",
            cat_df["category"].tolist()
        )
        sub_df = (
            period_df[period_df["category"] == selected_category]
            .groupby("subcategory", as_index=False)["amount"]
            .sum()
            .sort_values("amount", ascending=False)
        )
        fig_sub = px.pie(
            sub_df,
            names="subcategory",
            values="amount",
            title=f"{selected_category} – Subcategories",
            hole=0.4
        )
        fig_sub.update_layout(
            paper_bgcolor="#000000",
            plot_bgcolor="#000000",
            font=dict(color="#ffffff"),
            legend=dict(bgcolor="#000000")
        )
        st.plotly_chart(fig_sub, use_container_width=True)

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
import io
from datetime import date, timedelta
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib.units import cm
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
    total_amount = df["Amount"].sum()
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
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.grey)
        canvas.drawCentredString(A4[0] / 2, 1 * cm, footer_text)
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


# ================= SIDEBAR =================
page = st.sidebar.radio(
    "",
    [
        "Dashboard",
        "Expense",
        "Insights",
        "Manage Categories",
        "Manage Entries",
        "Export Data",
        "Income",   
    ]
)
# ================= ROUTER =================
if page == "Expense":
    add_expense()
elif page == "Income":
    income_section()
elif page == "Manage Categories":
    manage_categories()
elif page == "Manage Entries":
    manage_entries()
elif page == "Dashboard":
    dashboard()
elif page == "Insights":
    insights()
elif page == "Export Data":
    export_data()
