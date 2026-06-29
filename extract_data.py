import pandas as pd

excel_path = "Tobacco License Verification by State.xlsx"
df_state = pd.read_excel(excel_path, sheet_name="State Lookup")

df_filtered = df_state[df_state["License Availability"] == "License Number with Expiry"]

with open("extracted_data.txt", "w", encoding="utf-8") as f:
    f.write(f"Total rows with 'License Number with Expiry': {len(df_filtered)}\n")
    f.write("Columns in State Lookup:\n")
    f.write(str(list(df_state.columns)) + "\n\n")
    
    for idx, row in df_filtered.iterrows():
        f.write("============================================================\n")
        f.write(f"STATE: {row['State']}\n")
        f.write("============================================================\n")
        for col in df_state.columns:
            f.write(f"{col}: {row[col]}\n")
        f.write("\n")
        
    f.write("\n\n=========================================\n")
    f.write("SHEET: Automation Guide\n")
    f.write("=========================================\n")
    df_guide = pd.read_excel(excel_path, sheet_name="Automation Guide")
    for idx, row in df_guide.iterrows():
        f.write(f"Row {idx:02d} | Col 0: {row.iloc[0]} | Col 1: {row.iloc[1]}\n")
        
print("Wrote extracted data to extracted_data.txt")
