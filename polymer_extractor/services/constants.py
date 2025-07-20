"""
Constants including templates, lexicons, and other static data.
"""

# Canonical mappings
CANONICAL_POLYMERS = {
    "Teflon": "PTFE",
    "Lexan": "PC",
    "Polyethylene Terephthalate": "PET",
    "Poly(ethylene terephthalate)": "PET",
    "Polycarbonate": "PC",
    "Polytetrafluoroethylene": "PTFE",
    "Polystyrene": "PS",
    "Poly(methyl methacrylate)": "PMMA",
    "Polymethyl methacrylate": "PMMA",
    "Teflon": "PTFE",
    "Polytetrafluoroethylene": "PTFE",
    "Lexan": "PC",
    "Polycarbonate": "PC",
    "Plexiglas": "PMMA",
    "Polymethyl methacrylate": "PMMA",
    "Mylar": "PET",
    "Polyethylene terephthalate": "PET",
    "Polyethylene glycol": "PEG",
    "Polyvinyl chloride": "PVC",
    "Polystyrene": "PS",
    "Polyurethane": "PU"
}

CANONICAL_PROPERTIES = {
    "modulus of elasticity": "Young's modulus",
    "glass temp": "glass transition temperature",
    "Tg": "glass transition temperature",
    "glass transition temp": "glass transition temperature",
    "tensile strength": "ultimate tensile strength",
    "yield strength": "yield stress",
    "modulus of elasticity": "Young's modulus",
    "elastic modulus": "Young's modulus",
    "melting point": "Tm",
    "melting temperature": "Tm",
    "glass transition temperature": "Tg",
    "glass transition": "Tg",
    "tensile strength": "tensile strength",
    "yield strength": "yield strength",
    "thermal conductivity": "thermal conductivity",
    "electrical conductivity": "electrical conductivity"
}

# [GREEK LETTERS - FULL SET]
GREEK_LETTERS = {
    "lowercase": [
        "α", "β", "γ", "δ", "ε", "ζ", "η", "θ", "ι", "κ", "λ",
        "μ", "ν", "ξ", "ο", "π", "ρ", "σ", "τ", "υ", "φ", "χ", "ψ", "ω"
    ],
    "uppercase": [
        "Α", "Β", "Γ", "Δ", "Ε", "Ζ", "Η", "Θ", "Ι", "Κ", "Λ",
        "Μ", "Ν", "Ξ", "Ο", "Π", "Ρ", "Σ", "Τ", "Υ", "Φ", "Χ", "Ψ", "Ω"
    ],
    "named_variants": [
        "Delta", "delta", "Sigma", "sigma", "Epsilon", "epsilon", "Theta", "theta",
        "Alpha", "alpha", "Beta", "beta", "Gamma", "gamma", "Omega", "omega",
        "Mu", "mu", "Nu", "nu", "Kappa", "kappa", "Lambda", "lambda",
        "Xi", "xi", "Pi", "pi", "Rho", "rho", "Tau", "tau", "Upsilon", "upsilon",
        "Zeta", "zeta", "Eta", "eta", "Chi", "chi", "Psi", "psi", "Phi", "phi"
    ]
}

