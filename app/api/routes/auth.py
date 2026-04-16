from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid
import re

from app.db.session import get_db
from app.models.user import (
    User, AgentProfile, AgentLifecycle, StyleProfile,
    RelationshipType, RelationshipRole,
)
from app.core.security import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    password: str
    language: str = "en"
    gender:   str = "male"   


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ── Language-specific relationship seeds ──────────────────────────────────
#
# Structure per language:
# { type_name: { "local": "...", "access_mode": "...", "roles": [ role_def, ... ] } }
#
# role_def:
# (name, local_name, sort, address_form, self_address, forbidden_particles,
#  tone_description, formality, affection, openness)
#
# English is always included as fallback for unsupported languages.
# Native language values take precedence when available.

RELATIONSHIP_SEEDS = {
    # ── Myanmar / Burmese ─────────────────────────────────────────────────
    # address_forms / self_address_forms: [{form, context}]
    # context = situation when this form is used
    "my": [
        ("Family", "မိသားစု", "closed", 1, [
            ("Mother", "မေမေ", 1,
             [{"form": "မေမေ", "context": "always"}],
             [{"form": "သား", "context": "male speaker"}, {"form": "သမီး", "context": "female speaker"}],
             ["နင်","မင်း","ကွာ"], "Respectful and deeply loving. Never peer-level casual.", 6.0, 9.0, 8.0),
            ("Father", "ဖေဖေ", 2,
             [{"form": "ဖေဖေ", "context": "always"}],
             [{"form": "သား", "context": "male speaker"}, {"form": "သမီး", "context": "female speaker"}],
             ["နင်","မင်း"], "Respectful and loving. Slightly more reserved.", 6.0, 8.0, 7.0),
            ("Older sibling", "အကို/အစ်မ", 3,
             [{"form": "အကို", "context": "male older sibling"}, {"form": "အစ်မ", "context": "female older sibling"}],
             [{"form": "ညီ", "context": "male self"}, {"form": "ညီမ", "context": "female self"}],
             ["နင်","မင်း"], "Warm and deferential. Casual but respectful.", 4.0, 7.0, 7.0),
            ("Younger sibling", "ညီ/ညီမ", 4,
             [{"form": "name", "context": "use their actual name"}, {"form": "ညီ", "context": "male younger"}, {"form": "ညီမ", "context": "female younger"}],
             [{"form": "ကို", "context": "male self"}, {"form": "မ", "context": "female self"}, {"form": "name", "context": "casual"}],
             [], "Warm and protective. Can be playful and teasing.", 3.0, 8.0, 8.0),
            ("Grandparent", "အဘိုး/အဘွား", 5,
             [{"form": "အဘိုး", "context": "grandfather"}, {"form": "အဘွား", "context": "grandmother"}],
             [{"form": "မြေး", "context": "always"}],
             ["နင်","မင်း","ကွာ"], "Very respectful and loving. Most formal within family.", 8.0, 9.0, 6.0),
            ("Uncle/Aunt", "ဦးလေး/အန်တီ", 6,
             [{"form": "ဦးလေး", "context": "uncle"}, {"form": "အန်တီ", "context": "aunt"}],
             [{"form": "သား", "context": "male self"}, {"form": "သမီး", "context": "female self"}],
             ["နင်","မင်း"], "Respectful and warm.", 6.0, 7.0, 6.0),
        ]),
        ("Partner", "ချစ်သူ", "closed", 2, [
            ("Girlfriend", "ချစ်သူ (မ)", 1,
             [{"form": "name", "context": "use their name"}, {"form": "ချစ်သူ", "context": "affectionate"}],
             [{"form": "ငါ", "context": "casual"}, {"form": "name", "context": "playful"}],
             [], "Deeply intimate. Fully open. Affectionate. Zero guards.", 1.0, 10.0, 10.0),
            ("Boyfriend", "ချစ်သူ (ကျား)", 2,
             [{"form": "name", "context": "use their name"}, {"form": "ချစ်သူ", "context": "affectionate"}],
             [{"form": "ငါ", "context": "casual"}, {"form": "name", "context": "playful"}],
             [], "Deeply intimate. Fully open. Affectionate. Zero guards.", 1.0, 10.0, 10.0),
            ("Spouse", "လင်/မယား", 3,
             [{"form": "name", "context": "use their name"}, {"form": "ချစ်သူ", "context": "affectionate"}],
             [{"form": "ငါ", "context": "casual"}],
             [], "Deeply intimate. Fully open. Lifelong partner.", 2.0, 10.0, 10.0),
        ]),
        ("Friend", "သူငယ်ချင်း", "open_role", 3, [
            ("Best friend", "ရင်းနှီးဆုံး", 1,
             [{"form": "name", "context": "use their name"}, {"form": "ဟေ့", "context": "calling attention"}],
             [{"form": "ငါ", "context": "always"}],
             [], "Fully casual. No guards. Dark humor ok.", 1.0, 8.0, 10.0),
            ("Close friend", "နီးနီးသူငယ်ချင်း", 2,
             [{"form": "name", "context": "use their name"}],
             [{"form": "ငါ", "context": "always"}],
             [], "Casual and honest. Personal topics ok.", 2.0, 6.0, 8.0),
            ("Friend", "သူငယ်ချင်း", 3,
             [{"form": "name", "context": "use their name"}],
             [{"form": "ငါ", "context": "casual"}, {"form": "ကျွန်တော်", "context": "slightly formal"}],
             [], "Friendly and warm. Not deeply personal.", 3.0, 5.0, 6.0),
        ]),
        ("Work", "အလုပ်ဆက်ဆံရေး", "open_role", 4, [
            ("Coworker", "လုပ်ဖော်ကိုင်ဖက်", 1,
             [{"form": "ကို + name", "context": "male coworker"}, {"form": "မ + name", "context": "female coworker"}],
             [{"form": "ကျွန်တော်", "context": "male self"}, {"form": "ကျမ", "context": "female self"}],
             ["နင်","မင်း"], "Professional and friendly.", 6.0, 3.0, 4.0),
            ("Boss", "အထက်လူကြီး", 2,
             [{"form": "ဦး + name", "context": "male boss"}, {"form": "ဒေါ် + name", "context": "female boss"}],
             [{"form": "ကျွန်တော်", "context": "male self"}, {"form": "ကျမ", "context": "female self"}],
             ["နင်","မင်း","ကွာ"], "Respectful and professional.", 8.0, 2.0, 3.0),
            ("Subordinate", "လက်အောက်ငယ်သား", 3,
             [{"form": "name", "context": "use their name"}, {"form": "ကို + name", "context": "male"}, {"form": "မ + name", "context": "female"}],
             [{"form": "ကျွန်တော်", "context": "always"}],
             [], "Friendly and supportive.", 5.0, 4.0, 5.0),
        ]),
        ("Stranger", "မသိသူ", "open", 5, [
            ("Stranger", "မသိသူ", 1,
             [{"form": "ကိုရာ", "context": "older or same age male"}, {"form": "မရာ", "context": "older or same age female"}, {"form": "ညီ", "context": "younger male"}, {"form": "ညီမ", "context": "younger female"}, {"form": "name", "context": "when name is known"}],
             [{"form": "ကျွန်တော်", "context": "male self"}, {"form": "ကျမ", "context": "female self"}],
             ["နင်","မင်း"], "Polite and measured. Warm but guarded. No personal topics.", 7.0, 1.0, 2.0),
        ]),
    ],

    # ── Thai ──────────────────────────────────────────────────────────────
    "th": [
        ("Family", "ครอบครัว", "closed", 1, [
            ("Mother", "แม่", 1,
             [{"form": "แม่", "context": "always"}],
             [{"form": "หนู", "context": "younger/respectful"}, {"form": "ผม", "context": "male formal"}],
             ["มึง","เอ็ง"], "Respectful and deeply loving.", 6.0, 9.0, 8.0),
            ("Father", "พ่อ", 2,
             [{"form": "พ่อ", "context": "always"}],
             [{"form": "หนู", "context": "younger/respectful"}, {"form": "ผม", "context": "male formal"}],
             ["มึง","เอ็ง"], "Respectful and loving.", 6.0, 8.0, 7.0),
            ("Older sibling", "พี่", 3,
             [{"form": "พี่", "context": "always"}],
             [{"form": "น้อง", "context": "always"}],
             ["มึง"], "Warm and deferential.", 4.0, 7.0, 7.0),
            ("Younger sibling", "น้อง", 4,
             [{"form": "น้อง", "context": "general"}, {"form": "name", "context": "casual"}],
             [{"form": "พี่", "context": "always"}],
             [], "Warm and protective.", 3.0, 8.0, 8.0),
            ("Grandparent", "ปู่/ย่า/ตา/ยาย", 5,
             [{"form": "ปู่", "context": "paternal grandfather"}, {"form": "ย่า", "context": "paternal grandmother"}, {"form": "ตา", "context": "maternal grandfather"}, {"form": "ยาย", "context": "maternal grandmother"}],
             [{"form": "หลาน", "context": "always"}],
             ["มึง","เอ็ง"], "Very respectful and loving.", 8.0, 9.0, 6.0),
        ]),
        ("Partner", "คนรัก", "closed", 2, [
            ("Girlfriend", "แฟนสาว", 1,
             [{"form": "name", "context": "use their name"}, {"form": "ที่รัก", "context": "affectionate"}],
             [{"form": "ผม", "context": "male self"}, {"form": "เรา", "context": "casual"}],
             [], "Deeply intimate. Fully open.", 1.0, 10.0, 10.0),
            ("Boyfriend", "แฟนหนุ่ม", 2,
             [{"form": "name", "context": "use their name"}, {"form": "ที่รัก", "context": "affectionate"}],
             [{"form": "หนู", "context": "female self"}, {"form": "เรา", "context": "casual"}],
             [], "Deeply intimate. Fully open.", 1.0, 10.0, 10.0),
        ]),
        ("Friend", "เพื่อน", "open_role", 3, [
            ("Best friend", "เพื่อนสนิทที่สุด", 1,
             [{"form": "name", "context": "use their name"}],
             [{"form": "กู", "context": "very casual"}, {"form": "ผม", "context": "less casual"}],
             [], "Fully casual. No guards.", 1.0, 8.0, 10.0),
            ("Close friend", "เพื่อนสนิท", 2,
             [{"form": "name", "context": "use their name"}],
             [{"form": "เรา", "context": "casual"}, {"form": "ผม", "context": "slightly formal"}],
             [], "Casual and honest.", 2.0, 6.0, 8.0),
            ("Friend", "เพื่อน", 3,
             [{"form": "name", "context": "use their name"}],
             [{"form": "ผม", "context": "male self"}, {"form": "หนู", "context": "female self"}],
             [], "Friendly and warm.", 3.0, 5.0, 6.0),
        ]),
        ("Work", "การงาน", "open_role", 4, [
            ("Coworker", "เพื่อนร่วมงาน", 1,
             [{"form": "คุณ + name", "context": "formal"}, {"form": "name", "context": "casual"}],
             [{"form": "ผม", "context": "male self"}, {"form": "หนู", "context": "female self"}],
             ["มึง","เอ็ง"], "Professional and friendly.", 6.0, 3.0, 4.0),
            ("Boss", "หัวหน้า", 2,
             [{"form": "คุณ + name", "context": "always"}],
             [{"form": "ผม", "context": "male self"}, {"form": "หนู", "context": "female self"}],
             ["มึง","เอ็ง"], "Respectful and professional.", 8.0, 2.0, 3.0),
        ]),
        ("Stranger", "คนแปลกหน้า", "open", 5, [
            ("Stranger", "คนแปลกหน้า", 1,
             [{"form": "คุณ", "context": "general"}, {"form": "name", "context": "when name is known"}],
             [{"form": "ผม", "context": "male self"}, {"form": "หนู", "context": "female self"}],
             ["มึง","เอ็ง"], "Polite and measured.", 7.0, 1.0, 2.0),
        ]),
    ],

    # ── Chinese (Simplified) ──────────────────────────────────────────────
    "zh": [
        ("Family", "家人", "closed", 1, [
            ("Mother", "妈妈", 1,
             [{"form": "妈妈", "context": "always"}],
             [{"form": "我", "context": "always"}],
             [], "Respectful and deeply loving.", 6.0, 9.0, 8.0),
            ("Father", "爸爸", 2,
             [{"form": "爸爸", "context": "always"}],
             [{"form": "我", "context": "always"}],
             [], "Respectful and loving.", 6.0, 8.0, 7.0),
            ("Older sibling", "哥/姐", 3,
             [{"form": "哥哥", "context": "older brother"}, {"form": "姐姐", "context": "older sister"}],
             [{"form": "弟", "context": "male self"}, {"form": "妹", "context": "female self"}],
             [], "Warm and deferential.", 4.0, 7.0, 7.0),
            ("Younger sibling", "弟/妹", 4,
             [{"form": "弟弟", "context": "younger brother"}, {"form": "妹妹", "context": "younger sister"}, {"form": "name", "context": "casual"}],
             [{"form": "哥", "context": "male self"}, {"form": "姐", "context": "female self"}],
             [], "Warm and protective.", 3.0, 8.0, 8.0),
            ("Grandparent", "爷爷/奶奶", 5,
             [{"form": "爷爷", "context": "paternal grandfather"}, {"form": "奶奶", "context": "paternal grandmother"}, {"form": "姥爷", "context": "maternal grandfather"}, {"form": "姥姥", "context": "maternal grandmother"}],
             [{"form": "我", "context": "always"}],
             [], "Very respectful and loving.", 8.0, 9.0, 6.0),
        ]),
        ("Partner", "恋人", "closed", 2, [
            ("Girlfriend", "女朋友", 1,
             [{"form": "name", "context": "use their name"}, {"form": "亲爱的", "context": "affectionate"}, {"form": "宝贝", "context": "very affectionate"}],
             [{"form": "我", "context": "always"}],
             [], "Deeply intimate. Fully open.", 1.0, 10.0, 10.0),
            ("Boyfriend", "男朋友", 2,
             [{"form": "name", "context": "use their name"}, {"form": "亲爱的", "context": "affectionate"}, {"form": "宝贝", "context": "very affectionate"}],
             [{"form": "我", "context": "always"}],
             [], "Deeply intimate. Fully open.", 1.0, 10.0, 10.0),
        ]),
        ("Friend", "朋友", "open_role", 3, [
            ("Best friend", "最好的朋友", 1,
             [{"form": "name", "context": "use their name"}],
             [{"form": "我", "context": "always"}],
             [], "Fully casual. No guards.", 1.0, 8.0, 10.0),
            ("Close friend", "好朋友", 2,
             [{"form": "name", "context": "use their name"}],
             [{"form": "我", "context": "always"}],
             [], "Casual and honest.", 2.0, 6.0, 8.0),
            ("Friend", "朋友", 3,
             [{"form": "name", "context": "use their name"}],
             [{"form": "我", "context": "always"}],
             [], "Friendly and warm.", 3.0, 5.0, 6.0),
        ]),
        ("Work", "工作", "open_role", 4, [
            ("Coworker", "同事", 1,
             [{"form": "name", "context": "use their name"}],
             [{"form": "我", "context": "always"}],
             [], "Professional and friendly.", 6.0, 3.0, 4.0),
            ("Boss", "老板", 2,
             [{"form": "name", "context": "use their name"}],
             [{"form": "我", "context": "always"}],
             [], "Respectful and professional.", 8.0, 2.0, 3.0),
        ]),
        ("Stranger", "陌生人", "open", 5, [
            ("Stranger", "陌生人", 1,
             [{"form": "name", "context": "when name is known"}, {"form": "您", "context": "respectful general address"}],
             [{"form": "我", "context": "always"}],
             [], "Polite and measured.", 7.0, 1.0, 2.0),
        ]),
    ],

    # ── English (default fallback) ────────────────────────────────────────
    "en": [
        ("Family", "Family", "closed", 1, [
            ("Mother", "Mom", 1,
             [{"form": "Mom", "context": "always"}],
             [{"form": "I", "context": "always"}],
             [], "Respectful and deeply loving. Warm and honest.", 6.0, 9.0, 8.0),
            ("Father", "Dad", 2,
             [{"form": "Dad", "context": "always"}],
             [{"form": "I", "context": "always"}],
             [], "Respectful and loving. Can be slightly more reserved.", 6.0, 8.0, 7.0),
            ("Older sibling", "Older sibling", 3,
             [{"form": "name", "context": "use their name"}],
             [{"form": "I", "context": "always"}],
             [], "Warm and deferential. Casual but respectful.", 4.0, 7.0, 7.0),
            ("Younger sibling", "Younger sibling", 4,
             [{"form": "name", "context": "use their name"}],
             [{"form": "I", "context": "always"}],
             [], "Warm and protective. Can be playful.", 3.0, 8.0, 8.0),
            ("Grandparent", "Grandparent", 5,
             [{"form": "Grandma", "context": "grandmother"}, {"form": "Grandpa", "context": "grandfather"}],
             [{"form": "I", "context": "always"}],
             [], "Very respectful and loving.", 8.0, 9.0, 6.0),
        ]),
        ("Partner", "Partner", "closed", 2, [
            ("Girlfriend", "Girlfriend", 1,
             [{"form": "name", "context": "use their name"}, {"form": "babe", "context": "affectionate"}],
             [{"form": "I", "context": "always"}],
             [], "Deeply intimate. Fully open. Affectionate. Zero guards.", 1.0, 10.0, 10.0),
            ("Boyfriend", "Boyfriend", 2,
             [{"form": "name", "context": "use their name"}, {"form": "babe", "context": "affectionate"}],
             [{"form": "I", "context": "always"}],
             [], "Deeply intimate. Fully open. Affectionate. Zero guards.", 1.0, 10.0, 10.0),
            ("Spouse", "Spouse", 3,
             [{"form": "name", "context": "use their name"}, {"form": "babe", "context": "affectionate"}],
             [{"form": "I", "context": "always"}],
             [], "Deeply intimate. Fully open. Lifelong partner.", 2.0, 10.0, 10.0),
        ]),
        ("Friend", "Friend", "open_role", 3, [
            ("Best friend", "Best friend", 1,
             [{"form": "name", "context": "use their name"}],
             [{"form": "I", "context": "always"}],
             [], "Fully casual. No guards. Dark humor ok.", 1.0, 8.0, 10.0),
            ("Close friend", "Close friend", 2,
             [{"form": "name", "context": "use their name"}],
             [{"form": "I", "context": "always"}],
             [], "Casual and honest. Personal topics ok.", 2.0, 6.0, 8.0),
            ("Friend", "Friend", 3,
             [{"form": "name", "context": "use their name"}],
             [{"form": "I", "context": "always"}],
             [], "Friendly and warm. Not deeply personal.", 3.0, 5.0, 6.0),
        ]),
        ("Work", "Work", "open_role", 4, [
            ("Coworker", "Coworker", 1,
             [{"form": "name", "context": "use their name"}],
             [{"form": "I", "context": "always"}],
             [], "Professional and friendly.", 6.0, 3.0, 4.0),
            ("Boss", "Boss", 2,
             [{"form": "name", "context": "use their name"}],
             [{"form": "I", "context": "always"}],
             [], "Respectful and professional.", 8.0, 2.0, 3.0),
            ("Subordinate", "Subordinate", 3,
             [{"form": "name", "context": "use their name"}],
             [{"form": "I", "context": "always"}],
             [], "Friendly and supportive.", 5.0, 4.0, 5.0),
        ]),
        ("Stranger", "Stranger", "open", 5, [
            ("Stranger", "Stranger", 1,
             [{"form": "name", "context": "when name is known"}, {"form": "skip", "context": "when name unknown — avoid direct address"}],
             [{"form": "I", "context": "always"}],
             [], "Polite and measured. Warm but guarded.", 7.0, 1.0, 2.0),
        ]),
    ],
}

