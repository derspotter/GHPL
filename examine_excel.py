import pandas as pd
import os

def examine_excel_structure(excel_path: str):
    """Examine the structure of the documents-info.xlsx file."""
    if not os.path.exists(excel_path):
        print(f"File not found: {excel_path}")
        return
    
    try:
        # Load the Excel file
        df = pd.read_excel(excel_path)
        
        print("=== Excel File Structure ===")
        print(f"File: {excel_path}")
        print(f"Shape: {df.shape} (rows: {df.shape[0]}, columns: {df.shape[1]})")
        print()
        
        print("=== Column Names ===")
        for i, col in enumerate(df.columns, 1):
            print(f"{i:2d}. {col}")
        print()
        
        print("=== Column Data Types ===")
        print(df.dtypes)
        print()
        
        print("=== First Few Rows ===")
        print(df.head())
        print()
        
        print("=== Sample Data for Key Columns ===")
        # Look for common metadata columns
        potential_cols = ['title', 'creator', 'year', 'doc_type', 'health_topic', 'country', 'filename', 'file', 'path']
        for col in df.columns:
            col_lower = col.lower()
            if any(key in col_lower for key in potential_cols):
                print(f"\n{col}:")
                print(f"  Unique values: {df[col].nunique()}")
                print(f"  Sample values: {df[col].dropna().head(3).tolist()}")
                if df[col].isnull().sum() > 0:
                    print(f"  Missing values: {df[col].isnull().sum()}")
        
        print("\n=== Missing Data Summary ===")
        missing_data = df.isnull().sum()
        if missing_data.sum() > 0:
            print(missing_data[missing_data > 0])
        else:
            print("No missing data found!")
            
    except Exception as e:
        print(f"Error reading Excel file: {e}")

# Examine the documents-info.xlsx file
excel_path = "/home/justus/Nextcloud/GHPL/documents-info.xlsx"
examine_excel_structure(excel_path)