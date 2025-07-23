VALUE_FORMATS = [
    # Standard decimal
    "0", "1", "10", "100", "999",
    "0.1", "1.0", "12.5", "100.0", "999.999",
    "0.001", "0.00001", "0.0000001",
    "3.1415", "2.718", "6.626", "8.314",

    # Negative values
    "-0.1", "-1.0", "-100.0", "-999.999",
    "-0.001", "-0.00001", "-3.1415", "-2.718",

    # Scientific notation (uppercase/lowercase E)
    "1e1", "1e+1", "1E1", "1E+1",
    "3.45e2", "-2.3e-4", "6.022e23", "9.81E-2",
    "1.0e+3", "-1.0e+3", "0e0", "-0e0",

    # Math expressions sometimes seen in unprocessed text
    "1^2", "10^3", "1+E20", "1×10^6", "2×10^5",
    "10^-3", "10⁻³", "10⁶", "10⁻⁶",  # Unicode superscripts
    "1·10⁻¹", "5·10⁻²", "6·10³",  # Dot notation

    # Complex expressions as seen in raw literature
    "(1.2 ± 0.1) × 10³", "1200 ± 100", "1.2(1) × 10³",
    "1.20e3 ± 0.10e3", "1.20e+03", "1.200e+03"

    # Natural and decimal numbers
                                   "0", "1", "10", "100", "0.001", "1.0", "1.23", "123.456", "0.0001", "9999.99",

    # Negative versions
    "-1", "-0.001", "-100.0", "-9999", "-3.1415",

    # Scientific notation (standard)
    "1e1", "1e+1", "1e+03", "6.022e23", "-1e2", "-2.5e-4", "3.5e+00",

    # LaTeX-style notation
    "10^3", "10^6", "10^-1", "10^{-2}", "1.5×10^5", "2.1×10^{-3}", "4.5·10^2", "7.89∙10⁻³",

    # Unicode superscript exponents
    "10⁻²", "1.23×10⁻³", "6.02×10²³", "5·10⁴", "8∙10⁻¹",

    # Fractional approximations
    "1/2", "3/4", "5/1000",  # symbolic values used as approximations sometimes

    # Edge representations
    "±0.05", "1.5±0.2", "<0.001", ">1000", "≈0.8", "~1.2", "≅0.9",

    # OCR or corrupted notations
    "1 . 23", "1 , 23", "10e+3", "1 x10^4", "1 x 10 ^ 4", "10 × 10³"
]
