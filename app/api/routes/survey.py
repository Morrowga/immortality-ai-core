"""
app/api/routes/survey.py

Completely rebuilt from the old 900-line version.

Old: 14-section personality questionnaire, LLM personality extraction,
     memory generation from survey answers, language sample saving.

New: Simple identity form (name, age, birthday, blood type, zodiac,
     locations). No LLM calls. No memory generation from survey.
     Survey just anchors who the person is — personality comes from training.

Flow after submit:
  1. Survey saved → onboarding_step = "pronoun_setup"
  2. Frontend shows pronoun/relationship setup screen
  3. User sets address forms for their roles
  4. onboarding_step → "ready"
  5. User can now train and chat
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.db.session import get_db
from app.models.user import User, AgentProfile, PersonalitySurvey
from app.core.security import get_current_user
from app.services.survey import build_identity_summary

router = APIRouter()


# ── Request / Response schemas ─────────────────────────────────────────────

class SurveySubmitRequest(BaseModel):
    full_name: str
    age: Optional[int] = None
    birthdate: Optional[str] = None        # "15 March 1990" or ISO
    blood_type: Optional[str] = None       # A / B / AB / O / None
    zodiac_sign: Optional[str] = None
    current_location: Optional[str] = None
    past_locations: Optional[list[str]] = []


class OnboardingStepRequest(BaseModel):
    step: str   # "pronoun_setup" | "ready"


# ── Routes ─────────────────────────────────────────────────────────────────

@router.get("/questions")
async def get_survey_questions():
    """
    Returns the identity form fields for the frontend to render.
    Kept as a route so the frontend stays data-driven.
    """
    return {
        "sections": [
            {
                "id": "identity",
                "title": "Tell us about yourself",
                "subtitle": "This is how your agent knows who you are. Your personality, memories, and voice are built through training.",
                "questions": [
                    {
                        "id": "full_name",
                        "text": "What is your full name?",
                        "type": "free_text",
                        "required": True,
                        "placeholder": "e.g. Ko Aung Kyaw",
                    },
                    {
                        "id": "age",
                        "text": "How old are you?",
                        "type": "number",
                        "required": False,
                        "placeholder": "e.g. 28",
                    },
                    {
                        "id": "birthdate",
                        "text": "Date of birth",
                        "type": "free_text",
                        "required": False,
                        "placeholder": "e.g. 15 March 1995",
                    },
                    {
                        "id": "blood_type",
                        "text": "Blood type",
                        "type": "choice",
                        "required": False,
                        "options": ["A", "B", "AB", "O", "I don't know"],
                    },
                    {
                        "id": "zodiac_sign",
                        "text": "Zodiac sign",
                        "type": "choice",
                        "required": False,
                        "options": [
                            "Aries", "Taurus", "Gemini", "Cancer",
                            "Leo", "Virgo", "Libra", "Scorpio",
                            "Sagittarius", "Capricorn", "Aquarius", "Pisces",
                        ],
                    },
                    {
                        "id": "current_location",
                        "text": "Where do you live now?",
                        "type": "free_text",
                        "required": False,
                        "placeholder": "e.g. Yangon, Myanmar",
                    },
                    {
                        "id": "past_locations",
                        "text": "Where have you lived before? (optional — add as many as you want)",
                        "type": "multi_text",
                        "required": False,
                        "placeholder": "e.g. Mandalay 2000–2015",
                        "hint": "Add each place on a separate line or press Enter after each one",
                    },
                ],
            }
        ],
        "onboarding_next": {
            "step": "pronoun_setup",
            "title": "Set up how your agent speaks",
            "body": "Before training, tell your agent how to address people in your life — your mother, your friends, strangers. This is especially important for languages like Burmese and Thai where address forms carry deep meaning.",
        },
    }


@router.post("/submit")
async def submit_survey(
    data: SurveySubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Save identity survey. No LLM calls, no memory generation.
    Sets onboarding_step → 'pronoun_setup'.
    The frontend should show the pronoun setup screen after this.
    """
    if not data.full_name or not data.full_name.strip():
        raise HTTPException(status_code=400, detail="full_name is required")

    result = await db.execute(
        select(AgentProfile).where(AgentProfile.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Build the identity summary that goes into the agent system prompt
    identity_summary = build_identity_summary(
        full_name=data.full_name.strip(),
        age=data.age,
        birthdate=data.birthdate,
        blood_type=data.blood_type,
        zodiac_sign=data.zodiac_sign,
        current_location=data.current_location,
        past_locations=data.past_locations or [],
        language=current_user.language,
    )

    # Upsert survey row
    result = await db.execute(
        select(PersonalitySurvey).where(PersonalitySurvey.user_id == current_user.id)
    )
    survey = result.scalar_one_or_none()

    if survey:
        survey.full_name        = data.full_name.strip()
        survey.age              = data.age
        survey.birthdate        = data.birthdate
        survey.blood_type       = data.blood_type
        survey.zodiac_sign      = data.zodiac_sign
        survey.current_location = data.current_location
        survey.past_locations   = data.past_locations or []
        survey.identity_summary = identity_summary
        survey.is_completed     = True
        survey.completed_at     = datetime.utcnow()
        survey.onboarding_step  = "pronoun_setup"
        survey.updated_at       = datetime.utcnow()
    else:
        survey = PersonalitySurvey(
            user_id         = current_user.id,
            agent_id        = agent.id,
            full_name       = data.full_name.strip(),
            age             = data.age,
            birthdate       = data.birthdate,
            blood_type      = data.blood_type,
            zodiac_sign     = data.zodiac_sign,
            current_location = data.current_location,
            past_locations  = data.past_locations or [],
            identity_summary = identity_summary,
            is_completed    = True,
            completed_at    = datetime.utcnow(),
            onboarding_step = "pronoun_setup",
        )
        db.add(survey)

    # Mark agent survey as completed
    agent.survey_completed = True

    await db.commit()

    return {
        "message": "Identity saved.",
        "onboarding_step": "pronoun_setup",
        "next_screen": {
            "title": "Set up how your agent speaks",
            "body": "Before training, set up the address forms and pronouns for the people in your life. Your agent will follow these exactly when speaking to them.",
            "action": "Go to Pronoun Setup",
            "route": "/setup/pronouns",
        },
        "identity_summary": identity_summary,
    }


@router.post("/onboarding-step")
async def update_onboarding_step(
    data: OnboardingStepRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Called by the frontend when the user completes a setup step.

    Valid transitions:
      pronoun_setup → ready   (user finishes pronoun/relationship setup)

    'ready' means the user can now train and chat.
    The frontend should skip the setup screens and go straight to training
    once onboarding_step == 'ready'.
    """
    valid_steps = {"pronoun_setup", "ready"}
    if data.step not in valid_steps:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid step. Must be one of: {', '.join(valid_steps)}"
        )

    result = await db.execute(
        select(PersonalitySurvey).where(PersonalitySurvey.user_id == current_user.id)
    )
    survey = result.scalar_one_or_none()
    if not survey:
        raise HTTPException(
            status_code=404,
            detail="Complete the identity survey first."
        )

    if not survey.is_completed:
        raise HTTPException(
            status_code=400,
            detail="Complete the identity survey before advancing."
        )

    # Enforce forward-only transitions
    step_order = {"survey": 0, "pronoun_setup": 1, "ready": 2}
    current_order = step_order.get(survey.onboarding_step, 0)
    new_order = step_order.get(data.step, 0)
    if new_order <= current_order:
        # Already at this step or past it — idempotent, just return current state
        return {"onboarding_step": survey.onboarding_step}

    survey.onboarding_step = data.step
    survey.updated_at = datetime.utcnow()
    await db.commit()

    # When user marks themselves ready, return training guidance
    next_screen = None
    if data.step == "ready":
        next_screen = {
            "title": "Your agent is ready to learn",
            "body": "Start sharing your memories, stories, and experiences. The more you train, the more your agent becomes you.",
            "action": "Start Training",
            "route": "/training",
        }

    return {
        "onboarding_step": data.step,
        "next_screen": next_screen,
    }


@router.get("/me")
async def get_my_survey(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns current survey state and onboarding step.
    Frontend uses onboarding_step to decide which screen to show:
      "survey"        → show identity form
      "pronoun_setup" → show pronoun/relationship setup
      "ready"         → show training / chat
    """
    result = await db.execute(
        select(PersonalitySurvey).where(PersonalitySurvey.user_id == current_user.id)
    )
    survey = result.scalar_one_or_none()

    if not survey or not survey.is_completed:
        return {
            "is_completed": False,
            "onboarding_step": "survey",
            "identity": None,
        }

    return {
        "is_completed": True,
        "onboarding_step": survey.onboarding_step,
        "identity": {
            "full_name":        survey.full_name,
            "age":              survey.age,
            "birthdate":        survey.birthdate,
            "blood_type":       survey.blood_type,
            "zodiac_sign":      survey.zodiac_sign,
            "current_location": survey.current_location,
            "past_locations":   survey.past_locations or [],
        },
        "identity_summary": survey.identity_summary,
        "completed_at": survey.completed_at.isoformat() if survey.completed_at else None,
    }


@router.patch("/me")
async def update_survey(
    data: SurveySubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update identity info after initial submission.
    Rebuilds the identity_summary automatically.
    Does NOT reset onboarding_step.
    """
    result = await db.execute(
        select(PersonalitySurvey).where(PersonalitySurvey.user_id == current_user.id)
    )
    survey = result.scalar_one_or_none()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found. Submit first.")

    survey.full_name        = data.full_name.strip() if data.full_name else survey.full_name
    survey.age              = data.age              if data.age is not None else survey.age
    survey.birthdate        = data.birthdate        if data.birthdate else survey.birthdate
    survey.blood_type       = data.blood_type       if data.blood_type else survey.blood_type
    survey.zodiac_sign      = data.zodiac_sign      if data.zodiac_sign else survey.zodiac_sign
    survey.current_location = data.current_location if data.current_location else survey.current_location
    survey.past_locations   = data.past_locations   if data.past_locations is not None else survey.past_locations

    # Rebuild summary with updated values
    survey.identity_summary = build_identity_summary(
        full_name        = survey.full_name,
        age              = survey.age,
        birthdate        = survey.birthdate,
        blood_type       = survey.blood_type,
        zodiac_sign      = survey.zodiac_sign,
        current_location = survey.current_location,
        past_locations   = survey.past_locations or [],
        language         = current_user.language,
    )
    survey.updated_at = datetime.utcnow()

    await db.commit()

    return {
        "message": "Identity updated.",
        "identity_summary": survey.identity_summary,
    }