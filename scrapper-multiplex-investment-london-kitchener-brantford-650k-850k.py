import os
import requests

# === CONFIG ===
APIFY_TOKEN = os.getenv("APIFY_TOKEN")  # set with: export APIFY_TOKEN="your-token"
DATASET_ID = "8kqlg2ETJx08NDuUx"  # now a single dataset

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
    ameneties = property_info.get("AmmenitiesNearBy", [])

    city = address_info.get("City") or address_info.get("Municipality") or "Unknown"

    prop_type = building.get("Type", "")
    if not prop_type:
        return None

    prop_type_norm = prop_type.lower().replace("-", "").replace(" ", "")
    valid_types = [x.replace("-", "").replace(" ", "") for x in MULTIPLEX_TYPES]
    if prop_type_norm not in valid_types:
        return None

    community = (
        address_info.get("LocalLogicNeighbourHood")
        or address_info.get("Subdivision")
        or address_info.get("Province")
        or "Unknown Area"
    )

    price = property_info.get("Price", "N/A")
    units = building.get("TotalUnits", building.get("UnitTotal", "N/A"))
    beds = building.get("Bedrooms", "N/A")
    baths = building.get("BathroomTotal", "N/A")

    import re
    remarks = item.get("PublicRemarks", "")
    address_text = address_info.get("AddressText", "")
    if address_text:
        remarks = re.sub(re.escape(address_text), "", remarks, flags=re.IGNORECASE)
    remarks = re.sub(r"\([A-Za-z0-9]+\)", "", remarks)
    remarks = remarks.strip()
    remarks = re.sub(r"\bWelcome to [^\n.?!]*[\n.?!-]+", "", remarks, flags=re.IGNORECASE)

    summary_remarks = ""
    if remarks:
        first_sentence = remarks.split(".")[0].strip()
        keywords = ["income", "rent", "investment", "cashflow", "tenant", "legal", "triplex", "duplex", "multiplex"]
        for kw in keywords:
            if kw in first_sentence.lower():
                first_sentence = re.sub(f"(?i)({kw})", r"*\1*", first_sentence)
        summary_remarks = first_sentence + "."

    cf = estimate_cashflow(price, units, city)
    if not cf:
        return None

    # WhatsApp-style message format
    area_line = f"🔥 *Investment Opportunity in {city} - {community}*"
    property_details = (
        f"*Property Details*\n"
        f"- List Price: {price} | Units: {units} | Bedrooms: {beds} | Bathrooms: {baths}\n"
        f"- Type: {prop_type.title()}\n"
        f"- Ameneties Nearby: {ameneties}\n"
        ##f"- Address: {address_text}\n"
    )

    scenario = f"""
*💼 Opportunity For Investment Buyers*
    - Monthly Mortgage (20% down): ${cf['mortgage']:,}
    - Monthly Expenses: ${cf['expenses']:,}
    - Est. Income: ${cf['income']:,}/mo
    📈 *Get a Monthly Cashflow* of : ${cf['cashflow']:,}/mo from the property"
    """
    disclaimer = (
        "\n"
        "_*Assumptions based on Current Mortgage Rates and Estimates :*_\n"
        f"Purchase Price as is - {price}\n"
        f"Mortgage Rate - {MORTGAGE_RATE*100:.2f}%\n"
        f"{AMORT_YEARS} year amortization\n"
        f"Average rent per unit: ${AVG_RENT_MAP.get(city, 1500)}.\n"
    )
    summary_remarks_section = f"💬 {summary_remarks}\n" if summary_remarks else ""
    exclusive_section = (
        "\n\n"
        "📞 *Contact Details*\n"
        "To get PreApproved for these deals reach out to Preet (Mortgage Agent) from DLC Keystone\n"
        "DM -> +1(905)462-6007\n"
        "\n\n"
        "📩 *Property details exclusive for soldbyTeamPumpkin clients, DM for more information*\n"
        "DM -> +1(437)318-8126\n"
        "\n"
    )
    text = f"{area_line}\n{property_details}{disclaimer}{scenario}\n{summary_remarks_section}{exclusive_section}"
    return {
        "text": text,
        "cashflow": cf['cashflow'],
        "city": city
    }


def prepare_whatsapp_message():
    listings = fetch_dataset(DATASET_ID)
    city_groups = {}

    for item in listings:
        prop = format_property(item)
        if prop and prop["cashflow"] > 500:
            city_groups.setdefault(prop["city"], []).append(prop)

    message = "🔥 Top Investment Opportunities 🔥\n\n"

    preferred_order = ["London", "Kitchener", "Brantford"]
    sorted_cities = preferred_order + sorted([c for c in city_groups if c not in preferred_order])

    for city in sorted_cities:
        if city not in city_groups:
            continue
       ## message += f"📍 {city}\n"
        top_props = sorted(city_groups[city], key=lambda x: x["cashflow"], reverse=True)[:4]
        for i, p in enumerate(top_props, start=1):
            message += f"{p['text']}\n"

    message += "📲 Reply *INVEST* to get full details & cashflow analysis."

    # === Add Exclusive Section ===
    exclusive_section = (
        "\n"
        "📞 *Contact Details*\n"
        "To get PreApproved for these deals reach out to Preet (Mortgage Agent) from DLC Keystone\n"
        "DM -> +1(905)462-6007\n"
        "\n"
        "📩 *Property details exclusive for soldbyTeamPumpkin clients, DM for more information*\n"
        "DM -> +1(437)318-8126\n"
        "\n"
    )
    message += exclusive_section

    return message


if __name__ == "__main__":
    whatsapp_post = prepare_whatsapp_message()
    print("\n" + whatsapp_post + "\n")

    output_dir = r"C:\Users\user\pumpkinScrapper"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "output.txt")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(whatsapp_post)