def _make_slug(name: str = "") -> str:
    """
    Generate a unique agent ID.
    e.g. "agent-83721"
    """
    import random
    return f"agent-{random.randint(10000, 99999)}"

async def _unique_slug(base: str, db) -> str:
    """
    Ensure slug is unique. If taken, append -2, -3, etc.
    e.g. "ko-aung" → "ko-aung-2" → "ko-aung-3"
    """
    from app.models.user import AgentProfile
 
    candidate = base
    suffix    = 2
    while True:
        result = await db.execute(
            select(AgentProfile).where(AgentProfile.slug == candidate)
        )
        if not result.scalar_one_or_none():
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1


async def seed_relationship_defaults(
    agent_id: uuid.UUID,
    user_id: uuid.UUID,
    language: str,
    db: AsyncSession,
):
    """
    Create default relationship types and roles for a new agent.
    Uses language-specific seeds — falls back to English for unsupported languages.
    Idempotent — safe to call multiple times.
    """
    # Check if already seeded
    result = await db.execute(
        select(RelationshipType).where(
            RelationshipType.agent_id == agent_id,
            RelationshipType.is_system_default == True,
        )
    )
    if result.scalars().first():
        return

    # Use native language seed, fall back to English
    seeds = RELATIONSHIP_SEEDS.get(language, RELATIONSHIP_SEEDS["en"])

    for (type_name, type_local, access_mode, type_sort, roles) in seeds:
        rel_type = RelationshipType(
            agent_id=agent_id,
            user_id=user_id,
            name=type_name,
            name_local=type_local,
            access_mode=access_mode,
            is_system_default=True,
            sort_order=type_sort,
        )
        db.add(rel_type)
        await db.flush()

        for (role_name, role_local, role_sort, addr_forms, self_addr_forms,
             forbidden, tone, formality, affection, openness) in roles:
            db.add(RelationshipRole(
                type_id=rel_type.id,
                agent_id=agent_id,
                user_id=user_id,
                name=role_name,
                name_local=role_local,
                is_system_default=True,
                sort_order=role_sort,
                address_forms=addr_forms,
                self_address_forms=self_addr_forms,
                forbidden_particles=forbidden,
                tone_description=tone,
                formality_level=formality,
                affection_level=affection,
                openness_level=openness,
            ))


