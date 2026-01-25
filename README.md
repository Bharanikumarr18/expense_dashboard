# Personal Finance Tracker

A Python-based **Personal Finance Tracking Application** built using **Streamlit** and **SQLite**.  
The application helps manage expenses, income, and assets in a structured, reliable, and offline-first manner.

---

## ✨ Features

### 📌 Expense Management
- Add, edit, and delete expenses
- Category and subcategory support
- Date-based filtering and summaries

### 💰 Income Management
- Track income with categories and subcategories
- View total and period-wise income summaries

### 🧾 Asset Management
- Gold & Silver (weight-based valuation)
- Land assets
- Fixed Deposits (principal, interest, maturity value)
- LIC policies
- Household appliances with image support

### 📊 Reports & Summaries
- Expense and income summaries
- Asset net worth calculation
- Period-wise analytics
- PDF report generation

### 🔐 Data Handling
- Local SQLite database storage
- Safe fallback logic for asset pricing
- Fully functional without internet connection

---


## 🛠 Requirements

### System Requirements
- Python **3.9 or higher**
- pip (Python package manager)

### Python Dependencies
- streamlit
- pandas
- sqlalchemy
- plotly
- reportlab
- python-dateutil
- Pillow
- requests
- streamlit
- streamlit-aggrid
- setuptools
- matplotlib


---

## 📦 Installation

1. Clone the repository:
```bash
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>

Create and activate a virtual environment (recommended):
python -m venv venv
source venv/bin/activate      # Linux / macOS
venv\Scripts\activate         # Windows

Install dependencies:
pip install -r requirements.txt

If requirements.txt is not available:
pip install streamlit pandas sqlalchemy plotly reportlab python-dateutil pillow requests

▶️ Running the Application
Start the application using:
streamlit run main.py
