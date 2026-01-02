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

# ================= STREAMLIT CONFIG =================
st.set_page_config("Expense Dashboard", layout="wide")

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
        background: #000000 !important;
        border-bottom: none !important;
    }

    /* Remove top padding bar */
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

    /* Streamlit input wrappers */
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
       REMOVE STREAMLIT CONTAINERS
    =============================== */
    div[data-testid="stVerticalBlock"],
    div[data-testid="stHorizontalBlock"],
    div[data-testid="stContainer"] {
        background-color: #000000 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# ================= DATABASE =================
engine = create_engine("sqlite:///expense.db", echo=False)
SessionLocal = sessionmaker(bind=engine)
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
    category_id = Column(Integer, ForeignKey("categories.id"))
    subcategory_id = Column(Integer, ForeignKey("subcategories.id"))
    date = Column(Date, nullable=False)
    amount = Column(Float, nullable=False)

Base.metadata.create_all(engine)

# ================= SIDEBAR =================
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to",
    [
        "Add Expense",
        "Manage Categories",
        "Manage Entries",
        "Dashboard",
        "Insights",
        "Export"
    ]
)

# ====================================================
# ADD EXPENSE
# ====================================================
def add_expense():
    st.title("➕ Add Expense")
    db = SessionLocal()

    cats = db.query(Category).all()
    if not cats:
        st.warning("Please add categories first")
        db.close()
        return

    cat_name = st.selectbox("Category", [c.name for c in cats])
    cat = db.query(Category).filter_by(name=cat_name).first()

    subs = db.query(SubCategory).filter_by(category_id=cat.id).all()
    if not subs:
        st.info("Please add subcategories first")
        db.close()
        return

    sub_name = st.selectbox("Subcategory", [s.name for s in subs])
    sub = db.query(SubCategory).filter_by(name=sub_name, category_id=cat.id).first()

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
            st.success("Expense added ✅")
        else:
            st.error("Amount must be greater than 0")

    db.close()

# ====================================================
# MANAGE CATEGORIES
# ====================================================
def manage_categories():
    st.title("📂 Manage Categories")
    db = SessionLocal()

    # =========================
    # ADD CATEGORY
    # =========================
    with st.container():
        st.subheader("➕ Add Category")
        col1, col2 = st.columns([3, 1])

        with col1:
            new_cat = st.text_input("New Category", placeholder="e.g. Transport")

        with col2:
            if st.button("Add Category"):
                if new_cat.strip() and not db.query(Category).filter_by(name=new_cat).first():
                    db.add(Category(name=new_cat.strip()))
                    db.commit()
                    st.success("Category added")
                    st.rerun()

    st.divider()

    cats = db.query(Category).all()
    if not cats:
        st.info("No categories available")
        db.close()
        return

    # =========================
    # CATEGORY SELECTION
    # =========================
    st.subheader("📁 Manage Subcategories")
    cat_name = st.selectbox("Select Category", [c.name for c in cats])
    cat = db.query(Category).filter_by(name=cat_name).first()

    # =========================
    # ADD SUBCATEGORY
    # =========================
    col1, col2 = st.columns([3, 1])

    with col1:
        new_sub = st.text_input("New Subcategory", placeholder="e.g. Bus, Fuel")

    with col2:
        if st.button("Add Subcategory"):
            if new_sub.strip() and not db.query(SubCategory).filter_by(
                name=new_sub, category_id=cat.id
            ).first():
                db.add(SubCategory(name=new_sub.strip(), category_id=cat.id))
                db.commit()
                st.success("Subcategory added")
                st.rerun()

    st.divider()

    # =========================
    # DELETE SUBCATEGORY
    # =========================
    subs = db.query(SubCategory).filter_by(category_id=cat.id).all()

    if subs:
        st.subheader("🗑 Delete Subcategory")
        sub_name = st.selectbox(
            "Select Subcategory",
            [s.name for s in subs]
        )

        if st.checkbox("Confirm delete selected subcategory"):
            if st.button("❌ Delete Subcategory"):
                sub = db.query(SubCategory).filter_by(
                    name=sub_name,
                    category_id=cat.id
                ).first()

                db.query(Expense).filter_by(subcategory_id=sub.id).delete()
                db.delete(sub)
                db.commit()
                st.success("Subcategory deleted")
                st.rerun()
    else:
        st.info("No subcategories under this category")

    st.divider()

    # =========================
    # DELETE CATEGORY (DANGER)
    # =========================
    with st.expander("⚠️ Delete Entire Category (Danger Zone)"):
        st.warning("This will delete ALL subcategories and expenses under this category.")

        if st.checkbox("I understand and want to delete this category"):
            if st.button("❌ Delete Category"):
                db.query(Expense).filter_by(category_id=cat.id).delete()
                db.query(SubCategory).filter_by(category_id=cat.id).delete()
                db.delete(cat)
                db.commit()
                st.success("Category deleted")
                st.rerun()

    db.close()


