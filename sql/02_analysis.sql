-- ============================================================
-- d2c e-commerce analysis - query set (fragrance brand, anonymised)
-- postgres. money scaled by a constant, INR. ~64k orders, jun-nov 2026.
-- each block: the question, then the query. run them one at a time.
-- ============================================================


-- ------------------------------------------------------------
-- Q1. repeat purchase rate - what share of customers buy more than once?
-- (the core retention number for a d2c brand)
-- ------------------------------------------------------------
select
    count(*)                                            as customers,
    count(*) filter (where total_orders > 1)            as repeat_customers,
    round(100.0 * count(*) filter (where total_orders > 1) / count(*), 2) as repeat_rate_pct
from customers
where total_orders > 0;        -- ignore profiles that never ordered


-- ------------------------------------------------------------
-- Q2. cohort retention by signup month
-- group customers by the month of their first order, then see how many
-- came back in each following month. classic retention triangle.
-- ------------------------------------------------------------
with first_order as (
    select customer_hash, min(order_date) as first_dt
    from orders
    where customer_hash <> ''
    group by customer_hash
),
activity as (
    select
        f.customer_hash,
        date_trunc('month', f.first_dt)::date                       as cohort_month,
        date_trunc('month', o.order_date)::date                     as order_month,
        -- months between signup and this order
        (extract(year  from age(date_trunc('month', o.order_date), date_trunc('month', f.first_dt))) * 12
       + extract(month from age(date_trunc('month', o.order_date), date_trunc('month', f.first_dt))))::int as month_offset
    from first_order f
    join orders o on o.customer_hash = f.customer_hash
)
select
    cohort_month,
    month_offset,
    count(distinct customer_hash) as active_customers
from activity
group by cohort_month, month_offset
order by cohort_month, month_offset;


-- ------------------------------------------------------------
-- Q3. average order value (AOV) by sales channel
-- which channel brings the biggest baskets? (paid+partially paid only,
-- so COD-pending / cancelled don't distort revenue)
-- ------------------------------------------------------------
select
    channel,
    count(*)                       as orders,
    round(avg(total), 2)           as aov,
    round(sum(total), 2)           as revenue
from orders
where financial_status in ('paid','partially_paid','partially_refunded')
group by channel
order by revenue desc;


-- ------------------------------------------------------------
-- Q4. conversion rate by device type
-- sessions are aggregate (not joinable to orders), so this pairs total
-- sessions per device with total orders to get a blended conversion rate.
-- shows how mobile-heavy the traffic is and how it converts.
-- ------------------------------------------------------------
select
    d.device_type,
    d.sessions,
    round(100.0 * d.sessions / sum(d.sessions) over (), 1)  as pct_of_sessions
from device_sessions d
order by d.sessions desc;

-- overall conversion rate (all orders / all sessions) for context
select
    (select count(*) from orders)                        as orders,
    (select sum(sessions) from device_sessions)          as sessions,
    round(100.0 * (select count(*) from orders)
                / (select sum(sessions) from device_sessions), 2) as conversion_rate_pct;


-- ------------------------------------------------------------
-- Q5. contribution margin by SKU
-- revenue minus product cost per sku. needs cost_per_unit filled in
-- the products table. only the 6 main skus have costs; others show null.
-- ------------------------------------------------------------
select
    i.sku,
    p.product_name,
    sum(i.quantity)                                        as units_sold,
    round(sum(i.quantity * i.unit_price), 2)               as gross_revenue,
    round(sum(i.quantity * p.cost_per_unit), 2)            as total_cost,
    round(sum(i.quantity * i.unit_price)
        - sum(i.quantity * p.cost_per_unit), 2)            as contribution_margin,
    round(100.0 * (sum(i.quantity * i.unit_price) - sum(i.quantity * p.cost_per_unit))
                / nullif(sum(i.quantity * i.unit_price), 0), 1) as margin_pct
from order_items i
join products p on p.sku = i.sku
where p.cost_per_unit is not null
group by i.sku, p.product_name
order by contribution_margin desc;


-- ------------------------------------------------------------
-- extra: revenue by product (all skus, no cost needed) - supports the margin story
-- ------------------------------------------------------------
select
    i.sku,
    max(i.product_name)                      as product_name,
    sum(i.quantity)                          as units_sold,
    round(sum(i.quantity * i.unit_price), 2) as revenue
from order_items i
group by i.sku
order by revenue desc
limit 15;
