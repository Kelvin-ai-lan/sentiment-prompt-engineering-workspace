CREATE TABLE IF NOT EXISTS `dbhub-bigquery-test`.`sentiment_analytics`.`customer_feedback` (
  `review_id` STRING,
  `order_id` STRING,
  `review_date` DATE,
  `product_name` STRING,
  `rating` INTEGER,
  `review_text` STRING,
  `sentiment_label` STRING,
  `issue_type` STRING
);
