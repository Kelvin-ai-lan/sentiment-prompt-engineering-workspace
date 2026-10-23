# Predictive Prompt Engineering & Sentiment Analytics Workspace

A production-ready data pipeline and LLM benchmarking engine that loads customer behavior metrics into a cloud data warehouse architecture and runs a custom evaluation framework to audit prompt engineering accuracy.

## 🚀 System Architecture Overview

- **Cloud Warehouse Layer:** Extracted 1,000 corporate records from internal file targets and built a validation pipeline streaming straight into Google Cloud BigQuery.
- **Database Management Configuration:** Configured internal tool components via DBHub MCP servers to handle automated schema tracking and validation logic.
- **Evaluation Framework Engine:** Programmed a modular evaluation engine to wrap inputs within engineered templates, tracking model accuracy, data deviations, and token connection errors.

## 📊 Prompt Performance Matrix Results

During testing phases across 1,000 validation review tracks, the template configuration testing metrics returned the following baseline accuracy breakdown:

| Template Architecture Strategy | Core Prompt Constraint Logic         | Evaluated Benchmarking Accuracy |
| :----------------------------- | :----------------------------------- | :------------------------------ |
| **Prompt A**                   | Zero-Shot Direct Categorization      | **51.40%**                      |
| **Prompt B**                   | Few-Shot Text Context Examples       | **53.30%**                      |
| **Prompt C (Winner)**          | Role-Based Systematic Evidence Steps | **56.00%**                      |

_Takeaway: Enforcing systematic chain-of-thought logic constraints and structural roles significantly increases evaluation matching metrics and mitigates data hallucinations._

## 📂 Project Component Directory Layout

- `data/customer_reviews.csv`: Human-verified corporate baseline feedback dataset tracking text fields and labels.
- `data/bigquery_schema.sql`: Exported target cloud database schema definition tracking data structures.
- `scripts/init_bigquery.py`: Pipeline upload module configuring schema types and pushing tables to BigQuery.
- `scripts/export_bigquery_schema.py`: Extraction tool pulling structural table data back into regional environments.
- `scripts/evaluate_prompts.py`: Matrix orchestrator tracking engineered prompt evaluation logs and connection safety boundaries.
