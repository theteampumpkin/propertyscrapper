import os
import requests
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# === CONFIG ===

MORTGAGE_RATE = 0.04   # 4% mortgage rate
DOWN_PAYMENT = 0.20    # 20% down
AMORT_YEARS = 25       # 25-year amortization

MULTIPLEX_TYPES = ["duplex", "triplex", "fourplex", "multiplex", "quadruplex", "4plex"]

AVG_RENT_MAP = {
    "London": 1500,
    "Kitchener": 1700,
    "Brantford": 1400
}

url = "https://api2.realtor.ca/Listing.svc/PropertySearch_Post"

headers = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    "origin": "https://www.realtor.ca",
    "priority": "u=1, i",
    "referer": "https://www.realtor.ca/",
    "sec-ch-ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
}

cookies = {
    "reese84": "cookie"   # replace with your actual cookie value
}

#London
dataLondon = {
    "ZoomLevel": "10",
    "LatitudeMax": "43.18728",
    "LongitudeMax": "-80.62437",
    "LatitudeMin": "42.70981",
    "LongitudeMin": "-81.87270",
    "Sort": "6-D",
    "PropertyTypeGroupID": "1",
    "TransactionTypeId": "2",
    "PropertySearchTypeId": "8",
    "PriceMin": "650000",
    "PriceMax": "850000",
    "UnitRange": "3-0",
    "Currency": "CAD",
    "IncludeHiddenListings": "false",
    "RecordsPerPage": "100",
    "ApplicationId": "1",
    "CultureId": "1",
    "Version": "7.0",
    "CurrentPage": "1"
}

#KWC
dataKWC = {
    "ZoomLevel": "11",
    "LatitudeMax": "43.54874",
    "LongitudeMax": "-80.16433",
    "LatitudeMin": "43.31188",
    "LongitudeMin": "-80.78850",
    "Sort": "6-D",
    "PropertyTypeGroupID": "1",
    "TransactionTypeId": "2",
    "PropertySearchTypeId": "8",
    "PriceMin": "650000",
    "PriceMax": "850000",
    "UnitRange": "3-0",
    "Currency": "CAD",
    "IncludeHiddenListings": "false",
    "RecordsPerPage": "100",
    "ApplicationId": "1",
    "CultureId": "1",
    "Version": "7.0",
    "CurrentPage": "1"
}

#Brantford
dataBrantford = {
    "ZoomLevel": "10",
    "LatitudeMax": "43.20706",
    "LongitudeMax": "-80.11805",
    "LatitudeMin": "43.08808",
    "LongitudeMin": "-80.43013",
    "Sort": "6-D",
    "PropertyTypeGroupID": "1",
    "TransactionTypeId": "2",
    "PropertySearchTypeId": "8",
    "PriceMin": "650000",
    "PriceMax": "850000",
    "UnitRange": "3-0",
    "Currency": "CAD",
    "IncludeHiddenListings": "false",
    "RecordsPerPage": "100",
    "ApplicationId": "1",
    "CultureId": "1",
    "Version": "7.0",
    "CurrentPage": "1"
}

# === FUNCTIONS ===

