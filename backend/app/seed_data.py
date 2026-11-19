"""Realistic, entirely fictitious demo content: people, clinical histories, phone numbers, staff.

Everything here is *deterministic* (seeded per record), so re-seeding never changes a patient's
phone number or history, and two servers produce identical demo data. Nothing is a real person:
names are combined from common first-name / surname pools, phone numbers are random.
"""

from __future__ import annotations

import random
import re
from datetime import date
from typing import Any

DEMO_YEAR = 2026  # fixed, so a patient's age doesn't change on their birthday

# --------------------------------------------------------------------------------------------
# People
# --------------------------------------------------------------------------------------------

# (weight, cities, male first names, female first names, surnames). Cities all exist in the
# profile address table (seed_profiles._CITY_DETAILS).
_COMMUNITIES: list[tuple[int, list[str], list[str], list[str], list[str]]] = [
    (22, ["New Delhi", "New Delhi", "Lucknow", "Jaipur", "Chandigarh", "Bhopal"],
     ["Aarav", "Rohit", "Amit", "Vikas", "Manish", "Ankit", "Gaurav", "Nitin", "Sachin", "Mohit",
      "Tarun", "Ajay", "Pankaj", "Rajiv", "Sandeep", "Dinesh", "Harsh", "Yash", "Kunal", "Lokesh"],
     ["Neha", "Pooja", "Anjali", "Ritu", "Swati", "Nidhi", "Shweta", "Sunita", "Rekha", "Meena",
      "Kavita", "Shalini", "Preeti", "Seema", "Aarti", "Komal", "Divya", "Isha", "Priya", "Tanu"],
     ["Sharma", "Gupta", "Verma", "Khanna", "Mehra", "Bhatia", "Arora", "Kapoor", "Chopra",
      "Tyagi", "Yadav", "Mishra", "Tripathi", "Srivastava", "Pandey", "Saxena", "Rathore",
      "Agarwal", "Bansal", "Jindal"]),
    (13, ["Mumbai", "Pune", "Ahmedabad", "Pune", "Mumbai"],
     ["Aditya", "Omkar", "Swapnil", "Prathamesh", "Rahul", "Nilesh", "Sagar", "Chetan", "Hardik",
      "Jay", "Parth", "Dhruv", "Mihir", "Ketan", "Viraj"],
     ["Sneha", "Pallavi", "Rutuja", "Shruti", "Madhuri", "Vaishali", "Janhvi", "Ketki", "Hetal",
      "Foram", "Mansi", "Riddhi", "Aishwarya", "Gauri"],
     ["Patil", "Joshi", "Kulkarni", "Deshmukh", "Shinde", "Pawar", "More", "Gaikwad", "Naik",
      "Desai", "Shah", "Mehta", "Trivedi", "Modi", "Parikh", "Thakkar"]),
    (15, ["Bengaluru", "Chennai", "Hyderabad", "Kochi", "Vijayawada", "Chennai", "Bengaluru"],
     ["Karthik", "Arun", "Vignesh", "Sai", "Praveen", "Ramesh", "Suresh", "Anil", "Venkat",
      "Mahesh", "Naveen", "Krishna", "Harish", "Shyam", "Balaji", "Santhosh"],
     ["Lakshmi", "Divya", "Meera", "Anitha", "Kavya", "Deepa", "Revathi", "Padma", "Swathi",
      "Archana", "Nandini", "Aparna", "Sowmya", "Bhavana", "Janani"],
     ["Iyer", "Nair", "Menon", "Reddy", "Rao", "Naidu", "Krishnan", "Pillai", "Subramanian",
      "Gowda", "Hegde", "Shetty", "Varma", "Raman", "Narayanan", "Chandran", "Bhat"]),
    (8, ["Kolkata", "Guwahati", "Kolkata"],
     ["Arnab", "Subhajit", "Soumya", "Debashish", "Sourav", "Abhijit", "Rajat", "Tanmoy"],
     ["Ishita", "Moumita", "Sayani", "Rituparna", "Mitali", "Payel", "Tanushree", "Sreya"],
     ["Banerjee", "Mukherjee", "Chatterjee", "Das", "Ghosh", "Sen", "Bose", "Dutta", "Roy",
      "Sarkar", "Chakraborty", "Bhattacharya"]),
    (8, ["Ludhiana", "Chandigarh", "Ludhiana", "New Delhi"],
     ["Gurpreet", "Harjot", "Jaspreet", "Amandeep", "Manpreet", "Parminder", "Simranjit",
      "Kulwinder"],
     ["Harleen", "Simran", "Manpreet", "Jasleen", "Gurleen", "Navneet", "Rupinder", "Amrita"],
     ["Singh", "Gill", "Sandhu", "Dhillon", "Bajwa", "Grewal", "Sidhu", "Brar", "Randhawa"]),
    (10, ["Hyderabad", "Lucknow", "New Delhi", "Bhopal", "Mumbai"],
     ["Imran", "Faisal", "Zaid", "Arif", "Adnan", "Salman", "Rehan", "Sameer", "Aamir", "Farhan"],
     ["Ayesha", "Nazia", "Farida", "Shabana", "Zoya", "Iqra", "Sana", "Rukhsar", "Nasreen",
      "Humaira"],
     ["Khan", "Ansari", "Siddiqui", "Qureshi", "Sheikh", "Mirza", "Farooqui", "Ali", "Hussain",
      "Qazi"]),
    (3, ["Kochi", "Mumbai", "Bengaluru"],
     ["Joseph", "Thomas", "Samuel", "Abraham", "Neil", "Joel", "Mathew"],
     ["Mary", "Anju", "Elizabeth", "Rhea", "Ira", "Sheeba", "Tessa"],
     ["Thomas", "Varghese", "D'Souza", "Fernandes", "George", "Mathew", "Pereira"]),
]

