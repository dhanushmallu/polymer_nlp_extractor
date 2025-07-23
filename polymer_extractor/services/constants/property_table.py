
PROPERTY_TABLE = [
    # --- Thermal ---
    {"property": "Glass transition temp.", "symbol": "Tg", "unit": "K", "source": "Exp.",
     "data_range": "[8e+01, 9e+02]", "HP": 5183, "CP": 3312, "All": 8495},
    {"property": "Melting temp.", "symbol": "Tm", "unit": "K", "source": "Exp.", "data_range": "[2e+02, 9e+02]",
     "HP": 2132, "CP": 1523, "All": 3655},
    {"property": "Degradation temp.", "symbol": "Td", "unit": "K", "source": "Exp.", "data_range": "[3e+02, 1e+03]",
     "HP": 3584, "CP": 1064, "All": 4648},

    # --- Thermodynamic & Physical ---
    {"property": "Heat capacity", "symbol": "cp", "unit": "Jg⁻¹K⁻¹", "source": "Exp.", "data_range": "[8e−01, 2e+00]",
     "HP": 79, "CP": None, "All": 79},
    {"property": "Atomization energy", "symbol": "Eat", "unit": "eV atom⁻¹", "source": "DFT",
     "data_range": "[−7.4e+00, 5e+00]", "HP": 390, "CP": None, "All": 390},
    {"property": "Limiting oxygen index", "symbol": "Oi", "unit": "%", "source": "Exp.", "data_range": "[1e+01, 7e+01]",
     "HP": 101, "CP": None, "All": 101},
    {"property": "Crystallization tendency (DFT)", "symbol": "Xc (DFT)", "unit": "%", "source": "DFT",
     "data_range": "[1e–01, 1e+02]", "HP": 432, "CP": None, "All": 432},
    {"property": "Crystallization tendency (exp.)", "symbol": "Xc (Exp.)", "unit": "%", "source": "Exp.",
     "data_range": "[1e+00, 1e+02]", "HP": 111, "CP": None, "All": 111},
    {"property": "Density", "symbol": "ρ", "unit": "g cm⁻³", "source": "Exp.", "data_range": "[8e–01, 2e+00]",
     "HP": 910, "CP": None, "All": 910},

    # --- Electronic ---
    {"property": "Band gap (chain)", "symbol": "Eg^c", "unit": "eV", "source": "DFT", "data_range": "[2e–02, 1e+01]",
     "HP": 4224, "CP": None, "All": 4224},
    {"property": "Band gap (bulk)", "symbol": "Eg^b", "unit": "eV", "source": "DFT", "data_range": "[4e–01, 1e+01]",
     "HP": 597, "CP": None, "All": 597},
    {"property": "Electron affinity", "symbol": "Eea", "unit": "eV", "source": "DFT", "data_range": "[4e–01, 5e+00]",
     "HP": 368, "CP": None, "All": 368},
    {"property": "Ionization energy", "symbol": "Ei", "unit": "eV", "source": "DFT", "data_range": "[4e–00, 1e+01]",
     "HP": 370, "CP": None, "All": 370},
    {"property": "Electronic injection barrier", "symbol": "Eib", "unit": "eV", "source": "DFT",
     "data_range": "[2e–00, 7e+00]", "HP": 2610, "CP": None, "All": 2610},
    {"property": "Cohesive energy density", "symbol": "δ", "unit": "cal cm⁻³", "source": "Exp.",
     "data_range": "[2e+01, 3e+02]", "HP": 294, "CP": None, "All": 294},

    # --- Optical & Dielectric ---
    {"property": "Refractive index (DFT)", "symbol": "nc", "unit": None, "source": "DFT",
     "data_range": "[1e+00, 3e+00]", "HP": 382, "CP": None, "All": 382},
    {"property": "Refractive index (bulk)", "symbol": "nm", "unit": None, "source": "Exp.",
     "data_range": "[1e+00, 2e+00]", "HP": 516, "CP": None, "All": 516},
    {"property": "Dielectric constant (DFT)", "symbol": "κ", "unit": None, "source": "DFT",
     "data_range": "[3e+00, 3e+00]", "HP": 382, "CP": None, "All": 382},
    {"property": "Dielectric constant at freq. f", "symbol": "kf", "unit": None, "source": "Exp.",
     "data_range": "[2e+00, 1e+01]", "HP": 1187, "CP": None, "All": 1187},

    # --- Mechanical ---
    {"property": "Young’s modulus", "symbol": "E", "unit": "MPa", "source": "Exp.", "data_range": "[2e+02, 4e+03]",
     "HP": 592, "CP": 322, "All": 914},
    {"property": "Tensile strength at yield", "symbol": "σy", "unit": "MPa", "source": "Exp.",
     "data_range": "[3e–01, 1e+02]", "HP": 216, "CP": 78, "All": 294},
    {"property": "Tensile strength at break", "symbol": "σb", "unit": "MPa", "source": "Exp.",
     "data_range": "[5e–02, 2e+02]", "HP": 663, "CP": 318, "All": 981},
    {"property": "Elongation at break", "symbol": "εb", "unit": "%", "source": "Exp.", "data_range": "[3e–01, 1e+03]",
     "HP": 868, "CP": 260, "All": 1128},

    # --- Permeability ---
    {"property": "O₂ gas permeability", "symbol": "μO2", "unit": "barrer", "source": "Exp.",
     "data_range": "[5e–06, 1e+03]", "HP": 390, "CP": 210, "All": 600},
    {"property": "CO₂ gas permeability", "symbol": "μCO2", "unit": "barrer", "source": "Exp.",
     "data_range": "[1e–06, 5e+03]", "HP": 286, "CP": 119, "All": 405},
    {"property": "N₂ gas permeability", "symbol": "μN2", "unit": "barrer", "source": "Exp.",
     "data_range": "[3e–05, 5e+02]", "HP": 394, "CP": 99, "All": 493},
    {"property": "H₂ gas permeability", "symbol": "μH2", "unit": "barrer", "source": "Exp.",
     "data_range": "[2e–02, 5e+03]", "HP": 240, "CP": 46, "All": 286},
    {"property": "He gas permeability", "symbol": "μHe", "unit": "barrer", "source": "Exp.",
     "data_range": "[5e–02, 2e+03]", "HP": 239, "CP": 58, "All": 297},
    {"property": "CH₄ gas permeability", "symbol": "μCH4", "unit": "barrer", "source": "Exp.",
     "data_range": "[4e–04, 2e+03]", "HP": 331, "CP": 47, "All": 378}
]
