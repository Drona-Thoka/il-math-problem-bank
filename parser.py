"""
parser.py — Sends PDF text to the Anthropic API and returns structured problems.
"""

import json
import anthropic

client = anthropic.Anthropic()

PROBLEMS_PROMPT = """
You are parsing a math competition PDF into structured data.

Competition: {competition}
Year: {year}
Event (if applicable): {event}
Answer format: {answer_format}

The text below is extracted from a competition PDF.
Parse every problem you find and return a JSON array.

Each object in the array must have these fields:
  - problem_number: integer (1-based position in this document)
  - problem_text: the full problem statement as a LaTeX string
  - answer: the answer if present in this document, else null
  - comp_difficulty: difficulty label using this competition's native scale, else null
    ICTM: "Easy", "Medium", or "Hard"
    NSML: "Q1", "Q2", "Q3", "Q4", or "Q5"
    AMC10/AMC12: "Q1-Q10", "Q11-Q15", "Q16-Q20", or "Q21-Q25"
    AIME: "Q1-Q5", "Q6-Q10", or "Q11-Q15"
    ARML: "Q1-Q7", "Q8-Q14", "Q15-Q21", or "Q22-Q24"
  - topics: array of topic tags from this list only:
    ["Algebra", "Geometry", "Number Theory", "Combinatorics", "Precalculus", "Advanced Math"]
    Assign exactly one tag. If truly ambiguous, use "Advanced Math".
  - choices: object with keys A/B/C/D/E if multiple choice, else null
  - confident: true if you are certain about the parse, false if anything is unclear
  - review_notes: null if confident, otherwise a short note explaining what is unclear

Return ONLY the JSON array. No markdown, no explanation, no preamble.

PDF TEXT:
{text}
"""

SOLUTIONS_PROMPT = """
You are parsing a math competition solutions document.

Competition: {competition}
Year: {year}
Event (if applicable): {event}

The text below contains solutions to competition problems, in order.
Extract each solution and return a JSON array of strings.
Each string is the full solution text for that problem, as a LaTeX string.
Preserve the order exactly — the first solution is for problem 1, etc.

Return ONLY the JSON array of strings. No markdown, no explanation, no preamble.

PDF TEXT:
{text}
"""


def parse_problems(text: str, competition: str, year: int, event: str | None, answer_format: str) -> list[dict]:
    prompt = PROBLEMS_PROMPT.format(
        competition=competition,
        year=year,
        event=event or "N/A",
        answer_format=answer_format,
        text=text
    )

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()

    try:
        problems = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\n\nRaw output:\n{raw}")

    return problems


def parse_solutions(text: str, competition: str, year: int, event: str | None) -> list[str]:
    prompt = SOLUTIONS_PROMPT.format(
        competition=competition,
        year=year,
        event=event or "N/A",
        text=text
    )

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()

    try:
        solutions = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\n\nRaw output:\n{raw}")

    return solutions
