"""
Fully synthetic Patient/Member 360 data generator.

No real or de-identified PHI. Every value is randomly generated from fictional
name pools and statistical distributions. Safe to commit and safe to demo.

Outputs (./data):
  structured/  patients.csv members.csv encounters.csv claims.csv
               diagnoses.csv medications.csv labs.csv ed_visits.csv
  docs/        discharge summaries, prior-auth policies, drug safety labels,
               payer regulatory bulletins, quality measure specs
"""
import csv, json, os, random, uuid
from datetime import date, timedelta

random.seed(20260911)
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
S = os.path.join(ROOT, "structured"); D = os.path.join(ROOT, "docs")
os.makedirs(S, exist_ok=True); os.makedirs(D, exist_ok=True)
# start from a clean corpus: encounter IDs are regenerated on every run
for _d in (S, D):
    for _f in os.listdir(_d):
        os.remove(os.path.join(_d, _f))

FIRST = ["Aarav","Nadia","Ellis","Ravi","Imani","Soren","Lucia","Devin","Priya","Owen",
         "Maren","Kofi","Ines","Tomas","Yara","Niall","Zoya","Elias","Farah","Quinn"]
LAST  = ["Alvarez","Okafor","Lindqvist","Nambiar","Carvalho","Bright","Halloran","Mensah",
         "Vartanian","Dorsey","Kaminski","Ibarra","Rossetti","Farley","Nazari","Whitlock"]
CITY  = [("Fairview","OH"),("Cedar Falls","IA"),("Northgate","WA"),("Rio Vista","CA"),
         ("Millbrook","NY"),("Ashford","TX"),("Glenmoor","GA"),("Kestrel","CO")]
PLANS = [("HMO-BRONZE","Aegis Health Plan"),("PPO-SILVER","Aegis Health Plan"),
         ("HMO-GOLD","Northwind Mutual"),("MA-PPO","Northwind Mutual"),("MEDICAID-MCO","StateCare MCO")]

# (icd10, label, charlson_weight, hcc_flag)
COND = [
 ("I50.9","Congestive heart failure, unspecified",2,1),
 ("E11.22","Type 2 diabetes mellitus with diabetic chronic kidney disease",2,1),
 ("E11.9","Type 2 diabetes mellitus without complications",1,1),
 ("J44.1","COPD with acute exacerbation",2,1),
 ("N18.4","Chronic kidney disease, stage 4",2,1),
 ("I21.4","Non-ST elevation myocardial infarction",1,1),
 ("I63.9","Cerebral infarction, unspecified",1,1),
 ("F32.1","Major depressive disorder, single episode, moderate",0,0),
 ("I10","Essential hypertension",0,0),
 ("Z79.4","Long term use of insulin",0,0),
 ("C34.90","Malignant neoplasm of unspecified part of lung",2,1),
 ("K70.30","Alcoholic cirrhosis of liver without ascites",2,1),
]
MEDS = [
 ("RX-1001","Metformin HCl 1000 mg","biguanide"),
 ("RX-1002","Empagliflozin 10 mg","SGLT2 inhibitor"),
 ("RX-1003","Sacubitril/Valsartan 49-51 mg","ARNI"),
 ("RX-1004","Furosemide 40 mg","loop diuretic"),
 ("RX-1005","Apixaban 5 mg","DOAC"),
 ("RX-1006","Atorvastatin 40 mg","statin"),
 ("RX-1007","Tiotropium 18 mcg inhaler","LAMA"),
 ("RX-1008","Spironolactone 25 mg","MRA"),
 ("RX-1009","Sertraline 50 mg","SSRI"),
 ("RX-1010","Insulin glargine 100 U/mL","basal insulin"),
]
LABS = [
 ("2160-0","Creatinine, serum","mg/dL",0.6,1.3),
 ("4548-4","Hemoglobin A1c","%",4.8,6.4),
 ("33762-6","NT-proBNP","pg/mL",10,125),
 ("2823-3","Potassium, serum","mmol/L",3.5,5.1),
 ("718-7","Hemoglobin","g/dL",12.0,16.0),
 ("2085-9","HDL cholesterol","mg/dL",40,80),
]
ENC_TYPE = ["INPATIENT","OUTPATIENT","EMERGENCY","TELEHEALTH"]
N_PATIENTS = 220
today = date(2026, 9, 1)

def rdate(start_days, end_days):
    return today - timedelta(days=random.randint(end_days, start_days))

