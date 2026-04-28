from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass, field, asdict
from typing import Optional

HIGH_ABUSE_TLDS = {
    "tk": "Freenom free TLD, top of Spamhaus abuse rankings for years",
    "ml": "Freenom free TLD, very high phishing abuse rate",
    "ga": "Freenom free TLD, frequently used for malware C2",
    "cf": "Freenom free TLD, common in phishing campaigns",
    "gq": "Freenom free TLD, high abuse rate per Interisle",
    "top": "Cheap registration, consistently high abuse per Spamhaus",
    "buzz": "Frequently flagged in phishing landscape reports",
    "icu": "High abuse rate, often used in scams",
    "click": "Used heavily in click-fraud and malicious redirects",
    "link": "Often used for shortened malicious URLs",
    "xyz": "Cheap registration, high spam/phishing volume",
    "monster": "Frequently flagged in abuse reports",
    "rest": "Cheap nTLD, often abused",
    "country": "High abuse rate per Spamhaus",
    "stream": "Often used in malware distribution",
    "gdn": "High abuse rate per multiple reports",
    "racing": "Cheap nTLD, frequently abused",
    "download": "Often used to distribute malware",
    "review": "Heavily abused for scams",
    "loan": "Common in financial scam campaigns",
    "win": "High abuse rate in phishing",
    "work": "Cheap registration, abused for spam",
    "men": "Frequently flagged in abuse reports",
    "party": "Free/cheap nTLD with high abuse",
    "trade": "Frequently flagged for phishing",
    "date": "Used in romance scams and phishing",
    "cricket": "Cheap nTLD, often abused",
    "science": "Cheap nTLD, abused for scams",
    "cam": "Frequently abused for adult/scam content",
    "surf": "Often used in malicious campaigns",
}

# Tier-1 trustworthy TLDs (lower baseline suspicion)
LOW_ABUSE_TLDS = {"com", "org", "net", "edu", "gov", "mil",
                  "io", "ai", "co", "app", "dev", "uk", "de", "fr",
                  "jp", "ca", "au", "nl", "se", "no", "fi"}

# Phishing-related keywords. Derived from analysis of PhishTank/URLhaus corpora,
# Marchal et al. (2014) PhishStorm, and Garera et al. (2007).
PHISHING_KEYWORDS = {
    # Authentication & access
    "login", "signin", "logon", "auth", "authenticate", "authorize", "verify",
    "verification", "validate", "confirm", "confirmation", "reset", "unlock",
    # Account & security
    "account", "accounts", "secure", "security", "safety",
    "protected", "protection", "support", "service", "services",
    # Financial
    "pay", "payment", "billing", "invoice", "wallet", "transfer",
    "transaction", "checkout", "order", "purchase", "refund", "deposit",
    # Urgency & action
    "update", "upgrade", "renew", "alert", "warning", "important",
    "urgent", "expired", "suspended", "blocked", "limited",
    # Generic legitimacy claims
    "official", "genuine", "original", "authentic",
    "trusted", "verified",
    # Admin & access control
    "admin", "administrator", "portal", "dashboard", "console",
    # Common patterns
    "ssl", "https",
}

# Findings that indicate "randomness" or "unnaturalness" of the name itself.
# When 3+ of these fire together, that combination is itself a stronger signal
# than any individually (the academic basis for combined-feature DGA classifiers).
RANDOMNESS_TECHNIQUES = {
    "excessive_domain_length", "long_domain",
    "excessive_hyphens", "multiple_hyphens", "single_hyphen",
    "high_digit_ratio", "elevated_digit_ratio",
    "very_high_entropy", "elevated_entropy",
    "low_vowel_ratio", "below_normal_vowels",
    "long_consonant_run", "consonant_run",
    "unnatural_bigrams", "uncommon_bigrams",
    "long_hex_pattern", "hex_pattern",
    "excessive_repetition", "character_repetition",
}

