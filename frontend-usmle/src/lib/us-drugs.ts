/**
 * us-drugs.ts — USMLE-specific utility: maps US brand names to generic (INN)
 * names. Used by AI explanations and question-rendering to surface both names
 * so IMGs aren't tripped up by unfamiliar US brand names.
 *
 * This is a small starter map — extend as you author content.
 */
const BRAND_TO_GENERIC: Record<string, string> = {
    Tylenol: "Acetaminophen (Paracetamol)",
    Motrin: "Ibuprofen",
    Advil: "Ibuprofen",
    Aspirin: "Acetylsalicylic acid (ASA)",
    Coumadin: "Warfarin",
    Zocor: "Simvastatin",
    Lipitor: "Atorvastatin",
    Glucophage: "Metformin",
    Lasix: "Furosemide",
    Prinivil: "Lisinopril",
    Zestril: "Lisinopril",
    Norvasc: "Amlodipine",
    Lopressor: "Metoprolol tartrate",
    Toprol: "Metoprolol succinate",
    Synthroid: "Levothyroxine",
    Ventolin: "Albuterol (Salbutamol)",
    ProAir: "Albuterol (Salbutamol)",
    Flonase: "Fluticasone nasal",
    Zithromax: "Azithromycin",
    Augmentin: "Amoxicillin + Clavulanate",
    Cipro: "Ciprofloxacin",
    Levaquin: "Levofloxacin",
    Keflex: "Cephalexin",
    Omnicef: "Cefdinir",
    Zofran: "Ondansetron",
    Imodium: "Loperamide",
    Nexium: "Esomeprazole",
    Prilosec: "Omeprazole",
    Zantac: "Ranitidine",
    Pepcid: "Famotidine",
    Xanax: "Alprazolam",
    Valium: "Diazepam",
    Ativan: "Lorazepam",
    Ambien: "Zolpidem",
    Lunesta: "Eszopiclone",
    Provigil: "Modafinil",
    Nuvigil: "Armodafinil",
    Strattera: "Atomoxetine",
    Adderall: "Amphetamine + Dextroamphetamine",
    Vyvanse: "Lisdexamfetamine",
    Ritalin: "Methylphenidate",
    Concerta: "Methylphenidate ER",
    Elavil: "Amitriptyline",
    Zoloft: "Sertraline",
    Prozac: "Fluoxetine",
    Paxil: "Paroxetine",
    Lexapro: "Escitalopram",
    Celexa: "Citalopram",
    Effexor: "Venlafaxine",
    Cymbalta: "Duloxetine",
    Wellbutrin: "Bupropion",
    Seroquel: "Quetiapine",
    Risperdal: "Risperidone",
    Zyprexa: "Olanzapine",
    Abilify: "Aripiprazole",
    Haldol: "Haloperidol",
    Zyban: "Bupropion (smoking cessation)",
    Chantix: "Varenicline",
    Trileptal: "Oxcarbazepine",
    Keppra: "Levetiracetam",
    Lamictal: "Lamotrigine",
    Dilantin: "Phenytoin",
    Tegretol: "Carbamazepine",
    Depakote: "Valproate",
    Imitrex: "Sumatriptan",
    Maxalt: "Rizatriptan",
};

/**
 * Annotate a clinical text with both US brand and INN names where applicable.
 * Example: "Tylenol" → "Tylenol (Acetaminophen / Paracetamol)"
 */
export function annotateDrugs(text: string): string {
    if (!text) return text;
    let out = text;
    for (const [brand, generic] of Object.entries(BRAND_TO_GENERIC)) {
        const re = new RegExp(`\\b${brand}\\b`, "g");
        out = out.replace(re, `${brand} (${generic})`);
    }
    return out;
}

/** Look up the INN for a brand name. Returns undefined if unknown. */
export function genericFor(brand: string): string | undefined {
    return BRAND_TO_GENERIC[brand];
}
