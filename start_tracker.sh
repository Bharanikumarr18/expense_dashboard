#!/bin/bash
cd /home/bharani-kumar/Documents/expense_dashboard
source venv/bin/activate
streamlit run main.py --server.address 0.0.0.0
