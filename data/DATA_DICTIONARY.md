# Data dictionary

Source: Shopify exports from the store (orders, customers, sessions-by-device).
Raw exports are **not committed** — they contain real customer PII. `prepare_data.py`
turns them into the anonymised `clean/*.csv` the project loads.

## orders (one row per order)
| column | meaning |
|---|---|
| order_name | Shopify order name (e.g. #cf2073) |
| customer_hash | anonymised customer key (sha1 of email); blank for guest orders |
| financial_status | paid / partially_paid / pending / refunded / … |
| subtotal, shipping, taxes, total | order amounts (scaled by constant, INR) |
| discount_code, discount_amount | discount applied |
| refunded_amount | amount refunded |
| created_at, order_date | order timestamp / date |
| channel | sales channel (mapped from Shopify Source id) |
| payment_method | GoKwik UPI, Razorpay, Cashfree, etc. |
| ship_city, ship_province, ship_country | shipping location |

## order_items (one row per line item)
| column | meaning |
|---|---|
| order_name | FK to orders |
| sku | product SKU |
| product_name | product title |
| quantity | units in the line |
| unit_price | price per unit (scaled, INR) |
| line_discount | discount on the line |

## customers (one row per customer)
| column | meaning |
|---|---|
| customer_hash | anonymised key |
| city, province, country | default address |
| total_spent | lifetime spend (scaled, INR) |
| total_orders | lifetime order count |
| accepts_email | 1/0 email opt-in |

## products (one row per SKU)
| column | meaning |
|---|---|
| sku | product SKU |
| product_name | title |
| cost_per_unit | landed cost (₹90/bottle × bottles in pack, scaled) |

## device_sessions (aggregate)
| column | meaning |
|---|---|
| device_type | mobile / desktop / tablet / other |
| visitors, sessions | counts (not joinable to orders) |
