import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key= os.getenv("OPENAI_API_KEY"),
    base_url="https://api.deepseek.com"
)

MODEL = "deepseek-chat"


PROBLEMS_PROMPT = """
You are parsing a math competition PDF into structured data. Please follow directions very closely. If there is any doubt please flag the problem as not confident and include a note in review_notes. Be conservative with confidence — if you are unsure about any aspect of the problem, mark it as not confident and explain why in review_notes.

Competition - ICTM, NSML, AMC10/12, AIME, or ARML: {competition}
Year - The competition year: {year}
Event - Specific competition event (Only if the competition is ICTM): {event}
Answer format - Either Multiple Choice or Numeric: {answer_format}


The text below is extracted from a competition PDF.
Parse every problem you find and return a JSON array.

Each object in the array must have these fields:
  - problem_number: integer (1-based position in this document)
  - problem_text: the full problem statement as a LaTeX string
  - image: a Blob or base64 string of any image associated with the problem, else null. If a problem references an image and the image cannot be extracted, include a note in review_notes and set confident to false.
  - answer: the answer if present in this document, else null. For multiple choice, use the letter only (A/B/C/D/E). For numeric, use the number only, no units or explanation. Keep the answer in the form it is given (For example if the answer says sqrt(3) DO NOT put 1.732). Some answers may contain algebraic terms, ordered pairs, or short english phrases. Keep these as they are given, do not attempt to simplify or rewrite them. If there are multiple parts to the answer, include them all in a single string with clear formatting. If there are multiple answers, separate them with a comma and space (For example the quadratic x^2 - 5x + 6 = 0 has answer "2, 3"). 
  - comp_difficulty: difficulty label using this competition's native scale: use your own judgement according to the guidelines below, else null
    ICTM: "Easy", "Medium", or "Hard"
    NSML: "Q1", "Q2", "Q3", "Q4", or "Q5"
    AMC10/AMC12: "Q1-Q10", "Q11-Q15", "Q16-Q20", or "Q21-Q25"
    AIME: "Q1-Q5", "Q6-Q10", or "Q11-Q15"
    ARML: "Q1-Q7", "Q8-Q14", "Q15-Q21", or "Q22-Q24"
  - topics: array of topic tags from this list only if the competition is AMC10/AMC12, AIME, or ARML, else use your own judgement to assign 1-2 topic labels. For example a precaclucus problem invovoling polar coordinates from a ICTM competition may be labeled "Polars" in addition to its precaculus label, Be consistent with your labeling do not make similar labels. If a topic is best described with a general label use it.
    ["Algebra", "Geometry", "Number Theory", "Combinatorics", "Precalculus", "Advanced Math"]
    Assign exactly one tag if the competition is AMC10/AMC12, AIME, or ARML. If truly ambiguous, use "Advanced Math". Ädvanced Math may include: Floor/Ceiling, functional equations, recursion, inequalties, or logic puzzles, but it is not exclusive to said list.
  - choices: object with keys A/B/C/D/E if multiple choice, else null
  - confident: true if you are certain about the parse, false if anything is unclear. Please flag this liberally — if you are unsure about any aspect of the problem, mark it as not confident and explain why in review_notes.
  - review_notes: null if confident, otherwise a short note explaining what is unclear. Please keep to one or two sentences MAX. Include the specfic problem year and competition and event (if applicable). 

Return ONLY the JSON array. No markdown, no explanation, no preamble.

PDF TEXT:
{text}
"""

SOLUTIONS_PROMPT = """
You are parsing a math competition solutions document. Probelms may be found but you have already parsed the problem statements in a separate step, so you can rely on the order of solutions matching the order of problems. 

Competition: {competition}
Year: {year}
Image - Please flag if unable to be extracted: {image}
Event (if competition is ICTM): {event}


The text below contains solutions to competition problems, in order.
Extract each solution and return a JSON array of strings.
Each string is the full solution text for that problem, as a LaTeX string.
Preserve the order exactly — the first solution is for problem 1, etc.
Your array should have the following fields:

- solution_number: integer (1-based position in this document)
- solution_text: the full solution text as a LaTeX string
- image: a Blob or base64 string of any image associated with the problem, else null. If a problem references an image and the image cannot be extracted, include a note in review_notes and set confident to false.
- confident: true if you are certain about the parse, false if anything is unclear. Please flag this liberally — if you are unsure about any aspect of the problem, mark it as not confident and explain why in review_notes.
- review_notes: null if confident, otherwise a short note explaining what is unclear. Please keep to one or two sentences MAX. Include the specfic problem year and competition and event (if applicable). 


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

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=8000,
    )

    raw = response.choices[0].message.content.strip()
    raw = raw.strip("```json").strip("```").strip()

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

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=8000,
    )

    raw = response.choices[0].message.content.strip()
    raw = raw.strip("```json").strip("```").strip()

    try:
        solutions = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\n\nRaw output:\n{raw}")

    return solutions