# Roughly the Indian distribution: O+ and B+ dominate.
_BLOOD = [("O+", 36), ("B+", 31), ("A+", 21), ("AB+", 7), ("O-", 2), ("B-", 1), ("A-", 1),
          ("AB-", 1)]

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"]


def _weighted(rng: random.Random, pairs: list[tuple[Any, int]]) -> Any:
    return rng.choices([p[0] for p in pairs], weights=[p[1] for p in pairs])[0]


def realistic_phone(key: str) -> str:
    """A believable Indian mobile number (+91 9XXXX XXXXX), stable for a given key."""
    rng = random.Random(f"phone:{key}")
    lead = rng.choices(["9", "8", "7", "6"], weights=[46, 30, 18, 6])[0]
    digits = lead + "".join(str(rng.randrange(10)) for _ in range(9))
    return f"+91 {digits[:5]} {digits[5:]}"


def _age_for(rng: random.Random, *, child: bool) -> int:
    if child:
        return rng.randint(1, 15)
    band = rng.choices(
        [(16, 17), (18, 34), (35, 54), (55, 74), (75, 88)], weights=[3, 33, 33, 24, 7]
    )[0]
    return rng.randint(*band)


def _dob(rng: random.Random, age: int) -> date:
    return date(DEMO_YEAR - age, rng.randint(1, 12), rng.randint(1, 28))


# --------------------------------------------------------------------------------------------
# Clinical histories
# --------------------------------------------------------------------------------------------

# Structured detail per MRN, used for both the one-line note and the MongoDB profile.
CLINICAL: dict[str, dict[str, Any]] = {}

_ALLERGIES = [
    ("Penicillin", "Skin rash", "moderate"),
    ("Sulfonamides", "Rash", "mild"),
    ("Peanuts", "Hives", "moderate"),
    ("NSAIDs (ibuprofen)", "Urticaria", "moderate"),
    ("Dust mites", "Sneezing, watery eyes", "mild"),
    ("Shellfish", "Swelling of lips", "moderate"),
    ("Latex", "Contact dermatitis", "mild"),
    ("Cephalosporins", "Rash", "mild"),
]

_SCHEMES = [("none", None, 34), ("private", "Star Health", 14), ("private", "HDFC Ergo", 10),
            ("private", "Niva Bupa", 6), ("esi", None, 8), ("cghs", None, 9),
            ("ayushman_bharat", None, 10), ("private", "Care Health", 5), ("none", None, 4)]


def _month(rng: random.Random) -> str:
    return rng.choice(_MONTHS)


