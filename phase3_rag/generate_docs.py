"""
Phase 3: Generate Synthetic Business Documents for RAG Pipeline
================================================================
Creates 10 realistic documents across 3 categories:
  - Supplier Contracts (5): Amul Dairy, PepsiCo Bev, Unilever FMCG,
    Suguna Poultry, LocalPro Fruits & Veg
  - Standard Operating Procedures (3): Inventory Replenishment,
    Cold Chain Management, Order Fulfillment
  - Return/Refund Policies (2): Customer Returns, Supplier Returns

Each document contains specific, query-able details (dates, thresholds,
penalty percentages, temperature ranges, SLA windows) so the RAG system
can demonstrate precise retrieval.

Output:  phase3_rag/documents/  (10 .txt files)
"""

import os
import random
from pathlib import Path
from datetime import date

OUT_DIR = Path(__file__).resolve().parent / "documents"

# =============================================================================
# DOCUMENT TEMPLATES
# =============================================================================

DOCUMENTS = [
    # ── SUPPLIER CONTRACTS ─────────────────────────────────────────────
    {
        "filename": "SUPPLIER_CONTRACT_Amul_Dairy_Products.txt",
        "content": """
================================================================================
        MASTER SUPPLY AGREEMENT — DAIRY & PERISHABLE DAIRY PRODUCTS
================================================================================

Agreement #:  SUP-AMD-2024-001
Parties:      AIDA Quick-Commerce Pvt Ltd ("BUYER")
              Amul Dairy Cooperative ("SUPPLIER")
Effective:    January 1, 2024
Term:         36 months, auto-renewing for 12-month periods unless terminated

1. PRODUCT SCOPE
   The SUPPLIER shall provide the following categories on a daily basis:
   (a) Fresh Milk (Full Cream, Toned, Double Toned) — 500ml and 1L packs
   (b) Paneer — 200g and 500g blocks
   (c) Fresh Cream — 250ml and 500ml tubs
   (d) Yogurt (Plain, Flavoured) — 200g and 400g cups
   (e) Cheese (Slices, Blocks, Spread) — 100g to 500g
   (f) Butter (Salted, Unsalted) — 100g and 500g packs
   (g) Buttermilk — 200ml and 1L packs

2. DELIVERY & LOGISTICS
   2.1 Delivery Frequency: Daily, 7 days per week (including public holidays).
   2.2 Delivery Windows: Two mandatory slots — 05:00–06:30 IST and 14:00–15:30 IST.
   2.3 SLA Requirement: 98% of all line items must be delivered within the
       scheduled window. Failure to meet SLA for 3 consecutive days triggers
       an automatic penalty review.
   2.4 Cold Chain: All products must be maintained at 0–4°C during transit.
       Temperature loggers must accompany every shipment. Any shipment with
       recorded temperature >6°C for more than 30 minutes shall be rejected
       in full at the SUPPLIER's cost.

3. QUALITY & SHELF LIFE
   3.1 Minimum Remaining Shelf Life at Delivery:
       - Milk & Buttermilk: 80% of total shelf life
       - Paneer & Cream:   70% of total shelf life
       - Yogurt:           75% of total shelf life
       - Cheese & Butter:  60% of total shelf life
   3.2 The BUYER reserves the right to conduct random quality tests on 5%
       of each shipment. Failed tests trigger a batch rejection.

4. PRICING & PAYMENT
   4.1 Prices are fixed quarterly. Price revision requests must be submitted
       45 days before the quarter end with supporting cost data.
   4.2 Payment Terms: Net-30 days from the date of invoice and receipt of goods.
   4.3 Volume Rebate: If quarterly offtake exceeds INR 25,00,000, a 3% rebate
       applies to the entire quarter's invoicing.
   4.4 Early Payment Discount: 2% discount if payment is made within 10 days.

5. RETURNS & CREDITS
   5.1 Spoilage Claims: Any product found spoiled or past its shelf life at
       the time of delivery must be reported within 4 hours of receipt.
       Credit notes will be issued within 3 business days.
   5.2 Customer Returns Due to Quality: If customer returns exceed 2% of
       total units sold in a month for quality reasons, the SUPPLIER shall
       investigate root cause and submit a corrective action report within
       7 calendar days.

6. PENALTIES & TERMINATION
   6.1 Late Delivery Penalty: 1.5% of the PO value for each hour of delay
       beyond the delivery window, capped at 15% of the PO value.
   6.2 Short Delivery: If fill rate drops below 90% for any 7-day rolling
       period, a penalty of 5% of the shortfall value applies.
   6.3 Termination: Either party may terminate with 90 days written notice.
       BUYER may terminate immediately if SUPPLIER fails the 98% SLA for
       10 or more days in any 30-day period.

7. FORCE MAJEURE
   7.1 Neither party shall be liable for failures caused by events beyond
       reasonable control including natural disasters, government orders,
       epidemics, or civil unrest. The affected party must notify the other
       within 24 hours and provide a recovery plan within 3 business days.

Signed:
For AIDA Quick-Commerce: _________________  Date: _______________
For Amul Dairy Coop:     _________________  Date: _______________
""",
    },
    {
        "filename": "SUPPLIER_CONTRACT_PepsiCo_Beverages.txt",
        "content": """
================================================================================
           BEVERAGE SUPPLY & DISTRIBUTION AGREEMENT — PEPSICO
================================================================================

Agreement #:  SUP-PEP-2024-002
Parties:      AIDA Quick-Commerce Pvt Ltd ("BUYER")
              PepsiCo India Holdings Pvt Ltd ("SUPPLIER")
Effective:    February 15, 2024
Term:         24 months with 2 optional 12-month renewals

1. PRODUCT RANGE
   - Carbonated Soft Drinks: Pepsi, Mirinda, 7Up, Mountain Dew (250ml cans,
     500ml bottles, 750ml bottles, 1.5L and 2L PET bottles)
   - Hydration: Aquafina packaged drinking water (500ml, 1L, 2L)
   - Energy: Sting energy drink (250ml)
   All SKU codes and barcodes are listed in Annexure A.

2. ORDERING & DELIVERY
   2.1 Minimum Order Quantity (MOQ): 50 cases per SKU per store per order.
   2.2 Order Cut-off: Orders placed before 16:00 IST will be delivered by
       10:00 IST the next business day. Orders after cut-off shift by one day.
   2.3 Delivery SLA: 95% case fill rate measured monthly. Below 95% triggers
       an automatic 2% invoice deduction for that month.
   2.4 Direct Store Delivery (DSD): SUPPLIER's merchandisers shall visit each
       dark store at least twice per week to rotate stock, check expiry dates,
       and restock shelves.

3. PROMOTIONS & MARKETING
   3.1 Joint Business Plan: BUYER and SUPPLIER shall agree on quarterly
       promotion calendars at least 30 days before the quarter starts.
   3.2 Promo Funding: SUPPLIER shall provide marketing funds equal to 4% of
       quarterly net invoicing for in-app banners, push notifications, and
       homepage features.
   3.3 Exclusive Windows: SUPPLIER gets a 7-day exclusive promotion window
       during key calendar events (New Year, Holi, Diwali, Cricket Finals)
       with no competing brands in the same subcategory.

4. PRICING
   4.1 Base prices are valid for 6 months from the agreement date.
   4.2 Commodity Surcharge: If sugar prices (as published by NCDEX) increase
       by more than 15% from the base index, SUPPLIER may add a surcharge of
       INR 1.50 per unit. The surcharge is removed when prices normalize.
   4.3 Payment: Net-45 days.

5. RETURNS & DAMAGED GOODS
   5.1 Transit Damage: Damaged cases must be reported within 24 hours with
       photographic evidence. 100% credit issued.
   5.2 Expired Stock: SUPPLIER shall collect and credit all expired stock
       within its shelf life + 7 days, capped at 3% of monthly volume.
   5.3 Customer Returns: BUYER may deduct customer refund amounts for quality
       complaints directly from the next invoice, up to 1% of invoice value.

6. TERMINATION
   6.1 Either party: 60 days written notice.
   6.2 BUYER may terminate immediately if SUPPLIER fails the 95% fill rate
       for 3 consecutive months.
""",
    },
    {
        "filename": "SUPPLIER_CONTRACT_Unilever_FMCG.txt",
        "content": """
================================================================================
            FMCG & HOME CARE SUPPLY AGREEMENT — UNILEVER
================================================================================

Agreement #:  SUP-UNI-2024-003
Parties:      AIDA Quick-Commerce Pvt Ltd ("BUYER")
              Hindustan Unilever Ltd ("SUPPLIER")
Effective:    March 1, 2024
Term:         24 months

1. PRODUCT CATEGORIES
   1.1 Home Care: Surf Excel (detergents), Vim (dishwash liquids & bars),
       Domex (floor & toilet cleaners), Cif (surface cleaners)
   1.2 Personal Care: Dove, Sunsilk, Clinic Plus (shampoos & conditioners);
       Pepsodent, Closeup (oral care); Lifebuoy, Lux, Dove (soaps & body wash)
   1.3 Foods & Refreshment: Knorr (soups, noodles), Kissan (jams, ketchups),
       Bru (instant coffee)

2. ORDER FULFILLMENT
   2.1 Order Frequency: BUYER may place orders daily.
   2.2 Lead Time: Standard SKUs — 2 business days. Promotional packs — 5 business days.
   2.3 Fill Rate Target: 97% line fill rate measured monthly.
   2.4 Case Pick Accuracy: 99.5%. Miscased or mispicked items to be credited
       at 110% of invoice value (10% administrative penalty).

3. PRICING & DISCOUNTS
   3.1 Trade Margin: BUYER receives a base trade margin of 12% on MRP for
       all Home Care SKUs and 10% on Personal Care SKUs.
   3.2 Quarterly Volume Rebate:
       - INR 15,00,000 – 25,00,000 quarterly: additional 1.5% rebate
       - INR 25,00,001 – 40,00,000 quarterly: additional 2.5% rebate
       - Above INR 40,00,000 quarterly: additional 4% rebate
   3.3 Payment Terms: Net-30 days with 2% early payment discount if paid
       within 15 days.

4. RETURNS POLICY
   4.1 Damaged on Arrival (DOA): Report within 48 hours. Full credit + INR 100
       per case handling charge.
   4.2 Slow-Moving Stock: BUYER may return up to 5% of quarterly volume of
       any SKU that has sold less than 30% of average category velocity for
       30 consecutive days. SUPPLIER issues credit at 85% of invoice value.
   4.3 Packaging Changes: When SUPPLIER changes packaging, all old-pack stock
       to be collected at SUPPLIER's cost within 7 days of new pack launch.

5. SERVICE LEVEL PENALTIES
   5.1 Fill Rate Penalty: For every 1% below 97% fill rate, a penalty of
       0.5% of the shortfall invoice value applies.
   5.2 Late Delivery: INR 2,500 per late purchase order per day beyond the
       committed lead time.
   5.3 Order Cancellation by SUPPLIER: If SUPPLIER cancels a confirmed PO,
       penalty of 3% of the cancelled PO value.
""",
    },
    {
        "filename": "SUPPLIER_CONTRACT_Suguna_Poultry_Meat.txt",
        "content": """
================================================================================
         MEAT & POULTRY SUPPLY AGREEMENT — SUGUNA FOODS
================================================================================

Agreement #:  SUP-SUG-2024-004
Parties:      AIDA Quick-Commerce Pvt Ltd ("BUYER")
              Suguna Foods Pvt Ltd ("SUPPLIER")
Effective:    January 20, 2024
Term:         12 months, auto-renewing monthly

*** THIS AGREEMENT INCLUDES CRITICAL FOOD SAFETY PROVISIONS ***

1. PRODUCT SPECIFICATIONS
   1.1 Fresh Chicken:
       (a) Whole Chicken (1.0–1.5 kg dressed weight) — halal certified
       (b) Chicken Breast Boneless (450–550g pack)
       (c) Chicken Curry Cut (900–1100g pack)
       (d) Chicken Thigh & Drumstick (450–550g pack)
   1.2 Fresh Fish:
       (a) Rohu / Katla (500–700g dressed weight)
       (b) Basa / Tilapia Fillets (450–550g pack)
   1.3 Eggs: Farm fresh white/brown eggs in trays of 6, 12, and 30.

2. FOOD SAFETY & COLD CHAIN (CRITICAL)
   2.1 Temperature Range: 0°C to 4°C throughout the supply chain from
       processing plant to dark store cold room.
   2.2 Each delivery must carry a time-temperature data logger printout.
       ANY breach of >4°C for >20 minutes renders the ENTIRE shipment
       non-compliant and subject to immediate rejection.
   2.3 FSSAI Compliance: SUPPLIER must maintain valid FSSAI license and
       provide monthly microbiological test reports (Total Plate Count,
       E. coli, Salmonella) for each product category.
   2.4 Traceability: Every pack must carry a batch code traceable to the
       farm and processing date. In the event of a food safety recall,
       SUPPLIER shall bear 100% of recall costs including customer refunds,
       logistics, and disposal.

3. ORDERING & DELIVERY
   3.1 BUYER places orders by 20:00 IST for next-morning delivery.
   3.2 Delivery Window: 04:30–06:30 IST, 365 days per year.
   3.3 SLA Target: 99% line fill rate. Meat and poultry stockouts in
       quick-commerce directly cause lost customer baskets — the BUYER
       considers this a "critical-to-business" metric.
   3.4 Short Delivery Penalty: For every unit short-delivered, a penalty
       of 2x the BUYER's unit margin applies (i.e., the SUPPLIER compensates
       for not just the cost but the lost profit).

4. SHELF LIFE & RETURNS
   4.1 At delivery, products must have minimum 3 days of remaining shelf life
       for fresh chicken/fish and minimum 10 days for eggs.
   4.2 Products not sold by expiry date: SUPPLIER shall collect and credit
       100% for unsold fresh product at store level. BUYER to flag expiring
       stock 48 hours before expiry.
   4.3 Weight Variance: Random weight checks on 2% of packs. If >5% of
       checked packs are underweight by >3%, the ENTIRE delivery batch is
       rejected at SUPPLIER's cost.

5. PRICING
   5.1 Prices are reviewed weekly every Sunday due to live-bird price
       fluctuation. Price changes take effect from Monday deliveries.
   5.2 Payment: Net-7 days (accelerated due to perishable nature and daily
       delivery cycle).
""",
    },
    {
        "filename": "SUPPLIER_CONTRACT_LocalPro_Fruits_Vegetables.txt",
        "content": """
================================================================================
       FRESH FRUITS & VEGETABLES SUPPLY AGREEMENT — LOCALPRO MANDI
================================================================================

Agreement #:  SUP-LPM-2024-005
Parties:      AIDA Quick-Commerce Pvt Ltd ("BUYER")
              LocalPro Mandi Aggregators Pvt Ltd ("SUPPLIER")
Effective:    April 1, 2024
Term:         12 months

1. PRODUCT RANGE (seasonal availability per Annexure A)
   1.1 Vegetables: Onion, Potato, Tomato, Lady Finger (Okra), Brinjal,
       Cauliflower, Cabbage, Spinach, Coriander, Green Chilli, Ginger, Garlic
   1.2 Fruits: Banana (6pc comb), Apple (4pc pack, imported and domestic),
       Grapes (500g punnet), Pomegranate (2pc pack), Papaya, Watermelon
   1.3 Pre-Cut / Value-Added: Peeled Garlic (200g), Cut Vegetables Combo
       (Soup mix, Salad mix — 400g packs).

2. QUALITY GRADING & REJECTION STANDARDS
   2.1 All produce is graded at source into Grade A (premium, >90% visual
       appeal), Grade B (standard, >70% visual appeal), and Grade C (cooking
       grade, >50% visual appeal, sold at discount).
   2.2 BUYER sells only Grade A and Grade B on the platform.
   2.3 REJECTION CRITERIA — Delivery is rejected if:
       (a) >10% of items show visible bruising, pest damage, or decay.
       (b) >15% weight variance on pre-packaged items.
       (c) Product temperature at delivery exceeds 10°C for leafy vegetables
           or 15°C for hard vegetables/fruits.
   2.4 Rejection Process: BUYER's store manager shall inspect and photograph
       rejected items within 30 minutes of delivery. SUPPLIER has 2 hours to
       deliver replacement stock or accept the rejection.

3. DELIVERY & ORDERING
   3.1 Orders placed by 22:00 IST for delivery by 05:30 IST next morning.
       Morning orders (placed 06:00–10:00 IST) delivered same day by 17:00 IST.
   3.2 Delivery SLA: Mandi-sourced produce — daily delivery 7 days/week.
   3.3 MOQ: INR 3,000 per store per delivery slot.

4. PRICING & PAYMENT
   4.1 Daily Price List: SUPPLIER publishes a price list by 18:00 IST each
       evening for next-day deliveries. Prices reflect that day's mandi rates
       plus a fixed 8% handling margin.
   4.2 Price Floors & Ceilings: For the top 10 items by volume, prices may
       not vary more than 25% day-over-day unless driven by mandi auction data.
   4.3 Payment: Net-15 days. No early payment discount due to thin margins.

5. WASTAGE SHARING
   5.1 BUYER and SUPPLIER share wastage costs 50:50 for produce that spoils
       within 24 hours of delivery IF the spoilage exceeds 8% of delivered
       quantity by value.
   5.2 BUYER shall provide daily wastage reports itemizing SKU, quantity, and
       spoilage reason (over-ripe, physical damage, pest, temperature abuse,
       or unknown). Reports must be submitted by 10:00 IST for previous day.

6. SUSTAINABILITY
   6.1 SUPPLIER shall minimize single-use plastic. By month 6, at least 40%
       of packaging by weight must be compostable or returnable.
   6.2 Unsold edible produce shall be donated to BUYER's food bank partner
       (Robin Hood Army) within 12 hours of expiry tagging.
""",
    },
    # ── STANDARD OPERATING PROCEDURES ──────────────────────────────────
    {
        "filename": "SOP_Inventory_Replenishment.txt",
        "content": """
================================================================================
    STANDARD OPERATING PROCEDURE: INVENTORY REPLENISHMENT
================================================================================

SOP #:       SOP-INV-001
Version:     3.2
Effective:   January 15, 2024
Owner:       Head of Supply Chain, AIDA Quick-Commerce
Approved By: Chief Operating Officer

1. PURPOSE
   To define the standard process for inventory replenishment across all
   AIDA dark stores, ensuring optimal stock levels that balance product
   availability against working capital and wastage costs.

2. SCOPE
   This SOP applies to all Store Managers, Inventory Analysts, and the
   Central Replenishment Team (CRT).

3. DEFINITIONS
   - PAR Level:  Periodic Automatic Replenishment level — the target
     quantity to maintain for each SKU at each store.
   - ROP (Reorder Point): The inventory level at which a new purchase order
     must be triggered. ROP = (Average Daily Sales × Supplier Lead Time) + Safety Stock.
   - Safety Stock: Buffer inventory to absorb demand variability and
     supply uncertainty. Calculated as 1.65 × Standard Deviation of Daily Sales
     × sqrt(Lead Time) for a 95% service level.
   - EOQ (Economic Order Quantity): Optimal order quantity that minimizes
     total holding + ordering cost.

4. REPLENISHMENT WORKFLOW

   4.1 AUTOMATED MONITORING
       (a) The inventory management system checks stock levels against ROP
           every 30 minutes for all SKUs across all stores.
       (b) A replenishment alert is generated when:
           - Available Qty <= Reorder Point, OR
           - Days of Stock (available qty / 7-day avg daily sales) < 2 days
       (c) Alerts are prioritized as:
           - PRIORITY 1 (P1): Stockout imminent — days of stock < 1 day.
             Action required within 30 minutes.
           - PRIORITY 2 (P2): Stockout within 48 hours — days of stock 1-2 days.
             Action required within 2 hours.
           - PRIORITY 3 (P3): Below target — available qty <= ROP but > 2 days.
             Action required before end of shift.

   4.2 PURCHASE ORDER CREATION
       (a) For P1 alerts: Store Manager auto-generates a PO using the
           system-recommended order quantity. No approval needed — system
           auto-sends to supplier.
       (b) For P2 alerts: Inventory Analyst reviews and adjusts the
           recommended quantity before approving.
       (c) For P3 alerts: CRT reviews during the scheduled replenishment
           window (09:00–11:00 IST and 16:00–18:00 IST).

   4.3 ORDER QUANTITY LOGIC
       (a) Default: Order up to PAR level.
       (b) Perishables with shelf life < 5 days: Order max(ROP trigger qty,
           1.5 × forecasted daily demand). Never order more than 3 days of
           forecasted demand for ultra-perishables (shelf life <= 3 days).
       (c) Promotion periods: Apply a promo lift factor of 1.8–2.5× (based on
           historical lift for the category) to the order quantity starting
           3 days before the promotion start date.

   4.4 EXCEPTIONS & OVERRIDES
       (a) Manual overrides above the system recommendation require Store
           Manager + Regional Manager approval for amounts >INR 50,000.
       (b) Supplier MOQ constraint: If MOQ exceeds the system-recommended
           order quantity, the Inventory Analyst must either:
           (i)  Bypass MOQ (if supplier allows), or
           (ii) Accept the overstock and flag for inter-store transfer review.

5. PERFORMANCE METRICS
   5.1 Fill Rate: % of customer orders fulfilled completely. Target: 98%.
   5.2 Inventory Turnover: COGS / Average Inventory Value. Target: 18–22× per year.
   5.3 Wastage %: Value of written-off stock / Total COGS. Target: <1.5%.
   5.4 Stockout Rate: % of SKU-hours at zero available inventory. Target: <0.5%.

6. REVIEW CADENCE
   - Daily: P1/P2 alert review at 09:00 stand-up.
   - Weekly: Inventory health dashboard review every Monday 14:00 IST.
   - Monthly: Full SOP review and parameter tuning (ROP, safety stock, PAR
     levels) using the previous 90 days of sales data.
""",
    },
    {
        "filename": "SOP_Cold_Chain_Management.txt",
        "content": """
================================================================================
       STANDARD OPERATING PROCEDURE: COLD CHAIN MANAGEMENT
================================================================================

SOP #:       SOP-CCM-002
Version:     2.1
Effective:   February 1, 2024
Owner:       Head of Quality Assurance

1. PURPOSE
   To define the temperature control requirements and monitoring procedures
   for all cold-chain products from supplier receipt through last-mile delivery.

2. TEMPERATURE ZONES & PRODUCT MAPPING
   +----------------------+------------------+-------------------------------+
   | ZONE                 | TEMP RANGE       | PRODUCT CATEGORIES            |
   +----------------------+------------------+-------------------------------+
   | Frozen               | -18°C to -22°C   | Ice cream, frozen vegetables, |
   |                      |                  | frozen paratha/naan, nuggets  |
   | Chilled - Dairy      | 0°C to 4°C       | Milk, paneer, cream, yogurt,  |
   |                      |                  | cheese, butter, buttermilk    |
   | Chilled - Meat/Fish  | 0°C to 2°C       | Chicken, fish fillets, eggs   |
   | Cool - Produce       | 4°C to 10°C      | Leafy veg, soft fruits        |
   | Ambient              | 18°C to 28°C     | FMCG, beverages, snacks       |
   +----------------------+------------------+-------------------------------+

3. MONITORING PROCEDURE
   3.1 COLD ROOM MONITORING
       (a) Every cold room is equipped with 4 IoT temperature sensors
           (one per corner) logging every 5 minutes.
       (b) If any sensor reads outside the zone range for >10 continuous
           minutes, an SMS alert is sent to the Store Manager and QA Head.
       (c) If the condition persists for >30 minutes, the product in that zone
           must be quarantined and a QA inspection is mandatory before it can
           be sold.

   3.2 DELIVERY VEHICLE MONITORING
       (a) Supplier vehicles must have calibrated temperature loggers.
           Data is downloaded at every store receiving bay.
       (b) Acceptance Criteria at Receiving:
           - Chilled products: internal product temperature <= 4°C
           - Frozen products: internal product temperature <= -15°C
       (c) Rejection Protocol: Product temperature out of range → immediately
           rejected. QA fills Form CCM-R01 (Rejection Record). Photo evidence
           of temperature display + product is mandatory.

   3.3 LAST-MILE DELIVERY
       (a) Delivery riders carry chilled/frozen items in insulated thermal
           bags with phase-change gel packs.
       (b) Bags must maintain <8°C for chilled and < -10°C for frozen for at
           least 45 minutes (maximum delivery radius time).
       (c) Gel packs are re-frozen overnight. QA audits gel pack rotation
           weekly — any pack showing visible damage or >6 months old is
           discarded and replaced.

4. POWER FAILURE & EMERGENCY PROTOCOL
   4.1 All cold rooms have 100% DG (diesel generator) backup with automatic
       transfer switch. UPS bridge covers the 15-second generator start gap.
   4.2 If power is not restored within 2 minutes of outage, Store Manager
       escalates to Facilities Head.
   4.3 If cold room temperature rises >2°C above the zone maximum and is not
       recovering within 45 minutes, all perishable stock in that zone must
       be moved to a backup cold room or a reefer truck.

5. AUDIT & COMPLIANCE
   5.1 Internal Audit: QA team conducts unannounced cold chain audits at each
       store once every 14 days. Audit covers: sensor calibration, logger
       data review, gel pack condition, and receiving log completeness.
   5.2 Non-Compliance Scoring:
       - Minor (e.g., 1 sensor out of calibration by <1°C): Verbal warning,
         re-calibrate within 24 hours.
       - Major (e.g., product temp >2°C out of range at receiving, not
         rejected): Written warning + mandatory re-training within 7 days.
       - Critical (e.g., cold room failure >1 hour with no action taken):
         Store Manager suspension pending investigation.
""",
    },
    {
        "filename": "SOP_Order_Fulfillment.txt",
        "content": """
================================================================================
          STANDARD OPERATING PROCEDURE: ORDER FULFILLMENT
================================================================================

SOP #:       SOP-OF-003
Version:     4.0
Effective:   March 1, 2024
Owner:       Head of Operations

1. OVERVIEW
   This SOP defines the end-to-end order fulfillment process from the moment
   a customer places an order on the AIDA app to delivery at the customer's
   doorstep.

2. FULFILLMENT STAGES & TIME TARGETS
   +--------------------+-------------------+----------------------------+
   | STAGE              | TIME TARGET       | RESPONSIBLE                |
   +--------------------+-------------------+----------------------------+
   | Order Received     | T+0 min           | System                     |
   | Picking Started    | T+2 min           | Store Picker               |
   | Picking Complete   | T+8 min           | Store Picker               |
   | Packing Complete   | T+12 min          | Store Packer               |
   | Handover to Rider  | T+15 min          | Store Dispatcher           |
   | Delivery Complete  | T+30 min (max)    | Delivery Rider             |
   +--------------------+-------------------+----------------------------+
   Note: T+30 min is the absolute maximum from order to doorstep. Target is
   T+22 min for orders within 2 km of the dark store.

3. PICKING PROCEDURE
   3.1 The AIDA Picker App displays items in optimized pick-path sequence
       (dairy → produce → meat → frozen → ambient → FMCG) to minimize
       temperature abuse.
   3.2 Substitution Rules:
       (a) If ordered item is out of stock, the app suggests the top 3
           substitutes ranked by: same subcategory + same brand > same
           subcategory + different brand > similar price point.
       (b) Customer pre-selected substitution preference (accept best match,
           no substitution, or call me) is honored.
       (c) Substitution value delta: if the substitute is cheaper, customer
           is refunded the difference. If more expensive, AIDA absorbs the
           difference (customer is not charged extra).

   3.3 Weight-Based Items: Picker weighs and inputs actual weight. System
       recalculates price. Tolerance: +/- 10% of ordered weight. If actual
       weight exceeds tolerance, the picker must choose a different unit.

4. PACKING PROCEDURE
   4.1 Temperature-Based Segregation:
       - Frozen items → Silver thermal bag with dry ice pack
       - Chilled items (dairy, meat) → Blue thermal bag with gel pack
       - Produce → Green breathable mesh bag
       - Ambient → Brown paper bag (standard)
   4.2 Fragile items (eggs, glass bottles, chips) are packed with bubble wrap
       and marked FRAGILE.
   4.3 QC Check: Packer must verify:
       (a) Item count matches order
       (b) No visible damage or expiry within 24 hours
       (c) Temperature-sensitive items in correct bag type

5. LAST-MILE DELIVERY
   5.1 Rider Assignment: System auto-assigns nearest available rider. If no
       rider is available within 2 minutes, order is flagged as "DELAYED"
       and the Store Manager is alerted.
   5.2 Delivery Attempts: Maximum 2 attempts. If first attempt fails (customer
       unavailable, gate closed, wrong address), rider calls customer. If
       unreachable, order returns to store and is marked for re-attempt or
       cancellation per customer preference.
   5.3 Contactless Delivery: Default is contactless — rider places bag at
       doorstep, rings/knocks, steps back 2 meters, and waits for verbal
       confirmation of receipt.

6. EXCEPTION HANDLING
   6.1 Order Cancellation:
       - Before picking: Instant refund, no questions.
       - After picking, before dispatch: Refund minus INR 20 restocking fee
         (waived for perishables to avoid wastage).
       - After dispatch: No cancellation allowed. Customer may refuse at
         doorstep (refund minus delivery fee).
   6.2 Missing Items: If customer reports missing items within 30 minutes of
       delivery, Store Manager verifies CCTV picking footage. Confirmed →
       immediate refund + INR 50 credit for inconvenience. Unconfirmed →
       escalated to Ops Head.
   6.3 Wrong Item Delivered: Immediate re-delivery of correct item at no
       charge + customer keeps wrong item as goodwill.

7. PERFORMANCE METRICS (DAILY DASHBOARD)
   - Picking Accuracy: Target >99.5%
   - Packing Time: Avg <4 min per order
   - Delivery TAT (Turnaround Time): Avg <25 min, P95 <35 min
   - Order Defect Rate: <0.5% (defect = wrong item, missing item, damaged,
     or late >40 min)
""",
    },
    # ── RETURN & REFUND POLICIES ───────────────────────────────────────
    {
        "filename": "POLICY_Customer_Returns_Refunds.txt",
        "content": """
================================================================================
             AIDA CUSTOMER RETURNS & REFUNDS POLICY
================================================================================

Policy #:    POL-CUST-001
Version:     5.0
Effective:   January 1, 2024
Last Updated: June 15, 2024

This policy is published on the AIDA app and governs all customer-initiated
returns, refunds, and complaint resolutions.

1. RETURN ELIGIBILITY BY CATEGORY

   1.1 PERISHABLES (Dairy, Meat, Fish, Produce, Bakery, Frozen Foods)
       (a) Return Window: Within 30 MINUTES of delivery.
       (b) Valid Reasons: Spoiled, expired, damaged, wrong item, or
           quality not as described (e.g., sour milk, bruised produce,
           off-smell meat).
       (c) Refund Method: 100% instant refund to source payment method +
           INR 50 goodwill credit for spoiled/expired items.
       (d) No return pickup required — customer may discard the item.
           Photo evidence is mandatory for the refund to be processed.

   1.2 BEVERAGES
       (a) Return Window: Within 24 hours of delivery.
       (b) Valid Reasons: Damaged packaging, seal broken, expired, wrong
           flavour/variant.
       (c) Refund: 100% refund. Pickup required only for wrong item (rider
           collects during next delivery run in the zone).

   1.3 FMCG & PACKAGED FOODS
       (a) Return Window: Within 48 hours of delivery.
       (b) Valid Reasons: Damaged, opened seal, expired, wrong variant.
       (c) Refund: 100% refund. Item pickup may be required at AIDA's
           discretion.

   1.4 ALL OTHER CATEGORIES (Non-Food)
       (a) Return Window: 7 calendar days.
       (b) Valid Reasons: Defective, damaged, wrong item, or "changed my mind"
           (for unopened items only).
       (c) Refund: 100% for defective/damaged/wrong. 85% for change-of-mind
           returns (15% restocking fee). Pickup is free for defective items;
           INR 30 pickup charge for change-of-mind.

2. REFUND PROCESSING TIMELINES
   2.1 Digital Wallets (Paytm, PhonePe, GPay): Instant upon return approval.
   2.2 Credit/Debit Cards: 3–5 business days (bank processing time).
   2.3 Net Banking: 2–4 business days.
   2.4 AIDA Wallet Credit: Instant, with 5% bonus value for choosing wallet
       credit over bank refund (capped at INR 100 bonus per order).

3. QUALITY COMPLAINT ESCALATION
   3.1 If a customer reports 3 or more quality issues within a 30-day period,
       the account is flagged for a "quality review call" by the Customer
       Experience team.
   3.2 For any single order with total value >INR 2,000 and a quality
       complaint, the Store Manager must personally call the customer within
       2 hours.

4. FRAUD PREVENTION
   4.1 Customers with >5 returns in a 30-day window or >INR 5,000 in refund
       value per month are flagged for manual review.
   4.2 Accounts found to be abusing the return policy (e.g., claiming damage
       on every order) may have return privileges restricted to "pickup +
       inspection required" mode for 90 days.

5. EXCEPTIONS — NO REFUNDS FOR:
   (a) Perishables reported >30 minutes after delivery.
   (b) Items where the customer acknowledges receiving the correct item
       at the time of delivery (photo of accepted order).
   (c) Items damaged due to customer mishandling after delivery.
   (d) Change-of-mind on opened/used non-food products.
""",
    },
    {
        "filename": "POLICY_Supplier_Returns_Claims.txt",
        "content": """
================================================================================
            AIDA SUPPLIER RETURNS & CLAIMS POLICY
================================================================================

Policy #:    POL-SUP-002
Version:     3.1
Effective:   February 1, 2024
Owner:       AIDA Finance & Supply Chain

1. SCOPE
   This policy defines the process for AIDA to return goods to suppliers and
   file claims for: (a) damaged-on-arrival goods, (b) short-shipped quantities,
   (c) expired or short-dated products, (d) quality failures, and (e) goods
   recalled under food safety notices.

2. CLAIM CATEGORIES & TIMELINES

   2.1 DAMAGE ON ARRIVAL (DOA)
       (a) Reporting Window: Within 4 hours of receiving for perishables;
           24 hours for ambient/FMCG.
       (b) Evidence Required: Photo of damaged goods showing batch code/label,
           signed delivery receipt noting damage.
       (c) Supplier Response: Credit note within 3 business days.
       (d) Disputed Claims: Escalated to joint QA inspection within 48 hours.

   2.2 SHORT SHIPMENT
       (a) Reporting Window: Within 2 hours of receiving.
       (b) Evidence: Receiving team counts goods within 30 minutes of
           unloading. Shortages must be noted on the delivery challan AND
           confirmed by the delivery driver's signature.
       (c) Resolution: Supplier to deliver short quantity same-day (for
           perishables) or next-day (ambient), OR issue credit note within
           1 business day if redelivery is not feasible.

   2.3 EXPIRED / SHORT-DATED GOODS
       (a) Definition: Product delivered with remaining shelf life below the
           minimum specified in the respective supplier contract.
       (b) Reporting Window: Before the goods are accepted into inventory
           (i.e., at the receiving stage).
       (c) Resolution: Goods rejected immediately. Supplier credited 100%
           within 2 business days.

   2.4 QUALITY FAILURE (POST-RECEIVING)
       (a) If a quality issue is discovered after goods have been accepted
           into inventory (e.g., spoilage within 24 hours, foreign object
           found by customer), the Store Manager files a Quality Incident
           Report (QIR) within 1 hour of discovery.
       (b) Evidence: Photos, batch code, temperature log at time of issue,
           and retained sample in cold storage.
       (c) Investigation: Supplier has 48 hours to investigate and respond.
           If supplier does not respond within 48 hours, the claim is
           auto-approved and deducted from the next invoice.

   2.5 FOOD SAFETY RECALL
       (a) If a product is subject to an FSSAI-mandated or supplier-initiated
           recall, SUPPLIER bears 100% of costs: customer refunds, logistics
           (reverse pickup), disposal, and any regulatory fines.
       (b) AIDA will remove the product from the app within 15 minutes of
           receiving a recall notice.

3. FINANCIAL SETTLEMENT
   3.1 All approved credits and penalties are settled via deduction from the
       next payment run to the supplier (not via separate invoice).
   3.2 AIDA Finance issues a Debit Note for every deduction. The Debit Note
       references the original PO number, delivery challan number, and QIR
       reference (if applicable).
   3.3 Penalties specified in supplier contracts (late delivery penalty, fill
       rate penalty, etc.) are applied automatically by the AP system based
       on PO-vs-receipt data — no manual claim required.

4. SUPPLIER DISPUTE RESOLUTION
   4.1 Supplier may dispute any claim within 7 calendar days of the debit
       note date.
   4.2 Disputes are reviewed by a joint committee (AIDA Procurement Head +
       Supplier Account Manager) every 15 days.
   4.3 Unresolved disputes older than 30 days are escalated to AIDA COO and
       supplier's Regional Director.

5. SUPPLIER SCORECARD
   5.1 Every supplier is scored monthly on:
       - Quality Score (defect rate): 40% weight
       - Delivery Score (on-time + fill rate): 40% weight
       - Claims Cooperation (response time, dispute rate): 20% weight
   5.2 Suppliers scoring <70/100 for 2 consecutive months are placed on a
       Performance Improvement Plan (PIP) lasting 60 days.
   5.3 PIP failure → supplier is de-listed and replaced within 30 days.
""",
    },
]

# =============================================================================
# MAIN
# =============================================================================

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("AIDA Phase 3 — Generating Synthetic Business Documents")
    print("=" * 60)

    for doc in DOCUMENTS:
        path = OUT_DIR / doc["filename"]
        # Strip leading \n from content for clean file start
        content = doc["content"].lstrip("\n")
        path.write_text(content, encoding="utf-8")
        print(f"  OK {path.name}  ({len(content):,} chars)")

    print(f"\nGenerated {len(DOCUMENTS)} documents in {OUT_DIR}/")
    print("Next step: python phase3_rag/embed_docs.py")


if __name__ == "__main__":
    main()
