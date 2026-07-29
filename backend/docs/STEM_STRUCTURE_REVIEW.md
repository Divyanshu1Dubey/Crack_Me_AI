# Stem-structure fix — verification report

Verification-only probe. **No database writes performed.**

## Bucket counts

| Bucket | Count |
|---|---|
| `auto_rewrite` | 51 |
| `manual_review` | 32 |
| `accepted_a` | 0 |
| `already_structured` | 1054 |
| `skip_low_confidence` | 24 |
| `option_list` | 1 |
| `paragraph_broken` | 157 |
| `ocr_ambiguity` | 7 |
| `no_pattern` | 1165 |
| `empty` | 0 |

**Total candidates scanned**: 2491
**Auto-rewrite (≥0.98)**: 51
**Manual review (0.80–0.97)**: 32
**Shape-A accepted**: 0

## AUTO-REWRITE (≥0.98)

### 1. Question id=5824

- **Subject**: Community Medicine
- **Topic**: Vaccine Preventable Diseases
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are correct in respect of Diphtheria?
The incubation period is 14 to 28 days
Diphtheria antitoxin is used in treatment of cases
It is one of the diseases protected from, by the Pentavalent vaccine given in National Program
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following are correct in respect of Diphtheria?

1. The incubation period is 14 to 28 days.
2. Diphtheria antitoxin is used in treatment of cases.
3. It is one of the diseases protected from, by the Pentavalent vaccine given in National Program.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5824 (before)

+++ q5824 (after)

@@ -1,5 +1,6 @@

 Which of the following are correct in respect of Diphtheria?

-The incubation period is 14 to 28 days

-Diphtheria antitoxin is used in treatment of cases

-It is one of the diseases protected from, by the Pentavalent vaccine given in National Program

+

+1. The incubation period is 14 to 28 days.

+2. Diphtheria antitoxin is used in treatment of cases.

+3. It is one of the diseases protected from, by the Pentavalent vaccine given in National Program.

 Select the correct answer using the code given below.
```

### 2. Question id=5819

- **Subject**: Community Medicine
- **Topic**: Viral Exanthematous Diseases
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are true about measles?
It is highly infectious in the phase following the appearance of rash
Infection usually confers lifelong immunity
It has a low secondary attack rate
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following are true about measles?

1. It is highly infectious in the phase following the appearance of rash.
2. Infection usually confers lifelong immunity.
3. It has a low secondary attack rate.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5819 (before)

+++ q5819 (after)

@@ -1,5 +1,6 @@

 Which of the following are true about measles?

-It is highly infectious in the phase following the appearance of rash

-Infection usually confers lifelong immunity

-It has a low secondary attack rate

+

+1. It is highly infectious in the phase following the appearance of rash.

+2. Infection usually confers lifelong immunity.

+3. It has a low secondary attack rate.

 Select the correct answer using the code given below.
```

### 3. Question id=5847

- **Subject**: Community Medicine
- **Topic**: Global Health Initiatives and Vaccine Alliances
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following agencies are playing a key role in running of the "COVAX" initiative against COVID-19?
GAVI, the Vaccine Alliance
World Health Organisation (WHO)
Ford Foundation
Coalition for Epidemic Preparedness Innovations (CEPI)
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following agencies are playing a key role in running of the "COVAX" initiative against COVID-19?

1. GAVI, the Vaccine Alliance.
2. World Health Organisation (WHO).
3. Ford Foundation.
4. Coalition for Epidemic Preparedness Innovations (CEPI).
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5847 (before)

+++ q5847 (after)

@@ -1,6 +1,7 @@

 Which of the following agencies are playing a key role in running of the "COVAX" initiative against COVID-19?

-GAVI, the Vaccine Alliance

-World Health Organisation (WHO)

-Ford Foundation

-Coalition for Epidemic Preparedness Innovations (CEPI)

+

+1. GAVI, the Vaccine Alliance.

+2. World Health Organisation (WHO).

+3. Ford Foundation.

+4. Coalition for Epidemic Preparedness Innovations (CEPI).

 Select the correct answer using the code given below.
```

### 4. Question id=5695

- **Subject**: General Medicine
- **Topic**: Genetic Predisposition to Cancer
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following conditions are parts of inherited cancer syndrome?
Retinoblastoma
Li-Fraumeni syndrome
Xeroderma pigmentosum
Peutz-Jeghers syndrome
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following conditions are parts of inherited cancer syndrome?

1. Retinoblastoma.
2. Li-Fraumeni syndrome.
3. Xeroderma pigmentosum.
4. Peutz-Jeghers syndrome.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5695 (before)

+++ q5695 (after)

@@ -1,6 +1,7 @@

 Which of the following conditions are parts of inherited cancer syndrome?

-Retinoblastoma

-Li-Fraumeni syndrome

-Xeroderma pigmentosum

-Peutz-Jeghers syndrome

+

+1. Retinoblastoma.

+2. Li-Fraumeni syndrome.

+3. Xeroderma pigmentosum.

+4. Peutz-Jeghers syndrome.

 Select the correct answer using the code given below.
```

### 5. Question id=5659

- **Subject**: General Medicine
- **Topic**: Hemolytic Anemia
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following investigations indicate active hemolysis?
Increased reticulocyte count
Increased conjugated bilirubin
Increased urinary urobilinogen
Decreased haptoglobin
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following investigations indicate active hemolysis?

1. Increased reticulocyte count.
2. Increased conjugated bilirubin.
3. Increased urinary urobilinogen.
4. Decreased haptoglobin.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5659 (before)

+++ q5659 (after)

@@ -1,6 +1,7 @@

 Which of the following investigations indicate active hemolysis?

-Increased reticulocyte count

-Increased conjugated bilirubin

-Increased urinary urobilinogen

-Decreased haptoglobin

+

+1. Increased reticulocyte count.

+2. Increased conjugated bilirubin.

+3. Increased urinary urobilinogen.

+4. Decreased haptoglobin.

 Select the correct answer using the code given below.
```

### 6. Question id=5624

- **Subject**: General Medicine
- **Topic**: Paraneoplastic Syndromes and Extra-Pulmonary Manifestations of Lung Cancer
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are the non-metastatic extra-pulmonary manifestations of lung cancer?
Carcinoid syndrome
Nephrotic syndrome
Horner's syndrome
Lambert-Eaton syndrome
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following are the non-metastatic extra-pulmonary manifestations of lung cancer?

1. Carcinoid syndrome.
2. Nephrotic syndrome.
3. Horner's syndrome.
4. Lambert-Eaton syndrome.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5624 (before)

+++ q5624 (after)

@@ -1,6 +1,7 @@

 Which of the following are the non-metastatic extra-pulmonary manifestations of lung cancer?

-Carcinoid syndrome

-Nephrotic syndrome

-Horner's syndrome

-Lambert-Eaton syndrome

+

+1. Carcinoid syndrome.

+2. Nephrotic syndrome.

+3. Horner's syndrome.

+4. Lambert-Eaton syndrome.

 Select the correct answer using the code given below.
```

### 7. Question id=5696

- **Subject**: General Medicine
- **Topic**: Genetic Disorders and DNA Repeat Sequences
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are the diseases associated with DNA repeat sequences?
Huntington's disease
Myotonic dystrophy
Friedreich's ataxia
Klinefelter syndrome
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following are the diseases associated with DNA repeat sequences?

1. Huntington's disease.
2. Myotonic dystrophy.
3. Friedreich's ataxia.
4. Klinefelter syndrome.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5696 (before)

+++ q5696 (after)

@@ -1,6 +1,7 @@

 Which of the following are the diseases associated with DNA repeat sequences?

-Huntington's disease

-Myotonic dystrophy

-Friedreich's ataxia

-Klinefelter syndrome

+

+1. Huntington's disease.

+2. Myotonic dystrophy.

+3. Friedreich's ataxia.

+4. Klinefelter syndrome.

 Select the correct answer using the code given below.
```

### 8. Question id=5641

- **Subject**: General Medicine
- **Topic**: Chronic Kidney Disease and Anemia
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are the mechanisms for anemia in Chronic Kidney Disease?
Deficiency of erythropoietin
Folate and Vitamin B12 deficiency
Toxic effects of uraemia on bone marrow
Reduced utilization of dietary iron
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following are the mechanisms for anemia in Chronic Kidney Disease?

1. Deficiency of erythropoietin.
2. Folate and Vitamin B12 deficiency.
3. Toxic effects of uraemia on bone marrow.
4. Reduced utilization of dietary iron.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5641 (before)

+++ q5641 (after)

@@ -1,6 +1,7 @@

 Which of the following are the mechanisms for anemia in Chronic Kidney Disease?

-Deficiency of erythropoietin

-Folate and Vitamin B12 deficiency

-Toxic effects of uraemia on bone marrow

-Reduced utilization of dietary iron

+

+1. Deficiency of erythropoietin.

+2. Folate and Vitamin B12 deficiency.

+3. Toxic effects of uraemia on bone marrow.

+4. Reduced utilization of dietary iron.

 Select the correct answer using the code given below.
```

### 9. Question id=5613

- **Subject**: General Medicine
- **Topic**: Cardiac Glycosides and Digitalis Toxicity
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following electro-cardio-graphic findings are manifestations of digitalis intoxication?
Ventricular bigeminy
Ventricular tachycardia
Atrial flutter
Atrial tachycardia with variable block
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following electro-cardio-graphic findings are manifestations of digitalis intoxication?

1. Ventricular bigeminy.
2. Ventricular tachycardia.
3. Atrial flutter.
4. Atrial tachycardia with variable block.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5613 (before)

+++ q5613 (after)

@@ -1,6 +1,7 @@

 Which of the following electro-cardio-graphic findings are manifestations of digitalis intoxication?

-Ventricular bigeminy

-Ventricular tachycardia

-Atrial flutter

-Atrial tachycardia with variable block

+

+1. Ventricular bigeminy.

+2. Ventricular tachycardia.

+3. Atrial flutter.

+4. Atrial tachycardia with variable block.

 Select the correct answer using the code given below.
```

### 10. Question id=5753

- **Subject**: General Surgery
- **Topic**: Splenic Disorders and Splenectomy Indications
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are indications of splenectomy?
Pseudomyxoma peritonei
Trauma
Idiopathic thrombocytopenic purpura (ITP)
Hypersplenism
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following are indications of splenectomy?

1. Pseudomyxoma peritonei.
2. Trauma.
3. Idiopathic thrombocytopenic purpura (ITP).
4. Hypersplenism.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5753 (before)

+++ q5753 (after)

@@ -1,6 +1,7 @@

 Which of the following are indications of splenectomy?

-Pseudomyxoma peritonei

-Trauma

-Idiopathic thrombocytopenic purpura (ITP)

-Hypersplenism

+

+1. Pseudomyxoma peritonei.

+2. Trauma.

+3. Idiopathic thrombocytopenic purpura (ITP).

+4. Hypersplenism.

 Select the correct answer using the code given below.
```

### 11. Question id=5740