def _adult_conditions(
    rng: random.Random, age: int, sex: str
) -> list[tuple[str, str, list[tuple[str, str, str]]]]:
    """(condition, note text, medications) options the person is eligible for."""
    def year(lo: int, hi: int) -> int:
        return DEMO_YEAR - rng.randint(lo, hi)

    out: list[tuple[str, str, list[tuple[str, str, str]]]] = []
    if age >= 30:
        med = rng.choice([("Amlodipine", "5 mg"), ("Telmisartan", "40 mg"), ("Losartan", "50 mg")])
        sys_, dia = rng.randint(124, 142), rng.randint(78, 90)
        out.append(("Essential hypertension",
                    f"Hypertension since {year(1, 12)}; {med[0]} {med[1]} OD, "
                    f"BP {sys_}/{dia} ({_month(rng)} 2026).",
                    [(med[0], med[1], "OD")]))
    if age >= 35:
        a1c = round(rng.uniform(6.4, 8.6), 1)
        out.append(("Type 2 diabetes mellitus",
                    f"T2DM since {year(1, 14)}; metformin 500 mg BD, "
                    f"HbA1c {a1c}% ({_month(rng)} 2026).",
                    [("Metformin", "500 mg", "BD")]
                    + ([("Glimepiride", "1 mg", "OD")] if a1c > 7.6 else [])))
    if age >= 40:
        dose = rng.choice(["10 mg", "20 mg"])
        out.append(("Dyslipidaemia",
                    f"Dyslipidaemia; atorvastatin {dose} HS, LDL {rng.randint(88, 138)} mg/dL "
                    f"({_month(rng)} 2026).",
                    [("Atorvastatin", dose, "HS")]))
    if age >= 25:
        out.append(("GERD",
                    "GERD; pantoprazole 40 mg OD before breakfast, advised diet modification.",
                    [("Pantoprazole", "40 mg", "OD")]))
        tsh = round(rng.uniform(1.8, 6.2), 1)
        if sex == "female" or rng.random() < 0.2:
            dose = rng.choice(["25 mcg", "50 mcg", "75 mcg"])
            out.append(("Hypothyroidism",
                        f"Hypothyroidism on levothyroxine {dose} OD; TSH {tsh} mIU/L "
                        f"({_month(rng)} 2026).",
                        [("Levothyroxine", dose, "OD")]))
    if age >= 50:
        out.append(("Osteoarthritis (knees)",
                    "Bilateral knee osteoarthritis; physiotherapy, paracetamol PRN, "
                    "topical diclofenac.", [("Paracetamol", "500 mg", "PRN")]))
    if (sex == "male" and age >= 50) or (sex == "female" and age >= 58):
        out.append(("Coronary artery disease",
                    f"CAD, stent {year(1, 8)}; aspirin 75 mg OD, atorvastatin 40 mg HS, "
                    "metoprolol 25 mg BD. Cardiology follow-up every 6 months.",
                    [("Aspirin", "75 mg", "OD"), ("Atorvastatin", "40 mg", "HS"),
                     ("Metoprolol", "25 mg", "BD")]))
    if 18 <= age <= 50:
        out.append(("Migraine without aura",
                    "Migraine without aura, 2-3 episodes/month; sumatriptan 50 mg PRN, "
                    "trigger diary advised.", [("Sumatriptan", "50 mg", "PRN")]))
        out.append(("Allergic rhinitis",
                    "Seasonal allergic rhinitis; cetirizine 10 mg PRN, saline nasal rinse.",
                    [("Cetirizine", "10 mg", "PRN")]))
    if sex == "female" and 18 <= age <= 40:
        out.append(("PCOS",
                    "PCOS with irregular cycles; lifestyle plan, metformin 500 mg OD.",
                    [("Metformin", "500 mg", "OD")]))
        out.append(("Iron-deficiency anaemia",
                    f"Iron-deficiency anaemia; Hb {round(rng.uniform(9.4, 11.4), 1)} g/dL "
                    f"({_month(rng)} 2026), ferrous ascorbate 100 mg OD.",
                    [("Ferrous ascorbate", "100 mg", "OD")]))
    if age >= 18:
        out.append(("Bronchial asthma",
                    "Mild persistent asthma; budesonide-formoterol inhaler BD, salbutamol PRN.",
                    [("Budesonide-formoterol", "200/6 mcg", "BD"),
                     ("Salbutamol", "100 mcg", "PRN")]))
        out.append(("Vitamin D deficiency",
                    f"Vitamin D deficiency (25-OH D {rng.randint(9, 19)} ng/mL); "
                    "cholecalciferol 60,000 IU weekly x 8.",
                    [("Cholecalciferol", "60,000 IU", "Weekly")]))
        out.append(("Lumbar spondylosis",
                    "Chronic mechanical low back pain; core-strengthening physio, "
                    "no neurological deficit.", []))
        out.append(("Post-operative follow-up",
                    f"Laparoscopic cholecystectomy {year(1, 3)}; recovered, annual review.", []))
    return out


