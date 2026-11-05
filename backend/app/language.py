"""Supported UI/assessment language selection; existing records retain their language."""

from functools import lru_cache


@lru_cache(maxsize=1)
def error_translations():
    import json
    from .config import REFERENCE_DIR

    return json.loads((REFERENCE_DIR / "errors.en.json").read_text())


def error_message(code, original, language="en"):
    return (
        original
        if language == "tr"
        else error_translations().get(
            code,
            "The operation could not be completed. Contact support with the request ID.",
        )
    )


def request_language(request):
    value = request.headers.get("x-aptilume-language", "en").lower()
    return value if value in {"en", "tr"} else "en"


def english_examples(skills, team):
    """Deterministic English fixtures, not calibrated model output."""
    import json
    from .config import REFERENCE_DIR
    from .services import COMMON

    names = json.loads((REFERENCE_DIR / "skill-names.en.json").read_text())
    result = []
    labels = [
        "Conceptual accuracy",
        "Application and validation",
        "Boundaries and risk management",
    ]
    anchors = {
        "0": "Absent or incorrect",
        "1": "Mentions the concept; application is unclear",
        "2": "Partially applicable with significant gaps",
        "3": "Accurate and practical explanation",
        "4": "Concrete alternatives, boundaries and validation",
    }
    levels = ["Aware", "Developing", "Proficient", "Advanced", "Leader"]
    experiences = [
        "I recognize the concepts and when they apply.",
        "I can apply the approach with guidance.",
        "I can apply it independently and validate the result.",
        "I can handle complex cases and support others.",
        "I can define strategy, standards and organizational practice.",
    ]
    for index, skill in enumerate(skills):
        name = names.get(skill["id"], skill["name"])
        section = "common" if skill["id"] in COMMON else "role"
        for variant in range(2):
            descriptors = [
                f"Recognizes the key concepts of {name} in the scenario.",
                f"Applies {name} with explicit steps, assumptions, checks and verifiable sources.",
                f"Evaluates limitations, risks and alternatives for {name}, including when human review is required.",
            ]
            rubric = [
                {
                    "id": f"c{level}",
                    "label": labels[level - 1],
                    "level": level,
                    "indicator_id": f"{skill['id']}:L{level}",
                    "weight": 1,
                    "max_points": 4,
                    "descriptor": descriptors[level - 1],
                    "anchors": dict(anchors),
                }
                for level in range(1, 4)
            ]
            prompt = (
                f"In a business decision involving {name}, you notice an error or inconsistency in an AI output. Explain your approach, the checks you would perform and the conditions under which you would use the result."
                if variant == 0
                else f"Describe a concrete example of applying {name}. What was your task, what steps did you take, how did you validate the work and what was the outcome? If you have no experience, say so and explain how you would proceed."
            )
            result.append(
                {
                    "skill_id": skill["id"],
                    "type": "open_text",
                    "prompt": prompt,
                    "section": section,
                    "options": [],
                    "rubric": rubric,
                    "reference": "\n".join(descriptors),
                    "evidence_type": (
                        "scenario_reasoning"
                        if variant == 0
                        else "self_reported_experience"
                    ),
                }
            )
        if index in [0, 2, 3, 5]:
            result.append(
                {
                    "skill_id": skill["id"],
                    "type": "single_choice",
                    "prompt": f"Before using a decision-relevant AI output while applying {name}, which approach is most appropriate?",
                    "section": section,
                    "rubric": [],
                    "reference": "Validate the original source, assumptions and risks using checks appropriate to the business context.",
                    "options": [
                        {
                            "id": "a",
                            "text": "Use it directly if it sounds convincing.",
                            "correct": False,
                        },
                        {
                            "id": "b",
                            "text": "Check the original source, assumptions and risks before use.",
                            "correct": True,
                        },
                        {
                            "id": "c",
                            "text": "Only regenerate the same response using different words.",
                            "correct": False,
                        },
                        {"id": "d", "text": "I do not know.", "correct": False},
                    ],
                }
            )
        result.append(
            {
                "skill_id": skill["id"],
                "type": "self_assessment",
                "prompt": f"Which statement best describes your current experience with {name}?",
                "section": section,
                "rubric": [],
                "reference": "",
                "options": [
                    {
                        "id": str(level),
                        "text": f"L{level} · {labels_} — {experiences[level-1]}",
                        "level": level,
                    }
                    for level, labels_ in enumerate(levels, 1)
                ]
                + [{"id": "none", "text": "I have no experience yet.", "level": None}],
            }
        )
    return result