# [POLYMER FORMATS - COMMON, EXPANDED, MIXED]
POLYMER_NAMES = [
    # Abbreviated forms
    "PU", "PMMA", "PCL", "PDMS", "PVA", "PS", "PET", "PE", "PP", "PLA", "PTFE",
    "PDMAEMA", "PAA", "PA66", "PBAT", "PBT", "PC", "PES", "PVDF", "PVDC",

    # Expanded forms
    "polyurethane", "poly(methyl methacrylate)", "polycaprolactone",
    "polydimethylsiloxane", "polyvinyl alcohol", "polystyrene",
    "polyethylene terephthalate", "polyethylene", "polypropylene",
    "polylactic acid", "polytetrafluoroethylene", "poly(dimethyl siloxane)",
    "polyacrylic acid", "polyamide 66", "polybutylene adipate terephthalate",
    "polybutylene terephthalate", "polycarbonate", "polyethersulfone",
    "polyvinylidene fluoride", "polyvinylidene chloride",

    # Mixed naming formats
    "poly-methyl-methacrylate", "poly propylene", "poly-lactic acid",
    "poly(dimethylsiloxane)", "poly methyl methacrylate", "polyvinylidene-chloride",
    "polycapro-lactone", "polylactide", "poly ethylene glycol",
    "PEG", "PEGDA", "PEO", "PDLLA", "poly(ethylene glycol)", "poly(lactic-co-glycolic acid)",

    # Copolymers and blends
    "PU-VU", "PUU", "PCL-PEG", "PU-PLA", "PMMA-PLA", "PLA-PCL", "PCL-PLLA", "PU-VCL",
    "PUA", "PU-ECO", "HDI-PEG", "IPDI-PCL", "MDI-PU", "PU-V", "PCL-b-PDMS", "TPU",

    # Biopolymers / others
    "gelatin", "chitosan", "alginate", "collagen", "cellulose", "dextran",
    "starch-based polymer", "soy protein isolate", "zein",

    # === Abbreviated Forms (General Purpose Plastics) ===
    "PU", "PMMA", "PCL", "PDMS", "PVA", "PS", "PET", "PE", "PP", "PLA", "PTFE",
    "PC", "PES", "PVDF", "PVDC", "PBAT", "PBT", "PA6", "PA66", "PA12", "POM", "ABS",
    "SAN", "EVA", "ETFE", "PVF", "CPE", "EVOH", "LDPE", "HDPE", "LLDPE", "UHMWPE",

    # === Expanded Forms (Thermoplastics & Thermosets) ===
    "polyurethane", "poly(methyl methacrylate)", "polycaprolactone",
    "polydimethylsiloxane", "polyvinyl alcohol", "polystyrene",
    "polyethylene terephthalate", "polyethylene", "polypropylene",
    "polylactic acid", "polytetrafluoroethylene", "poly(dimethyl siloxane)",
    "polyacrylic acid", "polyamide 66", "polyamide 6", "polyamide 12",
    "polyoxymethylene", "polycarbonate", "polyethersulfone",
    "polyvinylidene fluoride", "polyvinylidene chloride", "polybutylene terephthalate",
    "polybutylene adipate terephthalate", "polyether ether ketone",
    "polyphenylene oxide", "polyphenylene sulfide", "polyetherimide",

    # === Biopolymers & Bio-Based Polymers ===
    "alginate", "chitosan", "gelatin", "collagen", "cellulose", "starch-based polymer",
    "dextran", "lignin", "zein", "soy protein isolate", "casein", "keratin",
    "polyhydroxybutyrate", "polyhydroxyvalerate", "PHBV", "polylactide",
    "poly(glycolic acid)", "poly(lactic-co-glycolic acid)", "PLGA",
    "polyhydroxyalkanoates", "PHA", "poly(butylene succinate)", "PBS", "PLA-PHB blend",

    # === Copolymers & Block Copolymers ===
    "PUA", "TPU", "SBS", "SEBS", "EPDM", "NBR", "SBR", "BR",
    "poly(styrene-butadiene)", "poly(acrylonitrile-butadiene-styrene)", "poly(styrene-isoprene-styrene)",
    "poly(styrene-b-isobutylene-b-styrene)", "PCL-b-PEG", "PEG-b-PLA", "PDLLA-b-PEG",
    "PLA-PEG-PLA", "PU-PLA", "PMMA-PLA", "PLA-PCL", "PCL-PLLA", "poly(lactide-co-caprolactone)",
    "poly(trimethylene terephthalate)", "PTT", "PBAT-PBS blend", "poly(ethylene-co-vinyl acetate)",

    # === Mixed Naming Variants ===
    "poly-methyl-methacrylate", "poly propylene", "poly-lactic acid",
    "poly(dimethylsiloxane)", "poly methyl methacrylate", "polyvinylidene-chloride",
    "polycapro-lactone", "polylactide", "poly ethylene glycol",
    "poly(ethylene glycol)", "poly(ethylene oxide)", "poly(lactic-co-glycolic acid)",
    "poly(ethylene-co-propylene)", "poly(ethylene oxide)-b-polystyrene",
    "poly(butylene adipate-co-terephthalate)",

    # === CANs & Vitrimers Related Systems ===
    "covalent adaptable network", "CAN", "vitrimer", "dynamic covalent network",
    "epoxy-vitrimer", "polyester-vitrimer", "acrylate-vitrimer", "imine-based CAN",
    "disulfide-exchange polymer", "transesterification-based CAN",
    "poly(lactic acid) vitrimer", "epoxy-based dynamic network", "urethane dynamic network",

    # === Elastomers & Thermoplastic Elastomers ===
    "thermoplastic polyurethane", "silicone elastomer", "natural rubber", "synthetic rubber",
    "polyisoprene", "polybutadiene", "fluoroelastomer", "fluorosilicone",
    "styrene-ethylene-butylene-styrene", "styrene-isoprene-styrene", "polyether block amide", "PEBA",

    # === Emerging Bio-Based Materials ===
    "epoxidized soybean oil", "epoxidized linseed oil", "epoxidized castor oil",
    "soybean oil-based polyurethane", "lignin-based thermoset", "tartaric acid-epoxy system",
    "citric acid-epoxy system", "eutectic hardener-based network",

    # === Others: Specialty Polymers ===
    "polyimide", "polybenzimidazole", "polybenzoxazine", "poly(p-phenylene terephthalamide)",
    "aramid", "Kevlar", "Nomex", "polytriazole", "poly(arylene ether ketone)", "PAEK",
    "poly(p-phenylene sulfide)", "polybenzothiazole", "polyurea",

    # === PEG and Derivatives ===
    "PEG", "PEGDA", "PEO", "mPEG", "PEG-b-PCL", "PEG-b-PLA",

    # === Miscellaneous Polymers ===
    "polyhydroxyurethane", "bio-based polycarbonate", "aliphatic polyester",
    "poly(amide-imide)", "poly(p-phenylene benzobisoxazole)", "PBO", "polybenzoxazole",

    # === Rubber and Blends ===
    "EPDM rubber", "SBR rubber", "NBR rubber", "chloroprene rubber",
    "thermoplastic vulcanizate", "TPV", "PVC-NBR blend", "PVC-ABS blend",

    # === Hydrogels ===
    "polyacrylamide hydrogel", "polyvinyl alcohol hydrogel", "chitosan hydrogel",
    "alginate hydrogel", "PEG hydrogel", "double network hydrogel",

    # === Additive Enhanced Polymers ===
    "carbon nanotube-epoxy composite", "graphene-epoxy composite", "silica reinforced PU",
    "nano clay reinforced PLA", "fiberglass-reinforced PBT", "CNT-PMMA composite",

    # === Thermosetting Resins ===
    "epoxy resin", "phenolic resin", "unsaturated polyester resin", "melamine-formaldehyde resin",
    "urea-formaldehyde resin", "cyanate ester resin", "benzoxazine resin",

    # === Renewable Source Derivatives ===
    "poly(ethylene furanoate)", "PEF", "bio-based PET", "castor oil polyurethane", "corn starch PLA",

    # === Experimental Systems ===
    "dynamic boronic ester polymer", "imine-exchange polymer", "disulfide bond polymer",
    "vinylogous urethane CAN", "DAE polymer (Diels-Alder exchange)", "urea-urethane network",
    "carbamate-exchange polymer",

    # === Fillers and Blends ===
    "polymer blend", "composite polymer", "polymer nanocomposite", "polymer hybrid material",

    # === Misc Abbreviations (from papers) ===
    "MDI-PU", "HDI-PEG", "IPDI-PCL", "TPU-PLA", "PLA-PEG", "PLA-PBS blend",
    "PBS-PHB blend", "PBSA", "PBSAT", "PBAT-PLA blend",

    # === Advanced Copolymers & Blends ===
    "poly(styrene-co-acrylonitrile)", "poly(styrene-co-butadiene)", "poly(ethylene-co-butylene)",
    "poly(ethylene-co-methyl acrylate)", "poly(propylene-co-ethylene)", "poly(acrylonitrile-co-styrene)",
    "poly(vinyl chloride-co-vinyl acetate)", "poly(lactic acid-co-glycolic acid)", "poly(styrene-block-butadiene)",
    "poly(lactic-co-caprolactone)", "poly(ethylene oxide-co-propylene oxide)", "poly(butylene succinate adipate)",
    "poly(ethylene-co-vinyl alcohol)", "poly(lactide-co-trimethylene carbonate)", "poly(propylene carbonate)",
    "poly(lactic acid) blend", "polybutadiene-styrene rubber blend", "PVC-PU blend", "HDPE-LDPE blend",

    # === Vitrimers & CAN Polymers ===
    "epoxy-amine dynamic network", "imine-crosslinked polymer", "disulfide-crosslinked elastomer",
    "poly(ester-urethane) dynamic network", "transesterification network polymer",
    "epoxy-vitrimer blend", "isoimide-based CAN", "DAE (Diels-Alder exchange) polymer",
    "vinylogous urethane vitrimer", "amine-exchange epoxy", "boronic ester-based dynamic network",
    "poly(acrylate-vitrimer)", "esterification-crosslinked network", "thiol-ene dynamic network",
    "siloxane-based dynamic polymer", "pyridine-exchange polymer",

    # === Biopolymers & Bio-Based Materials ===
    "poly(hydroxyalkanoate)", "poly(hydroxybutyrate-co-valerate)", "poly(butylene succinate)",
    "poly(ethylene furanoate)", "poly(trimethylene terephthalate)", "poly(butylene adipate terephthalate)",
    "PLA-PCL copolymer", "poly(hydroxyhexanoate)", "poly(propylene fumarate)",
    "poly(isosorbide succinate)", "lignin-epoxy hybrid", "cellulose acetate butyrate",
    "soy protein polymer", "zein-based polymer", "starch-polycaprolactone blend",

    # === Thermosetting Resins ===
    "bisphenol A epoxy resin", "novolac epoxy resin", "melamine-urea-formaldehyde resin",
    "cyanate ester-epoxy hybrid", "benzoxazine resin", "urea-formaldehyde copolymer",
    "phenol-formaldehyde resin", "furan resin", "polybenzoxazine network", "epoxy-cyanate ester blend",

    # === Elastomers & Rubbers ===
    "fluoroelastomer", "ethylene-propylene-diene monomer", "acrylonitrile-butadiene rubber",
    "butyl rubber", "styrene-butadiene rubber", "polyisoprene rubber", "chlorosulfonated polyethylene",
    "silicone rubber", "nitrile rubber", "thermoplastic vulcanizate", "TPV", "hydrogenated nitrile rubber",

    # === Specialty Polymers ===
    "poly(benzimidazole)", "poly(amide-imide)", "poly(aryl ether ketone)", "poly(ether ether ketone)",
    "poly(phenylene oxide)", "poly(phenylene sulfide)", "polybenzoxazole", "polybenzimidazole",
    "poly(p-phenylene benzobisoxazole)", "polyimide", "poly(benzothiazole)", "poly(benzoxazole)",

    # === PEG & Derivatives ===
    "methoxy polyethylene glycol", "PEG-methacrylate", "PEG-b-PLA", "PEG-b-PCL", "PEG-b-PTMC",
    "poly(ethylene glycol dimethacrylate)", "poly(ethylene oxide)-b-polystyrene",
    "poly(ethylene glycol)-block-poly(lactic acid)", "poly(ethylene oxide)-block-poly(caprolactone)",

    # === Hydrogels ===
    "alginate hydrogel", "chitosan hydrogel", "gelatin hydrogel", "hyaluronic acid hydrogel",
    "PVA hydrogel", "PEG-diacrylate hydrogel", "double network hydrogel", "polyacrylamide hydrogel",
    "collagen hydrogel", "dextran hydrogel", "smart hydrogel", "pH-responsive hydrogel",

    # === Additive Enhanced Polymers ===
    "CNT-PU composite", "graphene-PDMS composite", "nano clay reinforced PET",
    "carbon black-filled rubber", "silica-PMMA composite", "fiberglass-reinforced nylon",
    "carbon fiber-epoxy composite", "nanocellulose-PCL composite", "TiO₂-PLA nanocomposite",

    # === Renewable-Source Polymers ===
    "epoxidized linseed oil polymer", "citric acid-epoxy polymer", "tartaric acid-polyester network",
    "soy-based polyurethane", "glycerol-derived polyester", "castor oil-based PU", "green PE (bio-PE)",
    "bio-based polycarbonate", "isosorbide-based polycarbonate",

    # === Miscellaneous Advanced Systems ===
    "polyurethane acrylate", "poly(arylene ether ketone)", "polybenzimidazole-carbon nanofiber composite",
    "epoxy-polyimide blend", "polyether ether ketone-carbon fiber composite",
    "poly(lactic acid)-silica hybrid", "polyvinyl alcohol-silica hybrid",

    # === Experimental Dynamic Polymers ===
    "polyboronic ester", "urea-urethane dynamic network", "thiol-yne polymer network",
    "imine-exchange polyurethane", "pyridine-based CAN", "vinylogous urethane dynamic resin",

    # === Thermoplastic Blends ===
    "ABS-PC blend", "PC-PBT blend", "PE-PET blend", "PVC-ABS blend", "LDPE-HDPE blend",
    "PP-PS blend", "polycarbonate-polysulfone blend", "nylon-polyester blend",

    # === Trade Names (Genericized) ===
    "Teflon", "Lexan", "Delrin", "Hytrel", "Kapton", "Ultem", "Noryl", "Solef", "Kynar", "Zytel",

    # === Miscellaneous ===
    "bio-based polyamide", "aliphatic polyester", "sulfonated polyether ether ketone (SPEEK)",
    "poly(benzothiadiazole)", "poly(thiophene)", "poly(fluorene)", "poly(pyrrole)",
    "poly(aniline)", "poly(carbonate-co-ester)", "poly(p-phenylene ethynylene)",

    # === CAN-Related Emerging Systems ===
    "epoxy-dynamic covalent network", "ester-bond exchange polymer", "polyurethane vitrimer",
    "acid-catalyzed CAN", "amine-catalyzed dynamic network",

    # === Rare CANs & Vitrimers ===
    "imine-bonded dynamic network", "vinylogous urethane resin", "boronic ester-crosslinked polymer",
    "transcarbamoylation network polymer", "epoxy-anhydride vitrimer", "DAE-epoxy network",
    "poly(thioester CAN)", "ester-amide exchange polymer", "urea-exchange dynamic polymer",
    "self-healing epoxy network", "disulfide exchange elastomer", "polyhydrazone network",
    "β-hydroxy ester vitrimer", "poly(boronate ester) CAN", "siloxane dynamic network polymer",

    # === Biopolymers & Derivatives ===
    "pectin", "gellan gum", "curdlan", "xanthan gum", "guar gum", "κ-carrageenan", "ι-carrageenan",
    "fucoidan", "laminarin", "beta-glucan", "mannan", "arabinoxylan", "glycosaminoglycan",
    "keratin", "elastin", "resilin", "fibrin", "casein", "sericin", "silk fibroin", "hyaluronan",
    "poly(hydroxyvalerate)", "poly(hydroxyhexanoate)", "poly(hydroxyalkanoate-co-hydroxybutyrate)",

    # === Renewable & Green Polymers ===
    "isosorbide-based poly(ester carbonate)", "camphor-derived polycarbonate", "poly(ethylene 2,5-furandicarboxylate)",
    "furandicarboxylic acid polyester", "castor oil polyurethane", "epoxidized soybean oil resin",
    "citric acid-polyester network", "vanillin-based epoxy polymer", "levulinic acid-based resin",

    # === Trade Names & Synonyms ===
    "Tygon", "Viton", "Santoprene", "Neoprene", "Kraton", "Halar", "Parylene", "Saran",
    "Trogamid", "Vespel", "Pebax", "Tecoflex", "Tecophilic", "Biomer", "Pellethane",
    "Ultrason", "Torlon", "Arnite", "Radel", "Parmax", "Lustran", "Makrolon", "Duracon",

    # === Advanced Copolymers & Block Systems ===
    "poly(styrene-b-isoprene-b-styrene)", "poly(styrene-b-ethylene-co-butylene-b-styrene)",
    "poly(ethylene glycol)-b-poly(lactic acid)", "poly(ethylene glycol)-b-poly(trimethylene carbonate)",
    "poly(styrene-b-methyl methacrylate)", "poly(butadiene-b-polystyrene)", "poly(ethylene-co-propylene)",
    "poly(ethylene-co-octene)", "poly(propylene-co-ethylene)", "poly(styrene-co-maleic anhydride)",
    "poly(ethylene-co-vinyl acetate)", "poly(vinyl alcohol-co-ethylene)",

    # === Hybrid & Functionalized Systems ===
    "amine-functionalized polystyrene", "hydroxyl-terminated polybutadiene", "fluorinated polyethylene",
    "sulfonated polystyrene", "carboxylated nitrile rubber", "chlorinated polyethylene",
    "maleated polypropylene", "grafted polyethylene", "styrene-grafted polybutadiene",
    "epoxy-grafted polyethylene", "silane-grafted polyethylene", "chlorobutyl rubber",

    # === IUPAC / Hyphenated / Mixed Formats ===
    "poly[ethylene-co-(vinyl acetate)]", "poly(lactic-co-glycolic acid)", "poly(methyl methacrylate-co-butyl acrylate)",
    "poly(ethylene-co-1-octene)", "poly(butylene adipate-co-terephthalate)", "poly(trimethylene carbonate-co-lactide)",
    "poly(propylene glycol)-b-polylactide", "poly(lactic acid)-g-glycolide",
    "poly(acrylonitrile-co-butadiene-co-styrene)",

    # === Hydrogels (Expanded List) ===
    "dextran methacrylate hydrogel", "hyaluronic acid methacrylate hydrogel",
    "PEG-diacrylate hybrid hydrogel", "chitosan-gelatin interpenetrating network",
    "pH-sensitive hydrogel", "temperature-responsive hydrogel", "double-network hydrogel",
    "poly(N-isopropylacrylamide) hydrogel", "smart polymeric hydrogel",

    # === Elastomers (Rare Types) ===
    "chloroprene rubber", "styrene-isoprene-styrene block copolymer", "ethylene-vinyl acetate rubber",
    "fluorosilicone elastomer", "acrylic elastomer", "ethylene-propylene rubber",
    "polybutadiene rubber", "isoprene rubber", "silyl-terminated polyether elastomer",

    # === Specialty Polyamides & Polyesters ===
    "nylon-12", "nylon-6,12", "nylon-4,6", "nylon-6,10", "poly(hexamethylene adipamide)",
    "poly(trimethylene terephthalate)", "poly(hexamethylene terephthalate)", "poly(ethylene naphthalate)",
    "poly(propylene terephthalate)", "bio-based nylon", "aramid fiber", "meta-aramid", "para-aramid",

    # === Miscellaneous Advanced Systems ===
    "poly(silazane)", "poly(siloxane)", "polyphosphazene", "poly(benzoxazole)", "poly(benzothiadiazole)",
    "poly(fluorene-co-thiophene)", "poly(pyrrole-co-aniline)", "poly(silphenylene-siloxane)", "poly(dicyclopentadiene)",

    # === Emerging Systems ===
    "dynamic imine-based epoxy", "thioester crosslinked vitrimer", "transesterification epoxy CAN",
    "urea-exchange self-healing network", "vinylogous urethane vitrimer", "hydrazone exchange CAN",
    "amine-transcarbamoylation dynamic network", "multi-responsive dynamic covalent network",

    # === Hybrid & Functionalized Polymers ===
    "poly(styrene-block-butadiene-block-styrene)",
    "poly(ethylene oxide)-b-poly(propylene oxide)-b-poly(ethylene oxide)",
    "poly(ethylene glycol)-b-poly(caprolactone)", "poly(lactic acid)-b-poly(trimethylene carbonate)",
    "poly(2-hydroxyethyl methacrylate)", "poly(acrylamide-co-acrylic acid)", "poly(ethylene-co-butene)",
    "poly(vinyl alcohol-co-ethylene)", "poly(styrene-co-acrylonitrile)", "poly(acrylonitrile-co-methyl methacrylate)",
    "poly(vinylidene fluoride-co-hexafluoropropylene)", "poly(chlorotrifluoroethylene)", "poly(ether-block-amide)",

    # === Biopolymers & Derivatives ===
    "pullulan", "agarose", "glycogen", "amylopectin", "amylose", "lignin", "hemicellulose",
    "poly(beta-amino ester)", "poly(hydroxybutyrate-co-hydroxyvalerate)", "poly(3-hydroxybutyrate)",
    "poly(4-hydroxybutyrate)", "poly(3-hydroxyhexanoate)", "poly(3-hydroxyoctanoate)",

    # === Sustainable / Renewable Polymers ===
    "poly(isosorbide carbonate)", "poly(itaconic acid ester)", "poly(levulinic acid ester)",
    "poly(ethylene succinate)", "poly(butylene succinate)", "poly(propylene succinate)",
    "poly(trimethylene carbonate)", "poly(1,3-propylene carbonate)", "poly(ethylene furanate)",

    # === Trade Names / Synonyms ===
    "Kapton", "Hytrel", "Solef", "Delrin", "Celcon", "Hycar", "Thermoplastic Polyurethane (TPU)",
    "Santoprene TPV", "Pebax elastomer", "Elvax", "Saran wrap polymer", "Nafion", "Ionac", "Tefzel",
    "Calrex", "Novolac", "Halar ECTFE", "Fortron", "Xydar", "Vectra", "Zenite",

    # === Advanced Copolymers ===
    "poly(styrene-co-butadiene)", "poly(styrene-co-maleic acid)", "poly(acrylic acid-co-acrylamide)",
    "poly(acrylamide-co-diallyldimethylammonium chloride)", "poly(styrene-co-divinylbenzene)",
    "poly(acrylonitrile-co-butadiene)", "poly(vinyl chloride-co-vinyl acetate)", "poly(butadiene-co-nitrile)",

    # === Hydrogels Expanded ===
    "poly(N-vinylpyrrolidone) hydrogel", "poly(acrylic acid) hydrogel", "methacrylated gelatin (GelMA)",
    "polyethylene glycol diacrylate hydrogel", "polyacrylamide hydrogel", "poly(vinyl alcohol) hydrogel",
    "multi-network hydrogel", "photo-crosslinked hydrogel", "thermo-sensitive hydrogel", "redox-responsive hydrogel",

    # === Elastomers ===
    "polyisoprene rubber", "polybutadiene elastomer", "butyl rubber", "styrene-butadiene rubber (SBR)",
    "ethylene-propylene-diene monomer (EPDM)", "chlorosulfonated polyethylene (CSM)", "fluoroelastomer",
    "polyether elastomer", "acrylic rubber", "silicone rubber", "hydrogenated nitrile rubber (HNBR)",

    # === Polyamides & Polyesters (Specialty) ===
    "polyamide-11", "polyamide-12", "polyamide-6,6", "polyamide-6,10", "bio-based polyamide",
    "poly(trimethylene terephthalate)", "poly(butylene adipate terephthalate)", "poly(ethylene succinate)",
    "poly(propylene terephthalate)", "poly(ethylene isophthalate)",

    # === Miscellaneous Advanced Systems ===
    "poly(aryletherketone)", "poly(arylene sulfide)", "poly(arylene ether ketone)", "polyether ether ketone (PEEK)",
    "polyether ketone ketone (PEKK)", "polyetherimide", "polybenzimidazole", "polybenzoxazole",
    "polyoxymethylene copolymer", "polyphenylene oxide (PPO)", "polyphenylene sulfide (PPS)",

    # === Emerging Dynamic Networks ===
    "imine exchange-based CAN", "disulfide reshuffling CAN", "urea-exchange dynamic network",
    "vinylogous urethane CAN", "boronic ester dynamic network", "multi-responsive dynamic polymer network",
    "hydrazone-based CAN", "vitrimer epoxy matrix", "thioester vitrimer polymer", "transesterification network polymer",

    # === Grammar Variants (Hyphenation / Parenthetical) ===
    "poly-vinyl-alcohol", "poly (methyl methacrylate)", "poly(methyl-methacrylate)", "poly(lactic acid)",
    "poly (ethylene glycol)", "poly propylene glycol", "poly-lactic-glycolic acid", "poly-ε-caprolactone",
    "poly(N-isopropylacrylamide)", "poly(N-vinyl caprolactam)", "poly(ethylene glycol)-block-poly(propylene glycol)",

    # === Specialty Blends ===
    "thermoplastic polyurethane blend", "PLA-starch blend", "PCL-chitosan composite", "PEG-gelatin blend",
    "polyethylene-polypropylene copolymer", "acrylonitrile-butadiene-styrene (ABS)", "high-impact polystyrene (HIPS)",
    "styrene-maleic anhydride (SMA)", "polyether-block-polyamide (PEBAX)", "polyolefin elastomer blend",

    # === Rare & Exotic Vitrimers ===
    "poly(carbamate vitrimer)", "epoxy vitrimer network", "vitrimer polyurethane",
    "imine-crosslinked vitrimer", "epoxy-acid dynamic network", "urethane-exchange vitrimer",
    "ester-exchange-based CAN", "transamination vitrimer", "boronic ester CAN", "thioester CAN polymer",

    # === Biopolymers (Sourced & Synthetic Derivatives) ===
    "xanthan gum", "gellan gum", "pectin", "guar gum", "laminarin", "fucoidan",
    "poly(γ-glutamic acid)", "poly(hydroxyalkanoate)", "poly(β-hydroxybutyrate)",
    "poly(δ-valerolactone)", "poly(γ-butyrolactone)", "poly(pyrrolidone)", "poly(lysine)",
    "poly(glutamic acid)", "poly(hydroxyproline)", "poly(sarcosine)", "poly(histidine)",

    # === Dendrimers & Branched Polymers ===
    "poly(amidoamine) dendrimer", "poly(propylene imine) dendrimer", "polyester dendrimer",
    "PEGylated dendrimer", "hyperbranched poly(ether)", "hyperbranched poly(ester)", "poly(glycidol)",

    # === Organic-Inorganic Hybrids ===
    "siloxane-polyurethane hybrid", "silane-modified polyurethane", "organosilane-epoxy polymer",
    "poly(silazane)", "poly(carborane)", "boron nitride-polymer composite", "silica-grafted polymer matrix",
    "poly(tetramethyl orthosilicate)", "titanium dioxide-polymer hybrid",

    # === Trade Names & Specialty Grades ===
    "Lexan", "Makrolon", "Sustarin", "Tecapet", "Radel", "Udel", "Kynar", "Aflas", "Zytel", "Vespel",
    "Duracon", "Trovidur", "Halar", "Trogamid", "Celazole", "Tecaform", "Ardel", "Ryton", "Rylar", "Amodel",

    # === Responsive & Smart Polymers ===
    "poly(N-isopropylacrylamide)", "poly(N-vinylcaprolactam)", "poly(acrylic acid-co-acrylamide)",
    "poly(acrylamide-co-sodium acrylate)", "poly(ethylene oxide)-b-poly(propylene oxide)",
    "poly(2-ethyl-2-oxazoline)", "poly(N,N-dimethylacrylamide)", "poly(N-hydroxyethylacrylamide)",

    # === Advanced Elastomers ===
    "perfluoroelastomer", "ethylene-acrylic elastomer", "chlorinated polyethylene elastomer",
    "thermoplastic vulcanizate (TPV)", "hydrogenated nitrile butadiene rubber (HNBR)", "fluorosilicone elastomer",

    # === Sustainable / Green Polymers Expanded ===
    "poly(isosorbide ether)", "poly(succinic anhydride)", "poly(ethylene adipate)", "poly(1,4-butanediol succinate)",
    "poly(butylene fumarate)", "poly(ethylene glycol sebacate)", "poly(ethylene carbonate)", "poly(butylene carbonate)",

    # === Polymer Blends & Grafts ===
    "ABS-graft-PVC", "PVC-graft-CPVC", "poly(styrene-g-butadiene)", "poly(ethylene-g-acrylic acid)",
    "poly(vinyl alcohol-co-ethylene)", "poly(butadiene-g-acrylonitrile)", "polycarbonate-polyester blend",

    # === Expanded Grammar Variants ===
    "poly lactic acid", "poly-lactic-acid", "poly propylene oxide", "poly dimethyl siloxane",
    "poly(methyl acrylate)", "poly methyl acrylate", "poly(ethylene-alt-propylene)",
    "poly ethylene-co-propylene", "poly(styrene-alt-maleic anhydride)", "poly styrene-alt-maleic anhydride",

    # === Specialty Networks ===
    "dynamic imine polymer network", "multi-responsive CAN polymer", "transcarbamoylation vitrimer",
    "epoxy-poly(amide) hybrid network", "thermo-reversible network polymer", "urea-formaldehyde resin",
    "melamine-formaldehyde resin", "phenol-formaldehyde resin",

    # === High-Performance Thermoplastics ===
    "poly(ether ether ketone) (PEEK)", "poly(ether ketone ketone) (PEKK)", "polybenzoxazole (PBO)",
    "polybenzothiazole (PBT)", "polyphenylene ether (PPE)", "polyimide (PI)", "polyamide-imide (PAI)",
    "liquid crystal polymer (LCP)", "polyetheretherketone-blend (PEEK-blend)",

    # === Biodegradable Polyesters ===
    "poly(butylene succinate adipate)", "poly(butylene sebacate)", "poly(glycolide)",
    "poly(lactide-co-glycolide)", "poly(trimethylene carbonate)", "poly(hydroxybutyrate-co-valerate)",

    # === Crosslinkable & UV-curable Systems ===
    "epoxy acrylate resin", "urethane acrylate resin", "silicone acrylate resin", "polyurethane methacrylate",
    "acrylic urethane hybrid resin", "unsaturated polyester resin", "alkyd resin", "vinyl ester resin",

    # === Expanded Biopolymers ===
    "poly(sorbitol adipate)", "poly(glucose adipate)", "poly(galacturonic acid)", "poly(ribose)",
    "poly(arabinose)", "poly(mannose)", "poly(fucose)", "poly(glycolaldehyde)",

    # === Miscellaneous ===
    "poly(tetrahydrofuran)", "poly(2-methyl-2-oxazoline)", "poly(4-vinylphenol)", "poly(aniline)",
    "poly(pyrrole)", "poly(thiophene)", "poly(3-hexylthiophene)", "poly(3-octylthiophene)",
    "poly(phenylene vinylene)", "poly(para-phenylene)", "poly(meta-phenylene)", "poly(ortho-phenylene)"
]

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

