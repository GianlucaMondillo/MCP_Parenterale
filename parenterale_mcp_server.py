"""
MCP Server for Neonatal Parenteral Nutrition Calculation.

Calculates complete PN (parenteral nutrition) prescriptions for neonates,
including classic PN bags and Numeta G13E premixed solutions.

Uses the official MCP Python SDK (FastMCP) with stdio transport
for integration with Claude Desktop.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Parenterale")


# ---------------------------------------------------------------------------
# Helper: kcal from macronutrients (same as JS kcalFromMacros)
# ---------------------------------------------------------------------------
def _kcal_from_macros(cho: float, prot: float, lip: float) -> float:
    return cho * 4 + prot * 4 + lip * 9


# ===========================================================================
# DATA TABLES  (ported from Parenterale.html JavaScript)
# All numeric values are exact copies from the original JS.
# ===========================================================================

# ---------------------------------------------------------------------------
# 1. Solution concentrations (conc, lines 866-902)
# ---------------------------------------------------------------------------
CONC = {
    "aa": {
        "trof6": {"aa_g_per_ml": 0.06, "n_from_aa": 1 / 6.45},
    },
    "glu": {
        "g10": {"glu_g_per_ml": 0.10},
        "g33": {"glu_g_per_ml": 0.33},
        "g50": {"glu_g_per_ml": 0.50},
    },
    "lip": {
        "il10": {"lip_g_per_ml": 0.10},
        "il20": {"lip_g_per_ml": 0.20},
        "cl20": {"lip_g_per_ml": 0.20},
    },
    "na": {
        "nacl2": {"na_mEq_per_ml": 2, "cl_mEq_per_ml": 2},
        "naac3": {"na_mEq_per_ml": 3},
        "glycophos-na": {"na_mEq_per_ml": 2},
        "esafos-na": {"na_mEq_per_ml": 0.6},
    },
    "k": {
        "kcl2": {"k_mEq_per_ml": 2, "cl_mEq_per_ml": 2},
        "k3m": {"k_mEq_per_ml": 3},
    },
    "ca": {
        "caglu10": {"ca_mEq_per_ml": 0.465, "ca_mg_per_ml": 9.3},
    },
    "mg": {
        "mgso410": {"mg_mEq_per_ml": 0.81},
    },
    "p": {
        "glycophos-p": {"p_mEq_per_ml": 1, "p_mg_per_ml": 31},
        "esafos-p": {"p_mEq_per_ml": 0.47, "p_mg_per_ml": 0.47 * 31},
    },
}

# ---------------------------------------------------------------------------
# 2. Osmolarity values per solution (OSMOL_SOL, lines 905-944)
# ---------------------------------------------------------------------------
OSMOL_SOL = {
    "trof6": 440,
    "g33": 1832,
    "g10": 555,
    "g50": 2775,
    "il20": 260,
    "il10": 260,
    "cl20": 270,
    "nacl2": 4000,
    "naac3": 6000,
    "glycophos-na": 2570,
    "esafos-na": 830,
    "kcl2": 4000,
    "k3m": 6000,
    "caglu10": 660,
    "mgso410": 800,
    "esafos-p": 410,
    "glycophos-p": 2570,
    "soluvit": 1000,
}

# ---------------------------------------------------------------------------
# 3. Numeta G13E compositions (NUMETA, lines 946-973)
# ---------------------------------------------------------------------------
NUMETA = {
    "g13_240": {
        "aa_g_per_ml": 0.031,
        "glu_g_per_ml": 0.133,
        "lip_g_per_ml": 0.000,
        "na_mEq_per_ml": 0.022,
        "k_mEq_per_ml": 0.021,
        "mg_mEq_per_ml": 0.0032,
        "ca_mg_per_ml": 0.52,
        "p_mg_per_ml": 0.40,
        "cl_mEq_per_ml": 0.031,
        "kcal_per_ml": 0.656,
        "osm_mOsm_per_L": 1150,
    },
    "g13_300": {
        "aa_g_per_ml": 0.031,
        "glu_g_per_ml": 0.133,
        "lip_g_per_ml": 0.025,
        "na_mEq_per_ml": 0.022,
        "k_mEq_per_ml": 0.021,
        "mg_mEq_per_ml": 0.0032,
        "ca_mg_per_ml": 0.52,
        "p_mg_per_ml": 0.40,
        "cl_mEq_per_ml": 0.031,
        "kcal_per_ml": 0.91,
        "osm_mOsm_per_L": 1150,
    },
}

# ---------------------------------------------------------------------------
# 4. Formula/Milk compositions per 100 ml (LATTI, lines 981-1308)
# ---------------------------------------------------------------------------
_LATTI_BASE = {
    "latte_materno": {
        "kcal_per_100": 67,
        "prot_g_per_100": 1.2,
        "lip_g_per_100": 3.8,
        "cho_g_per_100": 7.0,
        "ca_mg_per_100": 30,
        "p_mg_per_100": 15,
        "k_mg_per_100": 55,
        "na_mg_per_100": 15,
        "mg_mg_per_100": 3,
    },
    "PreNidina FM85": {
        "kcal_per_100": _kcal_from_macros(5.2, 5.6, 2.8),
        "prot_g_per_100": 5.6,
        "lip_g_per_100": 2.8,
        "cho_g_per_100": 5.2,
        "ca_mg_per_100": 302.4,
        "p_mg_per_100": 175.2,
        "k_mg_per_100": 193.6,
        "na_mg_per_100": 146.8,
        "mg_mg_per_100": 16.0,
    },
    "PreAptamil": {
        "kcal_per_100": _kcal_from_macros(7.5, 2.1, 4.0),
        "prot_g_per_100": 2.1,
        "lip_g_per_100": 4.0,
        "cho_g_per_100": 7.5,
        "ca_mg_per_100": 87.0,
        "p_mg_per_100": 48.0,
        "k_mg_per_100": 78.0,
        "na_mg_per_100": 27.5,
        "mg_mg_per_100": 7.2,
    },
    "PreNAN": {
        "kcal_per_100": _kcal_from_macros(7.7, 2.0, 3.8),
        "prot_g_per_100": 2.0,
        "lip_g_per_100": 3.8,
        "cho_g_per_100": 7.7,
        "ca_mg_per_100": 82.0,
        "p_mg_per_100": 50.4,
        "k_mg_per_100": 85.5,
        "na_mg_per_100": 36.0,
        "mg_mg_per_100": 7.2,
    },
    "Humana 0": {
        "kcal_per_100": _kcal_from_macros(7.8, 2.1, 4.0),
        "prot_g_per_100": 2.1,
        "lip_g_per_100": 4.0,
        "cho_g_per_100": 7.8,
        "ca_mg_per_100": 100.0,
        "p_mg_per_100": 60.0,
        "k_mg_per_100": 75.0,
        "na_mg_per_100": 32.0,
        "mg_mg_per_100": 8.9,
    },
    "Humana 0-VLB": {
        "kcal_per_100": _kcal_from_macros(7.8, 2.1, 4.0),
        "prot_g_per_100": 2.1,
        "lip_g_per_100": 4.0,
        "cho_g_per_100": 7.8,
        "ca_mg_per_100": 100.0,
        "p_mg_per_100": 60.0,
        "k_mg_per_100": 75.0,
        "na_mg_per_100": 32.0,
        "mg_mg_per_100": 8.9,
    },
    "BBmilk 0": {
        "kcal_per_100": _kcal_from_macros(8.7, 2.4, 3.9),
        "prot_g_per_100": 2.4,
        "lip_g_per_100": 3.9,
        "cho_g_per_100": 8.7,
        "ca_mg_per_100": 115.0,
        "p_mg_per_100": 65.0,
        "k_mg_per_100": 82.0,
        "na_mg_per_100": 40.0,
        "mg_mg_per_100": 6.5,
    },
    "Hipp 0 Dr.Baby's": {
        "kcal_per_100": _kcal_from_macros(8.7, 2.4, 3.9),
        "prot_g_per_100": 2.4,
        "lip_g_per_100": 3.9,
        "cho_g_per_100": 8.7,
        "ca_mg_per_100": 100.0,
        "p_mg_per_100": 55.0,
        "k_mg_per_100": 90.0,
        "na_mg_per_100": 44.0,
        "mg_mg_per_100": 6.3,
    },
    "N5 0 (Sterilfarma)": {
        "kcal_per_100": _kcal_from_macros(8.7, 2.4, 3.9),
        "prot_g_per_100": 2.4,
        "lip_g_per_100": 3.9,
        "cho_g_per_100": 8.7,
        "ca_mg_per_100": 115.0,
        "p_mg_per_100": 65.0,
        "k_mg_per_100": 82.0,
        "na_mg_per_100": 40.0,
        "mg_mg_per_100": 6.5,
    },
    "Pregomin SP": {
        "kcal_per_100": _kcal_from_macros(7.2, 1.8, 3.4),
        "prot_g_per_100": 1.8,
        "lip_g_per_100": 3.4,
        "cho_g_per_100": 7.2,
        "ca_mg_per_100": 76.0,
        "p_mg_per_100": 47.0,
        "k_mg_per_100": 65.0,
        "na_mg_per_100": 21.7,
        "mg_mg_per_100": 5.1,
    },
    "Nutramigen 1 LGG": {
        "kcal_per_100": _kcal_from_macros(7.5, 1.91, 3.4),
        "prot_g_per_100": 1.91,
        "lip_g_per_100": 3.4,
        "cho_g_per_100": 7.5,
        "ca_mg_per_100": 77.0,
        "p_mg_per_100": 53.0,
        "k_mg_per_100": 83.0,
        "na_mg_per_100": 32.0,
        "mg_mg_per_100": 6.8,
    },
    "Infatrini Peptisorb": {
        "kcal_per_100": _kcal_from_macros(10.2, 2.6, 5.4),
        "prot_g_per_100": 2.6,
        "lip_g_per_100": 5.4,
        "cho_g_per_100": 10.2,
        "ca_mg_per_100": 90.0,
        "p_mg_per_100": 45.0,
        "k_mg_per_100": 111.0,
        "na_mg_per_100": 37.0,
        "mg_mg_per_100": 9.0,
    },
    "Allernova PRO": {
        "kcal_per_100": _kcal_from_macros(7.0, 1.6, 3.5),
        "prot_g_per_100": 1.6,
        "lip_g_per_100": 3.5,
        "cho_g_per_100": 7.0,
        "ca_mg_per_100": 81.0,
        "p_mg_per_100": 45.0,
        "k_mg_per_100": 84.0,
        "na_mg_per_100": 22.0,
        "mg_mg_per_100": 6.8,
    },
    "Aminova": {
        "kcal_per_100": _kcal_from_macros(8.7, 1.9, 3.3),
        "prot_g_per_100": 1.9,
        "lip_g_per_100": 3.3,
        "cho_g_per_100": 8.7,
        "ca_mg_per_100": 75.0,
        "p_mg_per_100": 52.0,
        "k_mg_per_100": 75.0,
        "na_mg_per_100": 27.0,
        "mg_mg_per_100": 6.8,
    },
    "Nutramigen AA": {
        "kcal_per_100": _kcal_from_macros(7.2, 1.89, 3.6),
        "prot_g_per_100": 1.89,
        "lip_g_per_100": 3.6,
        "cho_g_per_100": 7.2,
        "ca_mg_per_100": 64.0,
        "p_mg_per_100": 35.0,
        "k_mg_per_100": 74.0,
        "na_mg_per_100": 32.0,
        "mg_mg_per_100": 7.4,
    },
    "Heparon Junior": {
        "kcal_per_100": _kcal_from_macros(10.0, 2.2, 4.0),
        "prot_g_per_100": 2.2,
        "lip_g_per_100": 4.0,
        "cho_g_per_100": 10.0,
        "ca_mg_per_100": 51.9,
        "p_mg_per_100": 9.4,
        "k_mg_per_100": 88.1,
        "na_mg_per_100": 17.8,
        "mg_mg_per_100": 63.9,
    },
    "NAN AR (Nestle)": {
        "kcal_per_100": _kcal_from_macros(7.8, 1.3, 3.4),
        "prot_g_per_100": 1.3,
        "lip_g_per_100": 3.4,
        "cho_g_per_100": 7.8,
        "ca_mg_per_100": 45.6,
        "p_mg_per_100": 26.7,
        "k_mg_per_100": 72.4,
        "na_mg_per_100": 25.4,
        "mg_mg_per_100": 6.65,
    },
    "N5 AR (Sterilfarma)": {
        "kcal_per_100": _kcal_from_macros(6.8, 1.4, 3.5),
        "prot_g_per_100": 1.4,
        "lip_g_per_100": 3.5,
        "cho_g_per_100": 6.8,
        "ca_mg_per_100": 45.0,
        "p_mg_per_100": 28.0,
        "k_mg_per_100": 67.0,
        "na_mg_per_100": 19.0,
        "mg_mg_per_100": 5.1,
    },
    "Humana AR": {
        "kcal_per_100": _kcal_from_macros(7.5, 1.4, 3.1),
        "prot_g_per_100": 1.4,
        "lip_g_per_100": 3.1,
        "cho_g_per_100": 7.5,
        "ca_mg_per_100": 59.0,
        "p_mg_per_100": 33.0,
        "k_mg_per_100": 67.0,
        "na_mg_per_100": 22.0,
        "mg_mg_per_100": 5.8,
    },
    "Aptamil 1": {
        "kcal_per_100": 65.0,
        "prot_g_per_100": 1.3,
        "lip_g_per_100": 3.4,
        "cho_g_per_100": 7.3,
        "ca_mg_per_100": 58,
        "p_mg_per_100": 33,
        "k_mg_per_100": 70,
        "na_mg_per_100": 18,
        "mg_mg_per_100": 7,
    },
    "Humana 1": {
        "kcal_per_100": 66.3,
        "prot_g_per_100": 1.3,
        "lip_g_per_100": 3.5,
        "cho_g_per_100": 7.4,
        "ca_mg_per_100": 55,
        "p_mg_per_100": 30,
        "k_mg_per_100": 72,
        "na_mg_per_100": 19,
        "mg_mg_per_100": 7,
    },
    "Hipp 1": {
        "kcal_per_100": 65.9,
        "prot_g_per_100": 1.3,
        "lip_g_per_100": 3.5,
        "cho_g_per_100": 7.3,
        "ca_mg_per_100": 53,
        "p_mg_per_100": 29,
        "k_mg_per_100": 70,
        "na_mg_per_100": 19,
        "mg_mg_per_100": 7,
    },
    "NAN 1": {
        "kcal_per_100": 68.4,
        "prot_g_per_100": 1.4,
        "lip_g_per_100": 3.6,
        "cho_g_per_100": 7.6,
        "ca_mg_per_100": 58,
        "p_mg_per_100": 34,
        "k_mg_per_100": 73,
        "na_mg_per_100": 18,
        "mg_mg_per_100": 8,
    },
    "bbmilk 1": {
        "kcal_per_100": 66.4,
        "prot_g_per_100": 1.3,
        "lip_g_per_100": 3.6,
        "cho_g_per_100": 7.2,
        "ca_mg_per_100": 55,
        "p_mg_per_100": 32,
        "k_mg_per_100": 71,
        "na_mg_per_100": 18,
        "mg_mg_per_100": 7,
    },
    "Nidina 1": {
        "kcal_per_100": 64.0,
        "prot_g_per_100": 1.3,
        "lip_g_per_100": 3.2,
        "cho_g_per_100": 7.5,
        "ca_mg_per_100": 55,
        "p_mg_per_100": 30,
        "k_mg_per_100": 75,
        "na_mg_per_100": 18,
        "mg_mg_per_100": 7,
    },
    "N5 1": {
        "kcal_per_100": 65.0,
        "prot_g_per_100": 1.3,
        "lip_g_per_100": 3.4,
        "cho_g_per_100": 7.3,
        "ca_mg_per_100": 58,
        "p_mg_per_100": 30,
        "k_mg_per_100": 70,
        "na_mg_per_100": 18,
        "mg_mg_per_100": 7,
    },
    "Novalac 1": {
        "kcal_per_100": _kcal_from_macros(7.7, 1.4, 3.3),
        "prot_g_per_100": 1.4,
        "lip_g_per_100": 3.3,
        "cho_g_per_100": 7.7,
        "ca_mg_per_100": 49.0,
        "p_mg_per_100": 31.0,
        "k_mg_per_100": 68.0,
        "na_mg_per_100": 21.0,
        "mg_mg_per_100": 5.9,
    },
}

# Compute latte_materno_fm85 as sum of breast milk + FM85
_LM = _LATTI_BASE["latte_materno"]
_FM = _LATTI_BASE["PreNidina FM85"]
_LATTI_BASE["latte_materno_fm85"] = {
    "kcal_per_100": _LM["kcal_per_100"] + _FM["kcal_per_100"],
    "prot_g_per_100": _LM["prot_g_per_100"] + _FM["prot_g_per_100"],
    "lip_g_per_100": _LM["lip_g_per_100"] + _FM["lip_g_per_100"],
    "cho_g_per_100": _LM["cho_g_per_100"] + _FM["cho_g_per_100"],
    "ca_mg_per_100": _LM["ca_mg_per_100"] + _FM["ca_mg_per_100"],
    "p_mg_per_100": _LM["p_mg_per_100"] + _FM["p_mg_per_100"],
    "k_mg_per_100": _LM["k_mg_per_100"] + _FM["k_mg_per_100"],
    "na_mg_per_100": _LM["na_mg_per_100"] + _FM["na_mg_per_100"],
    "mg_mg_per_100": _LM["mg_mg_per_100"] + _FM["mg_mg_per_100"],
}

LATTI = _LATTI_BASE

# Formula groupings for the LLM
FORMULA_GROUPS = {
    "breast_milk": ["latte_materno", "latte_materno_fm85"],
    "formula_1": [
        "Aptamil 1", "Humana 1", "Hipp 1", "NAN 1",
        "bbmilk 1", "Nidina 1", "N5 1", "Novalac 1",
    ],
    "formula_0_special": [
        "PreAptamil", "PreNAN", "PreNidina FM85", "Humana 0",
        "Humana 0-VLB", "BBmilk 0", "Hipp 0 Dr.Baby's",
        "N5 0 (Sterilfarma)", "Pregomin SP", "Nutramigen 1 LGG",
        "Nutramigen AA", "Allernova PRO", "Aminova",
        "Infatrini Peptisorb", "Heparon Junior",
        "NAN AR (Nestle)", "N5 AR (Sterilfarma)", "Humana AR",
    ],
}

# ---------------------------------------------------------------------------
# 5. Fluid requirements by weight category and day (IDRICO, lines 1310-1347)
# ---------------------------------------------------------------------------
IDRICO = {
    "term": {
        1: {"min": 40, "max": 60},
        2: {"min": 50, "max": 70},
        3: {"min": 60, "max": 80},
        4: {"min": 60, "max": 100},
        5: {"min": 100, "max": 140},
        6: {"min": 140, "max": 170},
        7: {"min": 140, "max": 170},
    },
    "prem_gt1500": {
        1: {"min": 60, "max": 80},
        2: {"min": 80, "max": 100},
        3: {"min": 100, "max": 120},
        4: {"min": 120, "max": 140},
        5: {"min": 140, "max": 160},
        6: {"min": 140, "max": 160},
        7: {"min": 140, "max": 160},
    },
    "prem_1000_1500": {
        1: {"min": 70, "max": 90},
        2: {"min": 90, "max": 110},
        3: {"min": 110, "max": 130},
        4: {"min": 130, "max": 150},
        5: {"min": 160, "max": 180},
        6: {"min": 160, "max": 180},
        7: {"min": 160, "max": 180},
    },
    "prem_lt1000": {
        1: {"min": 80, "max": 100},
        2: {"min": 100, "max": 120},
        3: {"min": 120, "max": 140},
        4: {"min": 140, "max": 160},
        5: {"min": 160, "max": 180},
        6: {"min": 160, "max": 180},
        7: {"min": 160, "max": 180},
    },
}

# ---------------------------------------------------------------------------
# 6. Vento nutrient requirements by day (FABBISOGNI_VENTO, lines 1370-1382)
# ---------------------------------------------------------------------------
FABBISOGNI_VENTO = {
    "glu": {1: 5, 2: 6, 3: 7, 4: 8, 5: 9, 6: 10, 7: 12},
    "prot": {1: 1.25, 2: 1.50, 3: 1.75, 4: 2.00, 5: 2.25, 6: 2.50, 7: 3.00},
    "lip": {1: 2.0, 2: 2.5, 3: 2.5, 4: 3.0, 5: 3.0, 6: 3.0, 7: 3.5},
    "ca": {1: 40, 2: 40, 3: 45, 4: 50, 5: 55, 6: 60, 7: 70},
    "p": {1: 3, 2: 20, 3: 30, 4: 35, 5: 40, 6: 45, 7: 55},
    "mg": {1: 0, 2: 0, 3: 5, 4: 5, 5: 5, 6: 5, 7: 5},
    "na": {1: 0.2, 2: 1.3, 3: 1.9, 4: 2.2, 5: 2.5, 6: 2.8, 7: 3.4},
    "k": {1: 0, 2: 0, 3: 2, 4: 2, 5: 2.5, 6: 3, 7: 3.5},
    "cl": {1: 0, 2: 0, 3: 0, 4: 2, 5: 2.5, 6: 3, 7: 3.5},
}

# ---------------------------------------------------------------------------
# 7. Glucose requirements by weight band (FABBISOGNI_GLU_PESO, lines 1388-1416)
# ---------------------------------------------------------------------------
FABBISOGNI_GLU_PESO = {
    "prem_lt1500": {1: 4, 2: 6, 3: 8, 4: 10, 5: 12, 6: 14, 7: 16},
    "prem_1500_2000": {1: 4, 2: 6, 3: 8, 4: 10, 5: 12, 6: 14, 7: 15},
    "sopra_2000": {1: 4, 2: 6, 3: 8, 4: 10, 5: 12, 6: 13, 7: 14},
}

# Solution display names for pharmacy print
SOLUTION_LABELS = {
    "trof6": "Trofamine 6%",
    "g10": "Glucosio 10%",
    "g33": "Glucosio 33%",
    "g50": "Glucosio 50%",
    "il10": "Intralipid 10%",
    "il20": "Intralipid 20%",
    "cl20": "Clinoleic 20%",
    "nacl2": "NaCl 2 mEq/ml",
    "naac3": "Na Acetato 3M (3 mEq/ml)",
    "glycophos-na": "Glycophos (Na + P)",
    "esafos-na": "Esafosfina (Na + P)",
    "kcl2": "KCl 2 mEq/ml",
    "k3m": "K 3M (3 mEq/ml)",
    "caglu10": "Ca gluconato 10%",
    "mgso410": "Mg solfato 10%",
    "glycophos-p": "Glycophos",
    "esafos-p": "Esafosfina",
}


# ===========================================================================
# LOOKUP HELPER FUNCTIONS
# ===========================================================================

def _get_idrico_range(weight_kg: float, day: int) -> Optional[dict]:
    """Return fluid requirement range (ml/kg/day) for weight and day of life."""
    if not weight_kg or not day:
        return None
    d = max(1, min(7, round(day)))
    if weight_kg >= 2.5:
        cat = "term"
    elif weight_kg > 1.5:
        cat = "prem_gt1500"
    elif weight_kg >= 1.0:
        cat = "prem_1000_1500"
    else:
        cat = "prem_lt1000"
    tab = IDRICO.get(cat, {})
    return tab.get(d)


def _get_fabbisogno_vento(nutrient: str, day: int, weight_kg: float = 0) -> Optional[float]:
    """Return recommended intake (per kg) for a nutrient on a given day.

    For glucose, also considers weight band.
    """
    g = int(day)
    if g < 1:
        g = 1
    if g > 7:
        g = 7

    if nutrient == "glu" and weight_kg > 0:
        if weight_kg < 1.5:
            cat = "prem_lt1500"
        elif weight_kg <= 2.0:
            cat = "prem_1500_2000"
        else:
            cat = "sopra_2000"
        tab = FABBISOGNI_GLU_PESO.get(cat, {})
        return tab.get(g) or FABBISOGNI_VENTO.get("glu", {}).get(g)

    tab = FABBISOGNI_VENTO.get(nutrient, {})
    return tab.get(g)


def _confronto_fabbisogno(value_per_kg: float, target_per_kg: Optional[float]) -> str:
    """Return 'green', 'yellow', 'red', or '-' based on deviation from target."""
    if not target_per_kg or target_per_kg <= 0 or not value_per_kg or value_per_kg <= 0:
        return "-"
    diff = abs(value_per_kg - target_per_kg) / target_per_kg
    if diff >= 0.50:
        return "red"
    elif diff >= 0.25:
        return "yellow"
    else:
        return "green"


def _fmt(val: float, decimals: int) -> str:
    """Format a float to fixed decimals, returns '-' for NaN."""
    if val is None or val != val:
        return "-"
    return f"{val:.{decimals}f}"


# ===========================================================================
# COMPUTE FUNCTIONS (pure, no side effects)
# ===========================================================================

def _compute_milk_apporti(milk_type: str, milk_ml: float, weight_kg: float) -> dict:
    """Compute per-kg nutrient contributions from milk/formula.

    Returns dict with keys: prot_gkg, glu_gkg, lip_gkg, kcal, kcal_kg,
    ca_mgkg, p_mgkg, na_mEqkg, k_mEqkg, mg_mEqkg, vol_mlkg.
    All zero if no milk selected.
    """
    empty = {
        "prot_gkg": 0, "glu_gkg": 0, "lip_gkg": 0,
        "kcal": 0, "kcal_kg": 0,
        "ca_mgkg": 0, "p_mgkg": 0,
        "na_mEqkg": 0, "k_mEqkg": 0, "mg_mEqkg": 0,
        "vol_mlkg": 0,
    }
    if not milk_type or milk_ml <= 0 or weight_kg <= 0:
        return empty
    d = LATTI.get(milk_type)
    if not d:
        return empty

    factor = milk_ml / 100.0
    prot_g = d["prot_g_per_100"] * factor
    lip_g = d["lip_g_per_100"] * factor
    cho_g = d["cho_g_per_100"] * factor
    kcal = d["kcal_per_100"] * factor

    ca_mg = d["ca_mg_per_100"] * factor
    p_mg = d["p_mg_per_100"] * factor
    na_mg = d["na_mg_per_100"] * factor
    k_mg = d["k_mg_per_100"] * factor
    mg_mg = d["mg_mg_per_100"] * factor

    return {
        "prot_gkg": prot_g / weight_kg,
        "glu_gkg": cho_g / weight_kg,
        "lip_gkg": lip_g / weight_kg,
        "kcal": kcal,
        "kcal_kg": kcal / weight_kg,
        "ca_mgkg": ca_mg / weight_kg,
        "p_mgkg": p_mg / weight_kg,
        "na_mEqkg": (na_mg / 23.0) / weight_kg,
        "k_mEqkg": (k_mg / 39.0) / weight_kg,
        "mg_mEqkg": (mg_mg / 12.0) / weight_kg,
        "vol_mlkg": milk_ml / weight_kg,
    }


def _compute_vitamin_ml(
    vitalipid_active: bool, vitalipid_ml: float,
    soluvit_active: bool, soluvit_ml: float,
    peditrace_active: bool, peditrace_ml: float,
) -> float:
    """Return total vitamin/trace element volume in ml."""
    total = 0.0
    if vitalipid_active:
        total += vitalipid_ml
    if soluvit_active:
        total += soluvit_ml
    if peditrace_active:
        total += peditrace_ml
    return total


def _compute_numeta(
    numeta_type: str, numeta_h2o: float,
    weight_kg: float, fluid_target: float,
    milk_ml: float, tot_vit_ml: float,
) -> dict:
    """Compute Numeta G13E apporti and volume info.

    Returns dict with: aa, glu, lip, na, k, mg, ca, p, kcal, osm, vol (ml infused in 24h).
    All zero if numeta_type is empty.
    """
    empty = {
        "aa": 0, "glu": 0, "lip": 0,
        "na": 0, "k": 0, "mg": 0,
        "ca": 0, "p": 0, "kcal": 0,
        "osm": 0, "vol": 0,
        "bag_vol": 0, "vol_tot_sacca": 0,
    }
    if not numeta_type:
        return empty
    if not weight_kg or not fluid_target:
        return empty

    comp = NUMETA.get(numeta_type)
    if not comp:
        return empty

    bag_vol = 300 if numeta_type == "g13_300" else 240
    h2o = max(0, numeta_h2o)
    vol_tot_sacca = bag_vol + h2o

    target_tot_ml = fluid_target * weight_kg
    pn_target_ml = max(0, target_tot_ml - milk_ml)

    pn_mix_ml = max(0, pn_target_ml - tot_vit_ml)
    frac = pn_mix_ml / vol_tot_sacca if vol_tot_sacca > 0 and pn_mix_ml > 0 else 0

    # Apporti a sacca intera
    aa_bag = comp["aa_g_per_ml"] * bag_vol
    glu_bag = comp["glu_g_per_ml"] * bag_vol
    lip_bag = comp["lip_g_per_ml"] * bag_vol
    na_bag = comp["na_mEq_per_ml"] * bag_vol
    k_bag = comp["k_mEq_per_ml"] * bag_vol
    mg_bag = comp["mg_mEq_per_ml"] * bag_vol
    ca_bag = comp["ca_mg_per_ml"] * bag_vol
    p_bag = comp["p_mg_per_ml"] * bag_vol
    kcal_bag = comp["kcal_per_ml"] * bag_vol

    # Applico la frazione realmente infusa
    w = weight_kg
    return {
        "aa": (aa_bag * frac) / w if w > 0 else 0,
        "glu": (glu_bag * frac) / w if w > 0 else 0,
        "lip": (lip_bag * frac) / w if w > 0 else 0,
        "na": (na_bag * frac) / w if w > 0 else 0,
        "k": (k_bag * frac) / w if w > 0 else 0,
        "mg": (mg_bag * frac) / w if w > 0 else 0,
        "ca": (ca_bag * frac) / w if w > 0 else 0,
        "p": (p_bag * frac) / w if w > 0 else 0,
        "kcal": (kcal_bag * frac) / w if w > 0 else 0,
        "osm": comp["osm_mOsm_per_L"],
        "vol": pn_target_ml,
        "bag_vol": bag_vol,
        "vol_tot_sacca": vol_tot_sacca,
    }


def _compute_osmolarity_classic(
    solution_keys_vols: list,
    acqua_ml: float,
) -> Optional[float]:
    """Compute final osmolarity for classic PN bag after water dilution.

    solution_keys_vols: list of (solution_key, volume_ml) tuples.
    Returns mOsm/L or None if no solutions.
    """
    vol_sol_ml = 0.0
    somma_osm_per_vol = 0.0
    for key, vol in solution_keys_vols:
        osm = OSMOL_SOL.get(key)
        if not osm or not vol or vol <= 0:
            continue
        vol_sol_ml += vol
        somma_osm_per_vol += osm * vol
    if vol_sol_ml <= 0:
        return None
    osm_mix = somma_osm_per_vol / vol_sol_ml
    vol_tot = vol_sol_ml + acqua_ml
    return osm_mix * (vol_sol_ml / vol_tot) if vol_tot > 0 else osm_mix


def _compute_safety(
    osmolarity: Optional[float],
    tot_ca_mgkg: float,
    tot_p_mgkg: float,
    numeta_type: str,
    milk_apporti: dict,
    weight_kg: float,
    pn_target_ml: float,
    day_of_life: int,
    tot_aa_gkg: float,
    tot_glu_gkg: float,
    tot_lip_gkg: float,
    tot_na_meqkg: float,
    tot_k_meqkg: float,
    tot_mg_meqkg: float,
    tot_ca_mgkg_s: float,
    tot_p_mgkg_s: float,
) -> dict:
    """Compute safety checks: osmolarity access, Ca:P ratio, Numeta dilution advice."""
    safety = {}

    # Osmolarity access
    if osmolarity is not None:
        if osmolarity > 900:
            badge = "red"
            access = "Central venous access only"
        elif osmolarity > 600:
            badge = "yellow"
            access = "Elevated, evaluate central access"
        else:
            badge = "green"
            access = "Compatible with peripheral access"
        safety["osmolarity"] = {
            "value_mOsm_L": round(osmolarity),
            "badge": badge,
            "access": access,
        }

    # Ca:P ratio
    if tot_ca_mgkg > 0 and tot_p_mgkg > 0:
        ratio = tot_ca_mgkg / tot_p_mgkg
        if ratio < 1.0 or ratio > 2.0:
            badge = "red"
            msg = "Out of range: possible instability/precipitation risk"
        elif ratio < 1.3 or ratio > 1.7:
            badge = "yellow"
            msg = "Borderline: consider adjusting Ca/P"
        else:
            badge = "green"
            msg = "Ca:P ratio in recommended range"
        safety["ca_p_ratio"] = {
            "value": round(ratio, 2),
            "badge": badge,
            "message": msg,
        }

    # Numeta dilution advice
    if numeta_type:
        comp = NUMETA.get(numeta_type)
        bag_vol = 300 if numeta_type == "g13_300" else 240
        if comp and weight_kg > 0 and pn_target_ml > 0 and bag_vol > 0:
            nutrient_checks = [
                (milk_apporti["prot_gkg"], "prot", tot_aa_gkg, comp["aa_g_per_ml"], "proteins"),
                (milk_apporti["glu_gkg"], "glu", tot_glu_gkg, comp["glu_g_per_ml"], "glucose"),
                (milk_apporti["lip_gkg"], "lip", tot_lip_gkg, comp["lip_g_per_ml"], "lipids"),
                (milk_apporti["na_mEqkg"], "na", tot_na_meqkg, comp["na_mEq_per_ml"], "sodium"),
                (milk_apporti["k_mEqkg"], "k", tot_k_meqkg, comp["k_mEq_per_ml"], "potassium"),
                (milk_apporti["mg_mEqkg"], "mg", tot_mg_meqkg, comp["mg_mEq_per_ml"], "magnesium"),
                (milk_apporti["ca_mgkg"], "ca", tot_ca_mgkg_s, comp["ca_mg_per_ml"], "calcium"),
                (milk_apporti["p_mgkg"], "p", tot_p_mgkg_s, comp["p_mg_per_ml"], "phosphorus"),
            ]
            problems = []
            problems_latte = []
            candidates = []

            for latte_val, fab_key, tot_now, comp_per_ml, label in nutrient_checks:
                target = _get_fabbisogno_vento(fab_key, day_of_life, weight_kg)
                if not target or target <= 0 or not tot_now or tot_now <= target:
                    continue
                if label not in problems:
                    problems.append(label)
                if latte_val >= target and label not in problems_latte:
                    problems_latte.append(label)
                # Compute candidate H2O
                if latte_val >= target:
                    continue
                k_val = comp_per_ml * bag_vol * pn_target_ml / weight_kg
                den = target - latte_val
                if den <= 0:
                    continue
                res = (k_val / den) - bag_vol
                if res > 0:
                    candidates.append(res)

            if candidates:
                h2o_sug = max(candidates)
                if 0 < h2o_sug < 400:
                    rounded = round(h2o_sug / 5) * 5
                    txt = f"{rounded:.0f} ml H2O total in the bag"
                    if problems:
                        txt += " -- critical nutrients considered: " + ", ".join(problems)
                elif h2o_sug >= 400:
                    txt = "> 400 ml H2O (consider custom pharmacy PN)"
                    if problems:
                        txt += " -- critical nutrients: " + ", ".join(problems)
                else:
                    txt = "-- (apporti already within range for Numeta + milk)"
            else:
                if not problems:
                    txt = "-- (apporti already within range for Numeta + milk)"
                elif problems_latte:
                    txt = ("Cannot correct with Numeta dilution alone: milk quota "
                           "already exceeds range for " + ", ".join(problems_latte))
                else:
                    txt = ("Cannot find effective dilution with Numeta. "
                           "Nutrients still above range: " + ", ".join(problems))
            safety["numeta_dilution_advice"] = txt

    return safety


# ===========================================================================
# PYDANTIC MODELS
# ===========================================================================

class PNRequest(BaseModel):
    """Input model for the calculate_pn tool."""

    # Patient data
    weight_kg: float = Field(description="Patient weight in kg (REQUIRED, must be > 0)")
    day_of_life: int = Field(default=1, description="Day of life (1-7, clamped)")
    gestational_age: str = Field(default="", description="Gestational age e.g. '30+4'")
    patient_name: str = Field(default="", description="Patient name (informational)")
    prescription_date: str = Field(default="", description="Prescription date YYYY-MM-DD")
    notes: str = Field(default="", description="Optional clinical notes")

    # Mode
    mode: Literal["vol", "apporti"] = Field(
        default="apporti",
        description="'vol': provide volumes (ml), get g/kg. "
                    "'apporti': provide targets (g/kg), get volumes.",
    )

    # Fluids
    fluid_target_mlkg: float = Field(
        default=0,
        description="Fluid target in ml/kg/day. 0 = auto-compute from IDRICO table.",
    )
    tubing_ml: float = Field(
        default=20,
        description="Tubing/deflussore volume in ml (classic PN only, default 20).",
    )

    # Milk/Formula (only one group active)
    milk_type: str = Field(
        default="",
        description="Formula key from LATTI table (e.g. 'latte_materno', 'Aptamil 1'). Empty = no milk.",
    )
    milk_ml: float = Field(default=0, description="Milk volume in ml/day")

    # Numeta (overrides classic PN entirely)
    numeta_type: Literal["", "g13_240", "g13_300"] = Field(
        default="",
        description="Numeta G13E type. '' = not used. "
                    "'g13_300' = with lipids (300ml). "
                    "'g13_240' = without lipids (240ml).",
    )
    numeta_h2o_ml: float = Field(default=110, description="H2O added to Numeta bag (ml)")

    # Classic PN: Amino acids
    aa_solution: str = Field(default="trof6", description="AA solution key")
    aa_ml: float = Field(default=0, description="AA volume ml (vol mode)")
    aa_target_gkg: float = Field(default=0, description="Protein target g/kg (apporti mode)")

    # Glucose
    glu_solution: str = Field(default="g33", description="Glucose solution key (g10/g33/g50)")
    glu_ml: float = Field(default=0, description="Glucose volume ml (vol mode)")
    glu_target_gkg: float = Field(default=0, description="Glucose target g/kg (apporti mode)")

    # Lipids
    lip_solution: str = Field(default="il20", description="Lipid solution key")
    lip_ml: float = Field(default=0, description="Lipid volume ml (vol mode)")
    lip_target_gkg: float = Field(default=0, description="Lipid target g/kg (apporti mode)")

    # Sodium
    na_solution: str = Field(default="nacl2", description="Na solution key")
    na_ml: float = Field(default=0, description="Na volume ml (vol mode)")
    na_target_meqkg: float = Field(default=0, description="Na target mEq/kg (apporti mode)")

    # Potassium
    k_solution: str = Field(default="kcl2", description="K solution key")
    k_ml: float = Field(default=0, description="K volume ml (vol mode)")
    k_target_meqkg: float = Field(default=0, description="K target mEq/kg (apporti mode)")

    # Calcium
    ca_solution: str = Field(default="caglu10", description="Ca solution key")
    ca_ml: float = Field(default=0, description="Ca volume ml (vol mode)")
    ca_target_mgkg: float = Field(default=0, description="Ca target mg/kg (apporti mode)")

    # Magnesium
    mg_solution: str = Field(default="mgso410", description="Mg solution key")
    mg_ml: float = Field(default=0, description="Mg volume ml (vol mode)")
    mg_target_meqkg: float = Field(default=0, description="Mg target mEq/kg (apporti mode)")

    # Phosphorus
    p_solution: str = Field(default="esafos-p", description="P solution key")
    p_ml: float = Field(default=0, description="P volume ml (vol mode)")
    p_target_mgkg: float = Field(default=0, description="P target mg/kg (apporti mode)")

    # Vitamins / trace elements
    vitalipid_active: bool = Field(default=False, description="Include Vitalipid (fat-soluble vitamins)")
    vitalipid_ml: float = Field(default=0, description="Vitalipid volume ml/day")
    soluvit_active: bool = Field(default=False, description="Include Soluvit (water-soluble vitamins)")
    soluvit_ml: float = Field(default=0, description="Soluvit volume ml/day")
    peditrace_active: bool = Field(default=False, description="Include Peditrace (trace elements)")
    peditrace_ml: float = Field(default=0, description="Peditrace volume ml/day")


# ===========================================================================
# MAIN CALCULATION ENGINE
# ===========================================================================

def _calculate_pn(req: PNRequest) -> dict:
    """Core calculation. Returns the full result dict."""
    peso = req.weight_kg
    if peso <= 0:
        return {"error": "weight_kg must be > 0"}

    mode = req.mode
    numeta_attiva = req.numeta_type != ""

    # --- Resolve fluid target ---
    liq_target = req.fluid_target_mlkg
    idrico_range = _get_idrico_range(peso, req.day_of_life)
    idrico_hint = None
    if idrico_range:
        idrico_hint = f"{idrico_range['min']}-{idrico_range['max']} ml/kg/die"
    if not liq_target and idrico_range:
        liq_target = idrico_range["min"]

    # --- Milk apporti ---
    milk = _compute_milk_apporti(req.milk_type, req.milk_ml, peso)

    # --- Vitamins total volume ---
    tot_vit_ml = _compute_vitamin_ml(
        req.vitalipid_active, req.vitalipid_ml,
        req.soluvit_active, req.soluvit_ml,
        req.peditrace_active, req.peditrace_ml,
    )

    # --- Numeta ---
    numeta = _compute_numeta(
        req.numeta_type, req.numeta_h2o_ml,
        peso, liq_target, req.milk_ml, tot_vit_ml,
    )

    # --- Classic PN computation ---
    aa_g = 0.0; aa_gkg = 0.0; n_g = 0.0; aa_ml_res = 0.0
    glu_gkg = 0.0; glu_kcal = 0.0; glu_kcalkg = 0.0; glu_ml_res = 0.0
    lip_gkg = 0.0; lip_kcal = 0.0; lip_kcalkg = 0.0; lip_ml_res = 0.0
    na_mEqkg = 0.0; na_ml_res = 0.0
    k_mEqkg = 0.0; k_ml_res = 0.0
    ca_mgkg = 0.0; ca_ml_res = 0.0
    mg_mEqkg = 0.0; mg_ml_res = 0.0
    p_mgkg = 0.0; p_ml_res = 0.0
    cl_mEq = 0.0; cl_mEqkg = 0.0
    tot_ml_pn = 0.0

    # Osmolarity accumulator: list of (solution_key, vol_ml)
    osm_keys_vols = []

    if not numeta_attiva:
        # --- Amino acids ---
        aa_c = CONC["aa"].get(req.aa_solution)
        if aa_c:
            aa_ml_val = req.aa_ml
            if mode == "apporti":
                t_pn = max(0, req.aa_target_gkg - milk["prot_gkg"]) if peso > 0 else 0
                if peso > 0 and t_pn > 0:
                    aa_ml_val = (t_pn * peso) / aa_c["aa_g_per_ml"]
                else:
                    aa_ml_val = 0
            tot_ml_pn += aa_ml_val
            aa_ml_res = aa_ml_val
            g_aa = aa_ml_val * aa_c["aa_g_per_ml"]
            aa_g = g_aa
            aa_gkg = g_aa / peso if peso > 0 else 0
            n_g = g_aa * aa_c["n_from_aa"]
            osm_keys_vols.append((req.aa_solution, aa_ml_val))

        # --- Glucose ---
        glu_c = CONC["glu"].get(req.glu_solution)
        if glu_c:
            glu_ml_val = req.glu_ml
            if mode == "apporti":
                t_pn = max(0, req.glu_target_gkg - milk["glu_gkg"]) if peso > 0 else 0
                if peso > 0 and t_pn > 0:
                    glu_ml_val = (t_pn * peso) / glu_c["glu_g_per_ml"]
                else:
                    glu_ml_val = 0
            tot_ml_pn += glu_ml_val
            glu_ml_res = glu_ml_val
            g_glu = glu_ml_val * glu_c["glu_g_per_ml"]
            glu_gkg = g_glu / peso if peso > 0 else 0
            glu_kcal = g_glu * 3.4  # JS uses 3.4 kcal/g for glucose
            glu_kcalkg = glu_kcal / peso if peso > 0 else 0
            osm_keys_vols.append((req.glu_solution, glu_ml_val))

        # --- Lipids ---
        lip_c = CONC["lip"].get(req.lip_solution)
        if lip_c:
            lip_ml_val = req.lip_ml
            if mode == "apporti":
                t_pn = max(0, req.lip_target_gkg - milk["lip_gkg"]) if peso > 0 else 0
                if peso > 0 and t_pn > 0:
                    lip_ml_val = (t_pn * peso) / lip_c["lip_g_per_ml"]
                else:
                    lip_ml_val = 0
            tot_ml_pn += lip_ml_val
            lip_ml_res = lip_ml_val
            g_lip = lip_ml_val * lip_c["lip_g_per_ml"]
            lip_gkg = g_lip / peso if peso > 0 else 0
            lip_kcal = g_lip * 10  # JS uses 10 kcal/g for lipids
            lip_kcalkg = lip_kcal / peso if peso > 0 else 0
            osm_keys_vols.append((req.lip_solution, lip_ml_val))

        # --- Sodium ---
        na_c = CONC["na"].get(req.na_solution)
        if na_c:
            na_ml_val = req.na_ml
            if mode == "apporti":
                t_pn = max(0, req.na_target_meqkg - milk["na_mEqkg"]) if peso > 0 else 0
                if peso > 0 and t_pn > 0 and na_c["na_mEq_per_ml"]:
                    na_ml_val = (t_pn * peso) / na_c["na_mEq_per_ml"]
                else:
                    na_ml_val = 0
            tot_ml_pn += na_ml_val
            na_ml_res = na_ml_val
            mEq_na = (na_c.get("na_mEq_per_ml") or 0) * na_ml_val
            mEq_cl_from_na = (na_c.get("cl_mEq_per_ml") or 0) * na_ml_val
            na_mEqkg = mEq_na / peso if peso > 0 else 0
            cl_mEq += mEq_cl_from_na
            osm_keys_vols.append((req.na_solution, na_ml_val))

        # --- Potassium ---
        k_c = CONC["k"].get(req.k_solution)
        if k_c:
            k_ml_val = req.k_ml
            if mode == "apporti":
                t_pn = max(0, req.k_target_meqkg - milk["k_mEqkg"]) if peso > 0 else 0
                if peso > 0 and t_pn > 0 and k_c["k_mEq_per_ml"]:
                    k_ml_val = (t_pn * peso) / k_c["k_mEq_per_ml"]
                else:
                    k_ml_val = 0
            tot_ml_pn += k_ml_val
            k_ml_res = k_ml_val
            mEq_k = (k_c.get("k_mEq_per_ml") or 0) * k_ml_val
            mEq_cl_from_k = (k_c.get("cl_mEq_per_ml") or 0) * k_ml_val
            k_mEqkg = mEq_k / peso if peso > 0 else 0
            cl_mEq += mEq_cl_from_k
            osm_keys_vols.append((req.k_solution, k_ml_val))

        # --- Calcium ---
        ca_c = CONC["ca"].get(req.ca_solution)
        if ca_c:
            ca_ml_val = req.ca_ml
            if mode == "apporti":
                t_pn = max(0, req.ca_target_mgkg - milk["ca_mgkg"]) if peso > 0 else 0
                if peso > 0 and t_pn > 0 and ca_c["ca_mg_per_ml"]:
                    ca_ml_val = (t_pn * peso) / ca_c["ca_mg_per_ml"]
                else:
                    ca_ml_val = 0
            tot_ml_pn += ca_ml_val
            ca_ml_res = ca_ml_val
            mg_ca = (ca_c.get("ca_mg_per_ml") or 0) * ca_ml_val
            ca_mgkg = mg_ca / peso if peso > 0 else 0
            osm_keys_vols.append((req.ca_solution, ca_ml_val))

        # --- Magnesium ---
        mg_c = CONC["mg"].get(req.mg_solution)
        if mg_c:
            mg_ml_val = req.mg_ml
            if mode == "apporti":
                t_pn = max(0, req.mg_target_meqkg - milk["mg_mEqkg"]) if peso > 0 else 0
                if peso > 0 and t_pn > 0 and mg_c["mg_mEq_per_ml"]:
                    mg_ml_val = (t_pn * peso) / mg_c["mg_mEq_per_ml"]
                else:
                    mg_ml_val = 0
            tot_ml_pn += mg_ml_val
            mg_ml_res = mg_ml_val
            mEq_mg = (mg_c.get("mg_mEq_per_ml") or 0) * mg_ml_val
            mg_mEqkg = mEq_mg / peso if peso > 0 else 0
            osm_keys_vols.append((req.mg_solution, mg_ml_val))

        # --- Phosphorus ---
        p_c = CONC["p"].get(req.p_solution)
        if p_c:
            p_ml_val = req.p_ml
            if mode == "apporti":
                t_pn = max(0, req.p_target_mgkg - milk["p_mgkg"]) if peso > 0 else 0
                if peso > 0 and t_pn > 0 and p_c["p_mg_per_ml"]:
                    p_ml_val = (t_pn * peso) / p_c["p_mg_per_ml"]
                else:
                    p_ml_val = 0
            tot_ml_pn += p_ml_val
            p_ml_res = p_ml_val
            mg_p = (p_c.get("p_mg_per_ml") or 0) * p_ml_val
            p_mgkg = mg_p / peso if peso > 0 else 0
            osm_keys_vols.append((req.p_solution, p_ml_val))

        # Vitamins volume
        tot_ml_pn += tot_vit_ml

        # Add soluvit to osmolarity if active
        if req.soluvit_active and req.soluvit_ml > 0:
            osm_keys_vols.append(("soluvit", req.soluvit_ml))

    # --- Kcal ---
    tot_kcal_pn = glu_kcal + lip_kcal
    tot_kcal_pn_kg = tot_kcal_pn / peso if peso > 0 else 0

    # --- Numeta overrides ---
    if numeta_attiva and numeta["vol"] > 0:
        aa_gkg = numeta["aa"]
        glu_gkg = numeta["glu"]
        lip_gkg = numeta["lip"]
        tot_kcal_pn_kg = numeta["kcal"]
        tot_kcal_pn = tot_kcal_pn_kg * peso if peso > 0 else 0
        glu_kcalkg = numeta["glu"] * 3.4 if numeta["glu"] else 0
        lip_kcalkg = numeta["lip"] * 10 if numeta["lip"] else 0
        na_mEqkg = numeta["na"]
        k_mEqkg = numeta["k"]
        mg_mEqkg = numeta["mg"]
        ca_mgkg = numeta["ca"]
        p_mgkg = numeta["p"]

    # --- Totals PN + milk ---
    tot_aa_gkg = aa_gkg + milk["prot_gkg"]
    tot_glu_gkg = glu_gkg + milk["glu_gkg"]
    tot_lip_gkg = lip_gkg + milk["lip_gkg"]
    tot_kcal_tot = tot_kcal_pn + milk["kcal"]
    tot_kcal_tot_kg = tot_kcal_tot / peso if peso > 0 else 0

    tot_na_meqkg = na_mEqkg + milk["na_mEqkg"]
    tot_k_meqkg = k_mEqkg + milk["k_mEqkg"]
    tot_mg_meqkg = mg_mEqkg + milk["mg_mEqkg"]
    tot_ca_mgkg_val = ca_mgkg + milk["ca_mgkg"]
    tot_p_mgkg_val = p_mgkg + milk["p_mgkg"]

    cl_mEqkg = cl_mEq / peso if peso > 0 else 0

    # --- Volume / water ---
    vol_deflussore = 0 if numeta_attiva else max(0, req.tubing_ml)
    target_tot_ml = (liq_target * peso) if (liq_target > 0 and peso > 0) else 0
    pn_target_ml = max(0, target_tot_ml - req.milk_ml) if target_tot_ml > 0 else 0

    acqua_ml = 0.0
    if pn_target_ml > 0:
        acqua_ml = max(0, pn_target_ml - tot_ml_pn)

    pn_sacca_vol_ml = tot_ml_pn + acqua_ml

    # --- Osmolarity ---
    osm_final = None
    if numeta_attiva:
        comp = NUMETA.get(req.numeta_type)
        bv = 300 if req.numeta_type == "g13_300" else 240
        h2o_val = max(0, req.numeta_h2o_ml)
        if comp and bv > 0 and (bv + h2o_val) > 0:
            osm_final = comp["osm_mOsm_per_L"] * (bv / (bv + h2o_val))
    else:
        osm_final = _compute_osmolarity_classic(osm_keys_vols, acqua_ml)

    # --- Fluid summaries ---
    tot_liquidi_clinici = pn_sacca_vol_ml + req.milk_ml
    tot_liquidi_clinici_kg = tot_liquidi_clinici / peso if peso > 0 else 0
    pn_con_defl = pn_sacca_vol_ml + vol_deflussore
    tot_liquidi_con_defl = pn_con_defl + req.milk_ml
    liq_residuo = (liq_target - tot_liquidi_clinici_kg) if (liq_target > 0 and peso > 0) else 0
    vel_infusione = pn_sacca_vol_ml / 24 if pn_sacca_vol_ml > 0 else 0

    # --- Vento badges ---
    day = req.day_of_life
    badges = {}
    for key, tot_val, vento_key in [
        ("prot", tot_aa_gkg, "prot"),
        ("glu", tot_glu_gkg, "glu"),
        ("lip", tot_lip_gkg, "lip"),
        ("na", tot_na_meqkg, "na"),
        ("k", tot_k_meqkg, "k"),
        ("ca", tot_ca_mgkg_val, "ca"),
        ("p", tot_p_mgkg_val, "p"),
        ("mg", tot_mg_meqkg, "mg"),
    ]:
        target = _get_fabbisogno_vento(vento_key, day, peso)
        badges[key] = {
            "value": round(tot_val, 2),
            "target": round(target, 2) if target else None,
            "badge": _confronto_fabbisogno(tot_val, target),
        }

    # --- Safety ---
    # Adjust displayed volumes for Numeta
    acqua_mostrata = acqua_ml
    sacca_netta_mostrata = pn_sacca_vol_ml
    if numeta_attiva:
        acqua_mostrata = max(0, req.numeta_h2o_ml)
        sacca_netta_mostrata = pn_target_ml

    safety = _compute_safety(
        osm_final, tot_ca_mgkg_val, tot_p_mgkg_val,
        req.numeta_type,
        milk, peso, pn_target_ml, day,
        tot_aa_gkg, tot_glu_gkg, tot_lip_gkg,
        tot_na_meqkg, tot_k_meqkg, tot_mg_meqkg,
        tot_ca_mgkg_val, tot_p_mgkg_val,
    )

    # --- Solutions list for volumes section ---
    solutions_list = []
    if not numeta_attiva:
        for label, ml_val in [
            ("Trofamine 6%", aa_ml_res),
            (SOLUTION_LABELS.get(req.glu_solution, req.glu_solution), glu_ml_res),
            (SOLUTION_LABELS.get(req.lip_solution, req.lip_solution), lip_ml_res),
            (SOLUTION_LABELS.get(req.na_solution, req.na_solution), na_ml_res),
            (SOLUTION_LABELS.get(req.k_solution, req.k_solution), k_ml_res),
            (SOLUTION_LABELS.get(req.ca_solution, req.ca_solution), ca_ml_res),
            (SOLUTION_LABELS.get(req.mg_solution, req.mg_solution), mg_ml_res),
            (SOLUTION_LABELS.get(req.p_solution, req.p_solution), p_ml_res),
        ]:
            if ml_val > 0.01:
                solutions_list.append({"name": label, "ml": round(ml_val, 1)})
        if req.vitalipid_active and req.vitalipid_ml > 0:
            solutions_list.append({"name": "Vitalipid bambini", "ml": round(req.vitalipid_ml, 1)})
        if req.soluvit_active and req.soluvit_ml > 0:
            solutions_list.append({"name": "Soluvit", "ml": round(req.soluvit_ml, 1)})
        if req.peditrace_active and req.peditrace_ml > 0:
            solutions_list.append({"name": "Peditrace", "ml": round(req.peditrace_ml, 1)})

    # --- Pharmacy print ---
    patient_info = (
        f"Patient: {req.patient_name or '-'}\n"
        f"GA: {req.gestational_age or '-'}\n"
        f"Weight: {_fmt(peso, 2)} kg\n"
        f"Day of life: {req.day_of_life or '-'}\n"
        f"Date: {req.prescription_date or '-'}\n"
        f"Notes: {req.notes or '-'}"
    )

    if numeta_attiva:
        tipo_numeta = req.numeta_type
        label_numeta = "Numeta G13E 300 ml" if tipo_numeta == "g13_300" else "Numeta G13E 240 ml"
        vit_lines = ""
        if req.vitalipid_active and req.vitalipid_ml > 0:
            vit_lines += f"\n  Vitamine liposolubili: {_fmt(req.vitalipid_ml, 1)} ml"
        if req.soluvit_active and req.soluvit_ml > 0:
            vit_lines += f"\n  Vitamine idrosolubili: {_fmt(req.soluvit_ml, 1)} ml"
        if req.peditrace_active and req.peditrace_ml > 0:
            vit_lines += f"\n  Oligoelementi: {_fmt(req.peditrace_ml, 1)} ml"

        osm_teor = NUMETA.get(tipo_numeta, {}).get("osm_mOsm_per_L")
        pharmacy = (
            f"OmniNeo -- Parenteral Nutrition Prescription -- Pharmacy\n"
            f"\n{patient_info}\n"
            f"\nNumeta G13\n"
            f"  Preparation: {label_numeta}\n"
            f"  H2O to add: {_fmt(acqua_mostrata, 1)} ml"
            f"{vit_lines}\n"
            f"  Theoretical osmolarity: {_fmt(osm_teor, 0) if osm_teor else '-'} mOsm/L\n"
            f"  Final osmolarity: {_fmt(osm_final, 0) if osm_final else '-'} mOsm/L\n"
            f"  Infusion rate: {_fmt(vel_infusione, 2)} ml/h\n"
            f"\nDoctor signature: ________________________\n"
            f"Nurse signature:  ________________________"
        )
    else:
        # Classic PN pharmacy print with tubing scaling
        factor = (pn_sacca_vol_ml + vol_deflussore) / pn_sacca_vol_ml if (
            not numeta_attiva and pn_sacca_vol_ml > 0 and vol_deflussore > 0
        ) else 1.0

        vol_lines = ""
        for s in solutions_list:
            scaled_ml = s["ml"] * factor
            vol_lines += f"  {s['name']}: {_fmt(scaled_ml, 1)} ml\n"

        acqua_stampa = acqua_ml * factor
        sacca_stampa = pn_sacca_vol_ml * factor

        pharmacy = (
            f"OmniNeo -- Parenteral Nutrition Prescription -- Pharmacy\n"
            f"\n{patient_info}\n"
            f"\nPN Solution Volumes:\n"
            f"{vol_lines}"
            f"  Sterile water: {_fmt(acqua_stampa, 1)} ml\n"
            f"  Total PN bag: {_fmt(sacca_stampa, 1)} ml\n"
        )
        if osm_final is not None:
            pharmacy += f"  Final osmolarity: {_fmt(osm_final, 0)} mOsm/L\n"
        pharmacy += (
            f"  Infusion rate: {_fmt(vel_infusione, 2)} ml/h\n"
            f"\nDoctor signature: ________________________\n"
            f"Nurse signature:  ________________________"
        )

    # --- Build result ---
    result = {
        "macros": {
            "protein": {
                "pn_gkg": round(aa_gkg, 2),
                "pn_total_g": round(aa_g, 1),
                "milk_gkg": round(milk["prot_gkg"], 2),
                "total_gkg": round(tot_aa_gkg, 2),
                "confronto_fabbisogno": badges["prot"]["badge"],
                "fabbisogno_target": badges["prot"]["target"],
            },
            "nitrogen_g": round(n_g, 2),
            "glucose": {
                "pn_gkg": round(glu_gkg, 2),
                "milk_gkg": round(milk["glu_gkg"], 2),
                "total_gkg": round(tot_glu_gkg, 2),
                "pn_kcalkg": round(glu_kcalkg, 1),
                "confronto_fabbisogno": badges["glu"]["badge"],
                "fabbisogno_target": badges["glu"]["target"],
            },
            "lipids": {
                "pn_gkg": round(lip_gkg, 2),
                "milk_gkg": round(milk["lip_gkg"], 2),
                "total_gkg": round(tot_lip_gkg, 2),
                "pn_kcalkg": round(lip_kcalkg, 1),
                "confronto_fabbisogno": badges["lip"]["badge"],
                "fabbisogno_target": badges["lip"]["target"],
            },
            "kcal_total": {
                "pn_kcalkg": round(tot_kcal_pn_kg, 1),
                "pn_total_kcal": round(tot_kcal_pn, 1),
                "milk_kcalkg": round(milk["kcal_kg"], 1),
                "milk_total_kcal": round(milk["kcal"], 1),
                "total_kcalkg": round(tot_kcal_tot_kg, 1),
            },
        },
        "electrolytes": {
            "na": {
                "pn_meqkg": round(na_mEqkg, 2),
                "milk_meqkg": round(milk["na_mEqkg"], 2),
                "total_meqkg": round(tot_na_meqkg, 2),
                "confronto_fabbisogno": badges["na"]["badge"],
                "fabbisogno_target": badges["na"]["target"],
            },
            "k": {
                "pn_meqkg": round(k_mEqkg, 2),
                "milk_meqkg": round(milk["k_mEqkg"], 2),
                "total_meqkg": round(tot_k_meqkg, 2),
                "confronto_fabbisogno": badges["k"]["badge"],
                "fabbisogno_target": badges["k"]["target"],
            },
            "ca": {
                "pn_mgkg": round(ca_mgkg, 1),
                "milk_mgkg": round(milk["ca_mgkg"], 1),
                "total_mgkg": round(tot_ca_mgkg_val, 1),
                "confronto_fabbisogno": badges["ca"]["badge"],
                "fabbisogno_target": badges["ca"]["target"],
            },
            "p": {
                "pn_mgkg": round(p_mgkg, 1),
                "milk_mgkg": round(milk["p_mgkg"], 1),
                "total_mgkg": round(tot_p_mgkg_val, 1),
                "confronto_fabbisogno": badges["p"]["badge"],
                "fabbisogno_target": badges["p"]["target"],
            },
            "mg": {
                "pn_meqkg": round(mg_mEqkg, 2),
                "milk_meqkg": round(milk["mg_mEqkg"], 2),
                "total_meqkg": round(tot_mg_meqkg, 2),
                "confronto_fabbisogno": badges["mg"]["badge"],
                "fabbisogno_target": badges["mg"]["target"],
            },
            "cl": {
                "pn_meqkg": round(cl_mEqkg, 2),
            },
        },
        "volumes": {
            "solutions": solutions_list,
            "vitamins_ml": round(tot_vit_ml, 1),
            "water_ml": round(acqua_mostrata, 1),
            "bag_net_ml": round(sacca_netta_mostrata, 1),
            "tubing_ml": round(vol_deflussore, 1) if not numeta_attiva else 0,
            "bag_with_tubing_ml": round(pn_sacca_vol_ml + vol_deflussore, 1) if not numeta_attiva else 0,
            "infusion_rate_mlh": round(vel_infusione, 2),
            "milk_ml": round(req.milk_ml, 1),
            "milk_mlkg": round(milk["vol_mlkg"], 1),
            "clinical_fluids_ml": round(tot_liquidi_clinici, 1),
            "clinical_fluids_mlkg": round(tot_liquidi_clinici_kg, 1),
            "prepared_fluids_ml": round(tot_liquidi_con_defl, 1),
            "fluid_target_mlkg": round(liq_target, 1),
            "fluid_residual_mlkg": round(liq_residuo, 1),
            "osmolarity_final_mOsm_L": round(osm_final) if osm_final is not None else None,
            "idrico_range": idrico_hint,
        },
        "safety": safety,
        "confronto_fabbisognos": badges,
        "pharmacy_print": pharmacy,
    }

    # Numeta detail (if active)
    if numeta_attiva and numeta["vol"] > 0:
        result["numeta_detail"] = {
            "aa_gkg": round(numeta["aa"], 2),
            "glu_gkg": round(numeta["glu"], 2),
            "lip_gkg": round(numeta["lip"], 2),
            "na_mEqkg": round(numeta["na"], 2),
            "k_mEqkg": round(numeta["k"], 2),
            "mg_mEqkg": round(numeta["mg"], 2),
            "ca_mgkg": round(numeta["ca"], 1),
            "p_mgkg": round(numeta["p"], 1),
            "kcal_kg": round(numeta["kcal"], 1),
            "osm_mOsm_L": numeta["osm"],
            "bag_vol_ml": numeta["bag_vol"],
            "vol_tot_sacca_ml": numeta["vol_tot_sacca"],
            "vol_infused_24h_ml": round(numeta["vol"], 1),
        }

    return result


# ===========================================================================
# MCP TOOLS
# ===========================================================================

@mcp.tool()
def list_formulas() -> dict:
    """List all available milk/formula options with nutritional composition per 100 ml.

    Formulas are grouped into three mutually exclusive categories:
    - breast_milk: human milk options (plain or fortified)
    - formula_1: standard term formulas
    - formula_0_special: preterm, special, AR formulas

    Only one group can be active at a time. Use the formula key (e.g. 'latte_materno',
    'Aptamil 1') as the milk_type parameter in calculate_pn.
    """
    result = {}
    for group_name, keys in FORMULA_GROUPS.items():
        group = {}
        for key in keys:
            d = LATTI.get(key)
            if d:
                group[key] = d
        result[group_name] = group
    return result


@mcp.tool()
def list_solutions() -> dict:
    """List all available PN solution options with concentration data and osmolarity.

    Returns solutions grouped by nutrient type (aa, glu, lip, na, k, ca, mg, p).
    Each entry includes:
    - Concentration per ml (e.g. glu_g_per_ml, na_mEq_per_ml)
    - Osmolarity in mOsm/L

    Use the solution key (e.g. 'g33', 'nacl2') as the solution parameters in calculate_pn.
    """
    return {
        "amino_acids": {
            "trof6": {
                "label": "Trofamine 6%",
                "data": CONC["aa"]["trof6"],
                "osmolarity_mOsm_L": OSMOL_SOL["trof6"],
            },
        },
        "glucose": {
            k: {
                "label": SOLUTION_LABELS.get(k, k),
                "data": v,
                "osmolarity_mOsm_L": OSMOL_SOL.get(k),
            }
            for k, v in CONC["glu"].items()
        },
        "lipids": {
            k: {
                "label": SOLUTION_LABELS.get(k, k),
                "data": v,
                "osmolarity_mOsm_L": OSMOL_SOL.get(k),
            }
            for k, v in CONC["lip"].items()
        },
        "sodium": {
            k: {
                "label": SOLUTION_LABELS.get(k, k),
                "data": v,
                "osmolarity_mOsm_L": OSMOL_SOL.get(k),
            }
            for k, v in CONC["na"].items()
        },
        "potassium": {
            k: {
                "label": SOLUTION_LABELS.get(k, k),
                "data": v,
                "osmolarity_mOsm_L": OSMOL_SOL.get(k),
            }
            for k, v in CONC["k"].items()
        },
        "calcium": {
            k: {
                "label": SOLUTION_LABELS.get(k, k),
                "data": v,
                "osmolarity_mOsm_L": OSMOL_SOL.get(k),
            }
            for k, v in CONC["ca"].items()
        },
        "magnesium": {
            k: {
                "label": SOLUTION_LABELS.get(k, k),
                "data": v,
                "osmolarity_mOsm_L": OSMOL_SOL.get(k),
            }
            for k, v in CONC["mg"].items()
        },
        "phosphorus": {
            k: {
                "label": SOLUTION_LABELS.get(k, k),
                "data": v,
                "osmolarity_mOsm_L": OSMOL_SOL.get(k),
            }
            for k, v in CONC["p"].items()
        },
        "numeta": {
            k: {
                "label": "Numeta G13E 300 ml (with lipids)" if k == "g13_300" else "Numeta G13E 240 ml (no lipids)",
                "data": v,
            }
            for k, v in NUMETA.items()
        },
    }


@mcp.tool()
def get_requirements(
    weight_kg: float = Field(description="Patient weight in kg"),
    day_of_life: int = Field(description="Day of life (1-7)"),
) -> dict:
    """Get recommended nutrient targets (guidelines) and fluid requirements.

    Returns:
    - Per-kg targets for glucose, protein, lipids, Na, K, Ca, P, Mg, Cl
    - Fluid requirement range (ml/kg/day) from the IDRICO table
    - Suggested default fluid target (minimum of the range)

    Use this tool BEFORE calculate_pn to obtain suggested targets.
    The user can accept these or override them.
    """
    w = weight_kg
    d = max(1, min(7, day_of_life))

    targets = {}
    for nutrient in ["glu", "prot", "lip", "na", "k", "ca", "p", "mg", "cl"]:
        val = _get_fabbisogno_vento(nutrient, d, w)
        targets[nutrient] = val

    idrico = _get_idrico_range(w, d)
    fluid = None
    if idrico:
        fluid = {
            "min_mlkg": idrico["min"],
            "max_mlkg": idrico["max"],
            "suggested_default_mlkg": idrico["min"],
        }

    # Vitamin dosages
    vitamins = {}
    if w > 0:
        vitalipid = 0.0
        if w <= 10:
            vitalipid = 4 * w
        else:
            vitalipid = 10.0
        vitamins["vitalipid_ml"] = round(vitalipid, 1)

        soluvit = 0.0
        if w <= 10:
            soluvit = 1 * w
        else:
            soluvit = 10.0
        vitamins["soluvit_ml"] = round(soluvit, 1)

        peditrace = 0.0
        if w <= 15:
            peditrace = 1 * w
        else:
            peditrace = 15.0
        vitamins["peditrace_ml"] = round(peditrace, 1)

    return {
        "weight_kg": w,
        "day_of_life": d,
        "targets": targets,
        "fluid_requirements": fluid,
        "vitamin_dosages": vitamins,
    }


@mcp.tool()
def get_vitamin_dosages(
    weight_kg: float = Field(description="Patient weight in kg"),
) -> dict:
    """Get recommended vitamin and trace element dosages for a given weight.

    Returns:
    - vitalipid_ml: Vitalipid bambini (fat-soluble vitamins) recommended ml/day
    - soluvit_ml: Soluvit (water-soluble vitamins) recommended ml/day
    - peditrace_ml: Peditrace (trace elements) recommended ml/day

    Dosage rules:
    - Vitalipid: 4 ml/kg/day up to 10 kg, then max 10 ml/day
    - Soluvit: 1 ml/kg/day up to 10 kg, then max 10 ml/day
    - Peditrace: 1 ml/kg/day up to 15 kg, then max 15 ml/day
    """
    w = weight_kg
    if w <= 0:
        return {"error": "weight_kg must be > 0"}

    vitalipid = 4 * w if w <= 10 else 10.0
    soluvit = 1 * w if w <= 10 else 10.0
    peditrace = 1 * w if w <= 15 else 15.0

    return {
        "weight_kg": w,
        "vitalipid_ml": round(vitalipid, 1),
        "soluvit_ml": round(soluvit, 1),
        "peditrace_ml": round(peditrace, 1),
    }


@mcp.tool()
def calculate_pn(
    weight_kg: float = Field(description="Patient weight in kg (REQUIRED)"),
    day_of_life: int = Field(default=1, description="Day of life (1-7)"),
    gestational_age: str = Field(default="", description="Gestational age e.g. 30+4"),
    patient_name: str = Field(default="", description="Patient name"),
    prescription_date: str = Field(default="", description="Date YYYY-MM-DD"),
    notes: str = Field(default="", description="Clinical notes"),
    mode: str = Field(default="apporti", description="vol or apporti"),
    fluid_target_mlkg: float = Field(default=0, description="Fluid target ml/kg/day (0=auto)"),
    tubing_ml: float = Field(default=20, description="Tubing/deflussore ml"),
    milk_type: str = Field(default="", description="Formula key from LATTI"),
    milk_ml: float = Field(default=0, description="Milk volume ml/day"),
    numeta_type: str = Field(default="", description="g13_240, g13_300, or empty"),
    numeta_h2o_ml: float = Field(default=110, description="H2O added to Numeta bag ml"),
    aa_solution: str = Field(default="trof6", description="AA solution key"),
    aa_ml: float = Field(default=0, description="AA volume ml"),
    aa_target_gkg: float = Field(default=0, description="Protein target g/kg"),
    glu_solution: str = Field(default="g33", description="Glucose solution key"),
    glu_ml: float = Field(default=0, description="Glucose volume ml"),
    glu_target_gkg: float = Field(default=0, description="Glucose target g/kg"),
    lip_solution: str = Field(default="il20", description="Lipid solution key"),
    lip_ml: float = Field(default=0, description="Lipid volume ml"),
    lip_target_gkg: float = Field(default=0, description="Lipid target g/kg"),
    na_solution: str = Field(default="nacl2", description="Na solution key"),
    na_ml: float = Field(default=0, description="Na volume ml"),
    na_target_meqkg: float = Field(default=0, description="Na target mEq/kg"),
    k_solution: str = Field(default="kcl2", description="K solution key"),
    k_ml: float = Field(default=0, description="K volume ml"),
    k_target_meqkg: float = Field(default=0, description="K target mEq/kg"),
    ca_solution: str = Field(default="caglu10", description="Ca solution key"),
    ca_ml: float = Field(default=0, description="Ca volume ml"),
    ca_target_mgkg: float = Field(default=0, description="Ca target mg/kg"),
    mg_solution: str = Field(default="mgso410", description="Mg solution key"),
    mg_ml: float = Field(default=0, description="Mg volume ml"),
    mg_target_meqkg: float = Field(default=0, description="Mg target mEq/kg"),
    p_solution: str = Field(default="esafos-p", description="P solution key"),
    p_ml: float = Field(default=0, description="P volume ml"),
    p_target_mgkg: float = Field(default=0, description="P target mg/kg"),
    vitalipid_active: bool = Field(default=False, description="Include Vitalipid"),
    vitalipid_ml: float = Field(default=0, description="Vitalipid ml/day"),
    soluvit_active: bool = Field(default=False, description="Include Soluvit"),
    soluvit_ml: float = Field(default=0, description="Soluvit ml/day"),
    peditrace_active: bool = Field(default=False, description="Include Peditrace"),
    peditrace_ml: float = Field(default=0, description="Peditrace ml/day"),
) -> dict:
    """Calculate a complete neonatal parenteral nutrition prescription.

    WORKFLOW:
    1. Call get_requirements(weight_kg, day_of_life) to get suggested nutrient targets.
    2. Call list_formulas() and/or list_solutions() to look up available options.
    3. Fill in the parameters and call this tool.

    MODES:
    - 'vol': provide solution volumes (ml), the tool calculates resulting g/kg intake.
    - 'apporti': provide target intake per kg, the tool calculates volumes.
      In apporti mode, milk contributions are automatically subtracted from targets.

    MUTUALLY EXCLUSIVE:
    - Only one milk group can be active (breast milk, formula 1, or formula 0/special).
    - If numeta_type is set (g13_240 or g13_300), all classic PN inputs are ignored.

    REQUIRED: weight_kg must be > 0.

    OUTPUT SECTIONS:
    - macros: protein, glucose, lipids, kcal (PN, milk, total) with guideline comparison
    - electrolytes: Na, K, Ca, P, Mg, Cl (PN, milk, total) with guideline comparison
    - volumes: solution list, water, bag net, tubing, infusion rate, osmolarity
    - safety: osmolarity/access check, Ca:P ratio, Numeta dilution advice
    - confronti_fabbisogno: all nutrient badges compared to guidelines
    - pharmacy_print: ready-to-print pharmacy prescription text
    - numeta_detail: present only if Numeta mode is active
    """
    req = PNRequest(
        weight_kg=weight_kg,
        day_of_life=day_of_life,
        gestational_age=gestational_age,
        patient_name=patient_name,
        prescription_date=prescription_date,
        notes=notes,
        mode=mode if mode in ("vol", "apporti") else "apporti",
        fluid_target_mlkg=fluid_target_mlkg,
        tubing_ml=tubing_ml,
        milk_type=milk_type,
        milk_ml=milk_ml,
        numeta_type=numeta_type if numeta_type in ("", "g13_240", "g13_300") else "",
        numeta_h2o_ml=numeta_h2o_ml,
        aa_solution=aa_solution,
        aa_ml=aa_ml,
        aa_target_gkg=aa_target_gkg,
        glu_solution=glu_solution,
        glu_ml=glu_ml,
        glu_target_gkg=glu_target_gkg,
        lip_solution=lip_solution,
        lip_ml=lip_ml,
        lip_target_gkg=lip_target_gkg,
        na_solution=na_solution,
        na_ml=na_ml,
        na_target_meqkg=na_target_meqkg,
        k_solution=k_solution,
        k_ml=k_ml,
        k_target_meqkg=k_target_meqkg,
        ca_solution=ca_solution,
        ca_ml=ca_ml,
        ca_target_mgkg=ca_target_mgkg,
        mg_solution=mg_solution,
        mg_ml=mg_ml,
        mg_target_meqkg=mg_target_meqkg,
        p_solution=p_solution,
        p_ml=p_ml,
        p_target_mgkg=p_target_mgkg,
        vitalipid_active=vitalipid_active,
        vitalipid_ml=vitalipid_ml,
        soluvit_active=soluvit_active,
        soluvit_ml=soluvit_ml,
        peditrace_active=peditrace_active,
        peditrace_ml=peditrace_ml,
    )
    return _calculate_pn(req)


# ===========================================================================
# RUN
# ===========================================================================

if __name__ == "__main__":
    mcp.run()