def manage_entries():
    st.title("🧾 Manage Entries")
    db = SessionLocal()

    # -------- CATEGORY FILTER --------
    cats = db.query(Category).all()
    cat_names = ["All"] + [c.name for c in cats]
    sel_cat = st.selectbox("Category", cat_names)

    sub_names = ["All"]
    if sel_cat != "All":
        cat = db.query(Category).filter_by(name=sel_cat).first()
        sub_names += [
            s.name for s in db.query(SubCategory).filter_by(category_id=cat.id)
        ]

    sel_sub = st.selectbox("Subcategory", sub_names)

    # -------- DATE FILTER --------
    mode = st.radio(
        "Date filter",
        ["Weekly", "Monthly", "Yearly", "Custom"],
        horizontal=True
    )

    today = date.today()

    if mode == "Monthly":
        months = (
            db.query(func.strftime("%Y-%m", Expense.date))
            .distinct()
            .order_by(func.strftime("%Y-%m", Expense.date))
            .all()
        )

        month_map = {
            pd.to_datetime(m[0] + "-01").strftime("%b %Y"):
            pd.to_datetime(m[0] + "-01")
            for m in months
        }

        if not month_map:
            st.info("No monthly data available")
            db.close()
            return

        label = st.selectbox("Select Month", list(month_map.keys()))
        start = month_map[label].date()
        end = (month_map[label] + pd.offsets.MonthEnd(1)).date()

    elif mode == "Yearly":
        years = (
            db.query(func.strftime("%Y", Expense.date))
            .distinct()
            .order_by(func.strftime("%Y", Expense.date))
            .all()
        )
        years = [int(y[0]) for y in years]

        if not years:
            st.info("No yearly data available")
            db.close()
            return

        year = st.selectbox("Select Year", years)
        start = date(year, 1, 1)
        end = date(year, 12, 31)

    elif mode == "Weekly":
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

    else:  # Custom
        start, end = st.date_input(
            "Select date range",
            [today.replace(day=1), today]
        )

    # -------- QUERY --------
    q = (
        db.query(
            Expense.id,
            Expense.date,
            Category.name.label("category"),
            SubCategory.name.label("subcategory"),
            Expense.amount
        )
        .select_from(Expense)
        .join(Category, Expense.category_id == Category.id)
        .join(SubCategory, Expense.subcategory_id == SubCategory.id)
        .filter(Expense.date.between(start, end))
    )

    if sel_cat != "All":
        q = q.filter(Category.name == sel_cat)
    if sel_sub != "All":
        q = q.filter(SubCategory.name == sel_sub)

    df = pd.DataFrame(
        q.all(),
        columns=["id", "date", "category", "subcategory", "amount"]
    )

    if df.empty:
        st.info("No entries found for selected filters")
        db.close()
        return

    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

    # -------- GRID --------
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_column("id", editable=False)
    gb.configure_column("category", editable=False)
    gb.configure_column("subcategory", editable=False)
    gb.configure_pagination()
    gb.configure_selection("multiple", use_checkbox=True)

    grid = AgGrid(
        df,
        gridOptions=gb.build(),
        update_mode=GridUpdateMode.MODEL_CHANGED,
        fit_columns_on_grid_load=True
    )

    # -------- SAVE CHANGES --------
    if st.button("Save Changes"):
        for _, r in grid["data"].iterrows():
            exp = db.get(Expense, r["id"])
            exp.date = pd.to_datetime(r["date"]).date()
            exp.amount = r["amount"]
        db.commit()
        st.success("Changes saved ✅")

    # -------- DELETE (SAFE MULTI-DELETE) --------
    st.divider()
    st.subheader("🗑 Delete Entries")

    # -------- SELECT ALL OPTION --------
    select_all = st.checkbox("Select ALL entries in current filter")

    if select_all:
        delete_df = df.copy()
    else:
        selected_rows = grid.get("selected_rows")

        if selected_rows is None:
            delete_df = pd.DataFrame()
        elif isinstance(selected_rows, list):
            delete_df = pd.DataFrame(selected_rows)
        else:
            delete_df = selected_rows

    # -------- DELETE ACTION --------
    if not delete_df.empty:
        st.warning(f"Selected rows for deletion: {len(delete_df)}")

        confirm = st.checkbox("I understand this will permanently delete the entries")

        if confirm:
            if st.button("❌ Delete Selected Entries"):
                for _, row in delete_df.iterrows():
                    exp = db.get(Expense, int(row["id"]))
                    if exp:
                        db.delete(exp)

                db.commit()
                st.success(f"Deleted {len(delete_df)} entries successfully")
                st.rerun()


    db.close()