# ===== STEP 1. Fetch Latest Dataset from Apify =====
def fetch_dataset():
    try:
        all_listings = []
        responseLondon = requests.post(url, headers=headers, cookies=cookies, data=dataLondon)
        responseKWC = requests.post(url, headers=headers, cookies=cookies, data=dataKWC)
        responseBrantford = requests.post(url, headers=headers, cookies=cookies, data=dataBrantford)
        json_data_london = responseLondon.json()
        json_data_kwc = responseKWC.json()
        json_data_brantford = responseBrantford.json()

        print("✅ JSON response received:")
        #print(f"####################### London data #################### \n {json_data_london}")
        #print(f"####################### KWC data #################### \n {json_data_kwc}")
        #print(f"####################### Brantford data #################### \n {json_data_brantford}")

    except ValueError:
        print("⚠️ Response is not valid JSON. Here's the raw text:")
        print(response.text)
    
    all_listings = json_data_london['Results']
    all_listings.extend(json_data_kwc['Results'])
    all_listings.extend(json_data_brantford['Results'])

    return all_listings

    # return {
    #     "listings_london": json_data_london,
    #     "listings_kwc": json_data_kwc,
    #     "listings_brantford": json_data_brantford
    #     }


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
    building = item.get("Building", {}) or {}
    property_info = item.get("Property", {}) or {}
    address_info = property_info.get("Address", {}) or {}
    amenities = property_info.get("AmmenitiesNearBy", "") or ""

    # --- Property type filter ---
    prop_type = (building.get("Type") or "").strip()
    if not prop_type:
        return None

    prop_type_norm = prop_type.lower().replace("-", "").replace(" ", "")
    valid_types = [x.replace("-", "").replace(" ", "") for x in MULTIPLEX_TYPES]
    if prop_type_norm not in valid_types:
        return None

    # --- Basic property details ---
    price = property_info.get("Price", "N/A")
    price_value = property_info.get("PriceUnformattedValue", 0)
    if not price_value and isinstance(price, str) and "$" in price:
        try:
            price_value = int(price.replace("$", "").replace(",", "").strip())
        except:
            price_value = 0

    units = building.get("UnitTotal") or building.get("TotalUnits") or "N/A"
    beds = building.get("Bedrooms", "N/A")
    baths = building.get("BathroomTotal", "N/A")

    # --- Remarks cleanup ---
    import re
    remarks = item.get("PublicRemarks", "") or ""
    address_text = address_info.get("AddressText", "")

    # Try to parse address like: "415 CHATHAM Street|Brantford, Ontario N3S4J4"
    city, province = "Unknown", "Unknown"
    if "|" in address_text:
        try:
            parts = address_text.split("|")
            # Usually: [street, "City, Province Postal"]
            if len(parts) > 1:
                second_part = parts[1]
                # Split "Brantford, Ontario N3S4J4"
                city_part = second_part.split(",")[0].strip()
                city = city_part or "Unknown"
                if "," in second_part:
                    province = second_part.split(",")[1].split()[0].strip()
        except Exception:
            pass

    city = (
        address_info.get("City")
        or address_info.get("Municipality")
        or city
        or "Unknown"
    )

    community = (
        address_info.get("LocalLogicNeighbourHood")
        or address_info.get("Subdivision")
        or province
        or "Unknown Area"
    )

    if address_text:
        remarks = re.sub(re.escape(address_text), "", remarks, flags=re.IGNORECASE)
    remarks = re.sub(r"\([A-Za-z0-9]+\)", "", remarks)
    remarks = re.sub(r"\bWelcome to [^\n.?!]*[\n.?!-]+", "", remarks, flags=re.IGNORECASE)
    remarks = remarks.strip()

    # --- Extract first sentence with highlighted investment keywords ---
    summary_remarks = ""
    if remarks:
        first_sentence = remarks.split(".")[0].strip()
        keywords = ["income", "rent", "investment", "cashflow", "tenant", "legal", "triplex", "duplex", "multiplex"]
        for kw in keywords:
            if kw in first_sentence.lower():
                first_sentence = re.sub(f"(?i)({kw})", r"*\1*", first_sentence)
        summary_remarks = first_sentence + "."

    # --- Estimate cashflow ---
    cf = estimate_cashflow(price_value, units, city)
    if not cf:
        return None

    # --- Message formatting ---
    area_line = f"🔥 *Investment Opportunity in {city} - {community}*"
    property_details = (
        f"*Property Details*\n"
        f"- List Price: {price} | Units: {units} | Bedrooms: {beds} | Bathrooms: {baths}\n"
        f"- Type: {prop_type.title()}\n"
        f"- Amenities Nearby: {amenities}\n"
    )

    scenario = f"""
*💼 Opportunity For Investment Buyers*
    - Monthly Mortgage (20% down): ${cf['mortgage']:,}
    - Monthly Expenses: ${cf['expenses']:,}
    - Est. Income: ${cf['income']:,}/mo
    📈 *Get a Monthly Cashflow* of : ${cf['cashflow']:,}/mo from the property
    """

    disclaimer = (
        "\n"
        "_*Assumptions based on Current Mortgage Rates and Estimates:*_\n"
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
        "cashflow": cf["cashflow"],
        "city": city
    }

def prepare_whatsapp_message():
    # all_listings = []
    all_listings = fetch_dataset()
    city_groups = {}

    # all_listings = listings['listings_london']['Results']
    # all_listings.extend(listings['listings_kwc']['Results'])
    # all_listings.extend(listings['listings_brantford']['Results'])

    
    for item in all_listings:
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

    output_dir = r"C:\Workspace\pumpkinScrapper"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "output.txt")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(whatsapp_post)