@router.post("/register")
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email           = data.email,
        name            = data.name,
        hashed_password = hash_password(data.password),
        language        = data.language,
        gender          = data.gender,    
    )
    db.add(user)
    await db.flush()

    agent = AgentProfile(user_id=user.id, agent_name=f"{data.name}'s Agent")
    db.add(agent)
    await db.flush()

    # Generate a slug from the user's name immediately so the public URL works
    # without requiring the owner to set one manually after registration.
    base_slug = _make_slug(data.name)
    agent.slug = await _unique_slug(base_slug, db)

    db.add(AgentLifecycle(agent_id=agent.id, user_id=user.id))
    db.add(StyleProfile(
        user_id=user.id,
        agent_id=agent.id,
        language_primary=data.language,
    ))

    # Seed language-aware relationship defaults
    await seed_relationship_defaults(agent.id, user.id, data.language, db)

    await db.commit()

    token = create_access_token({"sub": str(user.id)})
    return {
        "access_token": token,
        "token_type":   "bearer",
        "user_id":      str(user.id),
        "name":         user.name,
        "language":     user.language,
        "agent_id":     str(agent.id),
    }


@router.post("/login")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    result = await db.execute(select(AgentProfile).where(AgentProfile.user_id == user.id))
    agent = result.scalar_one_or_none()

    token = create_access_token({"sub": str(user.id)})
    return {
        "access_token": token,
        "token_type":   "bearer",
        "user_id":      str(user.id),
        "name":         user.name,
        "language":     user.language,
        "agent_id":     str(agent.id) if agent else "",
    }


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {
        "id":       str(current_user.id),
        "email":    current_user.email,
        "name":     current_user.name,
        "language": current_user.language,
        "gender":   current_user.gender,
    }


# ── PATCH /auth/me ─────────────────────────────────────────────────────────

class UpdateMeRequest(BaseModel):
    email: Optional[str] = None


@router.patch("/me")
async def update_me(
    data:         UpdateMeRequest,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Update account email.
    Rejects if the email is already taken by another account.
    """
    if data.email is not None:
        email = data.email.strip().lower()

        # Basic format check
        import re as _re
        if not _re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
            raise HTTPException(status_code=400, detail="Enter a valid email address.")

        # Uniqueness check — exclude self
        result = await db.execute(
            select(User).where(User.email == email, User.id != current_user.id)
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Email is already in use.")

        current_user.email = email
        await db.commit()

    return {
        "id":    str(current_user.id),
        "email": current_user.email,
        "name":  current_user.name,
    }