- **Subject**: General Surgery
- **Topic**: Acute Colonic Pseudo-Obstruction (Ogilvie's Syndrome)
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following statements regarding Ogilvie's syndrome are correct?
It presents as acute large bowel mechanical obstruction
Marked caecal dilatation is a common feature on X-ray abdomen
Caecal perforation is a well recognized complication of this condition
Intravenous Neostigmine is used for the treatment of this condition
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following statements regarding Ogilvie's syndrome are correct?

1. It presents as acute large bowel mechanical obstruction.
2. Marked caecal dilatation is a common feature on X-ray abdomen.
3. Caecal perforation is a well recognized complication of this condition.
4. Intravenous Neostigmine is used for the treatment of this condition.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5740 (before)

+++ q5740 (after)

@@ -1,6 +1,7 @@

 Which of the following statements regarding Ogilvie's syndrome are correct?

-It presents as acute large bowel mechanical obstruction

-Marked caecal dilatation is a common feature on X-ray abdomen

-Caecal perforation is a well recognized complication of this condition

-Intravenous Neostigmine is used for the treatment of this condition

+

+1. It presents as acute large bowel mechanical obstruction.

+2. Marked caecal dilatation is a common feature on X-ray abdomen.

+3. Caecal perforation is a well recognized complication of this condition.

+4. Intravenous Neostigmine is used for the treatment of this condition.

 Select the correct answer using the code given below.
```

### 12. Question id=5741

- **Subject**: General Surgery
- **Topic**: Gastrointestinal Neuroendocrine Tumors
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following statements regarding Carcinoid tumour are correct?
Terminal ileum is the most common site for these tumours in the gastrointestinal tract
These tumors arise from Kulchitsky cells situated at the base of intestinal crypts
5-Hydroxytryptamine is the most common vasoactive peptide produced by these tumors
Serum chromogranin A is a useful marker for disease recurrence
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following statements regarding Carcinoid tumour are correct?

1. Terminal ileum is the most common site for these tumours in the gastrointestinal tract.
2. These tumors arise from Kulchitsky cells situated at the base of intestinal crypts.
3. 5-Hydroxytryptamine is the most common vasoactive peptide produced by these tumors.
4. Serum chromogranin A is a useful marker for disease recurrence.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5741 (before)

+++ q5741 (after)

@@ -1,6 +1,7 @@

 Which of the following statements regarding Carcinoid tumour are correct?

-Terminal ileum is the most common site for these tumours in the gastrointestinal tract

-These tumors arise from Kulchitsky cells situated at the base of intestinal crypts

-5-Hydroxytryptamine is the most common vasoactive peptide produced by these tumors

-Serum chromogranin A is a useful marker for disease recurrence

+

+1. Terminal ileum is the most common site for these tumours in the gastrointestinal tract.

+2. These tumors arise from Kulchitsky cells situated at the base of intestinal crypts.

+3. 5-Hydroxytryptamine is the most common vasoactive peptide produced by these tumors.

+4. Serum chromogranin A is a useful marker for disease recurrence.

 Select the correct answer using the code given below.
```

### 13. Question id=5728

- **Subject**: General Surgery
- **Topic**: Wound Healing
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are types of wound healing?
Primary Intention
Secondary Intention
Tertiary Intention
Quaternary Intention
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following are types of wound healing?

1. Primary Intention.
2. Secondary Intention.
3. Tertiary Intention.
4. Quaternary Intention.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5728 (before)

+++ q5728 (after)

@@ -1,6 +1,7 @@

 Which of the following are types of wound healing?

-Primary Intention

-Secondary Intention

-Tertiary Intention

-Quaternary Intention

+

+1. Primary Intention.

+2. Secondary Intention.

+3. Tertiary Intention.

+4. Quaternary Intention.

 Select the correct answer using the code given below.
```

### 14. Question id=5747

- **Subject**: General Surgery
- **Topic**: Gastrointestinal Surgery - Enteric Fever Complications
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following statements with regard to Enteric perforation are correct?
Salmonella typhi is the causative organism for Enteric fever
Enteric perforation characteristically occurs during third week of illness
Typhoid ulcers are placed transversely to the long axis of the gut
Terminal ileum is the most common site for enteric perforation
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following statements with regard to Enteric perforation are correct?

1. Salmonella typhi is the causative organism for Enteric fever.
2. Enteric perforation characteristically occurs during third week of illness.
3. Typhoid ulcers are placed transversely to the long axis of the gut.
4. Terminal ileum is the most common site for enteric perforation.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5747 (before)

+++ q5747 (after)

@@ -1,6 +1,7 @@

 Which of the following statements with regard to Enteric perforation are correct?

-Salmonella typhi is the causative organism for Enteric fever

-Enteric perforation characteristically occurs during third week of illness

-Typhoid ulcers are placed transversely to the long axis of the gut

-Terminal ileum is the most common site for enteric perforation

+

+1. Salmonella typhi is the causative organism for Enteric fever.

+2. Enteric perforation characteristically occurs during third week of illness.

+3. Typhoid ulcers are placed transversely to the long axis of the gut.

+4. Terminal ileum is the most common site for enteric perforation.

 Select the correct answer using the code given below.
```

### 15. Question id=5789

- **Subject**: Obstetrics & Gynaecology
- **Topic**: Precocious Puberty
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are causes of GnRH dependent precocious puberty?
Constitutional
Tubercular Encephalitis
McCune-Albright syndrome
Primary hypothyroidism
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following are causes of GnRH dependent precocious puberty?

1. Constitutional.
2. Tubercular Encephalitis.
3. McCune-Albright syndrome.
4. Primary hypothyroidism.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5789 (before)

+++ q5789 (after)

@@ -1,6 +1,7 @@

 Which of the following are causes of GnRH dependent precocious puberty?

-Constitutional

-Tubercular Encephalitis

-McCune-Albright syndrome

-Primary hypothyroidism

+

+1. Constitutional.

+2. Tubercular Encephalitis.

+3. McCune-Albright syndrome.

+4. Primary hypothyroidism.

 Select the correct answer using the code given below.
```

### 16. Question id=5792

- **Subject**: Obstetrics & Gynaecology
- **Topic**: Pelvic Inflammatory Disease (PID)
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are risk factors for developing pelvic inflammatory disease in females?
Use of oral contraception pills
Multiple sexual partners
Lower socioeconomic status
Genetic predisposition
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following are risk factors for developing pelvic inflammatory disease in females?

1. Use of oral contraception pills.
2. Multiple sexual partners.
3. Lower socioeconomic status.
4. Genetic predisposition.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5792 (before)

+++ q5792 (after)

@@ -1,6 +1,7 @@

 Which of the following are risk factors for developing pelvic inflammatory disease in females?

-Use of oral contraception pills

-Multiple sexual partners

-Lower socioeconomic status

-Genetic predisposition

+

+1. Use of oral contraception pills.

+2. Multiple sexual partners.

+3. Lower socioeconomic status.

+4. Genetic predisposition.

 Select the correct answer using the code given below.
```

### 17. Question id=5770

- **Subject**: Obstetrics & Gynaecology
- **Topic**: Breech Presentation and External Cephalic Version
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are contraindications to external cephalic version in antenatal management of breech presentation?
Antepartum haemorrhage
Multiple pregnancy
Reactive Non Stress Test
Severe oligohydramnios
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following are contraindications to external cephalic version in antenatal management of breech presentation?

1. Antepartum haemorrhage.
2. Multiple pregnancy.
3. Reactive Non Stress Test.
4. Severe oligohydramnios.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5770 (before)

+++ q5770 (after)

@@ -1,6 +1,7 @@

 Which of the following are contraindications to external cephalic version in antenatal management of breech presentation?

-Antepartum haemorrhage

-Multiple pregnancy

-Reactive Non Stress Test

-Severe oligohydramnios

+

+1. Antepartum haemorrhage.

+2. Multiple pregnancy.

+3. Reactive Non Stress Test.

+4. Severe oligohydramnios.

 Select the correct answer using the code given below.
```

### 18. Question id=5801

- **Subject**: Obstetrics & Gynaecology
- **Topic**: Complications of Abortion
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are the clinical features of septic abortion?
Persistent tachycardia ΓëÑ 90 bpm
Impaired mental status
Hypothermia
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following are the clinical features of septic abortion?

1. Persistent tachycardia ΓëÑ 90 bpm.
2. Impaired mental status.
3. Hypothermia.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5801 (before)

+++ q5801 (after)

@@ -1,5 +1,6 @@

 Which of the following are the clinical features of septic abortion?

-Persistent tachycardia ΓëÑ 90 bpm

-Impaired mental status

-Hypothermia

+

+1. Persistent tachycardia ΓëÑ 90 bpm.

+2. Impaired mental status.

+3. Hypothermia.

 Select the correct answer using the code given below.
```

### 19. Question id=5775

- **Subject**: Obstetrics & Gynaecology
- **Topic**: Antenatal Ultrasound in Obstetrics
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following statements are correct with respect to antenatal USG examination?
It helps in detecting gross fetal anomalies
It helps in identifying multiple pregnancies
It helps in identifying viable pregnancy
Best dating is possible with third trimester ultrasound scan
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following statements are correct with respect to antenatal USG examination?

1. It helps in detecting gross fetal anomalies.
2. It helps in identifying multiple pregnancies.
3. It helps in identifying viable pregnancy.
4. Best dating is possible with third trimester ultrasound scan.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5775 (before)

+++ q5775 (after)

@@ -1,6 +1,7 @@

 Which of the following statements are correct with respect to antenatal USG examination?

-It helps in detecting gross fetal anomalies

-It helps in identifying multiple pregnancies

-It helps in identifying viable pregnancy

-Best dating is possible with third trimester ultrasound scan

+

+1. It helps in detecting gross fetal anomalies.

+2. It helps in identifying multiple pregnancies.

+3. It helps in identifying viable pregnancy.

+4. Best dating is possible with third trimester ultrasound scan.

 Select the correct answer using the code given below.
```

### 20. Question id=5803

- **Subject**: Obstetrics & Gynaecology
- **Topic**: Contraceptive Methods and Failure Rates
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are correct regarding failure rate of contraceptive methods?
Depot medroxyprogesterone acetate 0 to 1 per HWY
Norplant 0.1 per HWY
LNG-IUS 0.02 per HWY
Levonorgestrel 3 per HWY
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following are correct regarding failure rate of contraceptive methods?

1. Depot medroxyprogesterone acetate 0 to 1 per HWY.
2. Norplant 0.1 per HWY.
3. LNG-IUS 0.02 per HWY.
4. Levonorgestrel 3 per HWY.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5803 (before)

+++ q5803 (after)

@@ -1,6 +1,7 @@

 Which of the following are correct regarding failure rate of contraceptive methods?

-Depot medroxyprogesterone acetate 0 to 1 per HWY

-Norplant 0.1 per HWY

-LNG-IUS 0.02 per HWY

-Levonorgestrel 3 per HWY

+

+1. Depot medroxyprogesterone acetate 0 to 1 per HWY.

+2. Norplant 0.1 per HWY.

+3. LNG-IUS 0.02 per HWY.

+4. Levonorgestrel 3 per HWY.

 Select the correct answer using the code given below.
```

### 21. Question id=5782

- **Subject**: Obstetrics & Gynaecology
- **Topic**: Operative Obstetrics
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are the pre-requisites of outlet forceps delivery?
Bladder should be empty
Membranes should be intact
Cervix should be fully dilated
Fetal skull has reached level of pelvic floor
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following are the pre-requisites of outlet forceps delivery?

1. Bladder should be empty.
2. Membranes should be intact.
3. Cervix should be fully dilated.
4. Fetal skull has reached level of pelvic floor.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5782 (before)

+++ q5782 (after)

@@ -1,6 +1,7 @@

 Which of the following are the pre-requisites of outlet forceps delivery?

-Bladder should be empty

-Membranes should be intact

-Cervix should be fully dilated

-Fetal skull has reached level of pelvic floor

+

+1. Bladder should be empty.

+2. Membranes should be intact.

+3. Cervix should be fully dilated.

+4. Fetal skull has reached level of pelvic floor.

 Select the correct answer using the code given below.
```

### 22. Question id=5798

- **Subject**: Obstetrics & Gynaecology
- **Topic**: Obstetric Management During Labour
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are indications of vaginal examinations during labour?
To stretch the vagina intermittently
At the onset of labour
To monitor progress of labour
Following rupture of membranes
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following are indications of vaginal examinations during labour?

1. To stretch the vagina intermittently.
2. At the onset of labour.
3. To monitor progress of labour.
4. Following rupture of membranes.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5798 (before)

+++ q5798 (after)

@@ -1,6 +1,7 @@

 Which of the following are indications of vaginal examinations during labour?

-To stretch the vagina intermittently

-At the onset of labour

-To monitor progress of labour

-Following rupture of membranes

+

+1. To stretch the vagina intermittently.

+2. At the onset of labour.

+3. To monitor progress of labour.

+4. Following rupture of membranes.

 Select the correct answer using the code given below.
```

### 23. Question id=5806

- **Subject**: Obstetrics & Gynaecology
- **Topic**: Contraception and Family Planning
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are absolute contraindications of Combined Oral Contraceptive (COCs)?
Arterial or venous thrombosis history
Severe hypertension
Gestational trophoblastic neoplasia
Diabetes with vascular complications
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following are absolute contraindications of Combined Oral Contraceptive (COCs)?

1. Arterial or venous thrombosis history.
2. Severe hypertension.
3. Gestational trophoblastic neoplasia.
4. Diabetes with vascular complications.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5806 (before)

+++ q5806 (after)

@@ -1,6 +1,7 @@

 Which of the following are absolute contraindications of Combined Oral Contraceptive (COCs)?

-Arterial or venous thrombosis history

-Severe hypertension

-Gestational trophoblastic neoplasia

-Diabetes with vascular complications

+

+1. Arterial or venous thrombosis history.

+2. Severe hypertension.

+3. Gestational trophoblastic neoplasia.

+4. Diabetes with vascular complications.

 Select the correct answer using the code given below.
```

### 24. Question id=5598

- **Subject**: Community Medicine
- **Topic**: Health Promotion and Ottawa Charter
- **Year**: 2020
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following key action areas are incorporated in the Ottawa Charter?
Building healthy public policy
Strengthening community action for health
Reorienting health services
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following key action areas are incorporated in the Ottawa Charter?

1. Building healthy public policy.
2. Strengthening community action for health.
3. Reorienting health services.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q5598 (before)

+++ q5598 (after)

@@ -1,5 +1,6 @@

 Which of the following key action areas are incorporated in the Ottawa Charter?

-Building healthy public policy

-Strengthening community action for health

-Reorienting health services

+

+1. Building healthy public policy.

+2. Strengthening community action for health.

+3. Reorienting health services.

 Select the correct answer using the code given below:
```

### 25. Question id=5597

- **Subject**: Community Medicine
- **Topic**: Healthcare Delivery Indicators
- **Year**: 2020
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are health care delivery indicators?
Population per trained birth attendant
Population per health/sub centre
Doctor-nurse ratio
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following are health care delivery indicators?

1. Population per trained birth attendant.
2. Population per health/sub centre.
3. Doctor-nurse ratio.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q5597 (before)

+++ q5597 (after)

@@ -1,5 +1,6 @@

 Which of the following are health care delivery indicators?

-Population per trained birth attendant

-Population per health/sub centre

-Doctor-nurse ratio

+

+1. Population per trained birth attendant.

+2. Population per health/sub centre.

+3. Doctor-nurse ratio.

 Select the correct answer using the code given below:
```

### 26. Question id=5568

- **Subject**: Community Medicine
- **Topic**: Disinfection and Sterilization
- **Year**: 2020
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following represent the properties of an ideal disinfectant?
It is broad spectrum
It is fast acting
It is non-toxic
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following represent the properties of an ideal disinfectant?

1. It is broad spectrum.
2. It is fast acting.
3. It is non-toxic.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q5568 (before)

+++ q5568 (after)

@@ -1,5 +1,6 @@

 Which of the following represent the properties of an ideal disinfectant?

-It is broad spectrum

-It is fast acting

-It is non-toxic

+

+1. It is broad spectrum.

+2. It is fast acting.

+3. It is non-toxic.

 Select the correct answer using the code given below:
```

### 27. Question id=5569

- **Subject**: Community Medicine
- **Topic**: Non-Communicable Diseases: Hypertension Prevention
- **Year**: 2020
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following measures can help reduce the risk of systemic hypertension?
Reduction in dietary intake of common salt
Controlling weight for age
Increasing potassium rich foods in the diet
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following measures can help reduce the risk of systemic hypertension?

1. Reduction in dietary intake of common salt.
2. Controlling weight for age.
3. Increasing potassium rich foods in the diet.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q5569 (before)

+++ q5569 (after)

@@ -1,5 +1,6 @@

 Which of the following measures can help reduce the risk of systemic hypertension?

-Reduction in dietary intake of common salt

-Controlling weight for age

-Increasing potassium rich foods in the diet

+

+1. Reduction in dietary intake of common salt.

+2. Controlling weight for age.

+3. Increasing potassium rich foods in the diet.

 Select the correct answer using the code given below:
```

### 28. Question id=5595

- **Subject**: Community Medicine
- **Topic**: Health Indicators and Indices
- **Year**: 2020
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following statements regarding Physical Quality of Life Index (PQLI) are correct?
It consolidates infant mortality, life expectancy at age one, and literacy
It does not measure economic growth but measures the result of economic policies
For each component, the performance of individual countries is placed on a scale of 0-100
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following statements regarding Physical Quality of Life Index (PQLI) are correct?

1. It consolidates infant mortality, life expectancy at age one, and literacy.
2. It does not measure economic growth but measures the result of economic policies.
3. For each component, the performance of individual countries is placed on a scale of 0-100.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q5595 (before)

+++ q5595 (after)

@@ -1,5 +1,6 @@

 Which of the following statements regarding Physical Quality of Life Index (PQLI) are correct?

-It consolidates infant mortality, life expectancy at age one, and literacy

-It does not measure economic growth but measures the result of economic policies

-For each component, the performance of individual countries is placed on a scale of 0-100

+

+1. It consolidates infant mortality, life expectancy at age one, and literacy.

+2. It does not measure economic growth but measures the result of economic policies.

+3. For each component, the performance of individual countries is placed on a scale of 0-100.

 Select the correct answer using the code given below:
```

### 29. Question id=5454

- **Subject**: General Medicine
- **Topic**: Systemic Sclerosis (Scleroderma)
- **Year**: 2020
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following features are associated with poor prognosis in Diffuse Cutaneous Systemic Sclerosis?
Older age
A high gas transfer factor for carbon monoxide (TLCO)
Proteinuria
Diffuse skin disease
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following features are associated with poor prognosis in Diffuse Cutaneous Systemic Sclerosis?

1. Older age.
2. A high gas transfer factor for carbon monoxide (TLCO).
3. Proteinuria.
4. Diffuse skin disease.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q5454 (before)

+++ q5454 (after)

@@ -1,6 +1,7 @@

 Which of the following features are associated with poor prognosis in Diffuse Cutaneous Systemic Sclerosis?

-Older age

-A high gas transfer factor for carbon monoxide (TLCO)

-Proteinuria

-Diffuse skin disease

+

+1. Older age.

+2. A high gas transfer factor for carbon monoxide (TLCO).

+3. Proteinuria.

+4. Diffuse skin disease.

 Select the correct answer using the code given below:
```

### 30. Question id=5455

- **Subject**: General Medicine
- **Topic**: Rheumatology and Gout Management
- **Year**: 2020
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following statements regarding pegloticase are correct?
It is enzyme conjugate
It is useful in chronic Gout management
The main adverse effects are infusion reactions and development of antibodies
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following statements regarding pegloticase are correct?

1. It is enzyme conjugate.
2. It is useful in chronic Gout management.
3. The main adverse effects are infusion reactions and development of antibodies.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q5455 (before)

+++ q5455 (after)

@@ -1,5 +1,6 @@

 Which of the following statements regarding pegloticase are correct?

-It is enzyme conjugate

-It is useful in chronic Gout management

-The main adverse effects are infusion reactions and development of antibodies

+

+1. It is enzyme conjugate.

+2. It is useful in chronic Gout management.

+3. The main adverse effects are infusion reactions and development of antibodies.

 Select the correct answer using the code given below:
```

### 31. Question id=5504

- **Subject**: General Surgery
- **Topic**: Splenic Artery Aneurysm
- **Year**: 2020
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are correct regarding splenic artery aneurysm?
Main arterial trunk is the common site
Palpable thrill can be felt
It is symptomless unless it ruptures
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following are correct regarding splenic artery aneurysm?

1. Main arterial trunk is the common site.
2. Palpable thrill can be felt.
3. It is symptomless unless it ruptures.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q5504 (before)

+++ q5504 (after)

@@ -1,5 +1,6 @@

 Which of the following are correct regarding splenic artery aneurysm?

-Main arterial trunk is the common site

-Palpable thrill can be felt

-It is symptomless unless it ruptures

+

+1. Main arterial trunk is the common site.

+2. Palpable thrill can be felt.

+3. It is symptomless unless it ruptures.

 Select the correct answer using the code given below:
```

### 32. Question id=5517

- **Subject**: General Surgery
- **Topic**: Post-Mastectomy Lymphedema
- **Year**: 2020
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following statements regarding lymphoedema following breast cancer treatment are correct?
Incidence has decreased due to rarely combined therapy of axillary LN dissection and radiotherapy
Precipitating cause like LN metastasis is a major determinant
The condition is often painful
Oedematous limb is susceptible to bacterial infection
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following statements regarding lymphoedema following breast cancer treatment are correct?

1. Incidence has decreased due to rarely combined therapy of axillary LN dissection and radiotherapy.
2. Precipitating cause like LN metastasis is a major determinant.
3. The condition is often painful.
4. Oedematous limb is susceptible to bacterial infection.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q5517 (before)

+++ q5517 (after)

@@ -1,6 +1,7 @@

 Which of the following statements regarding lymphoedema following breast cancer treatment are correct?

-Incidence has decreased due to rarely combined therapy of axillary LN dissection and radiotherapy

-Precipitating cause like LN metastasis is a major determinant

-The condition is often painful

-Oedematous limb is susceptible to bacterial infection

+

+1. Incidence has decreased due to rarely combined therapy of axillary LN dissection and radiotherapy.

+2. Precipitating cause like LN metastasis is a major determinant.

+3. The condition is often painful.

+4. Oedematous limb is susceptible to bacterial infection.

 Select the correct answer using the code given below:
```

### 33. Question id=5537

- **Subject**: Obstetrics & Gynaecology
- **Topic**: Medical Termination of Pregnancy (MTP) Act and Regulations
- **Year**: 2020
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following is/are required for a registered medical practitioner to qualify for performing Medical Termination of Pregnancy (MTP), as per revised rules of MTP Act?
Certified for assisting at least 15 MTP in an authorized centre
Diploma or degree in Obstetrics and Gynaecology
House surgeon training for 3 months in Obstetrics and Gynaecology
Certified training for 6 months in laparoscopic surgeries
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following is/are required for a registered medical practitioner to qualify for performing Medical Termination of Pregnancy (MTP), as per revised rules of MTP Act?

1. Certified for assisting at least 15 MTP in an authorized centre.
2. Diploma or degree in Obstetrics and Gynaecology.
3. House surgeon training for 3 months in Obstetrics and Gynaecology.
4. Certified training for 6 months in laparoscopic surgeries.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q5537 (before)

+++ q5537 (after)

@@ -1,6 +1,7 @@

 Which of the following is/are required for a registered medical practitioner to qualify for performing Medical Termination of Pregnancy (MTP), as per revised rules of MTP Act?

-Certified for assisting at least 15 MTP in an authorized centre

-Diploma or degree in Obstetrics and Gynaecology

-House surgeon training for 3 months in Obstetrics and Gynaecology

-Certified training for 6 months in laparoscopic surgeries

+

+1. Certified for assisting at least 15 MTP in an authorized centre.

+2. Diploma or degree in Obstetrics and Gynaecology.

+3. House surgeon training for 3 months in Obstetrics and Gynaecology.

+4. Certified training for 6 months in laparoscopic surgeries.

 Select the correct answer using the code given below:
```

### 34. Question id=5552

- **Subject**: Obstetrics & Gynaecology
- **Topic**: Vaginal Infections and Trichomoniasis
- **Year**: 2020
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are characteristics of Trichomonas vaginitis?
Presence of greenish frothy discharge
Vaginal pH > 4.5
Presence of clue cells in microscopic examination
Strawberry spots on the vaginal mucosa
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following are characteristics of Trichomonas vaginitis?

1. Presence of greenish frothy discharge.
2. Vaginal pH > 4.5.
3. Presence of clue cells in microscopic examination.
4. Strawberry spots on the vaginal mucosa.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q5552 (before)

+++ q5552 (after)

@@ -1,6 +1,7 @@

 Which of the following are characteristics of Trichomonas vaginitis?

-Presence of greenish frothy discharge

-Vaginal pH > 4.5

-Presence of clue cells in microscopic examination

-Strawberry spots on the vaginal mucosa

+

+1. Presence of greenish frothy discharge.

+2. Vaginal pH > 4.5.

+3. Presence of clue cells in microscopic examination.

+4. Strawberry spots on the vaginal mucosa.

 Select the correct answer using the code given below:
```

### 35. Question id=5563

- **Subject**: Obstetrics & Gynaecology
- **Topic**: Pelvic Organ Prolapse (POP)
- **Year**: 2020
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following symptoms can be associated with pelvic organ prolapse?
Difficulty in passing urine
Incomplete evacuation of urine
Urgency and frequency
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following symptoms can be associated with pelvic organ prolapse?

1. Difficulty in passing urine.
2. Incomplete evacuation of urine.
3. Urgency and frequency.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q5563 (before)

+++ q5563 (after)

@@ -1,5 +1,6 @@

 Which of the following symptoms can be associated with pelvic organ prolapse?

-Difficulty in passing urine

-Incomplete evacuation of urine

-Urgency and frequency

+

+1. Difficulty in passing urine.

+2. Incomplete evacuation of urine.

+3. Urgency and frequency.

 Select the correct answer using the code given below:
```

### 36. Question id=5549

- **Subject**: Obstetrics & Gynaecology
- **Topic**: Partograph in Labor Monitoring
- **Year**: 2020
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following information are provided by partograph?
Colour of liquor
Uterine contractions with duration and frequency
Dilatation of cervix
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following information are provided by partograph?

1. Colour of liquor.
2. Uterine contractions with duration and frequency.
3. Dilatation of cervix.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q5549 (before)

+++ q5549 (after)

@@ -1,5 +1,6 @@

 Which of the following information are provided by partograph?

-Colour of liquor

-Uterine contractions with duration and frequency

-Dilatation of cervix

+

+1. Colour of liquor.

+2. Uterine contractions with duration and frequency.

+3. Dilatation of cervix.

 Select the correct answer using the code given below:
```

### 37. Question id=22691

- **Subject**: Dermatology
- **Topic**: —
- **Year**: 0
- **Exam type**: neet_pg
- **Needs review**: True
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following statements are correct regarding Peutz-Jeghers syndrome?
It is an autosomal dominant condition
Mutation occurs in the STK11 gene on chromosome 19
Melanin spots characteristically occur on the mouth, lips, digits and perianal skin
Polyps are adenomatous in nature and confined to the colon
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following statements are correct regarding Peutz-Jeghers syndrome?

1. It is an autosomal dominant condition.
2. Mutation occurs in the STK11 gene on chromosome 19.
3. Melanin spots characteristically occur on the mouth, lips, digits and perianal skin.
4. Polyps are adenomatous in nature and confined to the colon.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q22691 (before)

+++ q22691 (after)

@@ -1,6 +1,7 @@

 Which of the following statements are correct regarding Peutz-Jeghers syndrome?

-It is an autosomal dominant condition

-Mutation occurs in the STK11 gene on chromosome 19

-Melanin spots characteristically occur on the mouth, lips, digits and perianal skin

-Polyps are adenomatous in nature and confined to the colon

+

+1. It is an autosomal dominant condition.

+2. Mutation occurs in the STK11 gene on chromosome 19.

+3. Melanin spots characteristically occur on the mouth, lips, digits and perianal skin.

+4. Polyps are adenomatous in nature and confined to the colon.

 Select the correct answer using the code given below:
```

### 38. Question id=22665

- **Subject**: General Surgery
- **Topic**: —
- **Year**: 0
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following statements are correct regarding indirect inguinal hernia?
It lies lateral to the inferior epigastric vessels
It can descend into the scrotum
Ring invagination test impulse is felt at the pulp of the examining finger
It is more common in premature infants and low birth weight babies
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following statements are correct regarding indirect inguinal hernia?

1. It lies lateral to the inferior epigastric vessels.
2. It can descend into the scrotum.
3. Ring invagination test impulse is felt at the pulp of the examining finger.
4. It is more common in premature infants and low birth weight babies.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q22665 (before)

+++ q22665 (after)

@@ -1,6 +1,7 @@

 Which of the following statements are correct regarding indirect inguinal hernia?

-It lies lateral to the inferior epigastric vessels

-It can descend into the scrotum

-Ring invagination test impulse is felt at the pulp of the examining finger

-It is more common in premature infants and low birth weight babies

+

+1. It lies lateral to the inferior epigastric vessels.

+2. It can descend into the scrotum.

+3. Ring invagination test impulse is felt at the pulp of the examining finger.

+4. It is more common in premature infants and low birth weight babies.

 Select the correct answer using the code given below:
```

### 39. Question id=22693

- **Subject**: General Surgery
- **Topic**: —
- **Year**: 0
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following statements are correct regarding Amsterdam II criteria for Lynch syndrome?
Requires three or more family members with a Lynch syndrome-related cancer
Two or more successive affected generations must be involved
At least one tumour must be diagnosed before age 50 years
FAP must be confirmed in at least one family member
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following statements are correct regarding Amsterdam II criteria for Lynch syndrome?

1. Requires three or more family members with a Lynch syndrome-related cancer.
2. Two or more successive affected generations must be involved.
3. At least one tumour must be diagnosed before age 50 years.
4. FAP must be confirmed in at least one family member.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q22693 (before)

+++ q22693 (after)

@@ -1,6 +1,7 @@

 Which of the following statements are correct regarding Amsterdam II criteria for Lynch syndrome?

-Requires three or more family members with a Lynch syndrome-related cancer

-Two or more successive affected generations must be involved

-At least one tumour must be diagnosed before age 50 years

-FAP must be confirmed in at least one family member

+

+1. Requires three or more family members with a Lynch syndrome-related cancer.

+2. Two or more successive affected generations must be involved.

+3. At least one tumour must be diagnosed before age 50 years.

+4. FAP must be confirmed in at least one family member.

 Select the correct answer using the code given below:
```

### 40. Question id=22687

- **Subject**: Expert Curated
- **Topic**: —
- **Year**: 0
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are macroscopic features characteristic of Crohn's disease?
Continuous mucosal involvement
Skip lesions
Cobblestone appearance of the mucosa
Creeping fat over the serosa
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following are macroscopic features characteristic of Crohn's disease?

1. Continuous mucosal involvement.
2. Skip lesions.
3. Cobblestone appearance of the mucosa.
4. Creeping fat over the serosa.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q22687 (before)

+++ q22687 (after)

@@ -1,6 +1,7 @@

 Which of the following are macroscopic features characteristic of Crohn's disease?

-Continuous mucosal involvement

-Skip lesions

-Cobblestone appearance of the mucosa

-Creeping fat over the serosa

+

+1. Continuous mucosal involvement.

+2. Skip lesions.

+3. Cobblestone appearance of the mucosa.

+4. Creeping fat over the serosa.

 Select the correct answer using the code given below:
```

### 41. Question id=22676

- **Subject**: Expert Curated
- **Topic**: —
- **Year**: 0
- **Exam type**: cms
- **Needs review**: True
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following criteria define Acute Liver Failure?
Coagulation abnormality (usually INR above 1.5)
Any degree of mental alteration (encephalopathy)
Absence of pre-existing liver disease
Illness duration of more than 26 weeks
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following criteria define Acute Liver Failure?

1. Coagulation abnormality (usually INR above 1.5).
2. Any degree of mental alteration (encephalopathy).
3. Absence of pre-existing liver disease.
4. Illness duration of more than 26 weeks.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q22676 (before)

+++ q22676 (after)

@@ -1,6 +1,7 @@

 Which of the following criteria define Acute Liver Failure?

-Coagulation abnormality (usually INR above 1.5)

-Any degree of mental alteration (encephalopathy)

-Absence of pre-existing liver disease

-Illness duration of more than 26 weeks

+

+1. Coagulation abnormality (usually INR above 1.5).

+2. Any degree of mental alteration (encephalopathy).

+3. Absence of pre-existing liver disease.

+4. Illness duration of more than 26 weeks.

 Select the correct answer using the code given below:
```

### 42. Question id=22603

- **Subject**: Expert Curated
- **Topic**: —
- **Year**: 0
- **Exam type**: cms
- **Needs review**: True
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following statements regarding puerperal blues are correct?
It usually occurs within the first week after delivery
It is associated with specific endocrine abnormalities
Management includes reassurance and emotional support
It affects nearly half of postpartum women
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following statements regarding puerperal blues are correct?

1. It usually occurs within the first week after delivery.
2. It is associated with specific endocrine abnormalities.
3. Management includes reassurance and emotional support.
4. It affects nearly half of postpartum women.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q22603 (before)

+++ q22603 (after)

@@ -1,6 +1,7 @@

 Which of the following statements regarding puerperal blues are correct?

-It usually occurs within the first week after delivery

-It is associated with specific endocrine abnormalities

-Management includes reassurance and emotional support

-It affects nearly half of postpartum women

+

+1. It usually occurs within the first week after delivery.

+2. It is associated with specific endocrine abnormalities.

+3. Management includes reassurance and emotional support.

+4. It affects nearly half of postpartum women.

 Select the correct answer using the code given below:
```

### 43. Question id=22595

- **Subject**: Expert Curated
- **Topic**: —
- **Year**: 0
- **Exam type**: cms
- **Needs review**: True
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following statements have obstetric significance at the level of the plane of least pelvic dimensions?
It is the narrowest plane of the pelvis
It is at this plane that external rotation of the fetal head occurs during labour
It marks the beginning of the forward curve of the pelvic axis
It is a landmark used for pudendal nerve block analgesia.
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following statements have obstetric significance at the level of the plane of least pelvic dimensions?

1. It is the narrowest plane of the pelvis.
2. It is at this plane that external rotation of the fetal head occurs during labour.
3. It marks the beginning of the forward curve of the pelvic axis.
4. It is a landmark used for pudendal nerve block analgesia.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q22595 (before)

+++ q22595 (after)

@@ -1,6 +1,7 @@

 Which of the following statements have obstetric significance at the level of the plane of least pelvic dimensions?

-It is the narrowest plane of the pelvis

-It is at this plane that external rotation of the fetal head occurs during labour

-It marks the beginning of the forward curve of the pelvic axis

-It is a landmark used for pudendal nerve block analgesia.

+

+1. It is the narrowest plane of the pelvis.

+2. It is at this plane that external rotation of the fetal head occurs during labour.

+3. It marks the beginning of the forward curve of the pelvic axis.

+4. It is a landmark used for pudendal nerve block analgesia.

 Select the correct answer using the code given below:
```

### 44. Question id=22574

- **Subject**: Expert Curated
- **Topic**: —
- **Year**: 0
- **Exam type**: cms
- **Needs review**: True
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are features of primary dysmenorrhea?
Mostly confined to adolescents
Confined to ovulatory cycles
Pain cured following pregnancy and vaginal delivery
Associated with pelvic pathology
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following are features of primary dysmenorrhea?

1. Mostly confined to adolescents.
2. Confined to ovulatory cycles.
3. Pain cured following pregnancy and vaginal delivery.
4. Associated with pelvic pathology.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q22574 (before)

+++ q22574 (after)

@@ -1,6 +1,7 @@

 Which of the following are features of primary dysmenorrhea?

-Mostly confined to adolescents

-Confined to ovulatory cycles

-Pain cured following pregnancy and vaginal delivery

-Associated with pelvic pathology

+

+1. Mostly confined to adolescents.

+2. Confined to ovulatory cycles.

+3. Pain cured following pregnancy and vaginal delivery.

+4. Associated with pelvic pathology.

 Select the correct answer using the code given below:
```

### 45. Question id=22222

- **Subject**: Expert Curated
- **Topic**: —
- **Year**: 0
- **Exam type**: cms
- **Needs review**: True
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are considered established risk factors for the development of Ovarian Hyperstimulation Syndrome (OHSS)?
Advanced maternal age (>40 years)
Polycystic Ovarian Syndrome (PCOS)
Rapidly rising serum E2 levels (>75% rise from previous day)
Presence of an ovarian ‘necklace sign’ on USG
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following are considered established risk factors for the development of Ovarian Hyperstimulation Syndrome (OHSS)?

1. Advanced maternal age (>40 years).
2. Polycystic Ovarian Syndrome (PCOS).
3. Rapidly rising serum E2 levels (>75% rise from previous day).
4. Presence of an ovarian ‘necklace sign’ on USG.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q22222 (before)

+++ q22222 (after)

@@ -1,6 +1,7 @@

 Which of the following are considered established risk factors for the development of Ovarian Hyperstimulation Syndrome (OHSS)?

-Advanced maternal age (>40 years)

-Polycystic Ovarian Syndrome (PCOS)

-Rapidly rising serum E2 levels (>75% rise from previous day)

-Presence of an ovarian ‘necklace sign’ on USG

+

+1. Advanced maternal age (>40 years).

+2. Polycystic Ovarian Syndrome (PCOS).

+3. Rapidly rising serum E2 levels (>75% rise from previous day).

+4. Presence of an ovarian ‘necklace sign’ on USG.

 Select the correct answer using the code given below:
```

### 46. Question id=22221

- **Subject**: Expert Curated
- **Topic**: —
- **Year**: 0
- **Exam type**: cms
- **Needs review**: True
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following conditions is considered a CONTRAINDICATION for performing Hysterosalpingography (HSG)?
Unexplained infertility
Acute Pelvic Inflammatory Disease (PID)
Suspected pelvic tuberculosis
Abnormal uterine bleeding
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following conditions is considered a CONTRAINDICATION for performing Hysterosalpingography (HSG)?

1. Unexplained infertility.
2. Acute Pelvic Inflammatory Disease (PID).
3. Suspected pelvic tuberculosis.
4. Abnormal uterine bleeding.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q22221 (before)

+++ q22221 (after)

@@ -1,6 +1,7 @@

 Which of the following conditions is considered a CONTRAINDICATION for performing Hysterosalpingography (HSG)?

-Unexplained infertility

-Acute Pelvic Inflammatory Disease (PID)

-Suspected pelvic tuberculosis

-Abnormal uterine bleeding

+

+1. Unexplained infertility.

+2. Acute Pelvic Inflammatory Disease (PID).

+3. Suspected pelvic tuberculosis.

+4. Abnormal uterine bleeding.

 Select the correct answer using the code given below:
```

### 47. Question id=22213

- **Subject**: Expert Curated
- **Topic**: —
- **Year**: 0
- **Exam type**: cms
- **Needs review**: True
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following statements about Klinefelter’s syndrome are correct?
It is the most common cause of testicular failure
Karyotype is 47, XXY
Clinical features include eunuchoid appearance, azoospermia, and gynecomastia
Serum testosterone is low and serum gonadotropins are elevated Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following statements about Klinefelter’s syndrome are correct?

1. It is the most common cause of testicular failure.
2. Karyotype is 47, XXY.
3. Clinical features include eunuchoid appearance, azoospermia, and gynecomastia.
4. Serum testosterone is low and serum gonadotropins are elevated.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q22213 (before)

+++ q22213 (after)

@@ -1,5 +1,7 @@

 Which of the following statements about Klinefelter’s syndrome are correct?

-It is the most common cause of testicular failure

-Karyotype is 47, XXY

-Clinical features include eunuchoid appearance, azoospermia, and gynecomastia

-Serum testosterone is low and serum gonadotropins are elevated Select the correct answer using the code given below:
+

+1. It is the most common cause of testicular failure.

+2. Karyotype is 47, XXY.

+3. Clinical features include eunuchoid appearance, azoospermia, and gynecomastia.

+4. Serum testosterone is low and serum gonadotropins are elevated.

+Select the correct answer using the code given below:
```

### 48. Question id=21895

- **Subject**: Expert Curated
- **Topic**: —
- **Year**: 0
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are causes of recurrent miscarriage?
Poorly controlled diabetes
Antiphospholipid antibody syndrome
Hyperhomocystinemia
Endometriosis
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following are causes of recurrent miscarriage?

1. Poorly controlled diabetes.
2. Antiphospholipid antibody syndrome.
3. Hyperhomocystinemia.
4. Endometriosis.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q21895 (before)

+++ q21895 (after)

@@ -1,6 +1,7 @@

 Which of the following are causes of recurrent miscarriage?

-Poorly controlled diabetes

-Antiphospholipid antibody syndrome

-Hyperhomocystinemia

-Endometriosis

+

+1. Poorly controlled diabetes.

+2. Antiphospholipid antibody syndrome.

+3. Hyperhomocystinemia.

+4. Endometriosis.

 Select the correct answer using the code given below:
```

### 49. Question id=22592

- **Subject**: Expert Curated
- **Topic**: —
- **Year**: 0
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following endocrine changes are seen in normal pregnancy?
Increase in maternal serum iodine levels
Increase in serum Corticotropin-Releasing Hormone (CRH)
Increase in serum aldosterone levels
Decrease in serum ACTH levels
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following endocrine changes are seen in normal pregnancy?

1. Increase in maternal serum iodine levels.
2. Increase in serum Corticotropin-Releasing Hormone (CRH).
3. Increase in serum aldosterone levels.
4. Decrease in serum ACTH levels.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q22592 (before)

+++ q22592 (after)

@@ -1,6 +1,7 @@

 Which of the following endocrine changes are seen in normal pregnancy?

-Increase in maternal serum iodine levels

-Increase in serum Corticotropin-Releasing Hormone (CRH)

-Increase in serum aldosterone levels

-Decrease in serum ACTH levels

+

+1. Increase in maternal serum iodine levels.

+2. Increase in serum Corticotropin-Releasing Hormone (CRH).

+3. Increase in serum aldosterone levels.

+4. Decrease in serum ACTH levels.

 Select the correct answer using the code given below:
```

### 50. Question id=22684

- **Subject**: Expert Curated
- **Topic**: —
- **Year**: 0
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following variables are included in the Ranson criteria for assessing acute pancreatitis at the time of admission?
Blood glucose > 200 mg/dL
Age > 55 years
Serum Calcium 16,000/mm3
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following variables are included in the Ranson criteria for assessing acute pancreatitis at the time of admission?

1. Blood glucose > 200 mg/dL.
2. Age > 55 years.
3. Serum Calcium 16,000/mm3.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q22684 (before)

+++ q22684 (after)

@@ -1,5 +1,6 @@

 Which of the following variables are included in the Ranson criteria for assessing acute pancreatitis at the time of admission?

-Blood glucose > 200 mg/dL

-Age > 55 years

-Serum Calcium 16,000/mm3

+

+1. Blood glucose > 200 mg/dL.

+2. Age > 55 years.

+3. Serum Calcium 16,000/mm3.

 Select the correct answer using the code given below:
```

### 51. Question id=22598

- **Subject**: Expert Curated
- **Topic**: —
- **Year**: 0
- **Exam type**: cms
- **Needs review**: True
- **Confidence**: 1.000
- **Reason accepted**: Score 1.000. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following statements regarding human chorionic gonadotropin (hCG) are correct?
It is a glycoprotein hormone
Its levels are decreased in multiple pregnancy
The α-subunit is common to LH, FSH and TSH
It is produced by the maternal pituitary gland
Select the correct answer using the codes given below:
```

**Rewritten stem:**
```text
Which of the following statements regarding human chorionic gonadotropin (hCG) are correct?

1. It is a glycoprotein hormone.
2. Its levels are decreased in multiple pregnancy.
3. The α-subunit is common to LH, FSH and TSH.
4. It is produced by the maternal pituitary gland.
Select the correct answer using the codes given below:
```

**Unified diff:**
```diff
--- q22598 (before)

+++ q22598 (after)

@@ -1,6 +1,7 @@

 Which of the following statements regarding human chorionic gonadotropin (hCG) are correct?

-It is a glycoprotein hormone

-Its levels are decreased in multiple pregnancy

-The α-subunit is common to LH, FSH and TSH

-It is produced by the maternal pituitary gland

+

+1. It is a glycoprotein hormone.

+2. Its levels are decreased in multiple pregnancy.

+3. The α-subunit is common to LH, FSH and TSH.

+4. It is produced by the maternal pituitary gland.

 Select the correct answer using the codes given below:
```

## MANUAL REVIEW (0.80–0.97)

### 1. Question id=5296

- **Subject**: Obstetrics & Gynaecology
- **Topic**: Cardiovascular Disorders in Pregnancy
- **Year**: 2024
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.950
- **Reason accepted**: Score 0.950. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following statements are correct regarding peripartum cardiomyopathy? It is usually seen in multiparous women. Echocardiography shows ejection fraction less than 45%. ACE inhibitors are contraindicated. History of prior heart disease is mostly present.
    Select the answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following statements are correct regarding peripartum cardiomyopathy? 
1. It is usually seen in multiparous women.
2. Echocardiography shows ejection fraction less than 45%.
3. ACE inhibitors are contraindicated.
4. History of prior heart disease is mostly present.
Select the answer using the code given below.
```

**Unified diff:**
```diff
--- q5296 (before)

+++ q5296 (after)

@@ -1,2 +1,6 @@

-Which of the following statements are correct regarding peripartum cardiomyopathy? It is usually seen in multiparous women. Echocardiography shows ejection fraction less than 45%. ACE inhibitors are contraindicated. History of prior heart disease is mostly present.

-    Select the answer using the code given below.
+Which of the following statements are correct regarding peripartum cardiomyopathy? 

+1. It is usually seen in multiparous women.

+2. Echocardiography shows ejection fraction less than 45%.

+3. ACE inhibitors are contraindicated.

+4. History of prior heart disease is mostly present.

+Select the answer using the code given below.
```

### 2. Question id=5230

- **Subject**: Paediatrics
- **Topic**: Burns and Fluid Resuscitation in Pediatrics
- **Year**: 2024
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.950
- **Reason accepted**: Score 0.950. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following statements are correct regarding the fluid management of pediatric inpatients with burn injuries? The Parkland formula estimates the amount of fluid to be replaced over 24 hours. Volume of fluid (mL) = 4 mL Weight (kg) Total body surface area burn(%). Additional maintenance fluid therapy is also to be given to the child. Half of the resuscitation volume should be given over 6 hours and the remaining half over the next 18 hours.
      Select the answer using code given below:
```

**Rewritten stem:**
```text
Which of the following statements are correct regarding the fluid management of pediatric inpatients with burn injuries? 
1. The Parkland formula estimates the amount of fluid to be replaced over 24 hours.
2. Volume of fluid (mL) = 4 mL Weight (kg) Total body surface area burn(%).
3. Additional maintenance fluid therapy is also to be given to the child.
4. Half of the resuscitation volume should be given over 6 hours and the remaining half over the next 18 hours.
Select the answer using code given below:
```

**Unified diff:**
```diff
--- q5230 (before)

+++ q5230 (after)

@@ -1,2 +1,6 @@

-Which of the following statements are correct regarding the fluid management of pediatric inpatients with burn injuries? The Parkland formula estimates the amount of fluid to be replaced over 24 hours. Volume of fluid (mL) = 4 mL Weight (kg) Total body surface area burn(%). Additional maintenance fluid therapy is also to be given to the child. Half of the resuscitation volume should be given over 6 hours and the remaining half over the next 18 hours.

-      Select the answer using code given below:
+Which of the following statements are correct regarding the fluid management of pediatric inpatients with burn injuries? 

+1. The Parkland formula estimates the amount of fluid to be replaced over 24 hours.

+2. Volume of fluid (mL) = 4 mL Weight (kg) Total body surface area burn(%).

+3. Additional maintenance fluid therapy is also to be given to the child.

+4. Half of the resuscitation volume should be given over 6 hours and the remaining half over the next 18 hours.

+Select the answer using code given below:
```

### 3. Question id=6034

- **Subject**: General Medicine
- **Topic**: Renal Pathophysiology - Nephrotic Syndrome
- **Year**: 2022
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.850
- **Reason accepted**: Score 0.850. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are consequences of nephrotic syndrome?
Increased lipoprotein synthesis
Low serum globulin levels
Increased serum aldosterone levels
Increased serum Antithrombin III levels
```

**Rewritten stem:**
```text
Which of the following are consequences of nephrotic syndrome?

1. Increased lipoprotein synthesis.
2. Low serum globulin levels.
3. Increased serum aldosterone levels.
4. Increased serum Antithrombin III levels.
```

**Unified diff:**
```diff
--- q6034 (before)

+++ q6034 (after)

@@ -1,5 +1,6 @@

 Which of the following are consequences of nephrotic syndrome?

-Increased lipoprotein synthesis

-Low serum globulin levels

-Increased serum aldosterone levels

-Increased serum Antithrombin III levels
+

+1. Increased lipoprotein synthesis.

+2. Low serum globulin levels.

+3. Increased serum aldosterone levels.

+4. Increased serum Antithrombin III levels.
```

### 4. Question id=6014

- **Subject**: General Medicine
- **Topic**: Metabolic Bone Disease
- **Year**: 2022
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.850
- **Reason accepted**: Score 0.850. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are correct with regard to osteoporosis?
It does not cause symptoms until a fracture occurs
Vertebral fracture can present with loss of height, in absence of pain
Smoking is protective
It sometimes presents incidentally as radiological osteopenia
```

**Rewritten stem:**
```text
Which of the following are correct with regard to osteoporosis?

1. It does not cause symptoms until a fracture occurs.
2. Vertebral fracture can present with loss of height, in absence of pain.
3. Smoking is protective.
4. It sometimes presents incidentally as radiological osteopenia.
```

**Unified diff:**
```diff
--- q6014 (before)

+++ q6014 (after)

@@ -1,5 +1,6 @@

 Which of the following are correct with regard to osteoporosis?

-It does not cause symptoms until a fracture occurs

-Vertebral fracture can present with loss of height, in absence of pain

-Smoking is protective

-It sometimes presents incidentally as radiological osteopenia
+

+1. It does not cause symptoms until a fracture occurs.

+2. Vertebral fracture can present with loss of height, in absence of pain.

+3. Smoking is protective.

+4. It sometimes presents incidentally as radiological osteopenia.
```

### 5. Question id=6063

- **Subject**: General Medicine
- **Topic**: Dialysis Access
- **Year**: 2022
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.850
- **Reason accepted**: Score 0.850. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following statements with regard to arterio-venous fistula in dialysis patient are correct?
Distension and thickening of vessel wall occurs
Formed upto a year before dialysis is contemplated
Leg veins are usually preferred
Synthetic graft may be used if fistula formation is not possible
```

**Rewritten stem:**
```text
Which of the following statements with regard to arterio-venous fistula in dialysis patient are correct?

1. Distension and thickening of vessel wall occurs.
2. Formed upto a year before dialysis is contemplated.
3. Leg veins are usually preferred.
4. Synthetic graft may be used if fistula formation is not possible.
```

**Unified diff:**
```diff
--- q6063 (before)

+++ q6063 (after)

@@ -1,5 +1,6 @@

 Which of the following statements with regard to arterio-venous fistula in dialysis patient are correct?

-Distension and thickening of vessel wall occurs

-Formed upto a year before dialysis is contemplated

-Leg veins are usually preferred

-Synthetic graft may be used if fistula formation is not possible
+

+1. Distension and thickening of vessel wall occurs.

+2. Formed upto a year before dialysis is contemplated.

+3. Leg veins are usually preferred.

+4. Synthetic graft may be used if fistula formation is not possible.
```

### 6. Question id=6058

- **Subject**: General Medicine
- **Topic**: Dermatology - Acne Treatment
- **Year**: 2022
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.850
- **Reason accepted**: Score 0.850. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are used in the treatment of Acne vulgaris?
Topical benzoyl peroxide
Topical antibiotics like clindamycin
Oral isotretinoin
Oral ivermectin
```

**Rewritten stem:**
```text
Which of the following are used in the treatment of Acne vulgaris?

1. Topical benzoyl peroxide.
2. Topical antibiotics like clindamycin.
3. Oral isotretinoin.
4. Oral ivermectin.
```

**Unified diff:**
```diff
--- q6058 (before)

+++ q6058 (after)

@@ -1,5 +1,6 @@

 Which of the following are used in the treatment of Acne vulgaris?

-Topical benzoyl peroxide

-Topical antibiotics like clindamycin

-Oral isotretinoin

-Oral ivermectin
+

+1. Topical benzoyl peroxide.

+2. Topical antibiotics like clindamycin.

+3. Oral isotretinoin.

+4. Oral ivermectin.
```

### 7. Question id=6057

- **Subject**: General Medicine
- **Topic**: Vitamin D Metabolism
- **Year**: 2022
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.850
- **Reason accepted**: Score 0.850. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following statements are correct in respect of vitamin D?
Skin exposure to sunlight is the main source
Deficiency of vitamin D causes distal muscle weakness
Vitamin D synthesis decreases in winter, as one moves away from equator
Body store accumulated during summer is consumed during winter
```

**Rewritten stem:**
```text
Which of the following statements are correct in respect of vitamin D?

1. Skin exposure to sunlight is the main source.
2. Deficiency of vitamin D causes distal muscle weakness.
3. Vitamin D synthesis decreases in winter, as one moves away from equator.
4. Body store accumulated during summer is consumed during winter.
```

**Unified diff:**
```diff
--- q6057 (before)

+++ q6057 (after)

@@ -1,5 +1,6 @@

 Which of the following statements are correct in respect of vitamin D?

-Skin exposure to sunlight is the main source

-Deficiency of vitamin D causes distal muscle weakness

-Vitamin D synthesis decreases in winter, as one moves away from equator

-Body store accumulated during summer is consumed during winter
+

+1. Skin exposure to sunlight is the main source.

+2. Deficiency of vitamin D causes distal muscle weakness.

+3. Vitamin D synthesis decreases in winter, as one moves away from equator.

+4. Body store accumulated during summer is consumed during winter.
```

### 8. Question id=6004

- **Subject**: General Medicine
- **Topic**: Diabetes Mellitus and Pharmacotherapy
- **Year**: 2022
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.850
- **Reason accepted**: Score 0.850. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are correct with regard to metformin?
The maximum tolerated dose is 2000 mg/day
Lactic acidosis is the major adverse effect of metformin
It may lower the blood levels of Vitamin B12 level
```

**Rewritten stem:**
```text
Which of the following are correct with regard to metformin?

1. The maximum tolerated dose is 2000 mg/day.
2. Lactic acidosis is the major adverse effect of metformin.
3. It may lower the blood levels of Vitamin B12 level.
```

**Unified diff:**
```diff
--- q6004 (before)

+++ q6004 (after)

@@ -1,4 +1,5 @@

 Which of the following are correct with regard to metformin?

-The maximum tolerated dose is 2000 mg/day

-Lactic acidosis is the major adverse effect of metformin

-It may lower the blood levels of Vitamin B12 level
+

+1. The maximum tolerated dose is 2000 mg/day.

+2. Lactic acidosis is the major adverse effect of metformin.

+3. It may lower the blood levels of Vitamin B12 level.
```

### 9. Question id=6001

- **Subject**: General Medicine
- **Topic**: Neurology
- **Year**: 2022
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.850
- **Reason accepted**: Score 0.850. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are the tests for functional assessment of encephalopathy?
Flapping tremors
Number connection test
Constructional apraxia
```

**Rewritten stem:**
```text
Which of the following are the tests for functional assessment of encephalopathy?

1. Flapping tremors.
2. Number connection test.
3. Constructional apraxia.
```

**Unified diff:**
```diff
--- q6001 (before)

+++ q6001 (after)

@@ -1,4 +1,5 @@

 Which of the following are the tests for functional assessment of encephalopathy?

-Flapping tremors

-Number connection test

-Constructional apraxia
+

+1. Flapping tremors.

+2. Number connection test.

+3. Constructional apraxia.
```

### 10. Question id=6012

- **Subject**: General Medicine
- **Topic**: Central Nervous System Infections
- **Year**: 2022
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.850
- **Reason accepted**: Score 0.850. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are correct regarding tuberculous meningitis?
Acid-Fast Bacilli are infrequently seen on direct smear of CSF
CSF culture for MTB is the gold standard for diagnosis
Xpert MTB/RIF assay is a preferred initial diagnostic option
```

**Rewritten stem:**
```text
Which of the following are correct regarding tuberculous meningitis?

1. Acid-Fast Bacilli are infrequently seen on direct smear of CSF.
2. CSF culture for MTB is the gold standard for diagnosis.
3. Xpert MTB/RIF assay is a preferred initial diagnostic option.
```

**Unified diff:**
```diff
--- q6012 (before)

+++ q6012 (after)

@@ -1,4 +1,5 @@

 Which of the following are correct regarding tuberculous meningitis?

-Acid-Fast Bacilli are infrequently seen on direct smear of CSF

-CSF culture for MTB is the gold standard for diagnosis

-Xpert MTB/RIF assay is a preferred initial diagnostic option
+

+1. Acid-Fast Bacilli are infrequently seen on direct smear of CSF.

+2. CSF culture for MTB is the gold standard for diagnosis.

+3. Xpert MTB/RIF assay is a preferred initial diagnostic option.
```

### 11. Question id=6000

- **Subject**: General Medicine
- **Topic**: Neuromuscular Disorders
- **Year**: 2022
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.850
- **Reason accepted**: Score 0.850. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are correct in respect of Myasthenia gravis?
Symptoms worsen towards the end of the day
There may be difficulty in chewing and swallowing
Acetylcholine receptors in the pre-junctional membrane are involved
Penicillamine may precipitate similar illness
```

**Rewritten stem:**
```text
Which of the following are correct in respect of Myasthenia gravis?

1. Symptoms worsen towards the end of the day.
2. There may be difficulty in chewing and swallowing.
3. Acetylcholine receptors in the pre-junctional membrane are involved.
4. Penicillamine may precipitate similar illness.
```

**Unified diff:**
```diff
--- q6000 (before)

+++ q6000 (after)

@@ -1,5 +1,6 @@

 Which of the following are correct in respect of Myasthenia gravis?

-Symptoms worsen towards the end of the day

-There may be difficulty in chewing and swallowing

-Acetylcholine receptors in the pre-junctional membrane are involved

-Penicillamine may precipitate similar illness
+

+1. Symptoms worsen towards the end of the day.

+2. There may be difficulty in chewing and swallowing.

+3. Acetylcholine receptors in the pre-junctional membrane are involved.

+4. Penicillamine may precipitate similar illness.
```

### 12. Question id=5998

- **Subject**: General Medicine
- **Topic**: Parkinson's Disease Management
- **Year**: 2022
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.850
- **Reason accepted**: Score 0.850. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are correct with regard to Levodopa?
It is most effective for relieving tremors
Only a small portion of total drug reaches the brain
Nausea may be offset by domperidone
It may trigger hallucinations
```

**Rewritten stem:**
```text
Which of the following are correct with regard to Levodopa?

1. It is most effective for relieving tremors.
2. Only a small portion of total drug reaches the brain.
3. Nausea may be offset by domperidone.
4. It may trigger hallucinations.
```

**Unified diff:**
```diff
--- q5998 (before)

+++ q5998 (after)

@@ -1,5 +1,6 @@

 Which of the following are correct with regard to Levodopa?

-It is most effective for relieving tremors

-Only a small portion of total drug reaches the brain

-Nausea may be offset by domperidone

-It may trigger hallucinations
+

+1. It is most effective for relieving tremors.

+2. Only a small portion of total drug reaches the brain.

+3. Nausea may be offset by domperidone.

+4. It may trigger hallucinations.
```

### 13. Question id=5997

- **Subject**: General Medicine
- **Topic**: Neurology - Parkinson's Disease
- **Year**: 2022
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.850
- **Reason accepted**: Score 0.850. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are correct regarding Idiopathic Parkinson's disease?
Motor symptoms are almost always initially symmetrical
Non-motor symptoms include hyposmia and constipation
Cognition is spared in early disease
Speech may become softer and indistinct
```

**Rewritten stem:**
```text
Which of the following are correct regarding Idiopathic Parkinson's disease?

1. Motor symptoms are almost always initially symmetrical.
2. Non-motor symptoms include hyposmia and constipation.
3. Cognition is spared in early disease.
4. Speech may become softer and indistinct.
```

**Unified diff:**
```diff
--- q5997 (before)

+++ q5997 (after)

@@ -1,5 +1,6 @@

 Which of the following are correct regarding Idiopathic Parkinson's disease?

-Motor symptoms are almost always initially symmetrical

-Non-motor symptoms include hyposmia and constipation

-Cognition is spared in early disease

-Speech may become softer and indistinct
+

+1. Motor symptoms are almost always initially symmetrical.

+2. Non-motor symptoms include hyposmia and constipation.

+3. Cognition is spared in early disease.

+4. Speech may become softer and indistinct.
```

### 14. Question id=5994

- **Subject**: General Medicine
- **Topic**: Movement Disorders
- **Year**: 2022
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.850
- **Reason accepted**: Score 0.850. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are correct regarding Essential Tremors?
It may present at any age
Head is almost never involved
Tremor may improve with small amount of alcohol
```

**Rewritten stem:**
```text
Which of the following are correct regarding Essential Tremors?

1. It may present at any age.
2. Head is almost never involved.
3. Tremor may improve with small amount of alcohol.
```

**Unified diff:**
```diff
--- q5994 (before)

+++ q5994 (after)

@@ -1,4 +1,5 @@

 Which of the following are correct regarding Essential Tremors?

-It may present at any age

-Head is almost never involved

-Tremor may improve with small amount of alcohol
+

+1. It may present at any age.

+2. Head is almost never involved.

+3. Tremor may improve with small amount of alcohol.
```

### 15. Question id=5983

- **Subject**: General Medicine
- **Topic**: Liver Disorders in Pregnancy
- **Year**: 2022
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.850
- **Reason accepted**: Score 0.850. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are correct with regard to acute fatty liver of pregnancy?
It is typically present in first trimester
It is more common in multiple pregnancies
Liver biopsy is rarely needed
Delivery of fetus is indicated
```

**Rewritten stem:**
```text
Which of the following are correct with regard to acute fatty liver of pregnancy?

1. It is typically present in first trimester.
2. It is more common in multiple pregnancies.
3. Liver biopsy is rarely needed.
4. Delivery of fetus is indicated.
```

**Unified diff:**
```diff
--- q5983 (before)

+++ q5983 (after)

@@ -1,5 +1,6 @@

 Which of the following are correct with regard to acute fatty liver of pregnancy?

-It is typically present in first trimester

-It is more common in multiple pregnancies

-Liver biopsy is rarely needed

-Delivery of fetus is indicated
+

+1. It is typically present in first trimester.

+2. It is more common in multiple pregnancies.

+3. Liver biopsy is rarely needed.

+4. Delivery of fetus is indicated.
```

### 16. Question id=5980

- **Subject**: General Medicine
- **Topic**: Interstitial Lung Diseases
- **Year**: 2022
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.850
- **Reason accepted**: Score 0.850. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are correct regarding Idiopathic Pulmonary Fibrosis?
Radiological pattern of usual interstitial pneumonia
Finger clubbing
More common in elderly
```

**Rewritten stem:**
```text
Which of the following are correct regarding Idiopathic Pulmonary Fibrosis?

1. Radiological pattern of usual interstitial pneumonia.
2. Finger clubbing.
3. More common in elderly.
```

**Unified diff:**
```diff
--- q5980 (before)

+++ q5980 (after)

@@ -1,4 +1,5 @@

 Which of the following are correct regarding Idiopathic Pulmonary Fibrosis?

-Radiological pattern of usual interstitial pneumonia

-Finger clubbing

-More common in elderly
+

+1. Radiological pattern of usual interstitial pneumonia.

+2. Finger clubbing.

+3. More common in elderly.
```

### 17. Question id=5974

- **Subject**: General Medicine
- **Topic**: Cardiac Pharmacology
- **Year**: 2022
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.850
- **Reason accepted**: Score 0.850. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are correct about Ivabradine?
It may be of use in severe heart failure
It acts on SA node
It reduces heart rate
It is effective in atrial fibrillation
```

**Rewritten stem:**
```text
Which of the following are correct about Ivabradine?

1. It may be of use in severe heart failure.
2. It acts on SA node.
3. It reduces heart rate.
4. It is effective in atrial fibrillation.
```

**Unified diff:**
```diff
--- q5974 (before)

+++ q5974 (after)

@@ -1,5 +1,6 @@

 Which of the following are correct about Ivabradine?

-It may be of use in severe heart failure

-It acts on SA node

-It reduces heart rate

-It is effective in atrial fibrillation
+

+1. It may be of use in severe heart failure.

+2. It acts on SA node.

+3. It reduces heart rate.

+4. It is effective in atrial fibrillation.
```

### 18. Question id=6015

- **Subject**: General Medicine
- **Topic**: Spondyloarthropathies
- **Year**: 2022
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.850
- **Reason accepted**: Score 0.850. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are correct with regard to Ankylosing spondylitis?
Bamboo spine may be seen
Early morning back pain is rare
Uveitis is most common extra articular feature
It is more common in males
```

**Rewritten stem:**
```text
Which of the following are correct with regard to Ankylosing spondylitis?

1. Bamboo spine may be seen.
2. Early morning back pain is rare.
3. Uveitis is most common extra articular feature.
4. It is more common in males.
```

**Unified diff:**
```diff
--- q6015 (before)

+++ q6015 (after)

@@ -1,5 +1,6 @@

 Which of the following are correct with regard to Ankylosing spondylitis?

-Bamboo spine may be seen

-Early morning back pain is rare

-Uveitis is most common extra articular feature

-It is more common in males
+

+1. Bamboo spine may be seen.

+2. Early morning back pain is rare.

+3. Uveitis is most common extra articular feature.

+4. It is more common in males.
```

### 19. Question id=6032

- **Subject**: General Medicine
- **Topic**: Contrast-Induced Nephropathy
- **Year**: 2022
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.850
- **Reason accepted**: Score 0.850. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following statements regarding contrast induced nephrotoxicity are correct?
Diabetes Mellitus is a risk factor.
N-acetylcysteine can fully reverse the renal injury.
Hydration is necessary.
Omit Metformin if nephrotoxicity occurs.
```

**Rewritten stem:**
```text
Which of the following statements regarding contrast induced nephrotoxicity are correct?

1. Diabetes Mellitus is a risk factor.
2. N-acetylcysteine can fully reverse the renal injury.
3. Hydration is necessary.
4. Omit Metformin if nephrotoxicity occurs.
```

**Unified diff:**
```diff
--- q6032 (before)

+++ q6032 (after)

@@ -1,5 +1,6 @@

 Which of the following statements regarding contrast induced nephrotoxicity are correct?

-Diabetes Mellitus is a risk factor.

-N-acetylcysteine can fully reverse the renal injury.

-Hydration is necessary.

-Omit Metformin if nephrotoxicity occurs.
+

+1. Diabetes Mellitus is a risk factor.

+2. N-acetylcysteine can fully reverse the renal injury.

+3. Hydration is necessary.

+4. Omit Metformin if nephrotoxicity occurs.
```

### 20. Question id=6047

- **Subject**: General Medicine
- **Topic**: Vitamin D Supplementation
- **Year**: 2022
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.850
- **Reason accepted**: Score 0.850. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following statements are correct about treatment with vit D supplement?
Serum calcium levels improve earlier than serum PTH levels.
Patients should be closely observed with serial vitamin D levels in blood as vitamin D toxicity occurs frequently
Vitamin D supplementation should always be in conjunction with calcium supplementation.
Nephrolithiasis is a known complication
```

**Rewritten stem:**
```text
Which of the following statements are correct about treatment with vit D supplement?

1. Serum calcium levels improve earlier than serum PTH levels.
2. Patients should be closely observed with serial vitamin D levels in blood as vitamin D toxicity occurs frequently.
3. Vitamin D supplementation should always be in conjunction with calcium supplementation.
4. Nephrolithiasis is a known complication.
```

**Unified diff:**
```diff
--- q6047 (before)

+++ q6047 (after)

@@ -1,5 +1,6 @@

 Which of the following statements are correct about treatment with vit D supplement?

-Serum calcium levels improve earlier than serum PTH levels.

-Patients should be closely observed with serial vitamin D levels in blood as vitamin D toxicity occurs frequently

-Vitamin D supplementation should always be in conjunction with calcium supplementation.

-Nephrolithiasis is a known complication
+

+1. Serum calcium levels improve earlier than serum PTH levels.

+2. Patients should be closely observed with serial vitamin D levels in blood as vitamin D toxicity occurs frequently.

+3. Vitamin D supplementation should always be in conjunction with calcium supplementation.

+4. Nephrolithiasis is a known complication.
```

### 21. Question id=6044

- **Subject**: General Medicine
- **Topic**: Diabetes in Pregnancy
- **Year**: 2022
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.850
- **Reason accepted**: Score 0.850. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following statements with regard to gestational diabetes mellitus (GDM) are correct?
Most women revert to normal glucose tolerance post partum
Children born to a GDM mother have no increased risk of diabetes mellitus later in life
Glucose intolerance develops during second and third trimesters
Insulin resistance is related to metabolic changes of pregnancy
```

**Rewritten stem:**
```text
Which of the following statements with regard to gestational diabetes mellitus (GDM) are correct?

1. Most women revert to normal glucose tolerance post partum.
2. Children born to a GDM mother have no increased risk of diabetes mellitus later in life.
3. Glucose intolerance develops during second and third trimesters.
4. Insulin resistance is related to metabolic changes of pregnancy.
```

**Unified diff:**
```diff
--- q6044 (before)

+++ q6044 (after)

@@ -1,5 +1,6 @@

 Which of the following statements with regard to gestational diabetes mellitus (GDM) are correct?

-Most women revert to normal glucose tolerance post partum

-Children born to a GDM mother have no increased risk of diabetes mellitus later in life

-Glucose intolerance develops during second and third trimesters

-Insulin resistance is related to metabolic changes of pregnancy
+

+1. Most women revert to normal glucose tolerance post partum.

+2. Children born to a GDM mother have no increased risk of diabetes mellitus later in life.

+3. Glucose intolerance develops during second and third trimesters.

+4. Insulin resistance is related to metabolic changes of pregnancy.
```

### 22. Question id=5845

- **Subject**: Community Medicine
- **Topic**: Vaccine Administration Routes
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.950
- **Reason accepted**: Score 0.950. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following vaccines are given through the intramuscular route?
BCG vaccine
Hepatitis B vaccine
Pentavalent vaccine
Inactivated Polio vaccine
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following vaccines are given through the intramuscular route?

1. BCG vaccine.
2. Hepatitis B vaccine.
3. Pentavalent vaccine.
4. Inactivated Polio vaccine.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5845 (before)

+++ q5845 (after)

@@ -1,6 +1,7 @@

 Which of the following vaccines are given through the intramuscular route?

-BCG vaccine

-Hepatitis B vaccine

-Pentavalent vaccine

-Inactivated Polio vaccine

+

+1. BCG vaccine.

+2. Hepatitis B vaccine.

+3. Pentavalent vaccine.

+4. Inactivated Polio vaccine.

 Select the correct answer using the code given below.
```

### 23. Question id=5809

- **Subject**: Community Medicine
- **Topic**: Health Indicators and Indices
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.950
- **Reason accepted**: Score 0.950. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following indicators stand consolidated in Physical Quality of Life Index (PQLI)?
Infant mortality
Life expectancy at age one
Per capita income
Literacy
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following indicators stand consolidated in Physical Quality of Life Index (PQLI)?

1. Infant mortality.
2. Life expectancy at age one.
3. Per capita income.
4. Literacy.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5809 (before)

+++ q5809 (after)

@@ -1,6 +1,7 @@

 Which of the following indicators stand consolidated in Physical Quality of Life Index (PQLI)?

-Infant mortality

-Life expectancy at age one

-Per capita income

-Literacy

+

+1. Infant mortality.

+2. Life expectancy at age one.

+3. Per capita income.

+4. Literacy.

 Select the correct answer using the code given below.
```

### 24. Question id=5661

- **Subject**: General Medicine
- **Topic**: Physiological Changes in Pregnancy
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.950
- **Reason accepted**: Score 0.950. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are decreased during pregnancy?
Iron stores
Vitamin B12 levels
Folate levels
Coagulation factors
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following are decreased during pregnancy?

1. Iron stores.
2. Vitamin B12 levels.
3. Folate levels.
4. Coagulation factors.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5661 (before)

+++ q5661 (after)

@@ -1,6 +1,7 @@

 Which of the following are decreased during pregnancy?

-Iron stores

-Vitamin B12 levels

-Folate levels

-Coagulation factors

+

+1. Iron stores.

+2. Vitamin B12 levels.

+3. Folate levels.

+4. Coagulation factors.

 Select the correct answer using the code given below.
```

### 25. Question id=5637

- **Subject**: General Medicine
- **Topic**: Gastrointestinal Disorders and Associated Conditions
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.950
- **Reason accepted**: Score 0.950. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following diseases may be associated with Coeliac Disease?
Type-2 Diabetes mellitus
IgA deficiency
Down syndrome
Turner's syndrome
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following diseases may be associated with Coeliac Disease?

1. Type-2 Diabetes mellitus.
2. IgA deficiency.
3. Down syndrome.
4. Turner's syndrome.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5637 (before)

+++ q5637 (after)

@@ -1,6 +1,7 @@

 Which of the following diseases may be associated with Coeliac Disease?

-Type-2 Diabetes mellitus

-IgA deficiency

-Down syndrome

-Turner's syndrome

+

+1. Type-2 Diabetes mellitus.

+2. IgA deficiency.

+3. Down syndrome.

+4. Turner's syndrome.

 Select the correct answer using the code given below.
```

### 26. Question id=5619

- **Subject**: General Medicine
- **Topic**: Obstructive Lung Diseases
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.950
- **Reason accepted**: Score 0.950. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are categorised under obstructive lung disease?
Bronchial asthma
Bronchiectasis
Bronchiolitis
Pulmonary sarcoidosis
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following are categorised under obstructive lung disease?

1. Bronchial asthma.
2. Bronchiectasis.
3. Bronchiolitis.
4. Pulmonary sarcoidosis.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5619 (before)

+++ q5619 (after)

@@ -1,6 +1,7 @@

 Which of the following are categorised under obstructive lung disease?

-Bronchial asthma

-Bronchiectasis

-Bronchiolitis

-Pulmonary sarcoidosis

+

+1. Bronchial asthma.

+2. Bronchiectasis.

+3. Bronchiolitis.

+4. Pulmonary sarcoidosis.

 Select the correct answer using the code given below.
```

### 27. Question id=5751

- **Subject**: General Surgery
- **Topic**: Gastrointestinal Pathology
- **Year**: 2021
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.950
- **Reason accepted**: Score 0.950. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are probable sites for Ectopic pancreas?
Submucosa of the stomach and duodenum
Liver
Small bowel mesentery
Splenic hilum
Select the correct answer using the code given below.
```

**Rewritten stem:**
```text
Which of the following are probable sites for Ectopic pancreas?

1. Submucosa of the stomach and duodenum.
2. Liver.
3. Small bowel mesentery.
4. Splenic hilum.
Select the correct answer using the code given below.
```

**Unified diff:**
```diff
--- q5751 (before)

+++ q5751 (after)

@@ -1,6 +1,7 @@

 Which of the following are probable sites for Ectopic pancreas?

-Submucosa of the stomach and duodenum

-Liver

-Small bowel mesentery

-Splenic hilum

+

+1. Submucosa of the stomach and duodenum.

+2. Liver.

+3. Small bowel mesentery.

+4. Splenic hilum.

 Select the correct answer using the code given below.
```

### 28. Question id=22667

- **Subject**: General Surgery
- **Topic**: —
- **Year**: 0
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.950
- **Reason accepted**: Score 0.950. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following hernias are included under the term 'Ventral Hernia'?
Spigelian hernia
Femoral hernia
Parastomal hernia
Lumbar hernia
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following hernias are included under the term 'Ventral Hernia'?

1. Spigelian hernia.
2. Femoral hernia.
3. Parastomal hernia.
4. Lumbar hernia.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q22667 (before)

+++ q22667 (after)

@@ -1,6 +1,7 @@

 Which of the following hernias are included under the term 'Ventral Hernia'?

-Spigelian hernia

-Femoral hernia

-Parastomal hernia

-Lumbar hernia

+

+1. Spigelian hernia.

+2. Femoral hernia.

+3. Parastomal hernia.

+4. Lumbar hernia.

 Select the correct answer using the code given below:
```

### 29. Question id=22254

- **Subject**: Expert Curated
- **Topic**: —
- **Year**: 0
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.950
- **Reason accepted**: Score 0.950. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following statements regarding the management of tension pneumothorax are correct? It is a clinical diagnosis; treatment should never be delayed by waiting for radiological confirmation. Immediate decompression is performed with a large-bore cannula in the second intercostal space at the mid-clavicular line of the affected side. Definitive chest tube is inserted in the fifth intercostal space at the anterior axillary line. Pericardiocentesis is performed as the first-line intervention. Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following statements regarding the management of tension pneumothorax are correct? 
1. It is a clinical diagnosis; treatment should never be delayed by waiting for radiological confirmation.
2. Immediate decompression is performed with a large-bore cannula in the second intercostal space at the mid-clavicular line of the affected side.
3. Definitive chest tube is inserted in the fifth intercostal space at the anterior axillary line.
4. Pericardiocentesis is performed as the first-line intervention.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q22254 (before)

+++ q22254 (after)

@@ -1 +1,6 @@

-Which of the following statements regarding the management of tension pneumothorax are correct? It is a clinical diagnosis; treatment should never be delayed by waiting for radiological confirmation. Immediate decompression is performed with a large-bore cannula in the second intercostal space at the mid-clavicular line of the affected side. Definitive chest tube is inserted in the fifth intercostal space at the anterior axillary line. Pericardiocentesis is performed as the first-line intervention. Select the correct answer using the code given below:
+Which of the following statements regarding the management of tension pneumothorax are correct? 

+1. It is a clinical diagnosis; treatment should never be delayed by waiting for radiological confirmation.

+2. Immediate decompression is performed with a large-bore cannula in the second intercostal space at the mid-clavicular line of the affected side.

+3. Definitive chest tube is inserted in the fifth intercostal space at the anterior axillary line.

+4. Pericardiocentesis is performed as the first-line intervention.

+Select the correct answer using the code given below:
```

### 30. Question id=22205

- **Subject**: Expert Curated
- **Topic**: —
- **Year**: 0
- **Exam type**: cms
- **Needs review**: True
- **Confidence**: 0.850
- **Reason accepted**: Score 0.850. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following correctly describe the features of Androgen Insensitivity Syndrome (Testicular Feminization)?
Inherited as X-linked recessive disorder
Karyotype is 46, XY
Serum testosterone is in the normal male range
Sex chromatin study is positive (Barr body present)
```

**Rewritten stem:**
```text
Which of the following correctly describe the features of Androgen Insensitivity Syndrome (Testicular Feminization)?

1. Inherited as X-linked recessive disorder.
2. Karyotype is 46, XY.
3. Serum testosterone is in the normal male range.
4. Sex chromatin study is positive (Barr body present).
```

**Unified diff:**
```diff
--- q22205 (before)

+++ q22205 (after)

@@ -1,5 +1,6 @@

 Which of the following correctly describe the features of Androgen Insensitivity Syndrome (Testicular Feminization)?

-Inherited as X-linked recessive disorder

-Karyotype is 46, XY

-Serum testosterone is in the normal male range

-Sex chromatin study is positive (Barr body present)
+

+1. Inherited as X-linked recessive disorder.

+2. Karyotype is 46, XY.

+3. Serum testosterone is in the normal male range.

+4. Sex chromatin study is positive (Barr body present).
```

### 31. Question id=22209

- **Subject**: Expert Curated
- **Topic**: —
- **Year**: 0
- **Exam type**: cms
- **Needs review**: True
- **Confidence**: 0.850
- **Reason accepted**: Score 0.850. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following correctly describe Premature Ovarian Insufficiency (POI)?
Ovarian failure occurring before the age of 40 years
Serum FSH >40 mIU/mL on two occasions at 4-week intervals
Serum Estradiol (E2) level is low (<20 pg/mL)
Normal or high serum E2 with amenorrhoea before 35 years
```

**Rewritten stem:**
```text
Which of the following correctly describe Premature Ovarian Insufficiency (POI)?

1. Ovarian failure occurring before the age of 40 years.
2. Serum FSH >40 mIU/mL on two occasions at 4-week intervals.
3. Serum Estradiol (E2) level is low (<20 pg/mL).
4. Normal or high serum E2 with amenorrhoea before 35 years.
```

**Unified diff:**
```diff
--- q22209 (before)

+++ q22209 (after)

@@ -1,5 +1,6 @@

 Which of the following correctly describe Premature Ovarian Insufficiency (POI)?

-Ovarian failure occurring before the age of 40 years

-Serum FSH >40 mIU/mL on two occasions at 4-week intervals

-Serum Estradiol (E2) level is low (<20 pg/mL)

-Normal or high serum E2 with amenorrhoea before 35 years
+

+1. Ovarian failure occurring before the age of 40 years.

+2. Serum FSH >40 mIU/mL on two occasions at 4-week intervals.

+3. Serum Estradiol (E2) level is low (<20 pg/mL).

+4. Normal or high serum E2 with amenorrhoea before 35 years.
```

### 32. Question id=22682

- **Subject**: Expert Curated
- **Topic**: —
- **Year**: 0
- **Exam type**: cms
- **Needs review**: False
- **Confidence**: 0.950
- **Reason accepted**: Score 0.950. Canonical opener matched, ≥3 clean statements, no option-prefixed rows, no \n\n, no instruction prefix in body, no tail-leak.

**Original stem:**
```text
Which of the following are recognized risk factors for the development of pancreatic adenocarcinoma?
Cigarette smoking
Chronic pancreatitis
Diabetes mellitus
Female gender
Select the correct answer using the code given below:
```

**Rewritten stem:**
```text
Which of the following are recognized risk factors for the development of pancreatic adenocarcinoma?

1. Cigarette smoking.
2. Chronic pancreatitis.
3. Diabetes mellitus.
4. Female gender.
Select the correct answer using the code given below:
```

**Unified diff:**
```diff
--- q22682 (before)

+++ q22682 (after)

@@ -1,6 +1,7 @@

 Which of the following are recognized risk factors for the development of pancreatic adenocarcinoma?

-Cigarette smoking

-Chronic pancreatitis

-Diabetes mellitus

-Female gender

+

+1. Cigarette smoking.

+2. Chronic pancreatitis.

+3. Diabetes mellitus.

+4. Female gender.

 Select the correct answer using the code given below:
```
