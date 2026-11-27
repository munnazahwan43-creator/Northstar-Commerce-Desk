CREATE DATABASE IF NOT EXISTS northstar_retail
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

USE northstar_retail;

CREATE TABLE IF NOT EXISTS sales (
    sale_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    sale_date DATE NOT NULL,
    item_name VARCHAR(100) NOT NULL,
    brand VARCHAR(100) NOT NULL DEFAULT 'Unbranded',
    category VARCHAR(60) NOT NULL,
    units_sold INT UNSIGNED NOT NULL,
    unit_price DECIMAL(12, 2) NOT NULL,
    total_revenue DECIMAL(22, 2)
        GENERATED ALWAYS AS (units_sold * unit_price) STORED,
    payment_mode VARCHAR(40) NOT NULL DEFAULT 'Not specified',
    customer_type VARCHAR(40) NOT NULL DEFAULT 'Not specified',
    region VARCHAR(80) NOT NULL DEFAULT 'Not specified',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (sale_id),
    INDEX idx_sales_date (sale_date),
    INDEX idx_sales_category (category),
    INDEX idx_sales_region (region),
    CONSTRAINT chk_sales_units_positive CHECK (units_sold > 0),
    CONSTRAINT chk_sales_price_positive CHECK (unit_price > 0)
) ENGINE=InnoDB;