# ====================================================
# DASHBOARD
# ====================================================
def dashboard():
    st.title("📊 Dashboard")
    db = SessionLocal()

    # -------- LOAD DATA --------
    q = (
        db.query(
            Expense.date,
            Expense.amount,
            Category.name.label("category"),
            SubCategory.name.label("subcategory")
        )
        .select_from(Expense)
        .join(Category, Expense.category_id == Category.id)
        .join(SubCategory, Expense.subcategory_id == SubCategory.id)
    )

    df = pd.DataFrame(q.all(), columns=["date", "amount", "category", "subcategory"])

    if df.empty:
        st.info("No data available")
        db.close()
        return

    df["date"] = pd.to_datetime(df["date"])
    today = pd.Timestamp.today().normalize()

    # ======================================
    # TOP PERIOD SELECTOR
    # ======================================
    period_mode = st.radio(
        "View spend for",
        ["Weekly", "Monthly", "Yearly", "Custom"],
        horizontal=True
    )

    # -------- DATE RANGE LOGIC --------
    if period_mode == "Weekly":
        week_option = st.selectbox(
            "Select Week",
            ["This Week", "Last Week"]
        )

        if week_option == "This Week":
            start = today - pd.to_timedelta(today.weekday(), unit="D")
            end = today
        else:
            end = today - pd.to_timedelta(today.weekday() + 1, unit="D")
            start = end - pd.to_timedelta(6, unit="D")

    elif period_mode == "Monthly":
        months = sorted(df["date"].dt.to_period("M").unique())
        month_labels = [m.strftime("%b %Y") for m in months]

        sel = st.selectbox("Select Month", month_labels, index=len(month_labels) - 1)
        sel_period = months[month_labels.index(sel)]

        start = sel_period.to_timestamp()
        end = (sel_period + 1).to_timestamp() - pd.Timedelta(days=1)

    elif period_mode == "Yearly":
        years = sorted(df["date"].dt.year.unique())
        year = st.selectbox("Select Year", years, index=len(years) - 1)

        start = pd.Timestamp(year=year, month=1, day=1)
        end = pd.Timestamp(year=year, month=12, day=31)

    else:  # Custom
        start, end = st.date_input(
            "Select date range",
            [today.replace(day=1), today]
        )
        start = pd.to_datetime(start)
        end = pd.to_datetime(end)

    # -------- FILTER DATA --------
    period_df = df[df["date"].between(start, end)]
    total_spend = period_df["amount"].sum()

    # ======================================
    # TOP METRICS
    # ======================================
    col1, col2, col3 = st.columns(3)

    week_start = today - pd.to_timedelta(today.weekday(), unit="D")
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    col1.metric(
        "This Week",
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
    st.subheader(f"Total for selected period: ₹ {total_spend:.2f}")

    # ======================================
    # CATEGORY PIE
    # ======================================
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
    legend=dict(
        bgcolor="#000000",
        bordercolor="#000000"
    )
)
    

    st.plotly_chart(fig_cat, use_container_width=True)

    # ======================================
    # SUBCATEGORY PIE
    # ======================================
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
    legend=dict(
        bgcolor="#000000",
        bordercolor="#000000"
    )
)

    st.plotly_chart(fig_sub, use_container_width=True)

    db.close()

