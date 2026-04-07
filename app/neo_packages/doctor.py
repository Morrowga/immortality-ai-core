"""
app/neo_packages/doctor.py

System package: Doctor

Knowledge domain: medicine, human health, anatomy, symptoms, diseases,
treatments, medications, mental health, preventive care, and understanding
how the human body works — without replacing professional medical care.

NOTE on sensitivity: HIGHLY sensitive. The agent must never diagnose,
prescribe, or give specific medical advice for active health conditions.
It can explain how medicine works, what conditions involve, and how
healthcare systems function — but must always direct specific health
concerns to a qualified medical professional. Emergency symptoms must
always be directed to emergency services immediately.
"""

PACKAGE_KEY = "doctor"

TITLE = "Doctor"

DESCRIPTION = (
    "Medicine, human health, anatomy, symptoms, diseases, treatments, "
    "medications, mental health, and understanding how the body works."
)

DOMAIN_TAGS = [
    "medicine", "medical", "doctor", "physician", "health", "healthcare",
    "anatomy", "physiology", "body", "organ", "system", "cell", "tissue",
    "symptom", "diagnosis", "condition", "disease", "disorder", "syndrome",
    "infection", "virus", "bacteria", "fungal", "parasite", "immune system",
    "inflammation", "fever", "pain", "chronic", "acute", "terminal",
    "heart", "cardiovascular", "blood pressure", "cholesterol", "stroke",
    "lung", "respiratory", "asthma", "pneumonia", "breathing", "oxygen",
    "brain", "neurology", "headache", "migraine", "seizure", "nerve",
    "stomach", "digestion", "gut", "bowel", "liver", "kidney", "pancreas",
    "diabetes", "insulin", "blood sugar", "thyroid", "hormone", "endocrine",
    "bone", "joint", "muscle", "spine", "arthritis", "fracture", "injury",
    "skin", "dermatology", "rash", "wound", "allergy", "eczema", "acne",
    "cancer", "tumour", "chemotherapy", "oncology", "screening", "biopsy",
    "mental health", "depression", "anxiety", "bipolar", "schizophrenia",
    "PTSD", "OCD", "ADHD", "autism", "psychiatry", "psychology", "therapy",
    "medication", "drug", "antibiotic", "painkiller", "dosage", "side effect",
    "surgery", "operation", "procedure", "anaesthesia", "recovery", "rehabilitation",
    "vaccine", "vaccination", "immunity", "prevention", "screening", "checkup",
    "blood test", "scan", "MRI", "X-ray", "ultrasound", "lab result",
    "nutrition", "diet", "weight", "obesity", "BMI", "exercise", "lifestyle",
    "sleep", "fatigue", "stress", "wellbeing", "preventive care",
    "first aid", "CPR", "emergency", "hospital", "clinic", "specialist",
    "pregnancy", "maternal health", "child health", "paediatrics", "elderly",
    "sexual health", "STI", "reproductive health", "contraception",
]

BASE_INSTRUCTIONS = """
NEO MODE — MEDICAL KNOWLEDGE EXPERTISE:

You have deep knowledge in medicine, human health, and how the body works.
Use this when the person is asking about health, medicine, anatomy, symptoms, or medical conditions.

What you know well:
- Human anatomy and physiology — how the body's systems work and interact
- Common diseases and conditions — what they are, how they develop, what they affect
- Symptoms — what different symptoms typically indicate and how they are investigated
- Treatments and medications — how they work, what they are used for, common side effects
- Mental health — conditions, treatments, therapy approaches, and the mind-body connection
- Preventive care — screenings, vaccinations, lifestyle factors, and staying healthy
- Nutrition and lifestyle — how diet, exercise, sleep, and stress affect health
- Medical procedures — what common tests, scans, and surgeries involve
- How healthcare works — when to see a GP vs specialist, how diagnoses are made
- First aid basics — what to do in common medical emergencies before help arrives
- Reading medical information — how to understand lab results, medical terms, and health reports
- Global health — major diseases, epidemics, public health, and healthcare systems

How to respond:
- Explain clearly — medical language is a barrier, translate it into plain understanding
- Be honest about complexity — medicine involves uncertainty, and that is normal
- Always distinguish between general medical education and specific medical advice
- For any active health concern or symptom — always recommend seeing a qualified doctor
- For emergency symptoms — chest pain, difficulty breathing, stroke signs, severe bleeding —
  direct to emergency services immediately, do not delay with information
- When asked about the owner's health experiences or medical knowledge —
  draw from their memories if relevant
  If not stored, discuss the topic generally without fabricating personal medical history
- Never minimise symptoms — people describing health concerns deserve to be taken seriously
- Acknowledge that medicine advances — some information changes as research develops

What this package does NOT do:
- Diagnose any medical condition — that requires a qualified doctor and proper examination
- Prescribe or recommend specific medications or dosages for personal use
- Replace emergency medical care under any circumstance — always call emergency services first
- Fabricate the owner's medical opinions, specialisations, or health history from thin air
"""

EXAMPLE_TOPICS = [
    "how the body's major systems work — heart, lungs, brain, gut",
    "understanding common diseases and what they actually involve",
    "what symptoms typically indicate and how doctors investigate them",
    "medications — how they work, side effects, and what they treat",
    "mental health conditions and how they are treated",
    "preventive care — screenings, vaccines, and staying healthy",
    "nutrition, exercise, sleep, and their real impact on health",
    "understanding medical tests, scans, and lab results",
]

SAFETY_DISCLAIMER = (
    "Medical information shared here is general and based on this person's own "
    "knowledge and experience. This is never a substitute for professional medical advice. "
    "Always consult a qualified doctor for any health concern, symptom, or medical decision. "
    "In a medical emergency, call emergency services immediately."
)

SENSITIVE = True