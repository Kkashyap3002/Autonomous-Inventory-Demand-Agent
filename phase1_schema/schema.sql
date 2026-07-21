-- =============================================================================
-- AIDA: Autonomous Inventory & Demand Agent
-- Phase 1: Relational Schema for Quick-Commerce Retail
-- =============================================================================
-- Domain context: A chain of "dark stores" (micro-fulfillment centers) that
-- stock ~500-2000 high-turnover SKUs and deliver within 30 minutes.
-- This schema models products, stores, suppliers, inventory, orders, and
-- promotions with full audit-trail support so the agent can answer temporal
-- questions ("what was the stock level last Tuesday?") and run ML forecasts.

-- =============================================================================
-- DIMENSION TABLES
-- =============================================================================

-- Product catalogue. Every SKU lives here exactly once.
CREATE TABLE products (
    product_id          SERIAL PRIMARY KEY,
    sku                 VARCHAR(24)  NOT NULL UNIQUE,   -- human-readable, e.g. 'DAIRY-MILK-500ML'
    product_name        VARCHAR(120) NOT NULL,
    category            VARCHAR(60)  NOT NULL,           -- e.g. 'Dairy', 'Bakery', 'Beverages', 'Snacks'
    subcategory         VARCHAR(60),                     -- e.g. 'Milk', 'Bread', 'Soft Drinks'
    brand               VARCHAR(60),
    unit_of_measure     VARCHAR(20)  NOT NULL DEFAULT 'each',  -- 'each', 'kg', 'litre', 'pack'
    unit_cost           NUMERIC(10,2) NOT NULL,          -- landed cost per unit (local currency)
    selling_price       NUMERIC(10,2) NOT NULL,          -- current retail price
    supplier_id         INTEGER      NOT NULL,           -- FK to suppliers (preferred supplier)
    lead_time_days      SMALLINT     NOT NULL DEFAULT 1, -- typical replenishment lead time
    min_order_qty       INTEGER      NOT NULL DEFAULT 1, -- supplier MOQ
    is_perishable       BOOLEAN      NOT NULL DEFAULT FALSE,
    shelf_life_days     SMALLINT,                        -- NULL = non-perishable
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- Dark stores / micro-fulfillment centers.
CREATE TABLE stores (
    store_id            SERIAL PRIMARY KEY,
    store_code          VARCHAR(10)  NOT NULL UNIQUE,    -- e.g. 'DS-BLR-01'
    store_name          VARCHAR(100) NOT NULL,
    city                VARCHAR(60)  NOT NULL,
    zone                VARCHAR(60),                     -- neighborhood / delivery zone
    address             TEXT,
    area_sqft           INTEGER,                         -- store floor area
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    opening_date        DATE         NOT NULL,
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- Supplier / vendor master.
CREATE TABLE suppliers (
    supplier_id         SERIAL PRIMARY KEY,
    supplier_code       VARCHAR(20)  NOT NULL UNIQUE,
    supplier_name       VARCHAR(120) NOT NULL,
    category            VARCHAR(60),                     -- 'Dairy', 'FMCG', 'Beverages', etc.
    contact_email       VARCHAR(100),
    contact_phone       VARCHAR(20),
    sla_delivery_hours  SMALLINT     NOT NULL DEFAULT 24,-- contractual delivery SLA in hours
    payment_terms_days  SMALLINT     NOT NULL DEFAULT 30,-- net-N payment terms
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- Promotions / flash-sales (cause of demand spikes).
CREATE TABLE promotions (
    promotion_id        SERIAL PRIMARY KEY,
    promotion_name      VARCHAR(100) NOT NULL,
    promotion_type      VARCHAR(30)  NOT NULL,           -- 'percentage_discount', 'bogo', 'flat_off', 'free_delivery'
    discount_pct        NUMERIC(5,2),                    -- e.g. 20.00 = 20% off
    starts_at           TIMESTAMP    NOT NULL,
    ends_at             TIMESTAMP    NOT NULL,
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- Which products are covered by which promotions (M:N).
CREATE TABLE promotion_products (
    promotion_id        INTEGER NOT NULL REFERENCES promotions(promotion_id),
    product_id          INTEGER NOT NULL REFERENCES products(product_id),
    PRIMARY KEY (promotion_id, product_id)
);

-- =============================================================================
-- FACT / TRANSACTION TABLES
-- =============================================================================

-- Current inventory snapshot per product per store.  Updated by application
-- logic or nightly batch — this is the "fast query" table for the agent.
CREATE TABLE inventory_levels (
    inventory_id        SERIAL PRIMARY KEY,
    store_id            INTEGER      NOT NULL REFERENCES stores(store_id),
    product_id          INTEGER      NOT NULL REFERENCES products(product_id),
    qty_on_hand         INTEGER      NOT NULL DEFAULT 0,
    qty_reserved        INTEGER      NOT NULL DEFAULT 0,   -- allocated to open orders, not yet picked
    qty_available       INTEGER      GENERATED ALWAYS AS (qty_on_hand - qty_reserved) STORED,
    reorder_point       INTEGER      NOT NULL DEFAULT 10,  -- trigger replenishment when available <= this
    reorder_qty         INTEGER      NOT NULL DEFAULT 50,  -- how much to order when triggered
    last_counted_at     TIMESTAMP,
    updated_at          TIMESTAMP    NOT NULL DEFAULT NOW(),
    UNIQUE (store_id, product_id)
);

-- Every stock movement is recorded here for full audit trail.
-- The agent uses this table for temporal queries ("what was sold last week?")
-- and for computing features for the demand forecast (sales velocity, etc.).
CREATE TABLE inventory_transactions (
    transaction_id      SERIAL PRIMARY KEY,
    store_id            INTEGER      NOT NULL REFERENCES stores(store_id),
    product_id          INTEGER      NOT NULL REFERENCES products(product_id),
    transaction_type    VARCHAR(20)  NOT NULL,
        -- 'receipt' (from supplier), 'sale' (to customer), 'return' (customer return),
        -- 'adjustment' (manual correction, damage/wastage), 'transfer_in', 'transfer_out'
    quantity            INTEGER      NOT NULL,  -- positive for IN, negative for OUT
    reference_type      VARCHAR(30),            -- 'order', 'purchase_order', 'manual'
    reference_id        INTEGER,                -- FK-ish to the source row (order_items.id, etc.)
    unit_cost           NUMERIC(10,2),          -- cost at time of transaction (for margin calc)
    running_qty         INTEGER,                -- qty_on_hand AFTER this transaction
    notes               TEXT,
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- Customer orders (online orders placed through the app).
CREATE TABLE orders (
    order_id            SERIAL PRIMARY KEY,
    store_id            INTEGER      NOT NULL REFERENCES stores(store_id),
    order_status        VARCHAR(20)  NOT NULL DEFAULT 'placed',
        -- 'placed', 'picked', 'packed', 'out_for_delivery', 'delivered', 'cancelled', 'returned'
    order_total         NUMERIC(10,2) NOT NULL,
    discount_total      NUMERIC(10,2) NOT NULL DEFAULT 0,
    promotion_id        INTEGER      REFERENCES promotions(promotion_id),
    customer_zone       VARCHAR(60),
    ordered_at          TIMESTAMP    NOT NULL DEFAULT NOW(),
    delivered_at        TIMESTAMP
);

-- Line items within an order.
CREATE TABLE order_items (
    order_item_id       SERIAL PRIMARY KEY,
    order_id            INTEGER      NOT NULL REFERENCES orders(order_id),
    product_id          INTEGER      NOT NULL REFERENCES products(product_id),
    quantity            INTEGER      NOT NULL,
    unit_price          NUMERIC(10,2) NOT NULL,     -- price at the moment of sale
    line_total          NUMERIC(10,2) NOT NULL,     -- quantity * unit_price, before discounts
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- Purchase orders to suppliers (replenishment).
CREATE TABLE purchase_orders (
    po_id               SERIAL PRIMARY KEY,
    supplier_id         INTEGER      NOT NULL REFERENCES suppliers(supplier_id),
    store_id            INTEGER      NOT NULL REFERENCES stores(store_id),
    po_status           VARCHAR(20)  NOT NULL DEFAULT 'draft',
        -- 'draft', 'sent', 'acknowledged', 'in_transit', 'received', 'cancelled'
    ordered_at          TIMESTAMP    NOT NULL DEFAULT NOW(),
    expected_delivery   TIMESTAMP,
    received_at         TIMESTAMP,
    total_cost          NUMERIC(10,2)
);

CREATE TABLE purchase_order_items (
    po_item_id          SERIAL PRIMARY KEY,
    po_id               INTEGER      NOT NULL REFERENCES purchase_orders(po_id),
    product_id          INTEGER      NOT NULL REFERENCES products(product_id),
    quantity_ordered    INTEGER      NOT NULL,
    quantity_received   INTEGER      DEFAULT 0,
    unit_cost           NUMERIC(10,2) NOT NULL
);

-- =============================================================================
-- INDEXES (tuned for the agent's most frequent query patterns)
-- =============================================================================
CREATE INDEX idx_inv_txn_store_prod    ON inventory_transactions(store_id, product_id);
CREATE INDEX idx_inv_txn_created       ON inventory_transactions(created_at);
CREATE INDEX idx_inv_txn_type          ON inventory_transactions(transaction_type);
CREATE INDEX idx_inv_lvl_store         ON inventory_levels(store_id);
CREATE INDEX idx_orders_store_status   ON orders(store_id, order_status);
CREATE INDEX idx_orders_ordered_at     ON orders(ordered_at);
CREATE INDEX idx_order_items_order     ON order_items(order_id);
CREATE INDEX idx_order_items_prod      ON order_items(product_id);
CREATE INDEX idx_products_category     ON products(category);
CREATE INDEX idx_products_supplier     ON products(supplier_id);
CREATE INDEX idx_po_supplier_status    ON purchase_orders(supplier_id, po_status);

-- =============================================================================
-- AGGREGATE VIEW: Daily Sales by Product & Store
-- (The forecasting model reads this view directly)
-- =============================================================================
CREATE VIEW daily_sales_view AS
SELECT
    DATE(ot.created_at)         AS sale_date,
    oi.product_id,
    o.store_id,
    COUNT(DISTINCT o.order_id)  AS order_count,
    SUM(oi.quantity)            AS total_units_sold,
    SUM(oi.line_total)          AS total_revenue,
    SUM(oi.line_total) - SUM(p.unit_cost * oi.quantity) AS estimated_gross_margin
FROM order_items oi
JOIN orders o        ON oi.order_id = o.order_id
JOIN products p      ON oi.product_id = p.product_id
JOIN inventory_transactions ot ON ot.reference_id = oi.order_item_id
    AND ot.transaction_type = 'sale'
    AND ot.reference_type = 'order'
WHERE o.order_status = 'delivered'
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3;