patients, members, encounters, claims, diagnoses, medications, labs, edv = [],[],[],[],[],[],[],[]

for i in range(N_PATIENTS):
    pid = f"SYN-P{i+1:05d}"
    mid = f"SYN-M{i+1:05d}"
    city, st = random.choice(CITY)
    age = random.choices([random.randint(19,44), random.randint(45,64), random.randint(65,89)],
                         weights=[0.25,0.35,0.40])[0]
    dob = date(today.year - age, random.randint(1,12), random.randint(1,28))
    sex = random.choice(["F","M"])
    plan, payer = random.choice(PLANS)
    patients.append(dict(
        patient_id=pid, member_id=mid,
        first_name=random.choice(FIRST), last_name=random.choice(LAST),
        birth_date=dob.isoformat(), sex=sex,
        city=city, state=st, postal_code=f"{random.randint(10000,99999)}",
        primary_language=random.choice(["EN","EN","EN","ES","HI"]),
        pcp_npi=f"NPI{random.randint(1000000000,1999999999)}",
        deceased_flag=0, data_source="SYNTHETIC_GENERATOR_V1"
    ))
    members.append(dict(
        member_id=mid, patient_id=pid, payer_name=payer, plan_id=plan,
        line_of_business=("MEDICARE" if plan=="MA-PPO" else "MEDICAID" if plan=="MEDICAID-MCO" else "COMMERCIAL"),
        enroll_start=(today - timedelta(days=random.randint(400,1400))).isoformat(),
        enroll_end="", risk_program=random.choice(["NONE","CARE_MGMT","CHF_PROGRAM","DIABETES_PROGRAM"]),
        attributed_clinic=random.choice(["FVMG-NORTH","FVMG-SOUTH","PRIME-PRIMARY","RIVERBEND"])
    ))

    n_cond = random.choices([0,1,2,3,4,5], weights=[.08,.20,.24,.22,.16,.10])[0]
    my_cond = random.sample(COND, n_cond)
    for c in my_cond:
        diagnoses.append(dict(patient_id=pid, icd10_code=c[0], description=c[1],
                              onset_date=rdate(1500, 60).isoformat(),
                              charlson_weight=c[2], hcc_flag=c[3],
                              clinical_status=random.choice(["active","active","resolved"])))

    n_enc = random.randint(1, 9)
    for _ in range(n_enc):
        eid = f"SYN-E{uuid.uuid4().hex[:10].upper()}"
        etype = random.choices(ENC_TYPE, weights=[.18,.46,.22,.14])[0]
        start = rdate(540, 5)
        los = random.choices([1,2,3,4,5,8,15], weights=[.3,.2,.15,.12,.1,.08,.05])[0] if etype=="INPATIENT" else 0
        admit_src = random.choices(["EMERGENCY","ELECTIVE"], weights=[.65,.35])[0] if etype=="INPATIENT" else "N/A"
        encounters.append(dict(encounter_id=eid, patient_id=pid, encounter_type=etype,
            start_date=start.isoformat(), end_date=(start+timedelta(days=los)).isoformat(),
            length_of_stay_days=los, admission_source=admit_src,
            discharge_disposition=(random.choice(["HOME","HOME_HEALTH","SNF"]) if etype=="INPATIENT" else "N/A"),
            facility=random.choice(["Fairview Regional","Cedar Falls Medical","Northgate General"]),
            readmit_30d=0))
        allowed = round(random.uniform(120, 900) if etype!="INPATIENT" else random.uniform(4800, 42000), 2)
        claims.append(dict(claim_id=f"SYN-C{uuid.uuid4().hex[:10].upper()}", encounter_id=eid,
            member_id=mid, patient_id=pid, claim_type=("FACILITY" if etype=="INPATIENT" else "PROFESSIONAL"),
            service_date=start.isoformat(), billed_amount=round(allowed*random.uniform(1.4,2.6),2),
            allowed_amount=allowed, paid_amount=round(allowed*random.uniform(0.6,0.95),2),
            member_liability=round(allowed*random.uniform(0.02,0.25),2),
            claim_status=random.choices(["PAID","DENIED","PENDING"],weights=[.82,.12,.06])[0],
            denial_reason=random.choice(["","PRIOR_AUTH_MISSING","NOT_MEDICALLY_NECESSARY","OUT_OF_NETWORK"]),
            drg_code=(f"DRG{random.randint(190,300)}" if etype=="INPATIENT" else "")))
        if etype=="EMERGENCY":
            edv.append(dict(patient_id=pid, ed_visit_date=start.isoformat(),
                            chief_complaint=random.choice(["dyspnea","chest pain","hyperglycemia","fall","cough"]),
                            admitted_flag=random.choice([0,0,1])))

    for m in random.sample(MEDS, random.randint(0,5)):
        medications.append(dict(patient_id=pid, rx_id=m[0], medication_name=m[1], drug_class=m[2],
            start_date=rdate(900,30).isoformat(), days_supply=random.choice([30,60,90]),
            refills=random.randint(0,5),
            adherence_pdc=round(random.uniform(0.35,1.0),2), active_flag=random.choice([1,1,0])))

    for l in random.sample(LABS, random.randint(2,6)):
        for _ in range(random.randint(1,3)):
            abnormal = random.random() < 0.35
            lo, hi = l[3], l[4]
            val = round(random.uniform(hi*1.05, hi*2.4) if abnormal else random.uniform(lo, hi), 2)
            labs.append(dict(patient_id=pid, loinc_code=l[0], test_name=l[1], unit=l[2],
                result_value=val, ref_low=lo, ref_high=hi,
                abnormal_flag=(1 if val>hi or val<lo else 0),
                collected_date=rdate(700,3).isoformat()))

