
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass, field, asdict
from typing import Optional


def strip_domain(domain: str) -> tuple[str, str]:
    """Return (name_without_tld, tld).  Handles multi-part TLDs like .co.uk."""
    domain = domain.lower().strip().lstrip(".")
    # Common compound TLDs
    compound_tlds = [
        ".co.uk", ".org.uk", ".ac.uk", ".gov.uk", ".com.au", ".co.nz",
        ".co.jp", ".co.kr", ".co.in", ".com.br", ".com.mx", ".co.za",
        ".net.au", ".org.au", ".com.cn", ".com.tw", ".com.sg",
    ]
    for ctld in compound_tlds:
        if domain.endswith(ctld):
            name = domain[: -len(ctld)]
            return name.rstrip("."), ctld.lstrip(".")
    parts = domain.rsplit(".", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return domain, ""

# 1. Levenshtein distance
def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        return levenshtein(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr
    return prev[-1]

# 2. Damerau-Levenshtein distance (transpositions)
def damerau_levenshtein(a: str, b: str) -> int:
    la, lb = len(a), len(b)
    d = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        d[i][0] = i
    for j in range(lb + 1):
        d[0][j] = j
    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(
                d[i - 1][j] + 1,
                d[i][j - 1] + 1,
                d[i - 1][j - 1] + cost,
            )
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + cost)
    return d[la][lb]

# 3. Jaro-Winkler similarity
def jaro_winkler(a: str, b: str, p: float = 0.1) -> float:
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return 0.0
    match_dist = max(la, lb) // 2 - 1
    a_matches = [False] * la
    b_matches = [False] * lb
    matches = 0
    transpositions = 0
    for i in range(la):
        lo = max(0, i - match_dist)
        hi = min(i + match_dist + 1, lb)
        for j in range(lo, hi):
            if b_matches[j] or a[i] != b[j]:
                continue
            a_matches[i] = True
            b_matches[j] = True
            matches += 1
            break
    if matches == 0:
        return 0.0
    k = 0
    for i in range(la):
        if not a_matches[i]:
            continue
        while not b_matches[k]:
            k += 1
        if a[i] != b[k]:
            transpositions += 1
        k += 1
    jaro = (matches / la + matches / lb + (matches - transpositions / 2) / matches) / 3
    prefix = 0
    for i in range(min(4, la, lb)):
        if a[i] == b[i]:
            prefix += 1
        else:
            break
    return jaro + prefix * p * (1 - jaro)

# 4. Keyboard-proximity typosquatting
QWERTY_NEIGHBORS: dict[str, set[str]] = {
    "q": {"w", "a"},          "w": {"q", "e", "a", "s"},
    "e": {"w", "r", "s", "d"}, "r": {"e", "t", "d", "f"},
    "t": {"r", "y", "f", "g"}, "y": {"t", "u", "g", "h"},
    "u": {"y", "i", "h", "j"}, "i": {"u", "o", "j", "k"},
    "o": {"i", "p", "k", "l"}, "p": {"o", "l"},
    "a": {"q", "w", "s", "z"}, "s": {"a", "w", "e", "d", "z", "x"},
    "d": {"s", "e", "r", "f", "x", "c"}, "f": {"d", "r", "t", "g", "c", "v"},
    "g": {"f", "t", "y", "h", "v", "b"}, "h": {"g", "y", "u", "j", "b", "n"},
    "j": {"h", "u", "i", "k", "n", "m"}, "k": {"j", "i", "o", "l", "m"},
    "l": {"k", "o", "p"},
    "z": {"a", "s", "x"}, "x": {"z", "s", "d", "c"},
    "c": {"x", "d", "f", "v"}, "v": {"c", "f", "g", "b"},
    "b": {"v", "g", "h", "n"}, "n": {"b", "h", "j", "m"},
    "m": {"n", "j", "k"},
    "1": {"2", "q"}, "2": {"1", "3", "q", "w"}, "3": {"2", "4", "w", "e"},
    "4": {"3", "5", "e", "r"}, "5": {"4", "6", "r", "t"}, "6": {"5", "7", "t", "y"},
    "7": {"6", "8", "y", "u"}, "8": {"7", "9", "u", "i"}, "9": {"8", "0", "i", "o"},
    "0": {"9", "o", "p"},
}


def keyboard_proximity_score(a: str, b: str) -> float:
    """Fraction of differing chars that are keyboard-adjacent (0-1)."""
    if len(a) != len(b):
        return 0.0
    diffs = 0
    adj = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            diffs += 1
            if cb in QWERTY_NEIGHBORS.get(ca, set()):
                adj += 1
    return adj / diffs if diffs else 0.0

# 5. Homoglyph / IDN homograph detection
HOMOGLYPHS: dict[str, str] = {
    # Latin lookalikes → ASCII
    "\u0430": "a", "\u0435": "e", "\u043e": "o", "\u0440": "p",
    "\u0441": "c", "\u0443": "y", "\u0445": "x", "\u0456": "i",
    "\u0458": "j", "\u04bb": "h", "\u0431": "b",
    # Common number/symbol substitutions
    "0": "o", "1": "l", "3": "e", "4": "a", "5": "s",
    "8": "b", "!": "i", "|": "l",
    # Latin Extended
    "\u0101": "a", "\u0113": "e", "\u012b": "i", "\u014d": "o",
    "\u016b": "u", "\u00e0": "a", "\u00e1": "a", "\u00e8": "e",
    "\u00e9": "e", "\u00f2": "o", "\u00f3": "o",
    # Greek
    "\u03b1": "a", "\u03b5": "e", "\u03bf": "o", "\u03c1": "p",
    "\u03b9": "i", "\u03ba": "k", "\u03bd": "v", "\u03c4": "t",
}


def normalize_homoglyphs(s: str) -> str:
    return "".join(HOMOGLYPHS.get(c, c) for c in s)


def homoglyph_score(legit: str, suspect: str) -> dict:
    """Check if suspect uses homoglyphs to mimic legit."""
    normalized = normalize_homoglyphs(suspect)
    substitutions = []
    for i, (orig, norm) in enumerate(zip(suspect, normalized)):
        if orig != norm and i < len(legit) and norm == legit[i]:
            substitutions.append({"position": i, "original": orig, "looks_like": norm})

    is_match = normalized == legit and suspect != legit
    return {
        "normalized_form": normalized,
        "is_homograph_match": is_match,
        "substitutions": substitutions,
    }


# 6. Bitsquatting detection
def is_single_bit_flip(a: str, b: str) -> list[dict]:
    """Identify characters that differ by exactly one bit (bitsquatting)."""
    if len(a) != len(b):
        return []
    flips = []
    for i, (ca, cb) in enumerate(zip(a, b)):
        xor = ord(ca) ^ ord(cb)
        if xor != 0 and (xor & (xor - 1)) == 0:  # exactly one bit set
            flips.append({"position": i, "original": ca, "flipped": cb, "bit": xor.bit_length() - 1})
    return flips

# 7. Character omission / insertion / repetition
def char_manipulation_check(legit: str, suspect: str) -> dict:
    result: dict = {"omission": False, "insertion": False, "repetition": False, "details": ""}
    ll, ls = len(legit), len(suspect)

    # Omission: suspect is legit minus one char
    if ls == ll - 1:
        for i in range(ll):
            if legit[:i] + legit[i + 1:] == suspect:
                result["omission"] = True
                result["details"] = f"char '{legit[i]}' omitted at position {i}"
                return result

    # Insertion: suspect is legit plus one char
    if ls == ll + 1:
        for i in range(ls):
            if suspect[:i] + suspect[i + 1:] == legit:
                result["insertion"] = True
                result["details"] = f"char '{suspect[i]}' inserted at position {i}"
                return result

    # Repetition: suspect has a repeated char that legit doesn't
    if ls == ll + 1:
        for i in range(1, ls):
            if suspect[i] == suspect[i - 1]:
                reduced = suspect[:i] + suspect[i + 1:]
                if reduced == legit:
                    result["repetition"] = True
                    result["details"] = f"char '{suspect[i]}' repeated at position {i}"
                    return result

    return result


# 8. Vowel swap
VOWELS = set("aeiou")
def vowel_swap_check(legit: str, suspect: str) -> dict:
    if len(legit) != len(suspect):
        return {"is_vowel_swap": False, "swaps": []}
    swaps = []
    non_vowel_diff = False
    for i, (a, b) in enumerate(zip(legit, suspect)):
        if a != b:
            if a in VOWELS and b in VOWELS:
                swaps.append({"position": i, "original": a, "swapped": b})
            else:
                non_vowel_diff = True
    return {"is_vowel_swap": len(swaps) > 0 and not non_vowel_diff, "swaps": swaps}


# 9. Hyphenation abuse
def hyphenation_check(legit_name: str, suspect_name: str) -> dict:
    stripped = suspect_name.replace("-", "")
    has_hyphens = "-" in suspect_name
    return {
        "has_hyphens": has_hyphens,
        "hyphen_count": suspect_name.count("-"),
        "matches_without_hyphens": has_hyphens and stripped == legit_name,
        "contains_brand_segment": has_hyphens and legit_name in suspect_name.split("-"),
    }


# 10. TLD swap / abuse
POPULAR_TLDS = {"com", "net", "org", "io", "co", "info", "biz", "us", "uk", "de", "app", "dev", "xyz"}
RISKY_TLDS = {"tk", "ml", "ga", "cf", "gq", "top", "buzz", "click", "link", "work", "rest", "surf", "icu", "cam"}
def tld_analysis(legit_tld: str, suspect_tld: str) -> dict:
    same_name_diff_tld = False  # handled by caller
    return {
        "legit_tld": legit_tld,
        "suspect_tld": suspect_tld,
        "tld_differs": legit_tld != suspect_tld,
        "suspect_tld_is_risky": suspect_tld in RISKY_TLDS,
        "suspect_tld_is_popular": suspect_tld in POPULAR_TLDS,
    }


# 11. Subdomain confusion
def subdomain_confusion(legit_full: str, suspect_full: str) -> dict:
    """Detect if suspect embeds legit domain as a subdomain prefix."""
    legit_name, _ = strip_domain(legit_full)
    suspect_name, _ = strip_domain(suspect_full)
    suspect_parts = suspect_full.split(".")

    # If the names are identical, this is just a TLD swap, not subdomain abuse
    if legit_name == suspect_name:
        return {
            "contains_legit_as_subdomain": False,
            "resembles_legit_subdomain": False,
            "suspect_depth": len(suspect_parts),
        }

    contains_legit_as_subdomain = False
    for i, part in enumerate(suspect_parts[:-1]):  # ignore TLD
        if legit_name in part or legit_full.replace(".", "") in part:
            contains_legit_as_subdomain = True
            break
    # e.g. example.com.evil.com
    resembles_legit_subdomain = suspect_full.startswith(legit_full + ".")
    return {
        "contains_legit_as_subdomain": contains_legit_as_subdomain,
        "resembles_legit_subdomain": resembles_legit_subdomain,
        "suspect_depth": len(suspect_parts),
    }


# 12. Soundex (phonetic)
def soundex(s: str) -> str:
    if not s:
        return "0000"
    s = s.upper()
    codes = {
        "B": "1", "F": "1", "P": "1", "V": "1",
        "C": "2", "G": "2", "J": "2", "K": "2", "Q": "2", "S": "2", "X": "2", "Z": "2",
        "D": "3", "T": "3",
        "L": "4",
        "M": "5", "N": "5",
        "R": "6",
    }
    result = s[0]
    prev = codes.get(s[0], "0")
    for ch in s[1:]:
        code = codes.get(ch, "0")
        if code != "0" and code != prev:
            result += code
        prev = code if code != "0" else prev
    return (result + "0000")[:4]



# 13. Double Metaphone (simplified)
def metaphone(s: str) -> str:
    """Simplified metaphone encoding for phonetic comparison."""
    s = s.upper()
    # Drop non-alpha
    s = re.sub(r"[^A-Z]", "", s)
    if not s:
        return ""

    # Drop duplicate adjacent letters
    deduped = s[0]
    for c in s[1:]:
        if c != deduped[-1]:
            deduped += c
    s = deduped

    transforms = [
        (r"^AE|^GN|^KN|^PN|^WR", lambda m: m.group()[1:]),
        (r"MB$", "M"),
        (r"PH", "F"), (r"CK", "K"),
        (r"SCH", "SK"), (r"SH", "X"),
        (r"TH", "0"), (r"TCH", "CH"),
        (r"CIA|CH", "X"),
        (r"C(?=[EIY])", "S"), (r"C", "K"),
        (r"DG(?=[EIY])", "J"), (r"D", "T"),
        (r"GH(?=[^AEIOU])", ""), (r"G(?=[EIY])", "J"), (r"G", "K"),
        (r"WR", "R"), (r"W(?=[^AEIOU])", ""),
        (r"X", "KS"),
        (r"QU", "KW"), (r"Q", "K"),
        (r"Z", "S"),
    ]
    for pattern, repl in transforms:
        if callable(repl):
            s = re.sub(pattern, repl, s)
        else:
            s = re.sub(pattern, repl, s)

    # Drop vowels except leading
    if len(s) > 1:
        s = s[0] + re.sub(r"[AEIOU]", "", s[1:])

    return s[:6]


# 14. Brand/keyword containment
def brand_containment(legit_name: str, suspect_name: str) -> dict:
    return {
        "suspect_contains_brand": legit_name in suspect_name and suspect_name != legit_name,
        "brand_at_start": suspect_name.startswith(legit_name) and suspect_name != legit_name,
        "brand_at_end": suspect_name.endswith(legit_name) and suspect_name != legit_name,
    }


# 15. Combo-squatting (brand + common prefix/suffix)
COMBO_TOKENS = [
    "login", "secure", "verify", "update", "account", "auth", "signin",
    "support", "help", "service", "pay", "billing", "admin", "portal",
    "online", "my", "web", "mail", "cloud", "app", "mobile", "ssl",
    "security", "confirm", "alert", "info", "official", "real", "true",
    "shop", "store", "checkout", "order", "download", "install",
]


def combo_squatting(legit_name: str, suspect_name: str) -> dict:
    found_tokens = []
    remainder = suspect_name
    if legit_name in suspect_name:
        remainder = suspect_name.replace(legit_name, "", 1)
        remainder = remainder.strip("-").strip(".")
    for token in COMBO_TOKENS:
        if token in remainder:
            found_tokens.append(token)
    return {
        "is_combo_squat": len(found_tokens) > 0 and legit_name in suspect_name,
        "found_tokens": found_tokens,
    }


# 16. N-gram structural similarity
def ngram_similarity(a: str, b: str, n: int = 2) -> float:
    """Sørensen–Dice coefficient on character n-grams."""
    if len(a) < n or len(b) < n:
        return 0.0
    a_grams = set(a[i: i + n] for i in range(len(a) - n + 1))
    b_grams = set(b[i: i + n] for i in range(len(b) - n + 1))
    overlap = a_grams & b_grams
    return 2 * len(overlap) / (len(a_grams) + len(b_grams))


# 17. TF-IDF character-trigram cosine similarity
def trigram_vector(s: str) -> Counter:
    return Counter(s[i: i + 3] for i in range(len(s) - 2))


def cosine_similarity(a: Counter, b: Counter) -> float:
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    mag_a = math.sqrt(sum(v * v for v in a.values()))
    mag_b = math.sqrt(sum(v * v for v in b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# 18. Entropy analysis (DGA detection)
def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    freq = Counter(s)
    length = len(s)
    return -sum((c / length) * math.log2(c / length) for c in freq.values())


# Risk scoring engine
@dataclass
class Finding:
    technique: str
    category: str          # e.g. "typosquatting", "phonetic", "visual", "semantic"
    risk_contribution: float  # 0-100 points
    details: dict = field(default_factory=dict)


def compute_risk(findings: list[Finding]) -> dict:
    """Aggregate findings into an overall risk score 0-100."""
    raw = sum(f.risk_contribution for f in findings)
    score = min(100.0, raw)
    if score >= 75:
        level = "CRITICAL"
    elif score >= 50:
        level = "HIGH"
    elif score >= 30:
        level = "MEDIUM"
    elif score >= 10:
        level = "LOW"
    else:
        level = "NONE"
    return {"score": round(score, 1), "level": level}

# Main analysis orchestrator
def analyze(legit_domain: str, suspect_domain: str) -> dict:
    legit_name, legit_tld = strip_domain(legit_domain)
    suspect_name, suspect_tld = strip_domain(suspect_domain)

    findings: list[Finding] = []

    # --- String distance metrics ---
    lev = levenshtein(legit_name, suspect_name)
    dam_lev = damerau_levenshtein(legit_name, suspect_name)
    jw = jaro_winkler(legit_name, suspect_name)

    max_len = max(len(legit_name), len(suspect_name), 1)
    norm_lev = 1 - lev / max_len

    if 0 < lev <= 2:
        findings.append(Finding("levenshtein_distance", "typosquatting",
                                 35 if lev == 1 else 25,
                                 {"distance": lev, "normalized_similarity": round(norm_lev, 3)}))
    elif lev == 3:
        findings.append(Finding("levenshtein_distance", "typosquatting", 12,
                                 {"distance": lev, "normalized_similarity": round(norm_lev, 3)}))

    if dam_lev < lev:
        findings.append(Finding("damerau_levenshtein", "typosquatting", 15,
                                 {"distance": dam_lev, "has_transposition": True}))

    if jw >= 0.90 and legit_name != suspect_name:
        findings.append(Finding("jaro_winkler", "typosquatting",
                                 20 if jw >= 0.95 else 10,
                                 {"similarity": round(jw, 4)}))

    # --- Keyboard proximity ---
    kb = keyboard_proximity_score(legit_name, suspect_name)
    if kb > 0:
        findings.append(Finding("keyboard_proximity", "typosquatting",
                                 25 * kb,
                                 {"adjacent_ratio": round(kb, 3)}))

    # --- Homoglyph ---
    hg = homoglyph_score(legit_name, suspect_name)
    if hg["is_homograph_match"]:
        findings.append(Finding("homoglyph_attack", "visual", 40, hg))
    elif hg["substitutions"]:
        findings.append(Finding("homoglyph_partial", "visual",
                                 10 * len(hg["substitutions"]), hg))

    # --- Bitsquatting ---
    bflips = is_single_bit_flip(legit_name, suspect_name)
    if bflips and len(bflips) == 1:
        findings.append(Finding("bitsquatting", "infrastructure", 30,
                                 {"flips": bflips}))

    # --- Char manipulation ---
    cm = char_manipulation_check(legit_name, suspect_name)
    if cm["omission"] or cm["insertion"] or cm["repetition"]:
        label = "omission" if cm["omission"] else ("insertion" if cm["insertion"] else "repetition")
        findings.append(Finding(f"char_{label}", "typosquatting", 30, cm))

    # --- Vowel swap ---
    vs = vowel_swap_check(legit_name, suspect_name)
    if vs["is_vowel_swap"]:
        findings.append(Finding("vowel_swap", "typosquatting", 25, vs))

    # --- Hyphenation ---
    hyph = hyphenation_check(legit_name, suspect_name)
    if hyph["matches_without_hyphens"]:
        findings.append(Finding("hyphenation_abuse", "semantic", 30, hyph))
    elif hyph["contains_brand_segment"]:
        findings.append(Finding("hyphenation_brand", "semantic", 15, hyph))

    # --- TLD ---
    tld = tld_analysis(legit_tld, suspect_tld)
    if tld["tld_differs"] and legit_name == suspect_name:
        risk = 35 if tld["suspect_tld_is_risky"] else 20
        findings.append(Finding("tld_swap", "tld_abuse", risk, tld))
    elif tld["tld_differs"] and tld["suspect_tld_is_risky"]:
        findings.append(Finding("risky_tld", "tld_abuse", 5, tld))

    # --- Subdomain confusion ---
    sd = subdomain_confusion(legit_domain, suspect_domain)
    if sd["contains_legit_as_subdomain"] or sd["resembles_legit_subdomain"]:
        findings.append(Finding("subdomain_confusion", "semantic", 30, sd))

    # --- Phonetic checks ---
    sx_legit = soundex(legit_name)
    sx_suspect = soundex(suspect_name)
    if sx_legit == sx_suspect and legit_name != suspect_name:
        findings.append(Finding("soundex_match", "phonetic", 20,
                                 {"legit_soundex": sx_legit, "suspect_soundex": sx_suspect}))

    mp_legit = metaphone(legit_name)
    mp_suspect = metaphone(suspect_name)
    if mp_legit == mp_suspect and legit_name != suspect_name:
        findings.append(Finding("metaphone_match", "phonetic", 20,
                                 {"legit_metaphone": mp_legit, "suspect_metaphone": mp_suspect}))
    elif mp_legit and mp_suspect and levenshtein(mp_legit, mp_suspect) == 1:
        findings.append(Finding("metaphone_near", "phonetic", 10,
                                 {"legit_metaphone": mp_legit, "suspect_metaphone": mp_suspect}))

    # --- Brand containment ---
    bc = brand_containment(legit_name, suspect_name)
    if bc["suspect_contains_brand"]:
        findings.append(Finding("brand_containment", "semantic", 20, bc))

    # --- Combo-squatting ---
    cs = combo_squatting(legit_name, suspect_name)
    if cs["is_combo_squat"]:
        findings.append(Finding("combo_squatting", "semantic", 30, cs))

    # --- N-gram similarity ---
    ng2 = ngram_similarity(legit_name, suspect_name, 2)
    ng3 = ngram_similarity(legit_name, suspect_name, 3)
    if ng2 >= 0.6 and legit_name != suspect_name:
        findings.append(Finding("ngram_similarity", "structural",
                                 15 * ng2,
                                 {"bigram_dice": round(ng2, 3), "trigram_dice": round(ng3, 3)}))

    # --- Cosine similarity ---
    cos = cosine_similarity(trigram_vector(legit_name), trigram_vector(suspect_name))
    if cos >= 0.5 and legit_name != suspect_name:
        findings.append(Finding("trigram_cosine", "structural",
                                 10 * cos,
                                 {"cosine_similarity": round(cos, 4)}))

    # --- Entropy ---
    ent_legit = shannon_entropy(legit_name)
    ent_suspect = shannon_entropy(suspect_name)
    # Flag if suspect has much higher entropy (possible DGA)
    if ent_suspect > ent_legit + 1.5 and ent_suspect > 3.5:
        findings.append(Finding("high_entropy", "dga_indicator", 10,
                                 {"legit_entropy": round(ent_legit, 3),
                                  "suspect_entropy": round(ent_suspect, 3)}))

    # --- Build report ---
    risk = compute_risk(findings)

    return {
        "analysis": {
            "legit_domain": legit_domain,
            "suspect_domain": suspect_domain,
            "legit_name": legit_name,
            "legit_tld": legit_tld,
            "suspect_name": suspect_name,
            "suspect_tld": suspect_tld,
        },
        "risk": risk,
        "findings": [asdict(f) for f in sorted(findings, key=lambda f: f.risk_contribution, reverse=True)],
        "metrics": {
            "levenshtein_distance": lev,
            "damerau_levenshtein_distance": dam_lev,
            "jaro_winkler_similarity": round(jw, 4),
            "keyboard_proximity_ratio": round(kb, 3),
            "bigram_dice_coefficient": round(ng2, 3),
            "trigram_dice_coefficient": round(ng3, 3),
            "trigram_cosine_similarity": round(cos, 4),
            "soundex": {"legit": sx_legit, "suspect": sx_suspect, "match": sx_legit == sx_suspect},
            "metaphone": {"legit": mp_legit, "suspect": mp_suspect, "match": mp_legit == mp_suspect},
            "shannon_entropy": {"legit": round(ent_legit, 3), "suspect": round(ent_suspect, 3)},
        },
    }

def main():
    parser = argparse.ArgumentParser(
        description="Analyze whether a suspect domain is a threat to your legitimate domain.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--legit", "-l", help="Yours")
    parser.add_argument("--suspect", "-s", help="suspect")
    parser.add_argument("--pretty", "-p", action="store_true", help="Pretty-print JSON output")
    parser.add_argument("--stdin", action="store_true", help='Read JSON from stdin ({"legit":"…","suspect":"…"})')
    args = parser.parse_args()

    if args.stdin:
        data = json.load(sys.stdin)
        legit = data["legit"]
        suspect = data["suspect"]
    elif args.legit and args.suspect:
        legit = args.legit
        suspect = args.suspect
    else:
        parser.error("Provide --legit and --suspect, or use --stdin")
        return

    result = analyze(legit, suspect)
    indent = 2 if args.pretty else None
    print(json.dumps(result, indent=indent, ensure_ascii=False))


if __name__ == "__main__":
    main()
