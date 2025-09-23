import os
import requests

# === CONFIG ===
APIFY_TOKEN = os.getenv("APIFY_TOKEN")  # set with: export APIFY_TOKEN="your-token"
DATASET_ID = "e0ZL4PDMfMJR4nEgt"  # now a single dataset

MORTGAGE_RATE = 0.04   # 4% mortgage rate
DOWN_PAYMENT = 0.20    # 20% down
AMORT_YEARS = 25       # 25-year amortization

MULTIPLEX_TYPES = ["duplex", "triplex", "fourplex", "multiplex", "quadruplex", "4plex"]

AVG_RENT_MAP = {
    "London": 1500,
    "Kitchener": 1700,
    "Brantford": 1400
}

# === FUNCTIONS ===

def fetch_dataset(dataset_id):
    url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={APIFY_TOKEN}"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()


def monthly_mortgage(principal, annual_rate=MORTGAGE_RATE, years=AMORT_YEARS):
    monthly_rate = annual_rate / 12
    n = years * 12
    return principal * (monthly_rate * (1 + monthly_rate) ** n) / ((1 + monthly_rate) ** n - 1)


def estimate_cashflow(price, units, city):
    avg_rent = AVG_RENT_MAP.get(city, 1500)
    try:
        units = int(units)
        price = int(str(price).replace("$", "").replace(",", ""))
    except:
        return None

    monthly_income = units * avg_rent
    mortgage_principal = price * (1 - DOWN_PAYMENT)
    mortgage_payment = monthly_mortgage(mortgage_principal)
    expenses = (price * 0.02) / 12
    cashflow = monthly_income - (mortgage_payment + expenses)

    return {
        "income": int(monthly_income),
        "mortgage": int(mortgage_payment),
        "expenses": int(expenses),
        "cashflow": int(cashflow)
    }


def format_property(item):
    building = item.get("Building", {})
    property_info = item.get("Property", {})
    address_info = property_info.get("Address", {})

    # Use City, fallback to Municipality, fallback to Unknown
    city = address_info.get("City") or address_info.get("Municipality") or "Unknown"

    prop_type = building.get("Type", "")
    if not prop_type:
        return None

    prop_type_norm = prop_type.lower().replace("-", "").replace(" ", "")
    valid_types = [x.replace("-", "").replace(" ", "") for x in MULTIPLEX_TYPES]
    if prop_type_norm not in valid_types:
        return None

    # Use LocalLogicNeighbourHood, fallback to Subdivision, fallback to Province, fallback to Unknown Area
    community = address_info.get("LocalLogicNeighbourHood") or address_info.get("Subdivision") or address_info.get("Province") or "Unknown Area"

    price = property_info.get("Price", "N/A")
    units = building.get("TotalUnits", building.get("UnitTotal", "N/A"))
    beds = building.get("Bedrooms", "N/A")
    baths = building.get("BathroomTotal", "N/A")
    import re
    remarks = item.get("PublicRemarks", "")
    # Remove property address (if present) and any MLS ID (e.g., (12345678) or similar)
    address_text = address_info.get("AddressText", "")
    if address_text:
        # Remove address text from remarks (case-insensitive)
        remarks = re.sub(re.escape(address_text), "", remarks, flags=re.IGNORECASE)
    # Remove any MLS ID in parentheses, e.g., (12345678) or (ABC12345)
    remarks = re.sub(r"\([A-Za-z0-9]+\)", "", remarks)
    remarks = remarks.strip()
    # Remove any phrase containing 'Welcome to [address]' even if not at the very start
    remarks = re.sub(r"\bWelcome to [^\n.?!]*[\n.?!-]+", "", remarks, flags=re.IGNORECASE)

    # Summarize remarks: take first sentence and highlight keywords
    summary_remarks = ""
    if remarks:
        # Extract first sentence
        first_sentence = remarks.split(".")[0].strip()
        # Highlight keywords if present
        keywords = ["income", "rent", "investment", "cashflow", "tenant", "legal", "triplex", "duplex", "multiplex"]
        for kw in keywords:
            if kw in first_sentence.lower():
                first_sentence = re.sub(f"(?i)({kw})", r"*\1*", first_sentence)
        summary_remarks = first_sentence + "."

    cf = estimate_cashflow(price, units, city)
    if not cf:
        return None

    summary = {
        "text": (
            f"🏠 {prop_type.title()} | {price} | 📍{city} - {community}\n"
            f"✅ {units} units | {beds} beds | {baths} baths\n"
            f"💰 Est. Income: ${cf['income']:,}/mo | 🏦 Mortgage: ${cf['mortgage']:,}/mo | 📉 Expenses: ${cf['expenses']:,}/mo | 📈 Cashflow: ${cf['cashflow']:,}/mo\n"
                + (f"💬 {summary_remarks}\n" if summary_remarks else "")
        ),
        "cashflow": cf['cashflow'],
        "city": city
    }

    if any(word in remarks.lower() for word in ["income", "rent", "cashflow"]):
        summary["text"] += "💡 Strong rental income potential\n"

    return summary


def prepare_whatsapp_message():
    listings = fetch_dataset(DATASET_ID)
    city_groups = {}

    # Group listings by city, only include cashflow > $500
    for item in listings:
        prop = format_property(item)
        if prop and prop["cashflow"] > 500:
            city_groups.setdefault(prop["city"], []).append(prop)

    message = "🔥 Top Investment Opportunities 🔥\n\n"

    # Define preferred city order
    preferred_order = ["London", "Kitchener", "Brantford"]
    # Sort cities: preferred first, then others alphabetically
    sorted_cities = preferred_order + sorted([c for c in city_groups if c not in preferred_order])

    for city in sorted_cities:
        if city not in city_groups:
            continue
        message += f"📍 {city}\n"
        top_props = sorted(city_groups[city], key=lambda x: x["cashflow"], reverse=True)[:4]
        for i, p in enumerate(top_props, start=1):
            message += f"{i}️⃣ {p['text']}\n"

    message += "📲 Reply *INVEST* to get full details & cashflow analysis."
    return message


if __name__ == "__main__":
    whatsapp_post = prepare_whatsapp_message()
    print("\n" + whatsapp_post + "\n")

    with open("multiplex_top_investment_message.txt", "w") as f:
        f.write(whatsapp_post)
