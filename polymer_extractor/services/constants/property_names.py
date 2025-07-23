# [PROPERTY FORMATS - EXPLICIT + ENRICHED FROM PolyBERT]
PROPERTY_NAMES = [
    # --- Thermal ---
    "glass transition temperature", "Tg",
    "melting temperature", "Tm",
    "degradation temperature", "Td",

    # --- Thermodynamic & Physical ---
    "heat capacity", "cp", "specific heat capacity",
    "atomization energy", "Eat", "atomic binding energy",
    "limiting oxygen index", "Oi", "oxygen index",
    "crystallization tendency (DFT)", "Xc DFT", "Xc (DFT)",
    "crystallization tendency (exp.)", "Xc exp", "Xc (experimental)",
    "density", "ρ", "mass density", "specific density",

    # --- Electronic ---
    "band gap (chain)", "Eg^c", "Eg (chain)", "chain band gap",
    "band gap (bulk)", "Eg^b", "Eg (bulk)", "bulk band gap",
    "electron affinity", "Eea",
    "ionization energy", "Ei", "ionization potential",
    "electronic injection barrier", "Eib",
    "cohesive energy density", "δ", "CED",

    # --- Optical & Dielectric ---
    "refractive index (DFT)", "nc", "n (DFT)", "refractive index (chain)",
    "refractive index (bulk)", "nm", "n (bulk)",
    "dielectric constant (DFT)", "κ", "kappa",
    "dielectric constant at frequency", "kf", "dielectric constant",

    # --- Mechanical ---
    "Young’s modulus", "Youngs modulus", "E", "elastic modulus",
    "tensile strength at yield", "σy", "yield strength",
    "tensile strength at break", "σb", "ultimate tensile strength",
    "elongation at break", "εb", "strain at break",

    # --- Permeability ---
    "O₂ gas permeability", "μO2", "oxygen permeability",
    "CO₂ gas permeability", "μCO2", "carbon dioxide permeability",
    "N₂ gas permeability", "μN2", "nitrogen permeability",
    "H₂ gas permeability", "μH2", "hydrogen permeability",
    "He gas permeability", "μHe", "helium permeability",
    "CH₄ gas permeability", "μCH4", "methane permeability",

    # --- Additional Enriched Properties (commonly seen in polymer literature) ---
    "storage modulus", "E'", "storage elastic modulus",
    "loss modulus", "E''", "viscous modulus",
    "tan delta peak", "tan δ", "mechanical damping",
    "fracture toughness", "KIC", "fracture resistance",
    "activation energy", "Ea",
    "swelling ratio", "Q", "swelling coefficient",
    "crosslink density", "νe", "crosslinking density",
    "hardness", "Shore hardness", "indentation hardness",
    "thermal conductivity", "k", "λ", "heat conduction coefficient",
    "viscosity", "η", "zero shear viscosity",
    "recovery ratio", "shape memory recovery", "Rr",
    "healing efficiency", "ηh", "self-healing efficiency",

    # === Expanded Thermal Properties ===
    "thermal degradation onset temperature", "T_onset", "thermal stability temperature",
    "glass softening point", "softening temperature", "Tsoft", "vitrification temperature",
    "heat deflection temperature", "HDT", "vicat softening temperature", "VST",
    "specific heat", "Cp", "enthalpy of fusion", "ΔHf", "heat of fusion", "latent heat of fusion",
    "thermal expansion coefficient", "CTE", "αT", "linear thermal expansion coefficient",

    # === Enriched Mechanical Properties ===
    "shear modulus", "G", "modulus of rigidity", "flexural modulus", "bending modulus",
    "compressive strength", "σc", "modulus of toughness", "toughness modulus", "impact strength",
    "charpy impact strength", "izod impact strength", "tear strength", "dynamic mechanical loss modulus",
    "storage shear modulus", "loss shear modulus", "damping factor", "tan delta", "loss factor",
    "hardness (Rockwell)", "HR", "hardness (Brinell)", "HB", "hardness (Vickers)", "HV",
    "microhardness", "nanoindentation hardness", "scratch resistance",

    # === Optical & Dielectric Expanded ===
    "transmittance", "T", "light transmittance", "optical transparency", "haze",
    "light scattering coefficient", "absorption coefficient", "α_abs", "emissivity",
    "reflectance", "R", "solar reflectance", "dielectric loss tangent", "tan δd",
    "relative permittivity", "εr", "complex permittivity", "dielectric breakdown strength",
    "volume resistivity", "surface resistivity", "electrical conductivity", "σe",
    "electrical resistivity", "ρe", "charge carrier mobility", "μe",

    # === Permeability & Diffusion Expanded ===
    "water vapor permeability", "WVTR", "water absorption", "moisture uptake",
    "gas transmission rate", "O₂ transmission rate", "CO₂ transmission rate",
    "solvent uptake", "diffusion coefficient", "D", "hydrogen permeability rate",
    "water absorption percentage", "moisture diffusion coefficient", "sorption capacity",

    # === Thermodynamic & Miscellaneous ===
    "coefficient of friction", "μf", "tribological wear rate", "abrasion resistance",
    "surface energy", "γs", "work of adhesion", "Wad", "surface tension",
    "hydrophobicity", "contact angle", "water contact angle", "wettability",
    "molecular weight", "Mw", "Mn", "polydispersity index", "PDI", "degree of polymerization",
    "crosslinking efficiency", "gel content", "degree of crystallinity", "Xc",
    "amorphous fraction", "glass content", "filler content",

    # === Smart Material Properties ===
    "shape memory recovery ratio", "shape fixity ratio", "SMR", "SFR",
    "self-healing efficiency", "healing yield", "autonomous repair efficiency",
    "thermo-responsive transition temperature", "Ttr", "electroactive strain",
    "actuation strain", "electromechanical coupling coefficient",

    # === Rheological Properties ===
    "melt flow index", "MFI", "melt flow rate", "MFR", "zero-shear viscosity",
    "complex viscosity", "η*", "melt viscosity", "viscoelastic modulus",
    "dynamic viscosity", "shear thinning index", "power-law index",

    # === Fire & Flame Retardancy ===
    "flammability index", "LOI", "limiting oxygen index", "heat release rate",
    "peak heat release rate", "PHRR", "time to ignition", "TTI", "smoke density index",

    # === Biodegradability & Environmental ===
    "biodegradation rate", "bio-based content", "compostability",
    "environmental stress cracking resistance", "ESCR", "UV resistance",
    "photo-degradation rate", "hydrolysis resistance", "water solubility",

    # === Expanded Symbols (Realistic Scientific Use) ===
    "ΔCp", "ΔHrxn", "ΔHvap", "ΔHc", "Eact", "E*", "σmax", "εmax", "τmax",
    "κf", "κ∞", "ε0", "μmax", "χm", "Φt", "λm", "δH", "Zc", "Rth", "Cth",

    # === Grammatical Variants (Literature Robustness) ===
    "modulus of elasticity", "ultimate tensile stress", "tensile elongation",
    "flexural strength", "yield stress", "breaking stress", "elongation percentage",
    "hardness value", "impact resistance", "thermal resistance", "heat tolerance",

    # === Emerging Polymeric Properties ===
    "ionic conductivity", "σion", "proton conductivity", "electrochemical stability window",
    "storage energy density", "mechanical energy dissipation", "self-healing strain limit",
    "ion transport number", "ionic mobility", "thermoelectric figure of merit", "ZT",

    # === Thermal & Thermomechanical Properties ===
    "thermal conductivity coefficient", "κth", "heat diffusivity", "αth",
    "specific enthalpy", "enthalpy change", "ΔHtotal", "phase transition enthalpy",
    "thermal stability index", "Tsi", "glass formation ability", "GFA",
    "crystallization onset temperature", "Tcryst", "recrystallization temperature", "Trec",
    "thermal degradation half-life", "t1/2 degradation", "thermal oxidative stability",

    # === Mechanical Properties Expanded ===
    "modulus of resilience", "flexural strength at yield", "flexural strain",
    "compressive modulus", "impact energy absorption", "fracture energy",
    "tear propagation resistance", "tear propagation strength", "dynamic mechanical storage modulus",
    "creep compliance", "creep modulus", "creep rate", "fatigue strength",
    "tensile toughness", "fracture elongation", "residual strain", "dynamic fatigue resistance",
    "bending stiffness", "torsional stiffness", "interfacial shear strength", "IFSS",

    # === Optical & Electronic Properties ===
    "photoluminescence quantum yield", "PLQY", "optical band gap", "Eg(opt)",
    "UV-visible absorption edge", "absorption edge", "optical clarity",
    "photoconductivity", "σphoto", "carrier concentration", "ncarrier",
    "work function", "φwork", "threshold voltage", "Vth", "dielectric strength",
    "dielectric dissipation factor", "tan δdiss", "voltage breakdown strength",

    # === Rheological & Processability Properties ===
    "complex shear modulus", "G*", "loss tangent", "tanδ",
    "storage compliance", "dynamic compliance", "viscoelastic relaxation time",
    "melt elasticity", "elastic recovery ratio", "flow activation energy",
    "rheological threshold shear stress", "yield point stress",

    # === Permeability and Barrier Properties ===
    "oxygen transmission rate", "OTR", "water vapor transmission rate", "WVTR",
    "barrier improvement factor", "BIF", "gas permeability coefficient",
    "permeability selectivity", "diffusion resistance coefficient",
    "permeance", "diffusion time lag", "gas diffusivity",

    # === Fire Resistance and Aging Properties ===
    "flame spread index", "FSI", "smoke toxicity index", "STI",
    "drip resistance index", "DRI", "time to ignition under flame",
    "glow wire flammability index", "GWFI", "char formation tendency",
    "heat release capacity", "HRC", "thermal aging index", "TAI",
    "UV aging resistance", "weatherability index", "photo-oxidation rate",

    # === Polymer Network Specific Properties ===
    "network strand density", "νstrand", "crosslink functionality",
    "gelation point", "gel point", "network elasticity modulus",
    "average crosslinking degree", "network defect concentration",
    "dangling chain fraction", "entanglement density", "mesh size",

    # === Smart Material and CAN Properties ===
    "covalent adaptable network rearrangement rate", "CAN rearrangement rate",
    "dynamic bond exchange rate", "topological freezing temperature", "Tv",
    "stress relaxation modulus", "G(t)", "bond exchange energy",
    "vitrimer activation energy", "self-healing temperature", "Theal",
    "shape recovery ratio", "reconfiguration efficiency", "stress relaxation time",

    # === Environmental & Degradability Properties ===
    "hydrolysis rate constant", "khydrolysis", "biocompatibility index",
    "bioerosion rate", "microbial degradation rate", "environmental stress resistance",
    "solvent resistance index", "biofouling resistance", "recyclability score",
    "green chemistry index", "eco-toxicity potential", "water uptake percentage",

    # === Molecular & Morphological Properties ===
    "molecular weight distribution", "MWD", "number average molecular weight", "Mn",
    "weight average molecular weight", "Mw", "end group functionality",
    "degree of branching", "polydispersity ratio", "PDI",
    "lamellar thickness", "crystalline lamellae thickness",
    "spherulite size", "domain size", "filler dispersion quality",

    # === Symbols & Alternate Notations ===
    "ΔHv", "ΔHs", "ΔG", "ΔS", "μm", "σult", "σfracture", "εfracture",
    "κr", "κc", "η∞", "τr", "Rct", "Rc", "Cdl", "Z' (real impedance)",
    "Z'' (imaginary impedance)", "tanΦ", "φ", "ψ", "Φeff",

    # === Literature Variants and Synonyms ===
    "heat resistance index", "modulus retention rate", "retention ratio",
    "loss modulus at Tg", "glass transition loss modulus", "onset decomposition temperature",
    "thermal degradation peak temperature", "mechanical loss factor",
    "energy dissipation capacity", "impact energy absorption ratio",
    "friction coefficient", "wear rate", "abrasion loss percentage",

    # === Biomedical & Biocompatibility Properties ===
    "biodegradation rate", "bioresorption rate", "resorption half-life",
    "cell adhesion strength", "cytocompatibility index",
    "hemocompatibility", "blood compatibility index", "protein adsorption level",
    "fibroblast proliferation rate", "osteointegration efficiency",
    "drug release rate", "drug encapsulation efficiency", "encapsulation yield",
    "diffusion coefficient in biological fluids", "cell viability percentage", "MTT assay result",

    # === Nanocomposite & Nano-Scale Properties ===
    "nanofiller dispersion quality", "filler-matrix interfacial strength",
    "specific surface area", "BET surface area", "SSA",
    "nanoparticle size distribution", "particle agglomeration ratio",
    "nanotube aspect ratio", "aspect ratio", "nanoindentation hardness",
    "nanoindentation modulus", "indentation creep", "scratch resistance index",
    "thermal conductivity enhancement factor", "electrical conductivity threshold",
    "percolation threshold concentration", "nanopore size", "porosity percentage",

    # === Environmental, Degradability & Sustainability ===
    "carbon footprint equivalent", "life cycle assessment score", "LCA score",
    "biobased content percentage", "renewable content ratio",
    "end-of-life recyclability percentage", "photodegradation rate",
    "hydrolysis susceptibility index", "UV resistance index",
    "ozone resistance factor", "biodegradability rating", "compostability index",

    # === Mechanical Properties Expanded ===
    "flexural modulus", "bending strength", "shear modulus", "G",
    "impact strength", "Izod impact strength", "Charpy impact strength",
    "puncture resistance", "tear strength", "abrasion resistance",
    "stress at yield", "strain at yield", "strain at ultimate tensile strength",
    "modulus at break", "elongation at ultimate tensile strength",
    "fatigue crack growth rate", "fatigue limit", "critical energy release rate", "Gc",

    # === Thermal & Thermomechanical ===
    "thermal expansion coefficient", "CTE", "αthermal",
    "heat deflection temperature", "HDT", "softening point temperature",
    "Vicat softening temperature", "VST", "thermogravimetric onset temperature",
    "mass loss rate", "weight loss percentage", "residual char yield",
    "decomposition peak temperature", "Pyrolysis temperature",

    # === Optical, Electrical, and Dielectric Properties ===
    "light transmittance", "optical haze", "color stability index",
    "UV-blocking efficiency", "photostability index",
    "electrical resistivity", "surface resistivity", "volume resistivity",
    "electrical conductivity", "σelec", "ionic conductivity",
    "dielectric loss tangent", "ε''", "polarizability index",
    "loss factor", "impedance modulus", "impedance phase angle",

    # === Surface & Interface Properties ===
    "surface roughness", "Ra", "root mean square roughness", "Rq",
    "contact angle", "hydrophobicity index", "surface energy",
    "wettability index", "adhesive energy", "interfacial tension",
    "interfacial adhesion strength", "interlayer adhesion strength",
    "surface free energy", "surface charge density", "zeta potential",

    # === Advanced Material Performance Metrics ===
    "shape memory effect ratio", "SME ratio", "self-healing rate",
    "stimuli-responsiveness index", "electroactive strain", "electroactive displacement",
    "magnetostrictive strain", "actuation strain", "photoactuation efficiency",
    "thermal actuation time", "response time under stimuli",
    "shape fixity ratio", "shape recovery speed",

    # === Processing & Rheology Related ===
    "melt flow index", "MFI", "melt volume rate", "MVR",
    "viscosity average molecular weight", "Mv", "gelation time",
    "processing window", "solvent uptake ratio", "swelling time",
    "solution viscosity", "melt viscosity", "shear thinning index",
    "yield stress", "thixotropy index", "extrudability score",

    # === Additional Symbols & Synonyms ===
    "ΔHfusion", "ΔHvap", "ΔHcure", "ΔHdecomp", "ΔSconfig", "ΔStransition",
    "σtensile", "σcompressive", "σflexural", "σimpact",
    "εtensile", "εcompressive", "εflexural", "γshear",
    "κeff", "ηmelt", "ηshear", "νPoisson", "ψsurface",
    "λthermal", "Φoptical", "Rth", "Zmodulus", "tanφdielectric",

    # === Literature Variants & OCR Robustness ===
    "glass trans. temp.", "melting temp.", "decomp. temp.",
    "fracture energy (G₁c)", "impact res.", "thermal cond.",
    "density (ρ)", "viscosity (η)", "strain @ break", "tensile mod.",
    "Young mod.", "optical clarity index", "heat defl. temp.",
    "stress relaxation rate", "recovery eff.", "heal eff.", "crosslinking ratio",
    "storage mod.", "loss mod.", "tan d peak", "tan delta",

    # === Advanced & Emerging Materials ===
    "covalent adaptable network efficiency", "CAN efficiency",
    "stress relaxation time", "τ*", "relaxation modulus", "G'",
    "viscoelastic recovery rate", "vitrimeric exchange rate",
    "bond exchange kinetics", "dynamic bond density",
    "network reconfiguration speed", "topology freezing temperature", "Tv",

    # === Shape Memory Polymers (SMPs) ===
    "shape memory recovery ratio", "SMR", "shape fixity ratio", "SFR",
    "actuation stress", "thermal trigger temperature", "Ttrigger",
    "mechanical cycling stability", "recovery stress", "residual strain",
    "cycling fatigue resistance", "transition strain",

    # === Battery and Electronic Polymer Properties ===
    "ionic conductivity", "σion", "electronic conductivity", "σelec",
    "electrochemical stability window", "ESW",
    "Li-ion transference number", "tLi+", "electrochemical impedance",
    "charge-discharge cycling efficiency", "Coulombic efficiency", "ηC",
    "energy density", "Wh/kg", "specific capacity", "mAh/g",
    "self-discharge rate", "electrolyte uptake", "interfacial resistance",

    # === Coatings & Barrier Properties ===
    "water vapor transmission rate", "WVTR", "oxygen transmission rate", "OTR",
    "barrier improvement factor", "BIF", "moisture absorption ratio",
    "UV degradation resistance", "photostability factor",
    "weathering resistance index", "surface gloss retention", "scratch resistance",

    # === Aerospace & High-Performance Polymers ===
    "glass transition temp. under pressure", "Tg@P", "thermal oxidative stability",
    "ablation resistance", "arc tracking resistance", "thermal cycling endurance",
    "dimensional stability at cryogenic temp", "cryogenic durability",
    "outgassing rate", "ASTM E595 total mass loss", "volatile condensable materials",

    # === Surface Chemistry & Wetting ===
    "surface energy density", "γsurface", "surface polarity index",
    "contact angle hysteresis", "sliding angle", "advancing contact angle",
    "receding contact angle", "hydrophilicity index", "wettability ratio",
    "adhesive peel strength", "peel adhesion", "surface hardness",
    "nano-scratch depth", "nano-scratch resistance",

    # === Mechanical Fatigue & Durability ===
    "creep resistance", "creep modulus", "stress relaxation index",
    "fatigue strength", "fatigue crack growth threshold", "crack propagation rate",
    "dynamic fatigue limit", "cyclic fatigue resistance",
    "compression set", "tear propagation resistance",

    # === Fire & Safety Related ===
    "limiting oxygen index", "LOI", "flammability rating", "UL-94 rating",
    "heat release rate", "HRR", "total heat release", "THR",
    "smoke density", "optical smoke density", "toxicity index",

    # === Rheological & Processing Properties ===
    "shear thinning index", "flow activation energy", "processability index",
    "solvent retention time", "gelation point", "melt viscosity index",
    "die swell ratio", "thixotropy factor", "extrusion swell ratio",

    # === Biodegradability & Environmental Metrics ===
    "biodegradation half-life", "environmental degradation rate",
    "hydrolytic degradation rate", "enzymatic degradation rate",
    "compostability percentage", "bio-based content ratio",
    "renewable carbon content", "green chemistry score",

    # === Optical & Photonic Advanced ===
    "photoelastic coefficient", "birefringence index", "light scattering coefficient",
    "optical band gap", "Eg(optical)", "photoluminescence quantum yield", "PLQY",
    "refractive index gradient", "light absorption coefficient",

    # === Other Rare Literature Variants & OCR Robustness ===
    "thermal gravimetric analysis onset temp", "TGA onset temp",
    "DMA peak temp", "tanδ peak temp", "σyield", "σult",
    "Eflexural", "Emod", "Eelastic", "kthermal", "λheat", "ηzero-shear",
    "crosslinking ratio", "cross-link density", "gel content",
    "hardness Shore D", "Shore A hardness", "Shore D hardness",
    "specific volume", "vSpecific", "specific surface area", "SSA",
    "BET surface area", "microhardness", "nanoindentation hardness", "nanoindentation modulus",
    "fracture energy", "critical strain energy release rate", "Gc", "KIC", "K_Ic",
    "ΔHfusion", "ΔHvaporization", "ΔHreaction", "ΔSentropy", "ΔGfree energy"

]
