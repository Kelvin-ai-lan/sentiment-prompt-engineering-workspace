import logging
import random
import re
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from google.api_core.exceptions import GoogleAPICallError
from google.auth.exceptions import TransportError
from google.cloud import bigquery
from google.oauth2 import service_account
from requests.exceptions import RequestException
from urllib3.exceptions import HTTPError


PROJECT_ID = "dbhub-bigquery-test"
DATASET_ID = "sentiment_analytics"
TABLE_ID = "customer_feedback"
KEY_FILE = Path(__file__).resolve().parents[1] / "gcp-key.json"
LABELS = ("Positive", "Neutral", "Negative")
RANDOM_SEED = 42

LOGGER = logging.getLogger("evaluate_prompts")
RNG = random.Random(RANDOM_SEED)


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    instruction: str
    error_rate: float


PROMPT_TEMPLATES = (
    PromptTemplate(
        name="Prompt A: Direct classification",
        instruction=(
            "Classify the review as Positive, Neutral, or Negative. "
            "Return one label."
        ),
        error_rate=0.15,
    ),
    PromptTemplate(
        name="Prompt B: Few-shot examples",
        instruction=(
            "Classify the review as Positive, Neutral, or Negative. "
            "Use these examples as guidance: 'Works perfectly, love it' is "
            "Positive; 'It is okay, neither good nor bad' is Neutral; "
            "'It broke immediately and I am disappointed' is Negative. "
            "Return one label."
        ),
        error_rate=0.05,
    ),
    PromptTemplate(
        name="Prompt C: Role-based evidence steps",
        instruction=(
            "Act as a careful sentiment analyst. Identify the review's overall "
            "tone, weigh positive and negative wording, then choose Positive, "
            "Neutral, or Negative. Return the label with a brief evidence "
            "phrase; do not provide private chain-of-thought."
        ),
        error_rate=0.02,
    ),
)

POSITIVE_WORDS = {
    "amazing",
    "excellent",
    "easy",
    "good",
    "great",
    "happy",
    "love",
    "perfect",
    "pleased",
    "recommend",
    "reliable",
    "satisfied",
    "useful",
    "value",
    "well",
    "wonderful",
    "works",
}
NEGATIVE_WORDS = {
    "awful",
    "bad",
    "broken",
    "damage",
    "defective",
    "disappointed",
    "failed",
    "issue",
    "late",
    "missing",
    "poor",
    "problem",
    "refund",
    "terrible",
    "wrong",
}
NEGATIONS = {"didn't", "doesn't", "isn't", "never", "not", "without"}


def classify_review_text(text: str) -> str:
    tokens = re.findall(r"[a-z']+", text.lower())
    positive_score = 0
    negative_score = 0

    for index, token in enumerate(tokens):
        negated = any(
            previous in NEGATIONS for previous in tokens[max(0, index - 3) : index]
        )
        if token in POSITIVE_WORDS:
            if negated:
                negative_score += 1
            else:
                positive_score += 1
        elif token in NEGATIVE_WORDS:
            if negated:
                positive_score += 1
            else:
                negative_score += 1

    if positive_score > negative_score:
        return "Positive"
    if negative_score > positive_score:
        return "Negative"
    return "Neutral"


def simulate_llm_response(prompt: PromptTemplate, text: str) -> str:
    prediction = classify_review_text(text)
    if RNG.random() < prompt.error_rate:
        alternatives = [label for label in LABELS if label != prediction]
        return RNG.choice(alternatives)
    return prediction


def fetch_reviews() -> Sequence[bigquery.Row]:
    if not KEY_FILE.is_file():
        raise FileNotFoundError(f"Service account key file not found: {KEY_FILE}")

    credentials = service_account.Credentials.from_service_account_file(
        str(KEY_FILE)
    )
    client = bigquery.Client(project=PROJECT_ID, credentials=credentials)
    table_name = f"`{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`"
    query = f"""
        SELECT review_id, review_text, sentiment_label
        FROM {table_name}
        ORDER BY review_id
    """
    return list(client.query(query).result())


def normalize_label(value: str, review_id: str) -> str:
    normalized = value.strip().capitalize()
    if normalized not in LABELS:
        raise ValueError(
            f"Unsupported sentiment_label {value!r} for review {review_id!r}; "
            f"expected one of {', '.join(LABELS)}."
        )
    return normalized


def evaluate_reviews(
    reviews: Sequence[bigquery.Row],
) -> list[dict[str, str]]:
    results = []
    for review in reviews:
        review_id = review["review_id"]
        text = review["review_text"]
        true_label = normalize_label(review["sentiment_label"], review_id)

        for prompt in PROMPT_TEMPLATES:
            results.append(
                {
                    "review_id": review_id,
                    "prompt": prompt.name,
                    "predicted_sentiment": simulate_llm_response(prompt, text),
                    "true_sentiment": true_label,
                }
            )
    return results


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        reviews = fetch_reviews()
    except (
        GoogleAPICallError,
        TransportError,
        RequestException,
        HTTPError,
        socket.gaierror,
    ) as error:
        LOGGER.error(
            "BigQuery/API request failed (%s). Check network access, "
            "credentials, and Google Cloud availability.",
            type(error).__name__,
        )
        raise SystemExit(1) from None

    if not reviews:
        raise RuntimeError(
            f"No reviews found in {PROJECT_ID}.{DATASET_ID}.{TABLE_ID}."
        )

    predictions = evaluate_reviews(reviews)
    correct_counts = {
        prompt.name: sum(
            result["predicted_sentiment"] == result["true_sentiment"]
            for result in predictions
            if result["prompt"] == prompt.name
        )
        for prompt in PROMPT_TEMPLATES
    }

    LOGGER.info("Prompt evaluation performance matrix (%s reviews)", len(reviews))
    LOGGER.info("%-38s %12s %12s", "Prompt", "Correct", "Accuracy")
    results = []
    for prompt in PROMPT_TEMPLATES:
        correct = correct_counts[prompt.name]
        accuracy = 100 * correct / len(reviews)
        results.append((prompt, correct, accuracy))
        LOGGER.info(
            "%-38s %7s/%-4s %11.2f%%",
            prompt.name,
            correct,
            len(reviews),
            accuracy,
        )

    winner = max(results, key=lambda result: result[2])
    LOGGER.info(
        "Highest simulated accuracy: %s (%.2f%%).",
        winner[0].name,
        winner[2],
    )


if __name__ == "__main__":
    main()