# ---- make the synthetic outcome coherent with the synthetic risk factors ----
# First pass generated readmit_30d as a coin flip and the risk bands came out
# backwards: LOW showed a HIGHER observed readmission rate than HIGH. Any judge
# would spot that in thirty seconds.
#
# Two things were wrong. The outcome was independent of the factors, and it was
# assigned per encounter while the risk table scores the LAST inpatient stay.
# A patient with six short admissions accumulated six coin flips and looked
# high-risk in the outcome while scoring LOW on the index.
#
# Fix: compute LACE the same way sql/03 does — patient level, off the index
# (most recent) inpatient stay — and attach the outcome to that stay only.
_ch = {}
for d in diagnoses:
    if d["clinical_status"] == "active":
        _ch[d["patient_id"]] = _ch.get(d["patient_id"], 0) + d["charlson_weight"]
_ed6 = {}
_cut6 = (today - timedelta(days=182)).isoformat()
for e in encounters:
    if e["encounter_type"] == "EMERGENCY" and e["start_date"] >= _cut6:
        _ed6[e["patient_id"]] = _ed6.get(e["patient_id"], 0) + 1
_pdc = {}
for m in medications:
    if m["active_flag"] == 1:
        _pdc[m["patient_id"]] = min(_pdc.get(m["patient_id"], 1.0), m["adherence_pdc"])

def _los_points(los):
    los = int(los or 0)
    return 7 if los >= 14 else 5 if los >= 7 else 4 if los >= 4 else los

# index stay = most recent inpatient encounter, matching V_PATIENT_LAST_ADMISSION
_index_stay = {}
for e in encounters:
    e["readmit_30d"] = 0
    if e["encounter_type"] != "INPATIENT":
        continue
    prev = _index_stay.get(e["patient_id"])
    if prev is None or e["end_date"] > prev["end_date"]:
        _index_stay[e["patient_id"]] = e

for pid, e in _index_stay.items():
    lace = (_los_points(e["length_of_stay_days"])
            + (3 if e["admission_source"] == "EMERGENCY" else 0)
            + min(_ch.get(pid, 0), 5)
            + min(_ed6.get(pid, 0), 4))
    prob = 0.06 + 0.030 * lace            # ~6% at LACE 0, ~62% at LACE 19
    if _pdc.get(pid, 1.0) < 0.80:
        prob += 0.06
    e["readmit_30d"] = 1 if random.random() < min(prob, 0.85) else 0

