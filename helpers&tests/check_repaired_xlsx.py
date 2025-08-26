#!/usr/bin/env python3
"""
Check if the same field issues exist in the repaired Excel file.
"""

import pandas as pd
import os

def check_repaired_xlsx():
    excel_file = "/home/jay/GHPL/meta_gpt5_results_20250810_190823_repaired.xlsx"
    csv_file = "/home/jay/GHPL/meta_gpt5_results_20250825_170822.csv"
    
    print("🔍 COMPARING FIELD POPULATION BETWEEN FILES")
    print("=" * 60)
    
    # Check if Excel file exists
    if not os.path.exists(excel_file):
        print(f"❌ Excel file not found: {excel_file}")
        return
    
    try:
        # Read Excel file
        df_excel = pd.read_excel(excel_file)
        print(f"📊 Excel file: {len(df_excel)} rows")
        
        # Read CSV file for comparison
        df_csv = pd.read_csv(csv_file)
        print(f"📊 CSV file: {len(df_csv)} rows")
        print()
        
        # Check if Excel has the same columns
        excel_cols = set(df_excel.columns)
        csv_cols = set(df_csv.columns)
        
        print("📋 COLUMN COMPARISON")
        print("-" * 30)
        common_cols = excel_cols & csv_cols
        excel_only = excel_cols - csv_cols
        csv_only = csv_cols - excel_cols
        
        print(f"Common columns: {len(common_cols)}")
        print(f"Excel only: {list(excel_only)}")
        print(f"CSV only: {list(csv_only)}")
        print()
        
        # Focus on documents with metadata extracted
        excel_extracted = df_excel[df_excel['metadata_extracted'] == True] if 'metadata_extracted' in df_excel.columns else pd.DataFrame()
        csv_extracted = df_csv[df_csv['metadata_extracted'] == True] if 'metadata_extracted' in df_csv.columns else pd.DataFrame()
        
        print("📈 METADATA EXTRACTION COMPARISON")
        print("-" * 40)
        print(f"Excel extracted docs: {len(excel_extracted)}")
        print(f"CSV extracted docs: {len(csv_extracted)}")
        print()
        
        # Check field population in both files
        fields_to_check = ['doc_type', 'health_topic', 'creator', 'governance_level']
        
        print("🔍 FIELD POPULATION ANALYSIS")
        print("=" * 60)
        print(f"{'Field':<15} | {'Excel':<15} | {'CSV':<15} | {'Status'}")
        print("-" * 60)
        
        for field in fields_to_check:
            # Excel stats
            if field in excel_cols and len(excel_extracted) > 0:
                excel_non_empty = excel_extracted[field].notna() & (excel_extracted[field] != '') & (excel_extracted[field] != 'None')
                excel_filled = excel_non_empty.sum()
                excel_pct = (excel_filled / len(excel_extracted)) * 100
                excel_stat = f"{excel_filled}/{len(excel_extracted)} ({excel_pct:.1f}%)"
            else:
                excel_stat = "N/A"
            
            # CSV stats
            if field in csv_cols and len(csv_extracted) > 0:
                csv_non_empty = csv_extracted[field].notna() & (csv_extracted[field] != '') & (csv_extracted[field] != 'None')
                csv_filled = csv_non_empty.sum()
                csv_pct = (csv_filled / len(csv_extracted)) * 100
                csv_stat = f"{csv_filled}/{len(csv_extracted)} ({csv_pct:.1f}%)"
            else:
                csv_stat = "N/A"
            
            # Status
            if excel_stat != "N/A" and csv_stat != "N/A":
                if "0/" in excel_stat and "0/" in csv_stat:
                    status = "❌ Both Empty"
                elif "0/" in csv_stat and "0/" not in excel_stat:
                    status = "🔴 CSV Broken"
                elif "0/" in excel_stat and "0/" not in csv_stat:
                    status = "🔴 Excel Broken"
                else:
                    status = "✅ Both Work"
            else:
                status = "⚠️ Missing"
            
            print(f"{field:<15} | {excel_stat:<15} | {csv_stat:<15} | {status}")
        
        print()
        
        # Show sample data from Excel if it has better field population
        if len(excel_extracted) > 0:
            print("📄 SAMPLE EXCEL DATA (First 3 extracted docs)")
            print("=" * 60)
            for i, (idx, row) in enumerate(excel_extracted.head(3).iterrows()):
                filename = row.get('filename', 'Unknown')
                print(f"\n{i+1}. {filename}")
                for field in fields_to_check:
                    if field in row:
                        value = row[field]
                        if pd.isna(value) or value == '' or value == 'None':
                            print(f"   {field:<15}: [EMPTY]")
                        else:
                            print(f"   {field:<15}: {value}")
        
    except Exception as e:
        print(f"❌ Error reading Excel file: {e}")

if __name__ == "__main__":
    check_repaired_xlsx()