def _child_conditions(
    rng: random.Random, age: int
) -> list[tuple[str, str, list[tuple[str, str, str]]]]:
    return [
        ("Growth & immunisation monitoring",
         f"Routine growth monitoring; immunisation up to date for age ({age} y).", []),
        ("Intermittent asthma",
         "Mild intermittent asthma, viral-triggered; salbutamol inhaler with spacer PRN.",
         [("Salbutamol", "100 mcg", "PRN")]),
        ("Recurrent tonsillitis",
         f"Recurrent tonsillitis ({rng.randint(3, 5)} episodes in last year); ENT opinion "
         "advised if it persists.", []),
        ("Atopic dermatitis",
         "Atopic dermatitis; emollients, mild topical steroid for flares.",
         [("Hydrocortisone 1% cream", "Thin layer", "BD (flares)")]),
        ("Allergic rhinitis",
         "Allergic rhinitis; levocetirizine 2.5 mg PRN.", [("Levocetirizine", "2.5 mg", "PRN")]),
        ("Mild iron deficiency",
         "Mild iron-deficiency anaemia; iron drops, dietary advice given.",
         [("Ferrous fumarate drops", "3 mg/kg", "OD")]),
    ]


def _clinical_for(mrn: str, age: int, sex: str, *, key: int) -> dict[str, Any]:
    rng = random.Random(f"clin:{key}")
    options = _child_conditions(rng, age) if age < 16 else _adult_conditions(rng, age, sex)
    n = 1 if age < 16 else rng.choices([0, 1, 2, 3], weights=[10, 40, 35, 15])[0]
    chosen = rng.sample(options, k=min(n, len(options))) if options else []
    conditions = [c[0] for c in chosen]
    meds: list[tuple[str, str, str]] = []
    for _, _, m in chosen:
        for item in m:
            if item not in meds:
                meds.append(item)
    pool: list[tuple[str, str, str] | None] = [None, *_ALLERGIES]
    allergy = rng.choices(pool, weights=[62] + [5] * len(_ALLERGIES))[0]
    scheme, provider, _ = rng.choices(_SCHEMES, weights=[s[2] for s in _SCHEMES])[0]
    parts = [c[1] for c in chosen]
    parts.append(f"Allergy: {allergy[0]} ({allergy[1].lower()})." if allergy else "NKDA.")
    return {
        "conditions": conditions,
        "allergies": [allergy] if allergy else [],
        "meds": meds,
        "scheme": scheme,
        "provider": provider,
        "note": " ".join(parts)[:480],
    }


# --------------------------------------------------------------------------------------------
# Patient rows
# --------------------------------------------------------------------------------------------

PatientRow = tuple[str, str, date, str, str, str, str, str, str | None]


def _family_contact(rng: random.Random, name: str, age: int, sex: str, key: str) -> str:
    other = "female" if sex == "male" else "male"
    if age < 18:
        relation, gender = ("father", "male") if rng.random() < 0.5 else ("mother", "female")
    elif age >= 62:
        relation, gender = rng.choice([("son", "male"), ("daughter", "female"),
                                       ("spouse", other)])
    else:
        relation, gender = rng.choice([("spouse", other), ("spouse", other),
                                       ("brother" if sex == "male" else "sister", sex),
                                       ("father", "male"), ("mother", "female")])
    comm = rng.choice(_COMMUNITIES)
    first = rng.choice(comm[2] if gender == "male" else comm[3])
    return f"{first} {name.split()[-1]} ({relation}) · {realistic_phone('em:' + key)}"


def generate_patients(first_number: int, count: int, existing_names: set[str]) -> list[PatientRow]:
    """``count`` new fictitious patients with MRNs CAD-{first_number}... (children included)."""
    rows: list[PatientRow] = []
    used = set(existing_names)
    for offset in range(count):
        number = first_number + offset
        mrn = f"CAD-{number:06d}"
        rng = random.Random(f"patient:{number}")
        child = offset % 6 == 0  # one in six, so the paediatric clinic has a real panel
        sex = rng.choice(["male", "female"])
        weights = [c[0] for c in _COMMUNITIES]
        for _ in range(20):  # avoid exact duplicate names
            community = rng.choices(_COMMUNITIES, weights=weights)[0]
            first = rng.choice(community[2] if sex == "male" else community[3])
            name = f"{first} {rng.choice(community[4])}"
            if name not in used:
                break
        used.add(name)
        age = _age_for(rng, child=child)
        dob = _dob(rng, age)
        info = _clinical_for(mrn, age, sex, key=number)
        CLINICAL[mrn] = info
        rows.append((
            mrn, name, dob, sex, realistic_phone(mrn), rng.choice(community[1]),
            _weighted(rng, _BLOOD), _family_contact(rng, name, age, sex, mrn), info["note"],
        ))
    return rows


