
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
