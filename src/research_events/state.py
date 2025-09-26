from pydantic import BaseModel, Field


class CategoriesWithEvents(BaseModel):
    early: str = Field(
        default="",
        description="Covers childhood, upbringing, family, education, and early influences that shaped the author.",
    )
    personal: str = Field(
        default="",
        description="Focuses on relationships, friendships, family life, places of residence, and notable personal traits or beliefs.",
    )
    career: str = Field(
        default="",
        description="Details their professional journey: first steps into writing, major publications, collaborations, recurring themes, style, and significant milestones.",
    )
    legacy: str = Field(
        default="",
        description="Explains how their work was received, awards or recognition, cultural/literary impact, influence on other authors, and how they are remembered today.",
    )