_DIABETES = re.compile(r"diabet", re.I)
_HTN = re.compile(r"hypertens|blood pressure", re.I)


def upgrade_existing(rows: list[PatientRow]) -> list[PatientRow]:
    """Give the original hand-written patients realistic phones and richer clinical notes.

    Names, dates of birth, cities and MRNs are untouched (other seed logic refers to them).
    """
    out: list[PatientRow] = []
    for index, (mrn, name, dob, sex, _phone, city, blood, emergency, note) in enumerate(rows):
        age = DEMO_YEAR - dob.year
        info = _clinical_for(mrn, age, sex, key=10_000 + index)
        rng = random.Random(f"upgrade:{mrn}")
        original = (note or "").strip()
        if original:
            # Keep the author's intent, add specifics where the note names a known condition.
            if _DIABETES.search(original):
                info = {**info, "conditions": ["Type 2 diabetes mellitus"],
                        "meds": [("Metformin", "500 mg", "BD")]}
                original = (f"T2DM since {DEMO_YEAR - rng.randint(2, 12)}; metformin 500 mg BD, "
                            f"HbA1c {round(rng.uniform(6.6, 8.2), 1)}% ({_month(rng)} 2026).")
            elif _HTN.search(original):
                info = {**info, "conditions": ["Essential hypertension"],
                        "meds": [("Amlodipine", "5 mg", "OD")]}
                original = (f"Hypertension; amlodipine 5 mg OD, BP {rng.randint(126, 140)}/"
                            f"{rng.randint(78, 88)} ({_month(rng)} 2026).")
            allergy = info["allergies"][0] if info["allergies"] else None
            if "allerg" in original.lower():  # the note already says it; don't add another
                allergy = None
                info = {**info, "conditions": [], "meds": []}
                if "penicillin" in original.lower():
                    info["allergies"] = [("Penicillin", "Skin rash", "moderate")]
            suffix = (f" Allergy: {allergy[0]} ({allergy[1].lower()})." if allergy
                      else (" NKDA." if "allerg" not in original.lower() else ""))
            info = {**info, "note": (original + suffix)[:480]}
            if not info["conditions"] and "allerg" not in original.lower():
                info["conditions"] = [original.rstrip(".")[:120]]
        CLINICAL[mrn] = info
        em_name = emergency.split("·")[0].strip()
        out.append((mrn, name, dob, sex, realistic_phone(mrn), city, blood,
                    f"{em_name} · {realistic_phone('em:' + mrn)}", info["note"] or None))
    return out


# --------------------------------------------------------------------------------------------
# Staff, appointment types
# --------------------------------------------------------------------------------------------

EXTRA_STAFF = [  # (name, email, role-name)
    ("Pallavi Joshi", "receptionist3@cadence.dev", "receptionist"),
    ("Meenakshi Rao", "nurse3@cadence.dev", "triage_nurse"),
    ("Dr. Sanjana Rao", "doctor7@cadence.dev", "doctor"),
    ("Dr. Farah Siddiqui", "doctor8@cadence.dev", "doctor"),
    ("Dr. Anil Deshpande", "doctor9@cadence.dev", "doctor"),
    ("Dr. Tejas Kulkarni", "doctor10@cadence.dev", "doctor"),
]

EXTRA_DOCTORS = {
    "doctor7@cadence.dev": "ent",
    "doctor8@cadence.dev": "gynaecology",
    "doctor9@cadence.dev": "pulmonology",
    "doctor10@cadence.dev": "neurology",
}

EXTRA_TYPES = [  # (name, minutes, specialty)
    ("ENT consultation", 30, "ent"),
    ("Gynaecology consultation", 30, "gynaecology"),
    ("Pulmonology consultation", 30, "pulmonology"),
    ("Neurology consultation", 45, "neurology"),
]

