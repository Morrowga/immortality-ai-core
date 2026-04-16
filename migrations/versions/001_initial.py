"""initial schema — complete

Revision ID: 001_init
Revises:
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.dialects.postgresql import ARRAY
from pgvector.sqlalchemy import Vector

revision = '001_init'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # ── users ──────────────────────────────────────────────────────────────
    op.create_table('users',
        sa.Column('id',              UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('email',           sa.String(255), nullable=False, unique=True),
        sa.Column('name',            sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('language',        sa.String(10),  server_default='en'),
        sa.Column('gender',          sa.String(20),  nullable=True),
        sa.Column('plan',            sa.String(20),  nullable=False, server_default='tester'),
        sa.Column('souls_balance',   sa.Integer(),   nullable=False, server_default='600'),
        sa.Column('created_at',      sa.DateTime,    server_default=sa.text('NOW()')),
        sa.Column('updated_at',      sa.DateTime,    server_default=sa.text('NOW()')),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # ── agent_profiles ─────────────────────────────────────────────────────
    op.create_table('agent_profiles',
        sa.Column('id',                        UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id',                   UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('agent_name',                sa.String(255), nullable=False),
        sa.Column('slug',                      sa.String(100), nullable=True, unique=True),
        sa.Column('total_memories',            sa.Integer,  server_default='0'),
        sa.Column('wisdom_score',              sa.Float,    server_default='0.0'),
        sa.Column('image_path',                sa.String(500), nullable=True),
        sa.Column('dominant_pattern_tags',     ARRAY(sa.String), server_default='{}'),
        sa.Column('survey_completed',          sa.Boolean,  server_default='false'),
        sa.Column('relationship_survey_completed', sa.Boolean, server_default='false'),
        sa.Column('created_at',                sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('last_updated_at',           sa.DateTime, server_default=sa.text('NOW()')),
    )

    # ── agent_lifecycle ────────────────────────────────────────────────────
    op.create_table('agent_lifecycle',
        sa.Column('id',                     UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('agent_id',               UUID(as_uuid=True), sa.ForeignKey('agent_profiles.id'), nullable=False),
        sa.Column('user_id',                UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('birth_date',             sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('current_age',            sa.Integer,  server_default='0'),
        sa.Column('interaction_count',      sa.Integer,  server_default='0'),
        sa.Column('training_session_count', sa.Integer,  server_default='0'),
        sa.Column('current_wisdom_score',   sa.Float,    server_default='0.0'),
        sa.Column('max_age_limit',          sa.Integer,  server_default='365'),
        sa.Column('status',                 sa.String(50), server_default='living'),
        sa.Column('generation_number',      sa.Integer,  server_default='1'),
        sa.Column('parent_agent_id',        UUID(as_uuid=True), nullable=True),
        sa.Column('last_active_at',         sa.DateTime, server_default=sa.text('NOW()')),
    )

    # ── style_profiles ─────────────────────────────────────────────────────
    op.create_table('style_profiles',
        sa.Column('id',                           UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id',                      UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('agent_id',                     UUID(as_uuid=True), sa.ForeignKey('agent_profiles.id'), nullable=False, unique=True),
        sa.Column('avg_speaking_pace',            sa.String(50), server_default='medium'),
        sa.Column('avg_sentence_length',          sa.Float, server_default='15.0'),
        sa.Column('dominant_emotions',            ARRAY(sa.String), server_default='{}'),
        sa.Column('humor_level',                  sa.Float, server_default='5.0'),
        sa.Column('directness_level',             sa.Float, server_default='5.0'),
        sa.Column('warmth_level',                 sa.Float, server_default='5.0'),
        sa.Column('cultural_expression_patterns', JSONB, nullable=True),
        sa.Column('language_primary',             sa.String(10), server_default='en'),
        sa.Column('total_training_minutes',       sa.Float, server_default='0.0'),
        sa.Column('last_trained_at',              sa.DateTime, nullable=True),
        sa.Column('voice_fingerprint',            JSONB, nullable=True),
    )

    # ── training_sessions ──────────────────────────────────────────────────
    op.create_table('training_sessions',
        sa.Column('id',                    UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id',               UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('agent_id',              UUID(as_uuid=True), sa.ForeignKey('agent_profiles.id'), nullable=False),
        sa.Column('mode',                  sa.String(50), nullable=False),
        sa.Column('section_covered',       sa.String(50), nullable=True),
        sa.Column('duration_minutes',      sa.Float, server_default='0.0'),
        sa.Column('memories_captured',     sa.Integer, server_default='0'),
        sa.Column('avg_weight_of_session', sa.Float, server_default='0.0'),
        sa.Column('created_at',            sa.DateTime, server_default=sa.text('NOW()')),
    )

    # ── memories ───────────────────────────────────────────────────────────
    op.create_table('memories',
        sa.Column('id',         UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id',    UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('agent_id',   UUID(as_uuid=True), sa.ForeignKey('agent_profiles.id'), nullable=False),
        sa.Column('session_id', UUID(as_uuid=True), sa.ForeignKey('training_sessions.id'), nullable=True),
        sa.Column('section',        sa.String(50), nullable=False),
        sa.Column('cross_sections', ARRAY(sa.String), server_default='{}'),
        sa.Column('is_core_memory', sa.Boolean, server_default='false'),
        # encrypted text columns — stored as TEXT, encrypted at app level
        sa.Column('transcript_text',              sa.Text, nullable=True),
        sa.Column('transcript_original',          sa.Text, nullable=True),
        sa.Column('transcript_language',          sa.String(10), server_default='en'),
        sa.Column('audio_file_ref',               sa.String(500), nullable=True),
        sa.Column('what_happened',                sa.Text, nullable=True),
        sa.Column('context',                      sa.Text, nullable=True),
        sa.Column('how_i_felt',                   sa.Text, nullable=True),
        sa.Column('why_it_mattered',              sa.Text, nullable=True),
        sa.Column('what_i_learned',               sa.Text, nullable=True),
        sa.Column('instinct_formed',              sa.Text, nullable=True),
        sa.Column('cultural_expression_notes',    sa.Text, nullable=True),
        sa.Column('what_happened_original',       sa.Text, nullable=True),
        sa.Column('how_i_felt_original',          sa.Text, nullable=True),
        sa.Column('why_it_mattered_original',     sa.Text, nullable=True),
        sa.Column('what_i_learned_original',      sa.Text, nullable=True),
        sa.Column('instinct_formed_original',     sa.Text, nullable=True),
        sa.Column('feeling_weight',       sa.Float, server_default='5.0'),
        sa.Column('never_forget',         sa.Boolean, server_default='false'),
        sa.Column('primary_emotion',      sa.String(100), nullable=True),
        sa.Column('secondary_emotion',    sa.String(100), nullable=True),
        sa.Column('emotion_intensity',    sa.Float, nullable=True),
        sa.Column('voice_pace',           sa.String(50), nullable=True),
        sa.Column('voice_tone',           sa.String(50), nullable=True),
        sa.Column('hesitation_moments',   JSONB, nullable=True),
        sa.Column('pattern_tags',         ARRAY(sa.String), server_default='{}'),
        sa.Column('embedding',            Vector(1536), nullable=True),
        sa.Column('training_mode',        sa.String(50), nullable=True),
        sa.Column('agent_age_at_capture', sa.Integer, server_default='0'),
        sa.Column('created_at',           sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('last_reinforced_at',   sa.DateTime, nullable=True),
        sa.Column('reinforcement_count',  sa.Integer, server_default='0'),
        sa.Column('is_active',            sa.Boolean, server_default='true'),
    )

    # ── relationship_types ─────────────────────────────────────────────────
    op.create_table('relationship_types',
        sa.Column('id',               UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('agent_id',         UUID(as_uuid=True), sa.ForeignKey('agent_profiles.id'), nullable=False),
        sa.Column('user_id',          UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('name',             sa.String(100), nullable=False),
        sa.Column('name_local',       sa.Text, nullable=True),
        sa.Column('is_system_default',sa.Boolean, server_default='false'),
        sa.Column('sort_order',       sa.Integer, server_default='0'),
        sa.Column('access_mode',      sa.String(20), nullable=False, server_default='open_role'),
        sa.Column('is_active',        sa.Boolean, server_default='true'),
        sa.Column('created_at',       sa.DateTime, server_default=sa.text('NOW()')),
    )

    # ── relationship_roles ─────────────────────────────────────────────────
    op.create_table('relationship_roles',
        sa.Column('id',                  UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('type_id',             UUID(as_uuid=True), sa.ForeignKey('relationship_types.id'), nullable=False),
        sa.Column('agent_id',            UUID(as_uuid=True), sa.ForeignKey('agent_profiles.id'), nullable=False),
        sa.Column('user_id',             UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('name',                sa.String(100), nullable=False),
        sa.Column('name_local',          sa.Text, nullable=True),
        sa.Column('is_system_default',   sa.Boolean, server_default='false'),
        sa.Column('sort_order',          sa.Integer, server_default='0'),
        sa.Column('address_forms',       JSONB, nullable=False, server_default='[]'),
        sa.Column('self_address_forms',  JSONB, nullable=False, server_default='[]'),
        sa.Column('forbidden_particles', ARRAY(sa.Text), server_default='{}'),
        sa.Column('required_particles',  ARRAY(sa.Text), server_default='{}'),
        sa.Column('allowed_endings',     ARRAY(sa.Text), server_default='{}'),
        sa.Column('tone_description',    sa.Text, nullable=True),
        sa.Column('openness_level',      sa.Float, server_default='5.0'),
        sa.Column('formality_level',     sa.Float, server_default='5.0'),
        sa.Column('affection_level',     sa.Float, server_default='5.0'),
        sa.Column('restricted_topics',   ARRAY(sa.String), server_default='{}'),
        sa.Column('is_active',           sa.Boolean, server_default='true'),
        sa.Column('created_at',          sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at',          sa.DateTime, server_default=sa.text('NOW()')),
    )

    # ── relationship_profiles ──────────────────────────────────────────────
    op.create_table('relationship_profiles',
        sa.Column('id',                   UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('agent_id',             UUID(as_uuid=True), sa.ForeignKey('agent_profiles.id'), nullable=False),
        sa.Column('user_id',              UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('role_id',              UUID(as_uuid=True), sa.ForeignKey('relationship_roles.id'), nullable=True),
        sa.Column('person_name',          sa.String(255), nullable=False),
        sa.Column('person_aliases',       ARRAY(sa.String), server_default='{}'),
        sa.Column('person_role',          sa.Text, nullable=True),
        sa.Column('zone',                 sa.Integer, nullable=True),
        sa.Column('relationship_language',sa.String(10), nullable=True),
        sa.Column('how_i_talk_to_them',   sa.Text, nullable=True),
        sa.Column('chat_samples',         ARRAY(sa.Text), server_default='{}'),
        sa.Column('address_forms',        JSONB, nullable=False, server_default='[]'),
        sa.Column('self_address_forms',   JSONB, nullable=False, server_default='[]'),
        sa.Column('voice_summary',        sa.Text, nullable=True),
        sa.Column('openness_level',       sa.Float, server_default='5.0'),
        sa.Column('warmth_level',         sa.Float, server_default='5.0'),
        sa.Column('humor_level',          sa.Float, server_default='5.0'),
        sa.Column('formality_level',      sa.Float, server_default='5.0'),
        sa.Column('affection_level',      sa.Float, server_default='5.0'),
        sa.Column('restricted_topics',    ARRAY(sa.String), server_default='{}'),
        sa.Column('is_active',            sa.Boolean, server_default='true'),
        sa.Column('is_zone_default',      sa.Boolean, server_default='false'),
        sa.Column('gender',               sa.String(20), nullable=True),
        sa.Column('age',                  sa.Integer, nullable=True),
        sa.Column('tone_description',     sa.Text, nullable=True),
        sa.Column('forbidden_particles',  ARRAY(sa.Text), server_default='{}'),
        sa.Column('required_particles',   ARRAY(sa.Text), server_default='{}'),
        sa.Column('allowed_endings',      ARRAY(sa.Text), server_default='{}'),
        sa.Column('access_key_hash',      sa.String(255), nullable=True),
        sa.Column('access_key_plain',     sa.String(255), nullable=True),
        sa.Column('access_key_preview',   sa.String(50), nullable=True),
        sa.Column('access_key_enabled',   sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at',           sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at',           sa.DateTime, server_default=sa.text('NOW()')),
    )

    # ── agent_responses ────────────────────────────────────────────────────
    op.create_table('agent_responses',
        sa.Column('id',              UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id',         UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('agent_id',        UUID(as_uuid=True), sa.ForeignKey('agent_profiles.id'), nullable=False),
        sa.Column('memory_id',       UUID(as_uuid=True), sa.ForeignKey('memories.id'), nullable=True),
        sa.Column('source_memory_ids', ARRAY(UUID(as_uuid=True)), server_default='{}'),
        sa.Column('response_text',   sa.Text, nullable=False),
        sa.Column('question_text',   sa.Text, nullable=True),
        sa.Column('speaker_name',    sa.String(255), nullable=True),
        sa.Column('session_key',     sa.String(255), nullable=True),
        sa.Column('response_type',   sa.String(100), nullable=False),
        sa.Column('response_language', sa.String(10), nullable=True),
        sa.Column('user_feedback',   sa.String(50), nullable=True),
        sa.Column('correction_text', sa.Text, nullable=True),
        sa.Column('created_at',      sa.DateTime, server_default=sa.text('NOW()')),
    )

    # ── pattern_abstractions ───────────────────────────────────────────────
    op.create_table('pattern_abstractions',
        sa.Column('id',                       UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('agent_id',                 UUID(as_uuid=True), sa.ForeignKey('agent_profiles.id'), nullable=False),
        sa.Column('pattern_summary',          sa.Text, nullable=False),
        sa.Column('pattern_summary_original', sa.Text, nullable=True),
        sa.Column('source_memory_ids',        ARRAY(UUID(as_uuid=True)), server_default='{}'),
        sa.Column('pattern_type',             sa.String(50), nullable=False),
        sa.Column('abstraction_weight',       sa.Float, server_default='5.0'),
        sa.Column('embedding',                Vector(1536), nullable=True),
        sa.Column('created_at',               sa.DateTime, server_default=sa.text('NOW()')),
    )

    # ── voice_samples ──────────────────────────────────────────────────────
    op.create_table('voice_samples',
        sa.Column('id',                  UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id',             UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('session_id',          UUID(as_uuid=True), sa.ForeignKey('training_sessions.id'), nullable=True),
        sa.Column('audio_file_ref',      sa.String(500), nullable=False),
        sa.Column('duration_seconds',    sa.Float, nullable=False),
        sa.Column('language_detected',   sa.String(10), nullable=True),
        sa.Column('elevenlabs_voice_id', sa.String(255), nullable=True),
        sa.Column('language_slot',       sa.String(10), nullable=True),
        sa.Column('created_at',          sa.DateTime, server_default=sa.text('NOW()')),
    )

    # ── wisdom_inheritance ─────────────────────────────────────────────────
    op.create_table('wisdom_inheritance',
        sa.Column('id',                 UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('from_agent_id',      UUID(as_uuid=True), sa.ForeignKey('agent_profiles.id'), nullable=False),
        sa.Column('to_agent_id',        UUID(as_uuid=True), sa.ForeignKey('agent_profiles.id'), nullable=False),
        sa.Column('inherited_patterns', ARRAY(UUID(as_uuid=True)), server_default='{}'),
        sa.Column('inherited_at',       sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('generation_number',  sa.Integer, nullable=False),
    )

    # ── agent_access ───────────────────────────────────────────────────────
    op.create_table('agent_access',
        sa.Column('id',                 UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('agent_id',           UUID(as_uuid=True), sa.ForeignKey('agent_profiles.id'), nullable=False),
        sa.Column('owner_user_id',      UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('granted_to_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('access_level',       sa.String(50), server_default='view'),
        sa.Column('granted_at',         sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('expires_at',         sa.DateTime, nullable=True),
    )

    # ── slang_dictionary ───────────────────────────────────────────────────
    op.create_table('slang_dictionary',
        sa.Column('id',               UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id',          UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('agent_id',         UUID(as_uuid=True), sa.ForeignKey('agent_profiles.id'), nullable=False),
        sa.Column('word_or_phrase',   sa.String(255), nullable=False),
        sa.Column('meanings',         ARRAY(sa.Text), server_default='{}'),
        sa.Column('example_sentences',ARRAY(sa.Text), server_default='{}'),
        sa.Column('grammar_note',     sa.Text, nullable=True),
        sa.Column('usage_context',    sa.Text, nullable=True),
        sa.Column('language',         sa.String(10), nullable=False),
        sa.Column('relationship_zone',sa.Integer, nullable=True),
        sa.Column('is_active',        sa.Boolean, server_default='true'),
        sa.Column('created_at',       sa.DateTime, server_default=sa.text('NOW()')),
    )

    # ── personality_survey ─────────────────────────────────────────────────
    op.create_table('personality_survey',
        sa.Column('id',               UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id',          UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False, unique=True),
        sa.Column('agent_id',         UUID(as_uuid=True), sa.ForeignKey('agent_profiles.id'), nullable=False, unique=True),
        sa.Column('full_name',        sa.Text, nullable=True),
        sa.Column('age',              sa.Integer, nullable=True),
        sa.Column('birthdate',        sa.String(50), nullable=True),
        sa.Column('blood_type',       sa.String(10), nullable=True),
        sa.Column('zodiac_sign',      sa.String(50), nullable=True),
        sa.Column('current_location', sa.Text, nullable=True),
        sa.Column('past_locations',   ARRAY(sa.Text), nullable=True),
        sa.Column('onboarding_step',  sa.String(50), nullable=False, server_default='survey'),
        sa.Column('identity_summary', sa.Text, nullable=True),
        sa.Column('is_completed',     sa.Boolean, server_default='false'),
        sa.Column('completed_at',     sa.DateTime, nullable=True),
        sa.Column('created_at',       sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at',       sa.DateTime, server_default=sa.text('NOW()')),
    )

    # ── language_samples ───────────────────────────────────────────────────
    op.create_table('language_samples',
        sa.Column('id',               UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id',          UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('agent_id',         UUID(as_uuid=True), sa.ForeignKey('agent_profiles.id'), nullable=False),
        sa.Column('language',         sa.String(10), nullable=False),
        sa.Column('sample_text',      sa.Text, nullable=False),
        sa.Column('relationship_zone',sa.Integer, nullable=True),
        sa.Column('source',           sa.String(50), nullable=True),
        sa.Column('created_at',       sa.DateTime, server_default=sa.text('NOW()')),
    )

    # ── neo_packages ───────────────────────────────────────────────────────
    op.create_table('neo_packages',
        sa.Column('id',                  UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('agent_id',            UUID(as_uuid=True), sa.ForeignKey('agent_profiles.id'), nullable=False),
        sa.Column('user_id',             UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('package_type',        sa.String(20), nullable=False),
        sa.Column('package_key',         sa.String(100), nullable=True),
        sa.Column('title',               sa.String(255), nullable=False),
        sa.Column('description',         sa.Text, nullable=True),
        sa.Column('slot_number',         sa.Integer, nullable=False),
        sa.Column('custom_instructions', sa.Text, nullable=True),
        sa.Column('domain_tags',         ARRAY(sa.String), server_default='{}'),
        sa.Column('neo_mode_disclaimer', sa.Text, nullable=True),
        sa.Column('char_count',          sa.Integer, nullable=True),
        sa.Column('is_active',           sa.Boolean, server_default='true'),
        sa.Column('is_publishable',      sa.Boolean, server_default='false'),
        sa.Column('installed_at',        sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at',          sa.DateTime, server_default=sa.text('NOW()')),
    )

    # ── souls_transactions ─────────────────────────────────────────────────
    op.create_table('souls_transactions',
        sa.Column('id',            UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id',       UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('amount',        sa.Integer(), nullable=False),
        sa.Column('reason',        sa.String(50), nullable=False),
        sa.Column('balance_after', sa.Integer(), nullable=False),
        sa.Column('meta',          JSONB, nullable=True),
        sa.Column('created_at',    sa.DateTime, server_default=sa.text('NOW()')),
    )
    op.create_index('ix_souls_transactions_user_id',    'souls_transactions', ['user_id'])
    op.create_index('ix_souls_transactions_created_at', 'souls_transactions', ['created_at'])


def downgrade():
    op.drop_table('souls_transactions')
    op.drop_table('neo_packages')
    op.drop_table('language_samples')
    op.drop_table('personality_survey')
    op.drop_table('slang_dictionary')
    op.drop_table('agent_access')
    op.drop_table('wisdom_inheritance')
    op.drop_table('voice_samples')
    op.drop_table('pattern_abstractions')
    op.drop_table('agent_responses')
    op.drop_table('relationship_profiles')
    op.drop_table('relationship_roles')
    op.drop_table('relationship_types')
    op.drop_table('memories')
    op.drop_table('training_sessions')
    op.drop_table('style_profiles')
    op.drop_table('agent_lifecycle')
    op.drop_table('agent_profiles')
    op.drop_table('users')