# All property tablevalues

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

# [VALUE FORMATS - EDGE CASES AND SCIENTIFIC VARIANTS]
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

# [SYMBOLS - SCIENTIFIC PROPERTY SYMBOLS]
SCIENTIFIC_SYMBOLS = [
    # Thermal & thermodynamic
    "Tg", "T_m", "T_d", "Tg'", "T_max", "T_onset", "ΔT", "ΔH", "q", "Q", "C_p", "Cp", "c_p",

    # Energy & kinetics
    "Ea", "E_a", "ΔE", "E_act", "H", "ΔH_rxn", "ΔE‡", "E‡",

    # Mechanical
    "σ", "σ_y", "σ_b", "σ_max", "σ_ult", "ε", "ε_b", "ε_max", "E", "E'", "E''", "η", "τ", "γ", "K_IC",

    # Dielectric & electronic
    "k", "κ", "κ_f", "ε_r", "ε₀", "n", "n_m", "n_c", "μ", "μ_O₂", "μ_CO₂", "μ_N₂", "μ_He", "μ_CH₄", "μ_H₂",
    "Eg", "E_g", "E_g^c", "E_g^b", "E_i", "E_ib", "E_ea", "χ", "Φ", "δ",

    # Optical
    "λ", "n_D", "RI", "α", "A", "T", "I", "I₀",

    # Physical & general
    "ρ", "V", "m", "d", "A", "l", "t", "f", "ν", "ω", "Z", "R", "R_g", "R_h",

    # Symbols with math presentation
    "Δ", "∇", "∂", "∑", "∫", "≈", "≠", "≡", "∞",

    # Unicode + stylized variants (for robustness)
    "σₓ", "εᵧ", "κₜ", "η₀", "μ*", "n*", "χₘ", "δₕ", "λₘ", "Φ₀", "γ₀", "ω₀",

    # === Thermal & Thermodynamic Symbols ===
    "Tg", "T_m", "T_d", "Tg'", "T_max", "T_onset", "ΔT", "ΔH", "ΔH_fusion", "ΔH_vaporization",
    "ΔH_rxn", "q", "Q", "Cp", "C_p", "c_p", "T_50%", "T_5%", "T_peak", "T_onset", "Tv", "Ttrigger",

    # === Energy & Kinetics Symbols ===
    "Ea", "E_a", "ΔE", "E‡", "ΔE‡", "E_act", "H", "ΔHrxn", "E_act", "t1/2", "kcat", "k_on", "k_off",

    # === Mechanical Symbols ===
    "σ", "σ_y", "σ_b", "σ_max", "σ_ult", "ε", "ε_b", "ε_max", "E", "E'", "E''", "G", "G'", "G''",
    "KIC", "K_Ic", "K_IC", "Gc", "SFR", "SMR", "τ", "γ", "η", "Rr", "ηh", "Q_swelling",

    # === Dielectric & Electronic Symbols ===
    "k", "κ", "κ_f", "ε_r", "ε₀", "n", "n_D", "n_m", "n_c", "μ", "μ*", "μ_O₂", "μ_CO₂", "μ_N₂",
    "μ_He", "μ_CH₄", "μ_H₂", "Eg", "E_g", "E_g^c", "E_g^b", "E_i", "E_ib", "E_ea", "χ", "Φ", "δ",

    # === Optical Symbols ===
    "λ", "RI", "α", "A", "T", "I", "I₀", "PLQY", "Δn", "Δλ", "ΔRI", "birefringence Δn", "θ", "ϕ",

    # === Surface & Adhesion Symbols ===
    "γ", "γ_surface", "γ_sl", "γ_sv", "γ_lv", "θA", "θR", "Δθ", "ΔCA", "W_adhesion", "F_pull-off",

    # === Physical & General Symbols ===
    "ρ", "V", "m", "d", "A", "l", "t", "f", "ν", "ω", "Z", "R", "R_g", "R_h", "SSA", "BET", "pKa",
    "pH", "pKa1", "pKa2", "Mw", "Mn", "Đ", "PDI", "Mn", "Mw/Mn", "M_n", "M_w", "M_n/M_w",

    # === Mathematical & Operators ===
    "Δ", "∇", "∂", "∑", "∫", "≈", "≠", "≡", "∞", "±", "≥", "≤", "→", "←", "↔", "⇌", "≅", "~",

    # === Unicode + OCR Variants ===
    "σₓ", "εᵧ", "κₜ", "η₀", "μ*", "n*", "χₘ", "δₕ", "λₘ", "Φ₀", "γ₀", "ω₀", "ϵ", "φ", "ψ", "ζ", "ξ",
    "Π", "Σ", "Ω", "Γ", "Δ", "Λ", "Θ", "Ψ",

    # === Rare Scientific Symbols from CANs/SMPs ===
    "τ*", "τ_relaxation", "Tv", "R_crosslink", "νe", "υ", "υe", "σf", "σc", "σr",
    "θrecovery", "ΔS", "ΔG", "ΔSentropy", "ΔGfree", "Φc",

    # === Battery/Polymer Electrolyte Symbols ===
    "σion", "σelec", "tLi+", "ESW", "ηC", "C_rate", "ηdischarge", "ηcharge",
    "V_ocv", "R_ct", "R_sei", "ΔV",

    # === Fire & Safety Related ===
    "LOI", "HRR", "THR", "T_peak", "T_flash", "T_autoignition", "SMPs", "FRR",

    # === Miscellaneous Symbols for Robustness ===
    "P", "S", "F", "M", "G*", "E*", "ν*", "α*", "β*", "κ*", "η*", "Δ*", "Ω*", "π", "ξ", "ζ"
]

