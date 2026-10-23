import csv
import logging
import tempfile
from datetime import datetime
from pathlib import Path

from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from google.oauth2 import service_account


PROJECT_ID = "dbhub-bigquery-test"
DATASET_ID = "sentiment_analytics"
TABLE_ID = "customer_feedback"
INPUT_CSV = Path(__file__).resolve().parents[1] / "data" / "ecommerce_reviews.csv"
KEY_FILE = Path(__file__).resolve().parents[1] / "gcp-key.json"

FIELDS = (
    "review_id",
    "order_id",
    "review_date",
    "product_name",
    "rating",
    "review_text",
    "sentiment_label",
    "issue_type",
)
SCHEMA = (
    bigquery.SchemaField("review_id", "STRING"),
    bigquery.SchemaField("order_id", "STRING"),
    bigquery.SchemaField("review_date", "DATE"),
    bigquery.SchemaField("product_name", "STRING"),
    bigquery.SchemaField("rating", "INTEGER"),
    bigquery.SchemaField("review_text", "STRING"),
    bigquery.SchemaField("sentiment_label", "STRING"),
    bigquery.SchemaField("issue_type", "STRING"),
)

LOGGER = logging.getLogger("init_bigquery")


def prepare_load_file(source_path: Path, output_path: Path) -> int:
    with source_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        headers = reader.fieldnames or []
        missing_fields = [field for field in FIELDS if field not in headers]
        if missing_fields:
            raise ValueError(
                f"{source_path} is missing required CSV columns: "
                f"{', '.join(missing_fields)}"
            )

        row_count = 0
        with output_path.open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=FIELDS)
            writer.writeheader()

            for line_number, row in enumerate(reader, start=2):
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(
                        f"Malformed CSV row at line {line_number}: "
                        "the number of values does not match the header"
                    )

                try:
                    row["review_date"] = datetime.strptime(
                        row["review_date"], "%Y-%m-%d"
                    ).date().isoformat()
                except ValueError as error:
                    raise ValueError(
                        f"Invalid review_date at CSV line {line_number}; "
                        "expected YYYY-MM-DD"
                    ) from error

                writer.writerow({field: row[field] for field in FIELDS})
                row_count += 1

    return row_count


def ensure_dataset(client: bigquery.Client) -> None:
    dataset_ref = bigquery.DatasetReference(PROJECT_ID, DATASET_ID)
    try:
        client.get_dataset(dataset_ref)
        LOGGER.info("Dataset %s.%s already exists.", PROJECT_ID, DATASET_ID)
    except NotFound:
        dataset = bigquery.Dataset(dataset_ref)
        client.create_dataset(dataset, exists_ok=True)
        LOGGER.info("Created dataset %s.%s.", PROJECT_ID, DATASET_ID)


def ensure_table(client: bigquery.Client) -> bigquery.TableReference:
    table_ref = bigquery.TableReference(
        bigquery.DatasetReference(PROJECT_ID, DATASET_ID), TABLE_ID
    )
    client.create_table(bigquery.Table(table_ref, schema=SCHEMA), exists_ok=True)

    table = client.get_table(table_ref)
    actual_schema = [
        (field.name, field.field_type.upper(), field.mode.upper())
        for field in table.schema
    ]
    expected_schema = [
        (field.name, field.field_type.upper(), field.mode.upper())
        for field in SCHEMA
    ]
    if actual_schema != expected_schema:
        raise RuntimeError(
            f"Existing table {PROJECT_ID}.{DATASET_ID}.{TABLE_ID} has a schema "
            "that does not match the required customer_feedback schema."
        )

    return table_ref


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if not INPUT_CSV.is_file():
        raise FileNotFoundError(f"Input CSV not found: {INPUT_CSV}")
    if not KEY_FILE.is_file():
        raise FileNotFoundError(f"Service account key file not found: {KEY_FILE}")

    with tempfile.TemporaryDirectory(prefix="bigquery_customer_feedback_") as temp_dir:
        load_path = Path(temp_dir) / "customer_feedback.csv"
        source_row_count = prepare_load_file(INPUT_CSV, load_path)
        LOGGER.info("Validated %s CSV rows for loading.", source_row_count)

        credentials = service_account.Credentials.from_service_account_file(
            str(KEY_FILE)
        )
        client = bigquery.Client(project=PROJECT_ID, credentials=credentials)

        ensure_dataset(client)
        table_ref = ensure_table(client)

        job_config = bigquery.LoadJobConfig(
            schema=SCHEMA,
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            allow_quoted_newlines=True,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )
        with load_path.open("rb") as load_file:
            load_job = client.load_table_from_file(
                load_file, table_ref, job_config=job_config
            )
        load_job.result()

        if load_job.output_rows != source_row_count:
            raise RuntimeError(
                f"BigQuery loaded {load_job.output_rows} rows, but "
                f"{source_row_count} CSV rows were prepared."
            )

        uploaded_count = client.get_table(table_ref).num_rows
        if uploaded_count != source_row_count:
            raise RuntimeError(
                f"BigQuery table contains {uploaded_count} rows after loading; "
                f"expected {source_row_count}."
            )

        LOGGER.info(
            "Successfully uploaded and verified %s rows to %s.%s.%s.",
            uploaded_count,
            PROJECT_ID,
            DATASET_ID,
            TABLE_ID,
        )


if __name__ == "__main__":
    main()