# Common English bigrams (top ~200 most frequent in domain names and English).
# Used to detect "naturalness" — random/DGA strings produce many uncommon bigrams.
COMMON_BIGRAMS = {
    "th", "he", "in", "er", "an", "re", "on", "at", "en", "nd",
    "ti", "es", "or", "te", "of", "ed", "is", "it", "al", "ar",
    "st", "to", "nt", "ng", "se", "ha", "as", "ou", "io", "le",
    "ve", "co", "me", "de", "hi", "ri", "ro", "ic", "ne", "ea",
    "ra", "ce", "li", "ch", "ll", "be", "ma", "si", "om", "ur",
    "ca", "el", "ta", "la", "ns", "di", "fo", "ho", "pe", "ec",
    "pr", "no", "ct", "us", "ac", "ot", "il", "tr", "ly", "nc",
    "et", "ut", "ss", "so", "rs", "un", "lo", "wa", "ge", "ie",
    "wh", "ee", "wi", "em", "ad", "ol", "rt", "po", "we", "na",
    "ul", "ni", "ts", "mo", "ow", "pa", "im", "mi", "ai", "sh",
    "ir", "su", "id", "os", "ia", "am", "fi", "ci", "vi", "pl",
    "ig", "tu", "ev", "ld", "ry", "mp", "fe", "bl", "ab", "gh",
    "ty", "op", "wo", "sa", "ay", "ex", "ke", "fr", "oo", "av",
    "ag", "if", "ap", "gr", "od", "bo", "sp", "rd", "do", "uc",
    "bu", "ei", "ov", "by", "rm", "ep", "tt", "oc", "fa", "ef",
    "cu", "rn", "sc", "gi", "da", "yo", "cr", "cl", "du", "ga",
    "qu", "ue", "ff", "ba", "ey", "ls", "va", "um", "pp", "ua",
    "up", "lu", "go", "ht", "ru", "ug", "ds", "lt", "pi", "rc",
    "rr", "eg", "au", "ck", "ew", "mu", "br", "bi", "pt", "ak",
    "pu", "ui", "rg", "ib", "tl", "ny", "ki", "rk", "ys", "ob",
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def strip_domain(domain: str) -> tuple[str, str, list[str]]:
    """Return (registered_name_without_tld, tld, full_parts)."""
    domain = domain.lower().strip().lstrip(".")
    parts = domain.split(".")
    compound_tlds = [
        ("co", "uk"), ("org", "uk"), ("ac", "uk"), ("gov", "uk"),
        ("com", "au"), ("co", "nz"), ("co", "jp"), ("co", "kr"),
        ("co", "in"), ("com", "br"), ("com", "mx"), ("co", "za"),
        ("net", "au"), ("org", "au"), ("com", "cn"), ("com", "tw"),
    ]
    if len(parts) >= 3 and (parts[-2], parts[-1]) in compound_tlds:
        tld = ".".join(parts[-2:])
        registered = parts[-3]
        return registered, tld, parts
    if len(parts) >= 2:
        return parts[-2], parts[-1], parts
    return domain, "", parts


# ─────────────────────────────────────────────────────────────────────────────
# Finding dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Finding:
    technique: str
    explanation: str          # one-line description of the technique
    observation: str          # what was actually observed in this domain
    severity: str             # "low" | "medium" | "high"
    risk_contribution: float  # points added to overall score (0-100 cap)
    metric_value: Optional[float] = None


# ─────────────────────────────────────────────────────────────────────────────
# 1. Domain length
# ─────────────────────────────────────────────────────────────────────────────

def check_domain_length(name: str) -> Optional[Finding]:
    """Le et al. (2011) PhishDef + Splunk ESCU: legit ~8-12, malicious skews longer."""
    length = len(name)
    if length >= 25:
        return Finding(
            technique="excessive_domain_length",
            explanation="Legitimate domains average 8-12 characters; malicious domains are statistically much longer (Le et al. 2011, Sahoo et al. 2017).",
            observation=f"Registered name is {length} characters long, which is well above the typical legitimate range.",
            severity="high",
            risk_contribution=15,
            metric_value=length,
        )
    if length >= 18:
        return Finding(
            technique="long_domain",
            explanation="Domains over ~18 characters are statistically more likely to be malicious or DGA-generated.",
            observation=f"Registered name is {length} characters long, longer than typical legitimate domains.",
            severity="medium",
            risk_contribution=8,
            metric_value=length,
        )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 2. Hyphen count
# ─────────────────────────────────────────────────────────────────────────────

def check_hyphens(name: str) -> Optional[Finding]:
    """Marchal et al. (2014) PhishStorm: real brands rarely use 2+ hyphens."""
    count = name.count("-")
    if count >= 3:
        return Finding(
            technique="excessive_hyphens",
            explanation="Real brands almost never use 3+ hyphens; attackers chain hyphenated keywords for phishing (Marchal et al. 2014, Mohammad et al. 2014).",
            observation=f"Domain contains {count} hyphens, a strong indicator of phishing/combosquatting.",
            severity="high",
            risk_contribution=18,
            metric_value=count,
        )
    if count == 2:
        return Finding(
            technique="multiple_hyphens",
            explanation="Two or more hyphens is unusual for legitimate brands and common in phishing domains.",
            observation=f"Domain contains {count} hyphens, above the typical legitimate threshold of 0-1.",
            severity="medium",
            risk_contribution=10,
            metric_value=count,
        )
    if count == 1:
        return Finding(
            technique="single_hyphen",
            explanation="A single hyphen is mildly elevated risk — not unusual but slightly more common in phishing than legitimate domains.",
            observation=f"Domain contains 1 hyphen, a minor indicator.",
            severity="low",
            risk_contribution=2,
            metric_value=1,
        )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 3. Digit ratio
# ─────────────────────────────────────────────────────────────────────────────

def check_digit_ratio(name: str) -> Optional[Finding]:
    """Verma & Dyer (2015) ACM CODASPY: high digit ratio is a top single feature."""
    if not name:
        return None
    digits = sum(c.isdigit() for c in name)
    ratio = digits / len(name)
    if ratio >= 0.4:
        return Finding(
            technique="high_digit_ratio",
            explanation="Legitimate domains rarely have >40% digits; high digit ratio strongly indicates DGA or generated names (Verma & Dyer 2015, Antonakakis et al. 2012).",
            observation=f"{digits} of {len(name)} characters are digits ({ratio:.0%}), well above legitimate norms.",
            severity="high",
            risk_contribution=15,
            metric_value=round(ratio, 3),
        )
    if ratio >= 0.2:
        return Finding(
            technique="elevated_digit_ratio",
            explanation="Digits making up over 20% of a domain name is unusual for legitimate brands.",
            observation=f"{digits} of {len(name)} characters are digits ({ratio:.0%}).",
            severity="medium",
            risk_contribution=7,
            metric_value=round(ratio, 3),
        )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 4. Subdomain depth
# ─────────────────────────────────────────────────────────────────────────────

def check_subdomain_depth(parts: list[str], tld: str) -> Optional[Finding]:
    """Whittaker et al. (2010) NDSS Google paper: subdomain count is a top phishing feature."""
    tld_parts = len(tld.split("."))
    subdomain_count = max(0, len(parts) - tld_parts - 1)
    if subdomain_count >= 4:
        return Finding(
            technique="excessive_subdomains",
            explanation="Phishing URLs often nest 4+ subdomains to hide the real domain or mimic brand structures (Whittaker et al. 2010 - Google).",
            observation=f"Domain has {subdomain_count} subdomain levels, far above typical legitimate sites.",
            severity="high",
            risk_contribution=15,
            metric_value=subdomain_count,
        )
    if subdomain_count == 3:
        return Finding(
            technique="deep_subdomains",
            explanation="Three subdomain levels is uncommon for direct user-facing domains and elevated in phishing.",
            observation=f"Domain has {subdomain_count} subdomain levels.",
            severity="medium",
            risk_contribution=7,
            metric_value=subdomain_count,
        )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 5. Special character density (underscores etc.)
# ─────────────────────────────────────────────────────────────────────────────

def check_special_chars(name: str) -> Optional[Finding]:
    """Underscores aren't valid in registered domains but appear in subdomains/paths."""
    # Within a registered name, only letters, digits, and hyphens are valid.
    # Anything else here would already indicate invalid/abusive use.
    suspicious = sum(1 for c in name if not (c.isalnum() or c == "-"))
    if suspicious > 0:
        return Finding(
            technique="invalid_characters",
            explanation="Registered domain names should only contain letters, digits, and hyphens; other characters indicate parsing tricks or invalid input.",
            observation=f"Found {suspicious} non-standard character(s) in the registered name.",
            severity="high",
            risk_contribution=20,
            metric_value=suspicious,
        )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 6. Shannon entropy
# ─────────────────────────────────────────────────────────────────────────────

def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    freq = Counter(s)
    length = len(s)
    return -sum((c / length) * math.log2(c / length) for c in freq.values())


def check_entropy(name: str) -> Optional[Finding]:
    """Wong (2023, arXiv:2304.07943) + Splunk ESCU: entropy >4.0 strongly suggests DGA."""
    if len(name) < 6:
        return None  # short names always have low entropy, unreliable
    ent = shannon_entropy(name)
    if ent >= 4.2:
        return Finding(
            technique="very_high_entropy",
            explanation="Shannon entropy above 4.2 strongly indicates algorithmically generated (DGA) domains used by malware C2 (Wong 2023, Splunk ESCU).",
            observation=f"Entropy is {ent:.2f}, indicative of random/algorithmic generation.",
            severity="high",
            risk_contribution=18,
            metric_value=round(ent, 3),
        )
    if ent >= 3.7:
        return Finding(
            technique="elevated_entropy",
            explanation="Elevated character entropy (3.7+) is a known feature of DGA/random domains.",
            observation=f"Entropy is {ent:.2f}, higher than typical legitimate domains.",
            severity="medium",
            risk_contribution=8,
            metric_value=round(ent, 3),
        )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 7. Vowel-consonant ratio
# ─────────────────────────────────────────────────────────────────────────────

def check_vowel_ratio(name: str) -> Optional[Finding]:
    """Schiavoni et al. (2014) Phoenix DGA tracker: vowel ratio is a strong DGA indicator."""
    letters = [c for c in name if c.isalpha()]
    if len(letters) < 5:
        return None
    vowels = sum(1 for c in letters if c in "aeiouy")
    ratio = vowels / len(letters)
    # English averages ~38% vowels; <15% or >65% is unnatural
    if ratio < 0.15:
        return Finding(
            technique="low_vowel_ratio",
            explanation="English-like domains average ~38% vowels; very low ratios indicate non-pronounceable strings (Schiavoni et al. 2014).",
            observation=f"Only {ratio:.0%} of letters are vowels, well below natural English distribution.",
            severity="high",
            risk_contribution=12,
            metric_value=round(ratio, 3),
        )
    if ratio < 0.22:
        return Finding(
            technique="below_normal_vowels",
            explanation="Vowel ratios below 22% suggest unnatural / generated strings.",
            observation=f"Only {ratio:.0%} of letters are vowels, slightly below natural distribution.",
            severity="medium",
            risk_contribution=6,
            metric_value=round(ratio, 3),
        )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 8. Long consonant runs
# ─────────────────────────────────────────────────────────────────────────────

def check_consonant_runs(name: str) -> Optional[Finding]:
    """Long consonant runs are unpronounceable; common in DGAs."""
    longest = 0
    current = 0
    for c in name:
        if c.isalpha() and c not in "aeiouy":
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    if longest >= 6:
        return Finding(
            technique="long_consonant_run",
            explanation="Runs of 6+ consonants are unpronounceable in English and characteristic of DGA-generated names (FANCI - Schüppen et al. 2018).",
            observation=f"Longest consonant run is {longest} characters, unnatural for human-chosen names.",
            severity="high",
            risk_contribution=12,
            metric_value=longest,
        )
    if longest == 5:
        return Finding(
            technique="consonant_run",
            explanation="Five consecutive consonants is unusual in natural language and slightly elevated in DGAs.",
            observation=f"Longest consonant run is {longest} characters.",
            severity="medium",
            risk_contribution=6,
            metric_value=longest,
        )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 9. Bigram naturalness
# ─────────────────────────────────────────────────────────────────────────────

def check_bigram_naturalness(name: str) -> Optional[Finding]:
    """Antonakakis et al. (2012) Pleiades + Schiavoni et al. (2014) Phoenix:
    legitimate domains use common English bigrams; DGAs do not."""
    letters = "".join(c for c in name if c.isalpha())
    if len(letters) < 6:
        return None
    bigrams = [letters[i:i+2] for i in range(len(letters) - 1)]
    if not bigrams:
        return None
    rare_count = sum(1 for bg in bigrams if bg not in COMMON_BIGRAMS)
    rare_ratio = rare_count / len(bigrams)
    if rare_ratio >= 0.7:
        return Finding(
            technique="unnatural_bigrams",
            explanation="Random/DGA strings produce many character pairs that don't occur in English; legitimate domains use common bigrams (Pleiades, Phoenix DGA classifiers).",
            observation=f"{rare_ratio:.0%} of character pairs are uncommon in English, suggesting non-linguistic generation.",
            severity="high",
            risk_contribution=14,
            metric_value=round(rare_ratio, 3),
        )
    if rare_ratio >= 0.5:
        return Finding(
            technique="uncommon_bigrams",
            explanation="Half or more uncommon bigrams suggests the name is partly random or non-English.",
            observation=f"{rare_ratio:.0%} of character pairs are uncommon in English.",
            severity="medium",
            risk_contribution=7,
            metric_value=round(rare_ratio, 3),
        )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 10. Risky TLD
# ─────────────────────────────────────────────────────────────────────────────

def check_tld_reputation(tld: str) -> Optional[Finding]:
    """Spamhaus 'Top Abused TLDs' + Interisle 'Phishing Landscape' reports."""
    base_tld = tld.split(".")[-1]  # for compound TLDs use the rightmost
    if base_tld in HIGH_ABUSE_TLDS:
        reason = HIGH_ABUSE_TLDS[base_tld]
        return Finding(
            technique="high_abuse_tld",
            explanation="Some TLDs have abuse rates many times higher than .com per Spamhaus and Interisle's Phishing Landscape reports.",
            observation=f"TLD '.{base_tld}' is on the high-abuse list: {reason}.",
            severity="high",
            risk_contribution=20,
            metric_value=None,
        )
    if base_tld not in LOW_ABUSE_TLDS and len(base_tld) >= 2:
        return Finding(
            technique="non_mainstream_tld",
            explanation="TLDs outside the well-established set (.com, .org, .net, ccTLDs) have moderately elevated risk profiles.",
            observation=f"TLD '.{base_tld}' is not in the trustworthy mainstream set.",
            severity="low",
            risk_contribution=3,
            metric_value=None,
        )
    return None



def check_phishing_keywords(name: str) -> Optional[Finding]:
    """Marchal et al. (2014) PhishStorm + Garera et al. (2007): keyword presence
    derived from analyzed phishing corpora."""
    found = []
    # Split by separators and also check for substring presence
    tokens = re.split(r"[-._]", name)
    for token in tokens:
        if token in PHISHING_KEYWORDS:
            found.append(token)
    # Also check substring matches for keywords merged without separators.
    # Threshold of 4 catches strong short signals like 'auth' while excluding
    # 3-char words ('pay', 'ssl') that are too prone to false positives.
    for kw in PHISHING_KEYWORDS:
        if kw not in found and len(kw) >= 4 and kw in name:
            found.append(kw)
 
    found = list(dict.fromkeys(found))  # dedupe, preserve order
    if len(found) >= 3:
        return Finding(
            technique="multiple_phishing_keywords",
            explanation="Multiple phishing-associated keywords (e.g. 'login', 'secure', 'verify') in one domain is a strong phishing signal (Marchal et al. 2014, Garera et al. 2007).",
            observation=f"Found {len(found)} phishing keywords: {', '.join(found)}.",
            severity="high",
            risk_contribution=22,
            metric_value=len(found),
        )
    if len(found) == 2:
        return Finding(
            technique="phishing_keywords",
            explanation="Two phishing-associated keywords together is a strong indicator of social-engineering intent.",
            observation=f"Found 2 phishing keywords: {', '.join(found)}.",
            severity="high",
            risk_contribution=14,
            metric_value=2,
        )
    if len(found) == 1:
        return Finding(
            technique="phishing_keyword",
            explanation="A single phishing keyword is a moderate indicator, especially when combined with other signals.",
            observation=f"Found phishing keyword: '{found[0]}'.",
            severity="medium",
            risk_contribution=8,
            metric_value=1,
        )
    return None

# ─────────────────────────────────────────────────────────────────────────────
# 13. Hex-like patterns
# ─────────────────────────────────────────────────────────────────────────────

def check_hex_patterns(name: str) -> Optional[Finding]:
    """Long hex sequences indicate malware C2 / fast-flux infrastructure."""
    # Look for runs of [0-9a-f] of length ≥ 8 that include both letters AND digits
    matches = re.findall(r"[0-9a-f]{8,}", name)
    hex_like = [m for m in matches if any(c.isdigit() for c in m) and any(c.isalpha() for c in m)]
    if hex_like:
        longest = max(hex_like, key=len)
        if len(longest) >= 12:
            return Finding(
                technique="long_hex_pattern",
                explanation="Long hexadecimal-looking strings often indicate malware C2 servers, fast-flux infrastructure, or auto-generated identifiers.",
                observation=f"Found hex-like sequence '{longest}' ({len(longest)} chars) in the domain.",
                severity="high",
                risk_contribution=12,
                metric_value=len(longest),
            )
        if len(longest) >= 8:
            return Finding(
                technique="hex_pattern",
                explanation="Hexadecimal-style mixed alphanumeric runs are common in malware infrastructure naming.",
                observation=f"Found hex-like sequence '{longest}' in the domain.",
                severity="medium",
                risk_contribution=6,
                metric_value=len(longest),
            )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 14. Character repetition
# ─────────────────────────────────────────────────────────────────────────────

def check_repetition(name: str) -> Optional[Finding]:
    """Excessive character repetition is a typosquatting/DGA pattern."""
    if not name:
        return None
    # Find runs of repeated identical characters
    longest_run = 1
    current = 1
    for i in range(1, len(name)):
        if name[i] == name[i - 1]:
            current += 1
            longest_run = max(longest_run, current)
        else:
            current = 1
    if longest_run >= 4:
        return Finding(
            technique="excessive_repetition",
            explanation="Four or more identical characters in a row is highly unusual in legitimate domain names.",
            observation=f"Found a run of {longest_run} identical characters.",
            severity="high",
            risk_contribution=10,
            metric_value=longest_run,
        )
    if longest_run == 3:
        return Finding(
            technique="character_repetition",
            explanation="Triple-character repetition is mildly elevated and common in typosquatting variants.",
            observation=f"Found a run of {longest_run} identical characters.",
            severity="low",
            risk_contribution=4,
            metric_value=longest_run,
        )
    return None
# ─────────────────────────────────────────────────────────────────────────────
# 16. Compound naturalness (multiple weak signals stacking)
# ─────────────────────────────────────────────────────────────────────────────

def check_compound_naturalness(findings: list[Finding]) -> Optional[Finding]:
    """Antonakakis et al. (2012) Pleiades + Schiavoni et al. (2014) Phoenix:
    combined-feature classifiers outperform individual-threshold approaches.
    Multiple weak randomness signals stacking is itself a strong signal —
    any one feature could be a quirky-but-legit domain, but 3+ together
    is the academic definition of an unnatural string."""
    matched = [f for f in findings if f.technique in RANDOMNESS_TECHNIQUES]
    n = len(matched)
    if n >= 5:
        return Finding(
            technique="strongly_unnatural_pattern",
            explanation="Five or more independent lexical-randomness signals firing together is overwhelming evidence of an algorithmically generated or non-human-chosen name.",
            observation=f"{n} randomness/unnaturalness indicators triggered together: {', '.join(f.technique for f in matched[:6])}.",
            severity="high",
            risk_contribution=28,
            metric_value=n,
        )
    if n >= 4:
        return Finding(
            technique="compound_unnatural_pattern",
            explanation="Four independent lexical-randomness signals together is the academic definition of an unnatural string (combined-feature DGA classifiers — Antonakakis et al. 2012, Schiavoni et al. 2014).",
            observation=f"{n} randomness/unnaturalness indicators triggered together: {', '.join(f.technique for f in matched)}.",
            severity="high",
            risk_contribution=22,
            metric_value=n,
        )
    if n >= 3:
        return Finding(
            technique="multiple_unnatural_signals",
            explanation="Three lexical-randomness signals firing together is a strong indicator of algorithmic or non-human-chosen names — individually each could be benign, but the combination is what real DGA classifiers detect on.",
            observation=f"{n} randomness/unnaturalness indicators triggered together: {', '.join(f.technique for f in matched)}.",
            severity="high",
            risk_contribution=15,
            metric_value=n,
        )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Risk aggregation
# ─────────────────────────────────────────────────────────────────────────────

def compute_risk(findings: list[Finding]) -> dict:
    raw = sum(f.risk_contribution for f in findings)
    score = min(100.0, raw)
    if score >= 75:
        level = "HIGHLY_MALICIOUS"
    elif score >= 50:
        level = "LIKELY_MALICIOUS"
    elif score >= 25:
        level = "SUSPICIOUS"
    elif score >= 12:
        level = "LOW_RISK"
    else:
        level = "BENIGN"
    return {"score": round(score, 1), "level": level}


def build_summary(findings: list[Finding], risk: dict) -> str:
    if not findings:
        return "No suspicious indicators detected. The domain appears benign on lexical analysis."
    high = [f for f in findings if f.severity == "high"]
    med = [f for f in findings if f.severity == "medium"]
    low = [f for f in findings if f.severity == "low"]
    parts = []
    if high:
        parts.append(f"{len(high)} high-severity indicator(s)")
    if med:
        parts.append(f"{len(med)} medium-severity indicator(s)")
    if low:
        parts.append(f"{len(low)} low-severity indicator(s)")
    return f"Domain rated {risk['level']} ({risk['score']}/100) based on {', '.join(parts)}."


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────────────

def analyze(domain: str) -> dict:
    name, tld, parts = strip_domain(domain)
    findings: list[Finding] = []

    checks = [
        check_domain_length(name),
        check_hyphens(name),
        check_digit_ratio(name),
        check_subdomain_depth(parts, tld),
        check_special_chars(name),
        check_entropy(name),
        check_vowel_ratio(name),
        check_consonant_runs(name),
        check_bigram_naturalness(name),
        check_tld_reputation(tld),
        check_phishing_keywords(name),
        check_hex_patterns(name),
        check_repetition(name),
    ]
    findings = [c for c in checks if c is not None]

    # Compound check runs over collected findings to catch stacked weak signals.
    compound = check_compound_naturalness(findings)
    if compound is not None:
        findings.append(compound)

    findings.sort(key=lambda f: f.risk_contribution, reverse=True)

    risk = compute_risk(findings)
    risk["summary"] = build_summary(findings, risk)

    # Compute raw metrics for context
    letters = "".join(c for c in name if c.isalpha())
    metrics = {
        "registered_name": name,
        "tld": tld,
        "name_length": len(name),
        "hyphen_count": name.count("-"),
        "digit_count": sum(c.isdigit() for c in name),
        "subdomain_count": max(0, len(parts) - len(tld.split(".")) - 1),
        "shannon_entropy": round(shannon_entropy(name), 3),
        "vowel_ratio": round(
            sum(1 for c in letters if c in "aeiouy") / len(letters), 3
        ) if letters else 0.0,
    }

    return {
        "domain": domain,
        "risk": risk,
        "findings": [asdict(f) for f in findings],
        "metrics": metrics,
    }

def main():
    parser = argparse.ArgumentParser(
        description="Score a domain on intrinsic indicators of maliciousness.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --domain example.com
  %(prog)s --domain secure-paypal-login.tk --pretty
  %(prog)s --domain xkqzwprblqwer.top --pretty
  echo '{"domain":"suspicious.com"}' | %(prog)s --stdin
        """,
    )
    parser.add_argument("--domain", "-d", help="Domain to evaluate")
    parser.add_argument("--pretty", "-p", action="store_true", help="Pretty-print JSON")
    parser.add_argument("--stdin", action="store_true", help='Read JSON from stdin ({"domain":"…"})')
    args = parser.parse_args()

    if args.stdin:
        data = json.load(sys.stdin)
        domain = data["domain"]
    elif args.domain:
        domain = args.domain
    else:
        parser.error("Provide --domain or use --stdin")
        return

    result = analyze(domain)
    indent = 2 if args.pretty else None
    print(json.dumps(result, indent=indent, ensure_ascii=False))


if __name__ == "__main__":
    main()
