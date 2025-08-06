import pikepdf

def get_internal_metadata(pdf_path):
    """Extract internal metadata from PDF's /Info dictionary."""
    try:
        with pikepdf.open(pdf_path) as pdf:
            docinfo = pdf.docinfo
            metadata = {key.lstrip('/'): str(value) for key, value in docinfo.items()}
            print(f"Internal PDF Metadata for: {pdf_path}")
            print("-" * 50)
            for key, value in metadata.items():
                print(f"{key}: {value}")
            print("-" * 50)
            return metadata
    except Exception as e:
        print(f"Could not extract internal metadata: {e}")
        return {}

# Test with the current PDF
pdf_path = "/home/justus/Nextcloud/GHPL/docs/ZAF_D1_Hypertension_Guideline_December_2006.pdf"
get_internal_metadata(pdf_path)