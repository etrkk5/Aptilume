"""Answer-level triage. Cases are provisional and require an explicit HR decision."""

import re
import unicodedata
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field


class QualityOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    category: Literal[
        "relevant",
        "no_experience",
        "nonsensical",
        "off_topic",
        "insufficient_content",
        "instruction_attempt",
    ]
    reason: str = Field(min_length=1, max_length=1000)
    evidence_quotes: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(
        max_length=3
    )


def readable_text(text):
    return "".join(
        c for c in text if unicodedata.category(c) not in {"Cf", "Cc"} or c in "\n\t"
    ).strip()


def explicit_no_experience(text):
    value = readable_text(text).casefold().strip(".! ")
    return value in {
        "bilmiyorum",
        "deneyimim yok",
        "bu konuda deneyimim yok",
        "henüz deneyimim yok",
        "deneyimim bulunmuyor",
        "i don't know",
        "no experience",
    }


def local_quality(text):
    value = readable_text(text)
    compact = "".join(c for c in value.casefold() if c.isalnum())
    if explicit_no_experience(value):
        return "no_experience"
    if not compact or (len(compact) >= 5 and len(set(compact)) == 1):
        return "nonsensical"
    if re.fullmatch(
        r"(?:(?:asdf|asdasd|qwerty|qwer|zxcv|loremipsum|abc|123|test|deneme))+", compact
    ):
        return "nonsensical"
    return None


def assess_quality(text, grade, simulated=False):
    local = local_quality(text)
    if local == "no_experience":
        return None
    quality = grade.quality
    category = local or quality.category
    if category in {"relevant", "no_experience"}:
        return None
    quotes = (
        [text[:200]]
        if local and text
        else [q for q in quality.evidence_quotes if q in text]
    )
    return {
        "category": category,
        "reason": (
            "Tekrarlı veya anlamlı sözcük içermeyen yanıt örüntüsü; İK doğrulaması gerekir."
            if local
            else quality.reason
        ),
        "evidence_quotes": quotes,
        "source": "rule" if local else "mock" if simulated else "llm",
    }