# Staff documents for MongoDB (same shape as seed_profiles._STAFF_EXTRAS).


def _qual(degree: str, institution: str, year: int) -> dict[str, Any]:
    return {"degree": degree, "institution": institution, "year": year}


def staff_extras() -> dict[str, dict[str, Any]]:
    def doc(emp: str, dept: str, langs: list[str], phone: str, joined: date,
            detail: dict[str, Any], kind: str) -> dict[str, Any]:
        return {"employee_id": emp, "department": dept, "languages": langs,
                "contact": {"phone": phone},
                "employment": {"joined_on": joined.isoformat(), "status": "active"},
                kind: detail}

    return {
        "receptionist3@cadence.dev": doc(
            "REC-003", "Front desk", ["en", "hi", "mr"], realistic_phone("staff-rec3"),
            date(2023, 9, 4),
            {"counter": "Front desk 3", "shift_pattern": "rotating",
             "training": ["Patient registration", "Insurance & cashless desk"]}, "reception"),
        "nurse3@cadence.dev": doc(
            "NUR-003", "Emergency & triage", ["en", "hi", "te"], realistic_phone("staff-nur3"),
            date(2021, 11, 15),
            {"registration": {"council": "Delhi Nursing Council", "number": "DNC-63107"},
             "qualifications": [_qual("B.Sc Nursing", "Rufaida College of Nursing", 2018)],
             "certifications": [{"name": "BLS", "expires_on": date(2027, 5, 31).isoformat()},
                                {"name": "Emergency triage",
                                 "expires_on": date(2028, 2, 29).isoformat()}],
             "ward": "Emergency", "shift_pattern": "night"}, "nurse"),
        "doctor7@cadence.dev": doc(
            "DOC-007", "ENT", ["en", "hi", "mr"], realistic_phone("staff-doc7"),
            date(2019, 1, 7),
            {"registration": {"council": "Maharashtra Medical Council", "number": "MMC-84120"},
             "qualifications": [_qual("MBBS", "Grant Medical College", 2010),
                                _qual("MS (ENT)", "Seth GS Medical College", 2014)],
             "sub_specialties": ["Rhinology", "Paediatric ENT"], "experience_years": 12,
             "consultation_fee_inr": 700,
             "bio": "ENT surgeon seeing sinus, ear and throat problems in adults and children."},
            "doctor"),
        "doctor8@cadence.dev": doc(
            "DOC-008", "Obstetrics & Gynaecology", ["en", "hi", "ur"],
            realistic_phone("staff-doc8"), date(2017, 6, 19),
            {"registration": {"council": "Delhi Medical Council", "number": "DMC-40256"},
             "qualifications": [_qual("MBBS", "Lady Hardinge Medical College", 2008),
                                _qual("MD (Obs & Gynae)", "AIIMS Delhi", 2012)],
             "sub_specialties": ["Antenatal care", "PCOS & infertility"], "experience_years": 14,
             "consultation_fee_inr": 800,
             "bio": "Gynaecologist focusing on antenatal care and menstrual health."}, "doctor"),
        "doctor9@cadence.dev": doc(
            "DOC-009", "Pulmonology", ["en", "hi", "mr"], realistic_phone("staff-doc9"),
            date(2020, 2, 3),
            {"registration": {"council": "Maharashtra Medical Council", "number": "MMC-91544"},
             "qualifications": [_qual("MBBS", "BJ Medical College", 2009),
                                _qual("MD (Pulmonary Medicine)", "VP Chest Institute", 2014)],
             "sub_specialties": ["Asthma & COPD", "Sleep medicine"], "experience_years": 12,
             "consultation_fee_inr": 750,
             "bio": "Chest physician managing asthma, COPD and sleep-disordered breathing."},
            "doctor"),
        "doctor10@cadence.dev": doc(
            "DOC-010", "Neurology", ["en", "hi", "kn"], realistic_phone("staff-doc10"),
            date(2018, 10, 22),
            {"registration": {"council": "Karnataka Medical Council", "number": "KMC-77309"},
             "qualifications": [_qual("MBBS", "Bangalore Medical College", 2008),
                                _qual("DM (Neurology)", "NIMHANS", 2015)],
             "sub_specialties": ["Headache medicine", "Epilepsy"], "experience_years": 11,
             "consultation_fee_inr": 1000,
             "bio": "Neurologist for migraine, epilepsy and neuropathy follow-up."}, "doctor"),
    }
