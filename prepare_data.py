"""
prepare_data.py
Cleans and anonymises the raw Shopify exports, then writes tidy CSVs ready to
load into Postgres. Run once; outputs land in ./clean/.

Notes to self:
 - money is scaled by a fixed factor (SCALE) so the repo is public-safe but every
   ratio / trend stays identical. factor lives only here, never in the output.
 - emails + names -> sha1 short hashes so repeat-buyer linking still works.
 - Shopify order export = one row per line item; order-level fields (Total, etc.)
   only populate on the FIRST row of each order. handled below.
 - customer IDs come out of Shopify with a junk leading apostrophe -> strip it.
"""
import csv, glob, hashlib, os, re

csv.field_size_limit(10_000_000)
RAW = "/mnt/user-data/attachments/93e72a37-1ab4-50c8-afd9-75face7a035a"
OUT = "clean"
os.makedirs(OUT, exist_ok=True)

SCALE = 0.8137          # hidden money multiplier (not round on purpose)
SALT  = "cf_attar_2026" # hash salt

def h(s):
    s = (s or "").strip().lower()
    if not s:
        return ""
    return "c_" + hashlib.sha1((SALT + s).encode()).hexdigest()[:10]

def money(x):
    try:
        return round(float(x) * SCALE, 2)
    except (TypeError, ValueError):
        return None

def clean_id(x):
    return re.sub(r"[^0-9]", "", x or "")   # drop the stray apostrophe etc.

# Source (sales channel) id -> readable label. The big numeric ones are Shopify
# channel/app ids; mapping the ones that actually show up in the data.
SOURCE_MAP = {
    "395888001025": "Custom Checkout (GoKwik)",
    "372588412929": "Online Store",
    "396566429697": "Subscription (Razorpay)",
    "web":          "Web",
    "shopify_draft_order": "Draft/Manual",
    "1608309":      "POS / Other",
}
def source_label(s):
    s = (s or "").strip()
    return SOURCE_MAP.get(s, "Other" if s else "Unknown")

# ---------------------------------------------------------------- orders
order_files = sorted(glob.glob(f"{RAW}/*orders_export_*.csv"))
orders_out = open(f"{OUT}/orders.csv", "w", newline="", encoding="utf-8")
items_out  = open(f"{OUT}/order_items.csv", "w", newline="", encoding="utf-8")
ow = csv.writer(orders_out); iw = csv.writer(items_out)
ow.writerow(["order_name","customer_hash","financial_status","currency",
             "subtotal","shipping","taxes","total","discount_code","discount_amount",
             "refunded_amount","created_at","order_date","channel","payment_method",
             "ship_city","ship_province","ship_country"])
iw.writerow(["order_name","sku","product_name","quantity","unit_price","line_discount"])

n_orders = n_items = 0
for f in order_files:
    with open(f, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            name = row.get("Name","").strip()
            # a line item always carries sku/qty; emit it
            sku = (row.get("Lineitem sku","") or "").strip()
            qty = (row.get("Lineitem quantity","") or "").strip()
            if sku or qty:
                iw.writerow([
                    name, sku, (row.get("Lineitem name","") or "").strip(),
                    qty or 0, money(row.get("Lineitem price")),
                    money(row.get("Lineitem discount")),
                ])
                n_items += 1
            # order header row = the one with a Total
            tot = (row.get("Total","") or "").strip()
            if tot:
                created = (row.get("Created at","") or "").strip()
                ow.writerow([
                    name, h(row.get("Email")), (row.get("Financial Status","") or "").strip(),
                    row.get("Currency","INR"),
                    money(row.get("Subtotal")), money(row.get("Shipping")),
                    money(row.get("Taxes")), money(row.get("Total")),
                    (row.get("Discount Code","") or "").strip(), money(row.get("Discount Amount")),
                    money(row.get("Refunded Amount")),
                    created, created[:10],
                    source_label(row.get("Source")),
                    (row.get("Payment Method","") or "").strip(),
                    (row.get("Shipping City","") or "").strip().title(),
                    (row.get("Shipping Province","") or "").strip(),
                    (row.get("Shipping Country","") or "").strip(),
                ])
                n_orders += 1
orders_out.close(); items_out.close()
print(f"orders: {n_orders}  line items: {n_items}")

# ---------------------------------------------------------------- customers
cust_out = open(f"{OUT}/customers.csv", "w", newline="", encoding="utf-8")
cw = csv.writer(cust_out)
cw.writerow(["customer_hash","city","province","country",
             "total_spent","total_orders","accepts_email"])
n_cust = 0
with open(f"{RAW}/5e8bb528-customers_export.csv", encoding="utf-8") as fh:
    for row in csv.DictReader(fh):
        email = row.get("Email","")
        # hash on email where present, else on the (cleaned) customer id so the row
        # still has a stable anonymous key
        key = email if (email or "").strip() else clean_id(row.get("Customer ID"))
        cw.writerow([
            h(key),
            (row.get("Default Address City","") or "").strip().title(),
            (row.get("Default Address Province Code","") or "").strip(),
            (row.get("Default Address Country Code","") or "").strip(),
            money(row.get("Total Spent")),
            (row.get("Total Orders","") or "0").strip(),
            1 if (row.get("Accepts Email Marketing","").strip().lower()=="yes") else 0,
        ])
        n_cust += 1
cust_out.close()
print(f"customers: {n_cust}")

# ---------------------------------------------------------------- device sessions
dev_out = open(f"{OUT}/device_sessions.csv", "w", newline="", encoding="utf-8")
dw = csv.writer(dev_out)
dw.writerow(["device_type","visitors","sessions"])
with open(f"{RAW}/5634b633-Sessions_by_device_type_-_2026-06-01_-_2026-10-31.csv", encoding="utf-8") as fh:
    for row in csv.DictReader(fh):
        dw.writerow([row.get("Session device type",""),
                     row.get("Online store visitors",""),
                     row.get("Sessions","")])
dev_out.close()
print("device sessions written")

# ---------------------------------------------------------------- products + costs
# cost_per_unit = hand-entered landed cost per unit. 0 => unknown, handled in SQL.
# prices here are the usual selling price (scaled) for reference only.
PRODUCTS = [
    # sku, product, cost_per_unit(raw INR, pre-scale)
    # landed cost = Rs.90 per bottle, so bundles scale by bottle count
    ("MOHINI-P1","Mohini Itr - Pack of 1",       90),   # 1 bottle
    ("MOHINI-P2","Mohini Itr - Pack of 3",       270),  # 3 bottles
    ("MOHINI-P3","Mohini Itr - Buy 3 Get 1",     360),  # 4 bottles
    ("KAMDEV-P1","Bad Boy - Pack of 1",          90),   # 1 bottle
    ("KAMDEV-P2","Bad Boy - Buy 2 Get 1",        270),  # 3 bottles
    ("KAMDEV-P3","Bad Boy - Buy 3 Get 1",        360),  # 4 bottles
]
pw = csv.writer(open(f"{OUT}/products.csv","w",newline="",encoding="utf-8"))
pw.writerow(["sku","product_name","cost_per_unit"])
for sku,name,cost in PRODUCTS:
    pw.writerow([sku, name, money(cost) if cost else ""])
print("products (costs pending) written")
print("done.")
