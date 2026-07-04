#!/usr/bin/env python3
"""
Enriches raw signals with specialty, geography, EHR, compliance, and objection inference.
Input:  .tmp/raw_signals.json
Output: .tmp/enriched_signals.json
API:    None (keyword matching only)
"""

import json
import os
import re
import sys

from dotenv import load_dotenv
load_dotenv()

CONFIG_PATH = "config/config.json"
INPUT_PATH = ".tmp/raw_signals.json"
OUTPUT_PATH = ".tmp/enriched_signals.json"


def load_json(path):
    with open(path) as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def extract_first_name(name):
    """Extract first name, stripping titles."""
    name = re.sub(r"^(Dr\.|Mr\.|Ms\.|Mrs\.|Prof\.)\s+", "", name.strip())
    parts = name.split()
    return parts[0] if parts else name


def infer_specialty(text):
    """Infer specialty profile from combined text. First match wins (most specific first)."""
    t = text.lower()
    patterns = [
        (
            ["hospital", "health system", "nhs trust", "icu ", " ed ", "procurement",
             " cio ", " cmio ", " cmo ", "enterprise pricing", "120 clinician", "it department"],
            "enterprise_health_system",
        ),
        (
            ["practice manager", "clinic manager", "operations manager", "practice admin"],
            "practice_manager",
        ),
        (
            ["gp ", "gps", " gp,", "general practice", "family medicine", "primary care",
             "bulk bill", " mbs ", "family med", "10-minute consult", "10 minute consult"],
            "family_medicine_gp",
        ),
        (
            ["psychiatr", "mental health", "psychology", "psychologist", "therapy note",
             "therapist", "counsell", "dsm", "therapy documentation"],
            "mental_health",
        ),
        (
            ["cardiol", "gastro", "oncol", "ortho", "dermatol", "neurol",
             "endocrin", "specialist", "cardiologist"],
            "medical_specialist",
        ),
        (
            ["nurse", " np ", "nursing", "nurse practitioner", "midwife", "community health"],
            "nurse_np",
        ),
        (
            ["allied health", "physio", "occupational therapy", "dietit",
             "social work", "speech"],
            "allied_health",
        ),
        (["dentist", "dental", "orthodont", "oral health"], "dentist"),
        (["vet ", "veterinar", "animal hospital"], "veterinarian"),
    ]
    for keywords, profile in patterns:
        if any(kw in t for kw in keywords):
            return profile
    return "unknown"


def infer_geography(text, email):
    """Infer geography from email domain and keywords. UK > AU > US (default)."""
    t = text.lower()
    e = email.lower()

    # UK: explicit domain or NHS keywords
    if any(x in e for x in [".nhs.uk", ".co.uk", ".uk"]) or any(
        x in t for x in ["nhs ", "nhs trust", "emis", "systmone", "nice ", "uk gdpr"]
    ):
        return "UK"

    # AU: .au domain or Australian keywords
    if e.endswith(".com.au") or e.endswith(".au") or any(
        x in t for x in ["australia", "medicare", " mbs ", "bulk billing",
                          "best practice", "genie solutions", "medical director"]
    ):
        return "AU"

    # US default
    return "US"


def infer_ehr(specialty, geography, config):
    """Map specialty + geography to most likely EHR from config."""
    ehr_map = config.get("ehr_map", {})
    if geography == "AU":
        if specialty in ["family_medicine_gp", "practice_manager", "nurse_np", "allied_health"]:
            return ehr_map.get("AU_gp", "Best Practice or Medical Director")
        else:
            return ehr_map.get("AU_specialist", "Genie Solutions")
    elif geography == "UK":
        return ehr_map.get("UK", "EMIS or SystmOne")
    else:  # US
        if specialty == "enterprise_health_system":
            return ehr_map.get("US_enterprise", "Epic or Cerner")
        else:
            return ehr_map.get("US_small", "Athenahealth or eClinicalWorks")


def infer_compliance(geography, config):
    """Return compliance frameworks for the inferred geography."""
    return config.get("compliance_map", {}).get(geography, ["HIPAA", "BAA required"])


def infer_objection(specialty):
    """Return the top objection most likely from this specialty profile."""
    objections = {
        "family_medicine_gp": "Does it work in a 10-min consult?",
        "mental_health": "Patient consent for recording",
        "medical_specialist": "Does it match my specialty's note format?",
        "enterprise_health_system": "HIPAA/data security/BAA",
        "practice_manager": "Will doctors actually use it?",
        "nurse_np": "Does it work on mobile / in community settings?",
        "allied_health": "Does it support my documentation format?",
        "dentist": "Does it handle dental-specific terminology?",
        "veterinarian": "Is it designed for veterinary workflows?",
        "unknown": "What happens to patient data?",
    }
    return objections.get(specialty, "What happens to patient data?")


def apollo_enrich(email, api_key):
    """Call Apollo People Match API. Returns dict of enriched fields, or {} on failure."""
    import urllib.request
    try:
        payload = json.dumps({
            "api_key": api_key,
            "email": email,
            "reveal_personal_emails": False,
        }).encode()
        req = urllib.request.Request(
            "https://api.apollo.io/api/v1/people/match",
            data=payload,
            headers={"Content-Type": "application/json", "Cache-Control": "no-cache"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        person = data.get("person") or {}
        org = person.get("organization") or {}
        return {
            "apollo_title": person.get("title", ""),
            "apollo_company": org.get("name", ""),
            "apollo_company_size": org.get("estimated_num_employees"),
            "apollo_industry": org.get("industry", ""),
            "apollo_linkedin": person.get("linkedin_url", ""),
        }
    except Exception:
        return {}


def enrich_signal(signal, config, apollo_key=None):
    """Add all enrichment fields to a single signal."""
    combined_text = " ".join([
        signal.get("subject", ""),
        signal.get("body_snippet", ""),
        signal.get("sender_name", ""),
    ])
    email = signal.get("sender_email", "")

    # Apollo enrichment (optional — skipped if no key or call fails)
    apollo = apollo_enrich(email, apollo_key) if apollo_key else {}

    # Specialty: prefer Apollo title if available (more reliable than email body keywords)
    specialty_text = apollo.get("apollo_title", "") + " " + combined_text
    specialty = infer_specialty(specialty_text)
    geography = infer_geography(combined_text, email)

    enriched = signal.copy()
    enriched["first_name"] = extract_first_name(signal.get("sender_name", ""))
    enriched["specialty_profile"] = specialty
    enriched["geography"] = geography
    enriched["compliance"] = infer_compliance(geography, config)
    enriched["ehr_likely"] = infer_ehr(specialty, geography, config)
    enriched["top_objection"] = infer_objection(specialty)

    # Merge Apollo fields (only set fields that returned a value)
    for k, v in apollo.items():
        if v:
            enriched[k] = v

    return enriched


def main():
    if not os.path.exists(CONFIG_PATH):
        print(f"ERROR: {CONFIG_PATH} not found", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(INPUT_PATH):
        print(f"ERROR: {INPUT_PATH} not found — run scan_inbox.py first or use --dry-run", file=sys.stderr)
        sys.exit(1)

    config = load_json(CONFIG_PATH)
    signals = load_json(INPUT_PATH)

    apollo_key = os.getenv("APOLLO_API_KEY") or None
    if apollo_key:
        print(f"Apollo enrichment enabled")
    enriched = [enrich_signal(s, config, apollo_key) for s in signals]
    save_json(OUTPUT_PATH, enriched)

    print(f"{len(enriched)} leads enriched")


if __name__ == "__main__":
    main()
