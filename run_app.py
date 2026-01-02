import subprocess
import webbrowser
import time

subprocess.Popen(["streamlit", "run", "main.py"])
time.sleep(3)
webbrowser.open("http://localhost:8501")
