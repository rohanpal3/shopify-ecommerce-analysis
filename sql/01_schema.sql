-- schema for the d2c e-commerce analysis (fragrance brand, anonymised)
-- postgres. all money is in INR, scaled by a constant (see readme / prepare_data.py)
-- grain: one row per order, one row per line item, one row per customer

drop table if exists order_items;
drop table if exists orders;
drop table if exists customers;
drop table if exists products;
drop table if exists device_sessions;

-- customers (from the shopify customer export)
create table customers (
    customer_hash   text primary key,       -- anonymised (sha1 of email)
    city            text,
    province        text,
    country         text,
    total_spent     numeric(12,2),
    total_orders    int,
    accepts_email   smallint
);

-- one row per order (the order-header fields)
create table orders (
    order_name        text primary key,      -- shopify order name e.g. #cf2073
    customer_hash     text,                  -- null/blank for guest orders
    financial_status  text,
    currency          text,
    subtotal          numeric(12,2),
    shipping          numeric(12,2),
    taxes             numeric(12,2),
    total             numeric(12,2),
    discount_code     text,
    discount_amount   numeric(12,2),
    refunded_amount   numeric(12,2),
    created_at        timestamptz,
    order_date        date,
    channel           text,
    payment_method    text,
    ship_city         text,
    ship_province     text,
    ship_country      text
);

-- one row per line item (orders can have more than one)
create table order_items (
    id            bigserial primary key,
    order_name    text references orders(order_name),
    sku           text,
    product_name  text,
    quantity      int,
    unit_price    numeric(12,2),
    line_discount numeric(12,2)
);

-- product cost table (hand-entered landed cost per unit, for margin)
create table products (
    sku            text primary key,
    product_name   text,
    cost_per_unit  numeric(12,2)   -- null where unknown
);

-- aggregate sessions by device (from shopify analytics, not joinable to orders)
create table device_sessions (
    device_type  text primary key,
    visitors     bigint,
    sessions     bigint
);

-- indexes for the joins / group bys the analyses actually use
create index idx_orders_customer on orders(customer_hash);
create index idx_orders_date     on orders(order_date);
create index idx_orders_channel  on orders(channel);
create index idx_orders_status   on orders(financial_status);
create index idx_items_order     on order_items(order_name);
create index idx_items_sku       on order_items(sku);