# [SCIENTIFIC UNITS AND THEIR VARIANTS]
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

MATERIALS = [
    # Chemical Materials
    "citric acid", "sodium chloride", "potassium chloride", "calcium carbonate",
    "sodium bicarbonate", "sodium sulfate", "potassium nitrate", "calcium sulfate",
    "oxidation", "reduction", "polymerization", "decomposition", "hydrolysis",
    "condensation", "saponification", "esterification", "transesterification",
    "oxidative stress", "catalysis", "enzymatic reaction", "acid-base reaction",
    "redox reaction", "precipitation", "crystallization", "adsorption", "absorption",
    "ion exchange", "chelation", "complexation", "dissolution", "evaporation",
    "epoxidized soybean oil", "epoxidized linseed oil", "epoxidized palm oil",
]

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

# Required environment variables for Appwrite
REQUIRED_ENV_VARS = [
    "APPWRITE_PROJECT_ID",
    "APPWRITE_API_KEY",
    "APPWRITE_ENDPOINT",
    "APPWRITE_DATABASE_ID",
    "APPWRITE_BUCKET_ID"
]

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

LABELS = [
    "O",
    "B-PROPERTY", "I-PROPERTY",
    "B-SYMBOL", "I-SYMBOL",
    "B-VALUE", "I-VALUE",
    "B-UNIT", "I-UNIT",
    "B-POLYMER", "I-POLYMER",
    "B-MATERIAL", "I-MATERIAL"
]

LABEL2ID = {label: idx for idx, label in enumerate(LABELS)}

ID2LABEL = {idx: label for label, idx in LABEL2ID.items()}
