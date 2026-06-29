import os
import pandas as pd
import pypdf
import pdfplumber

def inspect_excel_csv(file_path):
    print(f"\n--- FILE: {file_path} ---")
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext == '.csv':
            # read first 5 lines to see separator/encoding if needed, then load
            df = pd.read_csv(file_path, nrows=5)
        else:
            df = pd.read_excel(file_path, nrows=5)
        print("Columns:", list(df.columns))
        print("First 2 rows:")
        print(df.head(2))
    except Exception as e:
        print(f"Error reading {file_path}: {e}")

def inspect_pdf(file_path):
    print(f"\n--- FILE: {file_path} ---")
    try:
        with pdfplumber.open(file_path) as pdf:
            print(f"Number of pages: {len(pdf.pages)}")
            page = pdf.pages[0]
            text = page.extract_text()
            print("Page 1 Text Sample (First 500 chars):")
            print(text[:500] if text else "No text extracted")
            # Let's see if we can extract tables
            tables = page.extract_tables()
            print(f"Number of tables found on page 1: {len(tables)}")
            if tables:
                print("First table row headers/data:")
                for row in tables[0][:3]:
                    print(row)
    except Exception as e:
        print(f"Error reading PDF {file_path}: {e}")

# Delaware
inspect_excel_csv("distributors/Delaware/Delaware_Business_Licenses_20260626.xlsx")

# DC
inspect_excel_csv("distributors/District of Columbia/Basic_Business_License.csv")

# Kansas
inspect_excel_csv("distributors/Kansas/tb84ALL.csv")

# Kentucky
inspect_pdf("distributors/Kentucky/Licensees 6-4-26.pdf")

# North Dakota
inspect_pdf("distributors/North Dakota/Licensees-TobaccoRetail-byCity.pdf")
inspect_pdf("distributors/North Dakota/Licensees-TobaccoWholesale.pdf")

# Pennsylvania
inspect_excel_csv("distributors/Pennsylvania/Tobacco_Products_Tax_Licenses_Current_Daily_County_Revenue_20260626.xlsx")

# Rhode Island
inspect_pdf("distributors/Rhode Island/Unified License List - May 27, 2026.pdf")
inspect_pdf("distributors/Rhode Island/Uniform_CTE_ DEALERSList_05152026.pdf")

# Washington
inspect_excel_csv("distributors/Washington/CIG_TOB_VAPE_021026.xlsx")

# Wisconsin
inspect_excel_csv("distributors/Wisconsin/TobLicList.csv")
