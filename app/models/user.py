"""
app/models/user.py

Changes from previous version:
  RelationshipProfile — added 6 new optional fields:
    gender              : person's gender ("male" | "female" | "other")
    age                 : person's actual age (integer)
    tone_description    : optional override of role's tone_description
    forbidden_particles : optional override of role's forbidden_particles
    required_particles  : optional override of role's required_particles
    allowed_endings     : optional override of role's allowed_endings

  Rule: if person field is non-empty → use it. else fall back to role's field.
  This is enforced in chat.py _resolve_speaker_context() and public.py.

Everything else is unchanged.
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Float, Boolean, Integer,
    DateTime, Text, ForeignKey, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    language = Column(String(10), default="en")
    gender   = Column(String(20), nullable=True)
    plan           = Column(String(20),  default="tester",  nullable=False)
    souls_balance  = Column(Integer,     default=600,       nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    agents = relationship("AgentProfile", back_populates="user", cascade="all, delete-orphan")
    style_profile = relationship("StyleProfile", back_populates="user", uselist=False)
    voice_samples = relationship("VoiceSample", back_populates="user")
    personality_survey = relationship("PersonalitySurvey", back_populates="user", uselist=False)
    slang_dictionary = relationship("SlangDictionary", back_populates="user")
    language_samples = relationship("LanguageSample", back_populates="user")


class AgentProfile(Base):
    __tablename__ = "agent_profiles"
 
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    agent_name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=True, unique=True, index=True)
    total_memories = Column(Integer, default=0)
    wisdom_score = Column(Float, default=0.0)
    image_path = Column(String(500), nullable=True)          # ← NEW
    dominant_pattern_tags = Column(ARRAY(String), default=[])
    survey_completed = Column(Boolean, default=False)
    relationship_survey_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
 
    user = relationship("User", back_populates="agents")
    lifecycle = relationship("AgentLifecycle", back_populates="agent", uselist=False)
    style_profile = relationship("StyleProfile", back_populates="agent", uselist=False)
    relationship_profiles = relationship("RelationshipProfile", back_populates="agent", cascade="all, delete-orphan")
    relationship_types = relationship("RelationshipType", back_populates="agent", cascade="all, delete-orphan")


class AgentLifecycle(Base):
    __tablename__ = "agent_lifecycle"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_profiles.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    birth_date = Column(DateTime, default=datetime.utcnow)
    current_age = Column(Integer, default=0)
    interaction_count = Column(Integer, default=0)
    training_session_count = Column(Integer, default=0)
    current_wisdom_score = Column(Float, default=0.0)
    max_age_limit = Column(Integer, default=365)
    status = Column(String(50), default="living")
    generation_number = Column(Integer, default=1)
    parent_agent_id = Column(UUID(as_uuid=True), nullable=True)
    last_active_at = Column(DateTime, default=datetime.utcnow)

    agent = relationship("AgentProfile", foreign_keys=[agent_id], back_populates="lifecycle")


class StyleProfile(Base):
    __tablename__ = "style_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_profiles.id"), nullable=False, unique=True)
    avg_speaking_pace = Column(String(50), default="medium")
    avg_sentence_length = Column(Float, default=15.0)
    dominant_emotions = Column(ARRAY(String), default=[])
    humor_level = Column(Float, default=5.0)
    directness_level = Column(Float, default=5.0)
    warmth_level = Column(Float, default=5.0)
    cultural_expression_patterns = Column(JSONB, nullable=True)
    language_primary = Column(String(10), default="en")
    total_training_minutes = Column(Float, default=0.0)
    last_trained_at = Column(DateTime, nullable=True)
    voice_fingerprint = Column(JSONB, nullable=True)

    user = relationship("User", back_populates="style_profile")
    agent = relationship("AgentProfile", back_populates="style_profile")


class RelationshipType(Base):
    __tablename__ = "relationship_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_profiles.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    name_local = Column(Text, nullable=True)
    is_system_default = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)
    access_mode = Column(String(20), default="open_role", nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    agent = relationship("AgentProfile", back_populates="relationship_types")
    roles = relationship("RelationshipRole", back_populates="type", cascade="all, delete-orphan")


class RelationshipRole(Base):
    __tablename__ = "relationship_roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type_id = Column(UUID(as_uuid=True), ForeignKey("relationship_types.id"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_profiles.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    name_local = Column(Text, nullable=True)
    is_system_default = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)
    address_forms = Column(JSONB, default=[], nullable=False, server_default='[]')
    self_address_forms = Column(JSONB, default=[], nullable=False, server_default='[]')
    forbidden_particles = Column(ARRAY(Text), default=[])
    required_particles = Column(ARRAY(Text), default=[])
    allowed_endings = Column(ARRAY(Text), default=[])
    tone_description = Column(Text, nullable=True)
    openness_level = Column(Float, default=5.0)
    formality_level = Column(Float, default=5.0)
    affection_level = Column(Float, default=5.0)
    restricted_topics = Column(ARRAY(String), default=[])
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    type = relationship("RelationshipType", back_populates="roles")
    profiles = relationship("RelationshipProfile", back_populates="role", cascade="all, delete-orphan")


class RelationshipProfile(Base):
    """
    A specific known person linked to a role/pronoun group.

    Pronoun override fields (all optional):
      gender, age             → used by _pick_address_form_deterministic() when
                                the chat request doesn't supply speaker gender/age
      tone_description        → if set, overrides role.tone_description
      forbidden_particles     → if non-empty, overrides role.forbidden_particles
      required_particles      → if non-empty, overrides role.required_particles
      allowed_endings         → if non-empty, overrides role.allowed_endings

    If person fields are empty/None → system falls back to role fields.
    address_forms and self_address_forms follow the same pattern (already worked).
    """
    __tablename__ = "relationship_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_profiles.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role_id = Column(UUID(as_uuid=True), ForeignKey("relationship_roles.id"), nullable=True)

    person_name = Column(String(255), nullable=False)
    person_aliases = Column(ARRAY(String), default=[])
    person_role = Column(Text, nullable=True)
    zone = Column(Integer, default=5)
    relationship_language = Column(String(10), nullable=True)
    how_i_talk_to_them = Column(Text, nullable=True)
    chat_samples = Column(ARRAY(Text), default=[])
    address_forms = Column(JSONB, default=[], nullable=False, server_default='[]')
    self_address_forms = Column(JSONB, default=[], nullable=False, server_default='[]')
    voice_summary = Column(Text, nullable=True)
    openness_level = Column(Float, default=5.0)
    warmth_level = Column(Float, default=5.0)
    humor_level = Column(Float, default=5.0)
    formality_level = Column(Float, default=5.0)
    affection_level = Column(Float, default=5.0)
    restricted_topics = Column(ARRAY(String), default=[])
    is_active = Column(Boolean, default=True)
    is_zone_default = Column(Boolean, default=False)

    # ── Person-level pronoun overrides (NEW) ──────────────────────────────
    # All optional. If empty/None → fall back to role's equivalent field.
    # gender + age help _pick_address_form_deterministic() when the chat
    # request doesn't supply speaker_gender / speaker_age explicitly.
    gender              = Column(String(20),    nullable=True)
    age                 = Column(Integer(),     nullable=True)
    tone_description    = Column(Text,          nullable=True)
    forbidden_particles = Column(ARRAY(Text),   nullable=True, server_default="{}")
    required_particles  = Column(ARRAY(Text),   nullable=True, server_default="{}")
    allowed_endings     = Column(ARRAY(Text),   nullable=True, server_default="{}")

    # ── Public chat access key ────────────────────────────────────────────
    access_key_hash    = Column(String(255), nullable=True)
    access_key_plain   = Column(String(255), nullable=True)
    access_key_preview = Column(String(50),  nullable=True)
    access_key_enabled = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    agent = relationship("AgentProfile", back_populates="relationship_profiles")
    role  = relationship("RelationshipRole", back_populates="profiles")


class Memory(Base):
    __tablename__ = "memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_profiles.id"), nullable=False)
    session_id = Column(UUID(as_uuid=True), ForeignKey("training_sessions.id"), nullable=True)
    section = Column(String(50), nullable=False, default="PAST")
    cross_sections = Column(ARRAY(String), default=[])
    is_core_memory = Column(Boolean, default=False)
    transcript_text = Column(Text, nullable=True)
    transcript_original = Column(Text, nullable=True)
    transcript_language = Column(String(10), default="en")
    audio_file_ref = Column(String(500), nullable=True)
    what_happened = Column(Text, nullable=True)
    context = Column(Text, nullable=True)
    how_i_felt = Column(Text, nullable=True)
    why_it_mattered = Column(Text, nullable=True)
    what_i_learned = Column(Text, nullable=True)
    instinct_formed = Column(Text, nullable=True)
    cultural_expression_notes = Column(Text, nullable=True)
    what_happened_original = Column(Text, nullable=True)
    how_i_felt_original = Column(Text, nullable=True)
    why_it_mattered_original = Column(Text, nullable=True)
    what_i_learned_original = Column(Text, nullable=True)
    instinct_formed_original = Column(Text, nullable=True)
    feeling_weight = Column(Float, default=5.0)
    never_forget = Column(Boolean, default=False)
    primary_emotion = Column(String(100), nullable=True)
    secondary_emotion = Column(String(100), nullable=True)
    emotion_intensity = Column(Float, nullable=True)
    voice_pace = Column(String(50), nullable=True)
    voice_tone = Column(String(50), nullable=True)
    hesitation_moments = Column(JSONB, nullable=True)
    pattern_tags = Column(ARRAY(String), default=[])
    embedding = Column(Vector(1536), nullable=True)
    training_mode = Column(String(50), nullable=True)
    agent_age_at_capture = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_reinforced_at = Column(DateTime, nullable=True)
    reinforcement_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    agent_responses = relationship("AgentResponse", back_populates="memory")


class PatternAbstraction(Base):
    __tablename__ = "pattern_abstractions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_profiles.id"), nullable=False)
    pattern_summary = Column(Text, nullable=False)
    pattern_summary_original = Column(Text, nullable=True)
    source_memory_ids = Column(ARRAY(UUID(as_uuid=True)), default=[])
    pattern_type = Column(String(50), nullable=False)
    abstraction_weight = Column(Float, default=5.0)
    embedding = Column(Vector(1536), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class VoiceSample(Base):
    __tablename__ = "voice_samples"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    session_id = Column(UUID(as_uuid=True), ForeignKey("training_sessions.id"), nullable=True)
    audio_file_ref = Column(String(500), nullable=False)
    duration_seconds = Column(Float, nullable=False)
    language_detected = Column(String(10), nullable=True)
    elevenlabs_voice_id = Column(String(255), nullable=True)
    language_slot = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="voice_samples")


class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_profiles.id"), nullable=False)
    mode = Column(String(50), nullable=False)
    section_covered = Column(String(50), nullable=True)
    duration_minutes = Column(Float, default=0.0)
    memories_captured = Column(Integer, default=0)
    avg_weight_of_session = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentResponse(Base):
    __tablename__ = "agent_responses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_profiles.id"), nullable=False)
    memory_id = Column(UUID(as_uuid=True), ForeignKey("memories.id"), nullable=True)
    source_memory_ids = Column(ARRAY(UUID(as_uuid=True)), default=[])
    response_text = Column(Text, nullable=False)
    question_text = Column(Text, nullable=True)
    speaker_name = Column(String(255), nullable=True)
    session_key = Column(String(255), nullable=True)
    response_type = Column(String(100), nullable=False)
    response_language = Column(String(10), nullable=True)
    user_feedback = Column(String(50), nullable=True)
    correction_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    memory = relationship("Memory", back_populates="agent_responses")


class WisdomInheritance(Base):
    __tablename__ = "wisdom_inheritance"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_profiles.id"), nullable=False)
    to_agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_profiles.id"), nullable=False)
    inherited_patterns = Column(ARRAY(UUID(as_uuid=True)), default=[])
    inherited_at = Column(DateTime, default=datetime.utcnow)
    generation_number = Column(Integer, nullable=False)


class AgentAccess(Base):
    __tablename__ = "agent_access"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_profiles.id"), nullable=False)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    granted_to_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    access_level = Column(String(50), default="view")
    granted_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    agent = relationship("AgentProfile", foreign_keys=[agent_id])
    owner = relationship("User", foreign_keys=[owner_user_id])
    granted_to = relationship("User", foreign_keys=[granted_to_user_id])


class SlangDictionary(Base):
    __tablename__ = "slang_dictionary"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_profiles.id"), nullable=False)
    word_or_phrase = Column(String(255), nullable=False)
    meanings = Column(ARRAY(Text), default=[])
    example_sentences = Column(ARRAY(Text), default=[])
    grammar_note = Column(Text, nullable=True)
    usage_context = Column(Text, nullable=True)
    language = Column(String(10), nullable=False)
    relationship_zone = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="slang_dictionary")


class PersonalitySurvey(Base):
    __tablename__ = "personality_survey"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    agent_id   = Column(UUID(as_uuid=True), ForeignKey("agent_profiles.id"), nullable=False, unique=True)
    full_name        = Column(Text, nullable=True)
    age              = Column(Integer, nullable=True)
    birthdate        = Column(String(50), nullable=True)
    blood_type       = Column(String(10), nullable=True)
    zodiac_sign      = Column(String(50), nullable=True)
    current_location = Column(Text, nullable=True)
    past_locations   = Column(ARRAY(Text), default=[])
    onboarding_step  = Column(String(50), default="survey", nullable=False)
    identity_summary = Column(Text, nullable=True)
    is_completed     = Column(Boolean, default=False)
    completed_at     = Column(DateTime, nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow)
    updated_at       = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="personality_survey")


class LanguageSample(Base):
    __tablename__ = "language_samples"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_profiles.id"), nullable=False)
    language = Column(String(10), nullable=False)
    sample_text = Column(Text, nullable=False)
    relationship_zone = Column(Integer, nullable=True)
    source = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="language_samples")

class NeoPackage(Base):
    __tablename__ = "neo_packages"
 
    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id     = Column(UUID(as_uuid=True), ForeignKey("agent_profiles.id"), nullable=False)
    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
 
    # Package identity
    package_type         = Column(String(20), nullable=False)   # "system" | "custom"
    package_key          = Column(String(100), nullable=True)   # "life_coach" | "politician" | None for custom
    title                = Column(String(255), nullable=False)
    description          = Column(Text, nullable=True)
    slot_number          = Column(Integer, nullable=False)       # 1–4
 
    # Content
    custom_instructions  = Column(Text, nullable=True)          # owner additions / full custom content
    domain_tags          = Column(ARRAY(String), default=[])    # for query relevance matching
    neo_mode_disclaimer  = Column(Text, nullable=True)          # auto-injected for sensitive domains
 
    # Custom package only
    char_count           = Column(Integer, nullable=True)       # tracks size for custom packages
 
    # State
    is_active            = Column(Boolean, default=True)
    is_publishable       = Column(Boolean, default=False)       # future marketplace — don't build yet
    installed_at         = Column(DateTime, default=datetime.utcnow)
    updated_at           = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SoulsTransaction(Base):
    """
    Immutable ledger of every souls movement.
    Never update rows — only insert.
 
    reason values:
      "signup_tester"     — 600 Souls granted on register (tester plan)
      "signup_paid"       — 1000 Souls granted on paid plan activation
      "refill_pack"       — 1,000 Souls purchased ($12)
      "training_submit"   — deducted on training submit (~29 Souls)
      "chat_message_en"   — deducted on EN chat message (~47 Souls)
      "chat_message_intl" — deducted on MY/TH/KO chat message (~55 Souls)
      "admin_grant"       — manual grant by admin
      "refund"            — manual refund
    """
    __tablename__ = "souls_transactions"
 
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    amount     = Column(Integer, nullable=False)          # positive = credit, negative = debit
    reason     = Column(String(50), nullable=False)
    balance_after = Column(Integer, nullable=False)       # snapshot after transaction
    meta       = Column(JSONB, nullable=True)             # extra context: session_key, language, etc.
    created_at = Column(DateTime, default=datetime.utcnow, index=True)