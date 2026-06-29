from data_loader import load_and_preprocess
import pandas as pd

try:
    df = load_and_preprocess()
    print("Gender in cols:", "Gender" in df.columns)
    print("gender in cols:", "gender" in df.columns)
    print("Gender column values:", df["Gender"].unique() if "Gender" in df.columns else "Missing")
except Exception as e:
    print("Error:", e)
