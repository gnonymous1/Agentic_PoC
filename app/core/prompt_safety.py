import re

INSTRUCTION_BOUNDARY = "\n--- BRAND VOICE CONTEXT ---\n"

INJECTION_PATTERNS: list[str] = [
    r"ignore\s+(?:all\s+)?(?:previous|above|prior)\s+instructions",
    r" disregard\s+(?:all\s+)?(?:previous|above|prior)\s+(?:instructions|directions)",
    r" forget\s+(?:all\s+)?(?:previous|above|prior)\s+(?:instructions|directions)",
    r"you\s+(?:are\s+)?(?:now|are\s+free)\s+(?:to\s+)?(?:act\s+as|ignore|bypass)",
    r"(?:\b|^)system\s*(?:instruction|prompt)\s*:?\s*override",
    r"output\s+(?:only|just|exactly)\s+(?:this|the\s+following)",
    r"do\s+not\s+(?:follow|adhere\s+to|obey)\s+(?:any\s+)?(?:instructions|rules|guidelines)",
    r"new\s+(?:instructions|prompt|directive)\s*:\s*",
    r"##\s*(?:user\s*)?instruction\s*(?:override|injection)",
    r"brand\s+voice\s*(?:override|injection|bypass)",
]


def detect_prompt_injection(text: str) -> list[str]:
    matches = []
    for pattern in INJECTION_PATTERNS:
        found = re.findall(pattern, text, flags=re.IGNORECASE)
        matches.extend(found)
    return matches


def sanitize_brand_voice(override: str) -> str:
    injections = detect_prompt_injection(override)
    if injections:
        raise ValueError(
            f"Prompt injection detected in brand voice override: {injections[:3]}"
        )
    return f"{INSTRUCTION_BOUNDARY}{override}\n{INSTRUCTION_BOUNDARY}"
