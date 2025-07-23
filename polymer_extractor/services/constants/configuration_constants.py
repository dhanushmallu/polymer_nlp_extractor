# Processing patterns
MEASUREMENT_PATTERNS = [
    r"(\d+\.?\d*)\s*([°]?[CFK])",  # Temperature
    r"(\d+\.?\d*)\s*(MPa|GPa|Pa)",  # Pressure/Modulus
    r"(\d+\.?\d*)\s*(g/mol|kg/mol)",  # Molecular weight
    r"(\d+\.?\d*)\s*([%])",  # Percentage
]

# Export formats
EXPORT_FORMATS = {
    "json": {
        "extension": ".json",
        "mime_type": "application/json"
    },
    "csv": {
        "extension": ".csv",
        "mime_type": "text/csv"
    },
    "xlsx": {
        "extension": ".xlsx",
        "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    },
    "xml": {
        "extension": ".xml",
        "mime_type": "application/xml"
    },
    "txt": {
        "extension": ".txt",
        "mime_type": "text/plain"
    }
}

# Entity types - now includes MATERIAL
ENTITY_TYPES = ["polymer", "property", "value", "unit", "symbol", "material"]

SCIENTIFIC_SECTIONS = [
    # all possible ways of naming abstract
    "abstract", "summary", "overview", "introduction", "background", "context",

    # all possible ways of naming introduction
    "introduction", "intro", "background", "context", "motivation", "purpose",

    # all possible ways of naming methods
    "methods", "methodology", "experimental", "approach", "procedure", "technique",

    # all possible ways of naming results
    "results", "findings", "outcomes", "data", "analysis", "observations",

    # all possible ways of naming discussion
    "discussion", "analysis", "interpretation", "conclusion", "implications",

    # all possible ways of naming conclusion
    "conclusion", "conclusions", "summary", "final thoughts", "closing remarks"
]

CONTENT_MARKERS = [
    # common content markers
    "introduction", "methods", "results", "discussion", "conclusion",

    # common section markers
    "section", "subsection", "part", "chapter", "paragraph",

    # common formatting markers
    "bold", "italic", "underline", "highlight", "code", "quote",

    # common list markers
    "bullet", "numbered", "unordered", "ordered"
]
