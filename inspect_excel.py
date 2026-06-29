import pandas as pd

excel_path = "Tobacco License Verification by State.xlsx"
xls = pd.ExcelFile(excel_path)
print("Sheet names in workbook:", xls.sheet_names)

for sheet in xls.sheet_names:
    print(f"\n=========================================")
    print(f"SHEET: {sheet}")
    print(f"=========================================")
    df = pd.read_excel(excel_path, sheet_name=sheet)
    print(f"Shape: {df.shape}")
    print("Columns:", list(df.columns))
    print("\nFirst 10 rows:")
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    print(df.head(15))
