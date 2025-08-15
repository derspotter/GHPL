#!/usr/bin/env python3
"""
Convert CSV to Excel with proper formatting.
"""

import pandas as pd
import sys

def convert_csv_to_excel(csv_file, excel_file=None):
    """Convert CSV to Excel with proper data types preserved."""
    
    if excel_file is None:
        excel_file = csv_file.replace('.csv', '_python.xlsx')
    
    print(f"📖 Reading CSV: {csv_file}")
    
    # Read CSV with proper data types
    df = pd.read_csv(csv_file)
    
    # Ensure numeric columns are properly typed
    numeric_columns = ['overall_confidence', 'metadata_completeness', 
                      'question_1a_confidence', 'question_1b_confidence',
                      'processing_time_seconds', 'year']
    
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Convert boolean columns
    bool_columns = ['question_1a_health_policy', 'question_1b_ghpl_categories', 
                   'metadata_extracted', 'processed']
    
    for col in bool_columns:
        if col in df.columns:
            df[col] = df[col].map({'True': True, 'False': False, 
                                  True: True, False: False}).fillna(False)
    
    print(f"📊 Data shape: {df.shape[0]} rows, {df.shape[1]} columns")
    print(f"📈 Sample statistics:")
    
    if 'metadata_completeness' in df.columns:
        completeness = df['metadata_completeness'].dropna()
        if len(completeness) > 0:
            print(f"   Metadata completeness: min={completeness.min():.3f}, max={completeness.max():.3f}, mean={completeness.mean():.3f}")
    
    if 'overall_confidence' in df.columns:
        confidence = df['overall_confidence'].dropna()
        if len(confidence) > 0:
            print(f"   Overall confidence: min={confidence.min():.3f}, max={confidence.max():.3f}, mean={confidence.mean():.3f}")
    
    # Write to Excel with formatting
    print(f"💾 Writing Excel: {excel_file}")
    
    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Results', index=False, freeze_panes=(1, 1))
        
        # Get the workbook and worksheet
        workbook = writer.book
        worksheet = writer.sheets['Results']
        
        # Adjust column widths
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            
            for cell in column:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass
            
            # Set width with reasonable limits
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
        
        # Format percentage columns
        from openpyxl.styles import numbers
        
        for row in range(2, worksheet.max_row + 1):
            for col_name, col_idx in [('overall_confidence', None), ('metadata_completeness', None),
                                      ('question_1a_confidence', None), ('question_1b_confidence', None)]:
                if col_name in df.columns:
                    col_idx = df.columns.get_loc(col_name) + 1
                    cell = worksheet.cell(row=row, column=col_idx)
                    if cell.value is not None and isinstance(cell.value, (int, float)):
                        cell.number_format = '0.000'  # Three decimal places
    
    print(f"✅ Conversion complete!")
    
    # Verify the Excel file
    print(f"\n📋 Verifying Excel file...")
    df_check = pd.read_excel(excel_file)
    
    if 'metadata_completeness' in df_check.columns:
        sample = df_check[df_check['metadata_completeness'].notna()]['metadata_completeness'].head(5).tolist()
        print(f"   Sample completeness values: {sample}")
    
    if 'overall_confidence' in df_check.columns:
        sample = df_check[df_check['overall_confidence'].notna()]['overall_confidence'].head(5).tolist()
        print(f"   Sample confidence values: {sample}")
    
    return excel_file

if __name__ == "__main__":
    csv_file = sys.argv[1] if len(sys.argv) > 1 else 'meta_gpt5_results_20250810_190823_repaired.csv'
    excel_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    convert_csv_to_excel(csv_file, excel_file)