def insights():
    st.title("📈 Insights")
    db = SessionLocal()

    q = (
        db.query(
            Expense.date,
            Expense.amount,
            Category.name.label("category")
        )
        .select_from(Expense)
        .join(Category, Expense.category_id == Category.id)
    )

    df = pd.DataFrame(q.all(), columns=["date", "amount", "category"])

    if df.empty:
        st.info("No data available")
        db.close()
        return

    df["date"] = pd.to_datetime(df["date"])

    # ======================================
    # INSIGHT 1: AVERAGE DAILY SPEND
    # ======================================
    daily_avg = (
        df.groupby(df["date"].dt.date)["amount"]
        .sum()
        .mean()
    )

    # ======================================
    # INSIGHT 2: HIGHEST SPENDING MONTH
    # ======================================
    monthly = (
        df.groupby(df["date"].dt.to_period("M"))["amount"]
        .sum()
        .sort_values(ascending=False)
    )

    top_month = monthly.index[0].strftime("%b %Y")
    top_month_value = monthly.iloc[0]

    # ======================================
    # INSIGHT 3: TOP CATEGORY
    # ======================================
    cat_df = (
        df.groupby("category")["amount"]
        .sum()
        .sort_values(ascending=False)
    )

    top_category = cat_df.index[0]
    top_category_value = cat_df.iloc[0]

    # ======================================
    # INSIGHT 4: NO-SPEND DAYS
    # ======================================
    all_days = pd.date_range(df["date"].min(), df["date"].max())
    spent_days = df["date"].dt.normalize().unique()
    no_spend_days = len(set(all_days.date) - set(spent_days))

    # ======================================
    # DISPLAY METRICS
    # ======================================
    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Avg Daily Spend",
        f"₹ {daily_avg:.2f}"
    )

    col2.metric(
        "Highest Spend Month",
        top_month,
        f"₹ {top_month_value:.2f}"
    )

    col3.metric(
        "Top Category",
        top_category,
        f"₹ {top_category_value:.2f}"
    )

    col4.metric(
        "No-Spend Days",
        no_spend_days
    )

    db.close()


# ====================================================
# EXPORT
# ====================================================

def export_pdf(df):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=20
    )

    data = [df.columns.tolist()] + df.values.tolist()

    table = Table(data, repeatRows=1, hAlign="CENTER")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.black),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("FONT", (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("BACKGROUND", (0,1), (-1,-1), colors.whitesmoke),
        ("BOTTOMPADDING", (0,0), (-1,0), 8),
        ("TOPPADDING", (0,0), (-1,0), 8),
    ]))

    doc.build([table])
    buffer.seek(0)
    return buffer


def export_data():
    st.title("📤 Export")
    db = SessionLocal()

    # =========================
    # FILTER CONTROLS
    # =========================
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

    # =========================
    # DATE RANGE
    # =========================
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

    else:  # Custom
        start, end = st.date_input(
            "Custom Date Range",
            [today.replace(day=1), today]
        )

    st.divider()

    # =========================
    # APPLY FILTERS
    # =========================
    if st.button("Apply Filters"):
        q = (
            db.query(
                Expense.date,
                Category.name.label("Category"),
                SubCategory.name.label("Subcategory"),
                Expense.amount.label("Amount")
            )
            .select_from(Expense)
            .join(Category, Expense.category_id == Category.id)
            .join(SubCategory, Expense.subcategory_id == SubCategory.id)
            .filter(Expense.date.between(start, end))
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

            pdf_buf = export_pdf(df)

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
                    pdf_buf,
                    "expenses.pdf",
                    mime="application/pdf"
                )

    else:
        st.dataframe(
            pd.DataFrame(
                columns=["Date", "Category", "Subcategory", "Amount"]
            ),
            use_container_width=True
        )

    db.close()


# ================= ROUTER =================
if page == "Add Expense":
    add_expense()
elif page == "Manage Categories":
    manage_categories()
elif page == "Manage Entries":
    manage_entries()
elif page == "Dashboard":
    dashboard()
elif page == "Insights":
    insights()
elif page == "Export":
    export_data()
