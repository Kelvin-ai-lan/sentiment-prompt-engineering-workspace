import logging
from pathlib import Path

from google.cloud import bigquery
from google.oauth2 import service_account


PROJECT_ID = "dbhub-bigquery-test"
DATASET_ID = "sentiment_analytics"
TABLE_ID = "customer_feedback"
KEY_FILE = Path(__file__).resolve().parents[1] / "gcp-key.json"
OUTPUT_FILE = Path(__file__).resolve().parents[1] / "data" / "bigquery_schema.sql"

LOGGER = logging.getLogger("export_bigquery_schema")


def render_field_type(field: bigquery.SchemaField) -> str:
    field_type = field.field_type.upper()
    if field_type in {"RECORD", "STRUCT"}:
        nested_fields = ", ".join(
            f"{quote_identifier(nested.name)} {render_field_type(nested)}"
            for nested in field.fields
        )
        rendered_type = f"STRUCT<{nested_fields}>"
    else:
        rendered_type = field_type

    if field.mode.upper() == "REPEATED":
        return f"ARRAY<{rendered_type}>"
    return rendered_type


def quote_identifier(identifier: str) -> str:
    return f"`{identifier.replace('`', '``')}`"


def render_create_table(table: bigquery.Table) -> str:
    columns = []
    for field in table.schema:
        column = (
            f"  {quote_identifier(field.name)} {render_field_type(field)}"
        )
        if field.mode.upper() == "REQUIRED":
            column += " NOT NULL"
        columns.append(column)

    table_name = ".".join(
        quote_identifier(part) for part in (PROJECT_ID, DATASET_ID, TABLE_ID)
    )
    return (
        f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
        + ",\n".join(columns)
        + "\n);\n"
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if not KEY_FILE.is_file():
        raise FileNotFoundError(f"Service account key file not found: {KEY_FILE}")

    credentials = service_account.Credentials.from_service_account_file(
        str(KEY_FILE)
    )
    client = bigquery.Client(project=PROJECT_ID, credentials=credentials)
    table = client.get_table(f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}")
    sql = render_create_table(table)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(sql, encoding="utf-8")
    LOGGER.info(
        "Exported %s schema fields to %s.",
        len(table.schema),
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()
