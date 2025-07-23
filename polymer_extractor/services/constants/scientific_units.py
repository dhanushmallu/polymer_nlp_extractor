SCIENTIFIC_UNITS = [
    # Temperature
    "K", "°C", "C", "deg C", "° C", "·C", "degC", "Kelvin", "°", "°C/min", "K/min",

    # Energy
    "kJ/mol", "J/mol", "kJ·mol⁻¹", "J·mol⁻¹", "kcal/mol", "cal/mol", "kcal·mol⁻¹", "cal·mol⁻¹",
    "eV", "eV/atom", "eV·atom⁻¹", "eV per atom",

    # Specific heat
    "J/g·K", "J/gK", "J·g⁻¹·K⁻¹", "J·g⁻¹K⁻¹", "cal/g·K", "cal·g⁻¹·K⁻¹", "J kg⁻¹ K⁻¹", "J/kg·K",

    # Modulus and strength
    "MPa", "GPa", "Pa", "kPa", "N/mm²", "N·mm⁻²", "kgf/cm²", "psi",

    # Density
    "g/cm³", "g·cm⁻³", "kg/m³", "mg/cm³", "g/ml", "g·mL⁻¹", "kg/L",

    # Time and rate
    "s", "min", "h", "hr", "ms", "μs", "s⁻¹", "Hz", "kHz", "MHz", "rad/s",

    # Permeability and diffusion
    "barrer", "mol·m⁻¹·s⁻¹·Pa⁻¹", "cm³(STP)·cm/cm²·s·Pa", "cm²/s", "m²/s", "mol·s⁻¹·m⁻¹·Pa⁻¹",

    # Concentration and molarity
    "mol/L", "mol·L⁻¹", "mmol/L", "M", "mM", "mol/m³", "mol·dm⁻³",

    # Optical and dielectric
    "RI", "nD", "no unit", "unitless", "",  # for refractive index etc.

    # Pressure and force
    "atm", "bar", "Pa", "kPa", "mbar", "torr", "mmHg", "psi", "N", "N/m", "N·m",

    # Thermal conductivity
    "W/m·K", "W·m⁻¹·K⁻¹", "W/mK", "W·K⁻¹·m⁻¹",

    # Toughness / Fracture
    "J/m²", "kJ/m²", "MPa·m½", "MPa·m^0.5", "MPa·√m", "MPa√m", "N·m", "N·m⁻¹",

    # Others
    "%", "wt%", "mol%", "vol%", "ppm", "ppb", "mg/L", "μg/mL", "ng/g", "g/mol", "Da", "kDa",

    # === Temperature ===
    "K", "°C", "° C", "deg C", "°", "℃", "degC", "Kelvin", "K/min", "°C/min",
    "C", "Celsius", "Δ°C", "ΔK", "°C/s", "K/s", "° C/min", "°C hr⁻¹", "K hr⁻¹",
    "\u00B0C", "\u2103", "deg·C", "deg-C", "°C\u2215min", "°C/hr",

    # === Energy ===
    "kJ/mol", "J/mol", "kcal/mol", "cal/mol", "kJ·mol⁻¹", "J·mol⁻¹", "kcal·mol⁻¹",
    "cal·mol⁻¹", "eV", "eV/atom", "eV·atom⁻¹", "eV per atom", "J/kg", "MJ/kg",
    "kJ g⁻¹", "J g⁻¹", "eV/molecule", "meV", "keV", "MeV", "eV·Å⁻¹",

    # === Specific heat & Thermal ===
    "J/g·K", "J/gK", "J·g⁻¹·K⁻¹", "J·g⁻¹K⁻¹", "cal/g·K", "cal·g⁻¹·K⁻¹",
    "J kg⁻¹ K⁻¹", "J/kg·K", "mJ/m²·K", "W/m²K", "W·m⁻²·K⁻¹", "BTU/lb·°F",
    "J/kg K", "W/cm·K", "kW/m·K", "J/mol·K", "cal/mol·K", "kcal/mol·K",

    # === Modulus & Strength ===
    "MPa", "GPa", "Pa", "kPa", "N/mm²", "N·mm⁻²", "kgf/cm²", "psi",
    "lbf/in²", "ksi", "N/m²", "MN/m²", "bar", "dyne/cm²",
    "MPa·m½", "MPa√m", "N/m²", "kg/cm²", "kg/mm²", "lb/in²",

    # === Density ===
    "g/cm³", "g·cm⁻³", "kg/m³", "mg/cm³", "g/ml", "g·mL⁻¹", "kg/L",
    "g/cm^3", "g cm⁻³", "g/cm3", "kg·m⁻³", "mg/L", "g/L", "mg/m³",

    # === Time & Rate ===
    "s", "min", "h", "hr", "ms", "μs", "ns", "ps", "fs", "s⁻¹", "Hz",
    "kHz", "MHz", "GHz", "rad/s", "rpm", "cycles/min", "rpm·min⁻¹",

    # === Permeability & Diffusion ===
    "barrer", "mol·m⁻¹·s⁻¹·Pa⁻¹", "cm³(STP)·cm/cm²·s·Pa",
    "mol·s⁻¹·m⁻¹·Pa⁻¹", "cm²/s", "m²/s", "D", "cm³(STP)/cm²·s·atm",
    "mol/(m·s·Pa)", "cm³(STP)/(cm²·s·Pa)", "mol/m²·s·Pa",

    # === Concentration & Molarity ===
    "mol/L", "mol·L⁻¹", "mmol/L", "M", "mM", "mol/m³", "mol·dm⁻³",
    "mol/kg", "mol%", "mol fraction", "wt%", "vol%", "ppm", "ppb",
    "mg/L", "μg/mL", "ng/g", "mg/kg", "mg/dL", "mmol/kg",

    # === Optical & Dielectric ===
    "RI", "nD", "unitless", "no unit", "F/m", "S/m", "Ω·cm",
    "Ω·m", "F/cm", "μF/cm²", "pF/m", "H/m", "S·m⁻¹",

    # === Pressure & Force ===
    "atm", "bar", "mbar", "torr", "mmHg", "psi", "N", "N/m", "N·m",
    "dyne/cm", "kgf", "lbf", "kg·m/s²", "pN", "μN", "kN", "MN",

    # === Thermal Conductivity ===
    "W/m·K", "W·m⁻¹·K⁻¹", "W/mK", "kW/mK", "BTU/hr·ft·°F",
    "cal/s·cm·K", "erg/s·cm·K", "mW/mK", "mW·cm⁻¹·K⁻¹",

    # === Toughness / Fracture ===
    "J/m²", "kJ/m²", "MJ/m²", "MPa·m½", "MPa√m", "kJ/m³", "N·m",
    "N·m⁻¹", "kN·m", "ft-lb", "in-lb",

    # === Miscellaneous ===
    "%", "wt%", "mol%", "vol%", "ppm", "ppb", "g/mol", "kg/mol", "amu",
    "Da", "kDa", "MDa", "g/mol", "mol wt", "MW", "Mw", "Mn", "PDI",

    # === OCR Edge Cases & Unicode ===
    "\u00B0C", "\u2103", "\u2212", "\u2022C", "\u00B0 C", "\u33A1",
    "m\u00B2", "cm\u00B2", "\u2126·cm", "µm", "μm", "uM", "µL", "μL",
    "°C/min", "°C s⁻¹", "mol·dm−³", "mol dm⁻³", "g cm⁻³", "kg m⁻³",
    "Å", "nm", "μs", "μg", "μmol", "uM", "μΩ·m",

    # === Temperature Variants ===
    "°K", "degK", "Kelvins", "K/sec", "°C/sec", "deg·K", "K/s", "°C/s",
    "u+00B0C", "u00B0C", "u2103", "u2022C", "°C·min⁻¹", "K·min⁻¹", "°C/h", "K/h",
    "°F", "degF", "Fahrenheit", "°F/min", "°F/s",

    # === Energy Variants ===
    "kJ kg⁻¹", "J/kg·K", "mJ/cm³", "μJ/mm³", "MJ/m³", "cal/cm³", "BTU/lb",
    "kcal kg⁻¹", "kcal/m³", "J·mol⁻¹·K⁻¹", "kcal/mol·K", "mWh/g", "Wh/kg",

    # === Specific Heat & Thermal ===
    "mW/cm·K", "mW·cm⁻¹·K⁻¹", "kW/mK", "BTU·hr⁻¹·ft⁻¹·°F⁻¹", "cal/s·cm·K",
    "erg/s·cm·K", "mJ/m²·K", "kW/cm·K", "J/m²·K", "J/kg K", "J/kg·K",
    "mcal/cm³·K", "kcal/kg·K", "cal/g°C",

    # === Mechanical Units ===
    "GPa·m½", "kN/m", "kN·m⁻¹", "N·mm", "N/mm", "kgf/mm²", "lb/in²",
    "ksi", "Mpsi", "Pa·s", "kPa·s", "MPa·s", "cP", "P", "N·m²", "dyn/cm²",

    # === Density Variants ===
    "kg/m³", "kg·m⁻³", "mg/L", "mg/ml", "g/L", "μg/m³", "mg/cm³",
    "mg/mm³", "g/dm³", "mg/dL", "kg/mL", "mg/L", "ug/L", "μg/L",
    "g·L⁻¹", "g/L", "g cm⁻³", "g/cm³", "u+33A1", "u+33A0",

    # === Time & Rate Variants ===
    "sec", "min⁻¹", "h⁻¹", "s⁻¹", "rpm", "cycles/min", "cycles/s",
    "rev/s", "rps", "r/min", "r·min⁻¹", "Hz", "kHz", "MHz", "GHz", "THz",
    "fs", "ps", "ns", "μs", "μs⁻¹", "ms⁻¹", "s⁻²",

    # === Permeability & Diffusion ===
    "mol/(m²·s·Pa)", "mol/m²·s·Pa", "cm³(STP)/cm²·s·atm",
    "mol/m²·Pa·s", "barrer", "perm", "mol/(m·s·Pa)", "mol·s⁻¹·m⁻¹·Pa⁻¹",
    "cm²/s", "m²/s", "cm³(STP)·cm/cm²·s·Pa", "mol/(m²·s·bar)",

    # === Concentration Variants ===
    "wt.%", "vol.%", "mol.%", "ppm", "ppb", "ppt", "mg/L", "mg/ml",
    "μg/mL", "ng/mL", "pg/mL", "mol/kg", "mol/dm³", "M", "mM", "μM",
    "nM", "pM", "fM", "mol fraction", "parts per million", "parts per billion",

    # === Optical & Dielectric ===
    "ε₀", "ε_r", "μ₀", "μ_r", "F/m", "H/m", "S/m", "S·m⁻¹", "Ω·m",
    "Ω·cm", "ohm·cm", "ohm·m", "μF/cm²", "pF/m", "C/V·m", "F/cm",

    # === Pressure & Force Variants ===
    "atm", "bar", "Pa", "kPa", "MPa", "GPa", "Torr", "mmHg",
    "psi", "lbf/in²", "dyn/cm²", "kgf/cm²", "kgf/m²", "pN", "μN", "nN",
    "kN", "MN", "GN", "mN", "N·m", "lbf·ft", "lbf·in",

    # === Thermal Conductivity Variants ===
    "W/mK", "W·m⁻¹·K⁻¹", "mW/cmK", "kW/mK", "BTU/hr·ft·°F", "cal/s·cm·K",
    "erg/s·cm·K", "W/cm·K", "W/mm·K", "W·mm⁻¹·K⁻¹",

    # === Toughness / Fracture Variants ===
    "J/m³", "kJ/m³", "MJ/m³", "MPa·m½", "MPa√m", "kJ/m³", "N·m", "N·m⁻¹",
    "kN·m", "lbf·ft", "lbf·in", "ft-lb", "in-lb", "J·cm⁻³", "kJ/cm³",

    # === Miscellaneous ===
    "mol wt", "MW", "Mw", "Mn", "PDI", "Rr", "ηh", "η", "νe", "Q", "KIC",
    "Shore A", "Shore D", "Rockwell", "Brinell", "Vickers", "durometer",

    # === OCR / Unicode ===
    "\u00B0C", "\u00B0F", "\u2103", "\u2109", "\u2022C", "\u2212", "\u00B7",
    "°C·min⁻¹", "°C/min", "mol·dm−³", "mol dm⁻³", "g·cm⁻³", "kg·m⁻³",
    "Å", "nm", "µm", "μm", "pm", "fm", "nm³", "Å³", "µL", "μL", "uL",

    # === Temperature Expanded ===
    "u+00B0K", "u+2103", "u+2109", "degK", "degF", "Kelvin", "Fahrenheit",
    "°C per min", "°C per hour", "K per s", "K·h⁻¹", "°C/h", "K/h",
    "°F/s", "°F/min", "Δ°C", "ΔK", "u2022C", "u2022K", "u2022F",

    # === Energy & Power ===
    "kWh/kg", "Wh/g", "kJ/cm³", "J/mm³", "μJ/μL", "eV/molecule",
    "meV/atom", "kcal/cm³", "erg/cm³", "mcal/m³", "kJ/kg·K", "mWh/cm³",
    "BTU/hr", "BTU/s", "ft-lb", "in-lb", "u00B7kJ", "u00B7J",

    # === Specific Heat / Thermal ===
    "cal·mol⁻¹·K⁻¹", "J mol⁻¹ K⁻¹", "kcal/mol·K", "W/m²·K", "W·m⁻²·K⁻¹",
    "cal/cm²·s·K", "kW/m²·K", "mW/mm·K", "μW/cm²·K", "pW/nm·K",

    # === Mechanical Units ===
    "kN/mm²", "MN/m²", "N·mm²", "kgf/m²", "lbf/in²", "ksi", "Mpsi",
    "GPa·m^0.5", "MPa√m", "Pa·s", "kPa·s", "MPa·s", "cP", "P",
    "dyn·cm⁻²", "kg·m⁻²", "lbf·ft", "u+33A0", "u+33A1", "kgf/mm²",

    # === Density Variants ===
    "g/cm³", "kg/m³", "mg/dm³", "mg/cc", "μg/L", "pg/mL", "g/cc",
    "mg/mL", "g/L", "mol/L", "mmol/L", "μmol/L", "mol/m³", "mol·dm⁻³",
    "u+33A0", "u+33A1", "g·mL⁻¹", "kg/L", "kg/mL", "mg/dL",

    # === Time & Rate Variants ===
    "femtoseconds", "picoseconds", "nanoseconds", "microseconds",
    "ms", "s", "sec", "min", "h", "hr", "days", "cycles/sec",
    "Hz", "kHz", "MHz", "GHz", "rpm", "rps", "r/min", "rad/s",
    "deg/s", "°/s", "rev/s", "u+2212Hz", "u+2212s",

    # === Permeability & Diffusion ===
    "barrer", "mol/m²·s·Pa", "mol/m·s·Pa", "cm³(STP)/cm²·s·atm",
    "mol/(m²·s·bar)", "perm", "permeability units", "mol/m²·s·atm",
    "g/m²·day", "g/(m²·day)", "cm²/s", "m²/s", "μm²/s",

    # === Concentration / Molarity ===
    "% w/v", "% v/v", "wt%", "vol%", "mol%", "ppm", "ppb", "ppt",
    "mol/kg", "mmol/kg", "mol fraction", "parts per million",
    "mg/L", "mg/ml", "μg/mL", "ng/mL", "pg/mL", "M", "mM", "μM",
    "nM", "pM", "fM", "p.p.m", "pphm", "pptr",

    # === Optical & Dielectric ===
    "RI", "nD", "no unit", "unitless", "", "F/m", "H/m",
    "S/m", "S·m⁻¹", "Ω·m", "Ω·cm", "ohm·cm", "ohm·m",
    "μF/cm²", "pF/m", "C/V·m", "F/cm", "S·cm⁻¹", "mS/cm",

    # === Pressure & Force Variants ===
    "atm", "bar", "Pa", "kPa", "MPa", "GPa", "Torr", "mmHg",
    "psi", "lbf/in²", "dyn/cm²", "kgf/cm²", "kgf/m²", "N",
    "kN", "MN", "GN", "mN", "pN", "μN", "nN", "u00B7Pa", "u00B7bar",

    # === Thermal Conductivity ===
    "W/mK", "W·m⁻¹·K⁻¹", "mW/cmK", "kW/mK", "cal/s·cm·K",
    "BTU/hr·ft·°F", "erg/s·cm·K", "W/cm·K", "W/mm·K",

    # === Toughness / Fracture ===
    "J/m²", "kJ/m²", "MJ/m²", "J/m³", "kJ/m³", "MJ/m³",
    "MPa·m½", "MPa√m", "N·m", "N·m⁻¹", "kN·m", "lbf·ft", "lbf·in",

    # === Miscellaneous ===
    "mol wt", "MW", "Mw", "Mn", "PDI", "Shore A", "Shore D",
    "Rockwell", "Brinell", "Vickers", "durometer", "g/mol", "Da", "kDa",

    # === OCR & Unicode Defensive ===
    "\u00B0C", "\u00B0F", "\u2103", "\u2109", "\u2022C", "\u2022K",
    "\u2212K", "\u2212°C", "\u00B7K", "\u00B7°C", "\u03BCm", "\u00B5m",
    "\u006BPa", "\u006DKPa", "\u006DGPa", "\u03A9·cm", "\u2126·cm",
    "u+00B0C", "u+00B0K", "u+03BCg", "u+03BCL", "u+00B7mol", "u+2212mol"
]