def dump(name, rows):
    with open(os.path.join(S, name), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    return f"{name}: {len(rows)} rows"

report = [dump("patients.csv",patients), dump("members.csv",members),
          dump("encounters.csv",encounters), dump("claims.csv",claims),
          dump("diagnoses.csv",diagnoses), dump("medications.csv",medications),
          dump("labs.csv",labs), dump("ed_visits.csv",edv)]

# ---------------- unstructured documents ----------------
ip = [e for e in encounters if e["encounter_type"]=="INPATIENT"]
random.shuffle(ip)
pmap = {p["patient_id"]: p for p in patients}

for e in ip[:70]:
    p = pmap[e["patient_id"]]
    dxs = [d for d in diagnoses if d["patient_id"]==p["patient_id"]] or [{"description":"Essential hypertension","icd10_code":"I10"}]
    mds = [m for m in medications if m["patient_id"]==p["patient_id"]][:4]
    txt = f"""# Discharge Summary (SYNTHETIC)

**Document ID:** DS-{e['encounter_id']}
**Patient ID:** {p['patient_id']}   **Encounter ID:** {e['encounter_id']}
**Facility:** {e['facility']}   **Admit:** {e['start_date']}   **Discharge:** {e['end_date']}
**Length of stay:** {e['length_of_stay_days']} days   **Admission source:** {e['admission_source']}
**Disposition:** {e['discharge_disposition']}

## Hospital Course
Patient presented with {random.choice(['progressive dyspnea and lower-extremity edema','substernal chest pressure','productive cough and wheeze','polyuria and fatigue'])}.
Initial assessment was consistent with {dxs[0]['description']} ({dxs[0]['icd10_code']}). Management included
{random.choice(['IV diuresis with transition to oral therapy','guideline-directed medical therapy titration','bronchodilator and systemic corticosteroid course','basal-bolus insulin adjustment'])}.
Symptoms improved by hospital day {max(1,e['length_of_stay_days']-1)} and the patient was deemed stable for discharge.

## Problem List at Discharge
""" + "\n".join(f"- {d['description']} ({d['icd10_code']}) - {d.get('clinical_status','active')}" for d in dxs) + f"""

## Discharge Medications
""" + ("\n".join(f"- {m['medication_name']} ({m['drug_class']}), {m['days_supply']}-day supply" for m in mds) or "- None") + f"""

## Care Gaps and Follow-up Plan
- Follow-up with {random.choice(['cardiology','primary care','nephrology','pulmonology'])} within {random.choice([3,7,14])} days.
- Repeat {random.choice(['basic metabolic panel','NT-proBNP','HbA1c'])} at follow-up visit.
- {random.choice(['Daily weight log and 2 g sodium restriction reviewed with patient.','Inhaler technique demonstrated; teach-back completed.','Home glucose monitoring four times daily until next visit.'])}
- Barriers documented: {random.choice(['transportation','no barriers identified','medication cost concerns','lives alone, limited caregiver support'])}.

## Safety Notes
{random.choice(['No adverse drug events during admission.','Mild hypotension after ARNI up-titration; dose reduced and tolerated.','Transient hyperkalemia 5.4 mmol/L after MRA initiation; resolved with dietary counseling.','Reported dizziness after diuretic dose increase; orthostatics negative at discharge.'])}

_All content in this document is synthetic and generated for demonstration. It does not describe a real person._
"""
    with open(os.path.join(D, f"discharge_{e['encounter_id']}.md"), "w") as f: f.write(txt)

policies = [
 ("PA-CARD-014","Prior Authorization Policy: Sacubitril/Valsartan (ARNI)","UTILIZATION_POLICY","Aegis Health Plan","2026-01-01",
  """## Coverage Criteria
ARNI therapy is covered when ALL of the following are documented:
1. Diagnosis of chronic heart failure with reduced ejection fraction (LVEF <= 40%).
2. NYHA class II-IV symptoms documented within the previous 90 days.
3. Current or prior trial of an ACE inhibitor or ARB, unless contraindicated.
4. Systolic blood pressure >= 100 mmHg at the most recent visit.
5. eGFR >= 30 mL/min/1.73 m2 and serum potassium <= 5.4 mmol/L.

## Exclusions
- Concurrent ACE inhibitor use (36-hour washout required).
- History of angioedema related to prior ACE inhibitor or ARB therapy.
- Pregnancy.

## Authorization Duration
Initial approval 12 months. Renewal requires documented functional improvement or stability.

## Appeals
A denial may be appealed within 60 calendar days. Peer-to-peer review is available within 5 business days of request."""),
 ("PA-ENDO-022","Prior Authorization Policy: SGLT2 Inhibitors","UTILIZATION_POLICY","Northwind Mutual","2026-03-15",
  """## Coverage Criteria
Covered for members with type 2 diabetes mellitus and ANY of:
1. HbA1c >= 7.0% despite >= 90 days of metformin at maximally tolerated dose, OR
2. Established atherosclerotic cardiovascular disease, OR
3. Chronic kidney disease with eGFR 25-90 mL/min/1.73 m2, OR
4. Heart failure of any ejection fraction.

## Step Therapy
Metformin is required first-line unless contraindicated (eGFR < 30, intolerance documented in the chart).

## Monitoring Requirements
Renal function at baseline and annually. Counsel on euglycemic ketoacidosis and genital mycotic infection risk.

## Authorization Duration
12 months, renewable with documented adherence (PDC >= 0.80)."""),
 ("REG-CMS-2026-07","Regulatory Bulletin: Hospital Readmissions Reduction Reporting","REGULATORY_BULLETIN","StateCare MCO","2026-07-01",
  """## Scope
Applies to all contracted acute care facilities reporting 30-day all-cause readmission measures.

## Reporting Requirements
1. Submit index admission and readmission pairs quarterly, within 45 days of quarter close.
2. Risk-adjust for age, sex, and comorbidity burden using the documented comorbidity index.
3. Exclude planned readmissions per the published planned-readmission algorithm.
4. Retain source documentation for 7 years and make it auditable on request.

## Data Quality Controls
Records with missing discharge disposition or missing admission source are rejected. Facilities must
resubmit corrected records within 15 business days.

## Member Notification
Members identified as high readmission risk must be offered a transitional care management contact
within 2 business days of discharge."""),
 ("SAFETY-ARNI-01","Drug Safety Label Summary: Sacubitril/Valsartan","DRUG_SAFETY_LABEL","Fictional Pharma Labs","2026-02-10",
  """## Boxed Warning
Fetal toxicity. Discontinue as soon as pregnancy is detected.

## Contraindications
- Concomitant use with an ACE inhibitor; allow a 36-hour washout.
- History of angioedema with prior ACE inhibitor or ARB therapy.
- Concomitant aliskiren in patients with diabetes.

## Warnings and Precautions
Hypotension, hyperkalemia, renal impairment, and angioedema. Monitor serum potassium and creatinine
within 1-2 weeks of initiation or dose change.

## Common Adverse Reactions
Hypotension, hyperkalemia, cough, dizziness, renal failure.

## Notes
This label text is fictional and written for demonstration purposes only."""),
 ("SAFETY-SGLT2-01","Drug Safety Label Summary: SGLT2 Inhibitor Class","DRUG_SAFETY_LABEL","Fictional Pharma Labs","2026-04-22",
  """## Warnings and Precautions
- Ketoacidosis may occur with normal or only mildly elevated blood glucose. Hold therapy 3 days before
  scheduled surgery.
- Volume depletion and symptomatic hypotension, particularly with loop diuretics or in patients over 65.
- Urosepsis and pyelonephritis; evaluate urinary symptoms promptly.
- Necrotizing fasciitis of the perineum has been reported rarely.

## Drug Interactions
Increased risk of volume depletion when combined with loop diuretics. Insulin or sulfonylurea dose
reduction may be required to limit hypoglycemia.

## Monitoring
Renal function before initiation and periodically thereafter.

## Notes
Fictional label summary for demonstration."""),
 ("QM-HEDIS-LIKE-03","Quality Measure Specification: Post-Discharge Follow-up","QUALITY_MEASURE","Aegis Health Plan","2026-05-05",
  """## Measure Intent
Percentage of inpatient discharges with an ambulatory follow-up visit within 14 days.

## Numerator
Any outpatient, telehealth, or home visit with a qualifying clinician within 14 days of discharge date.

## Denominator
All acute inpatient discharges for members continuously enrolled 30 days post discharge.

## Exclusions
Discharges to hospice, deaths during the measurement window, and planned readmissions.

## Stratification
Report by line of business and by attributed clinic. Minimum denominator of 30 for public reporting."""),
]
for doc_id, title, dtype, owner, eff, body in policies:
    with open(os.path.join(D, f"{doc_id}.md"), "w") as f:
        f.write(f"""# {title}

**Document ID:** {doc_id}
**Document Type:** {dtype}
**Owner:** {owner}
**Effective Date:** {eff}
**Status:** ACTIVE (SYNTHETIC DEMO CONTENT)

{body}
""")

with open(os.path.join(ROOT, "MANIFEST.json"), "w") as f:
    json.dump({"generator":"gen_synthetic.py","seed":20260911,"phi":"none-fully-synthetic",
               "structured_files":report,
               "doc_count":len(os.listdir(D))}, f, indent=2)
print("\n".join(report)); print("docs:", len(os.listdir(D)))
