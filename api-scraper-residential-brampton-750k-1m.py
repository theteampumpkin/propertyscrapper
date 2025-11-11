import os
import requests
import math
from datetime import datetime
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ===== CONFIG =====
MORTGAGE_RATE = 0.04                     # 4% interest
AMORTIZATION_YEARS = 30
BASEMENT_RENT = 1800
UPSTAIRS_RENT = 3000
CURRENT_YEAR = datetime.now().year
TOP_N = 5
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

data = {
    "ZoomLevel": "10",
    "LatitudeMax": "43.96034",
    "LongitudeMax": "-79.13541",
    "LatitudeMin": "43.48894",
    "LongitudeMin": "-80.38373",
    "Sort": "6-D",
    "PropertyTypeGroupID": "1",
    "TransactionTypeId": "2",
    "PropertySearchTypeId": "1",
    "PriceMin": "700000",
    "PriceMax": "1000000",
    "BedRange": "4-0",
    "BathRange": "3-0",
    "BuildingTypeId": "1",
    "ConstructionStyleId": "3",
    "Keywords": "Legal BASEMENT",
    "Currency": "CAD",
    "IncludeHiddenListings": "false",
    "RecordsPerPage": "100",
    "ApplicationId": "1",
    "CultureId": "1",
    "Version": "7.0",
    "CurrentPage": "1"
}



# ===== STEP 1. Fetch Latest Dataset from Apify =====
def fetch_latest_properties():
    response = requests.post(url, headers=headers, cookies=cookies, data=data)
    try:
        json_data = response.json()
        print("✅ JSON response received:")
        print(json_data)
    except ValueError:
        print("⚠️ Response is not valid JSON. Here's the raw text:")
        print(response.text)
    
    return json_data

# ===== STEP 2. Mortgage Helper Functions =====
def cmhc_premium_rate(downpayment_percent):
    if downpayment_percent < 0.10:
        return 0.04
    elif downpayment_percent < 0.15:
        return 0.031
    elif downpayment_percent < 0.20:
        return 0.028
    return 0.0

def calculate_monthly_payment(price, downpayment_percent=0.05, rate=MORTGAGE_RATE, years=AMORTIZATION_YEARS):
    """
    Calculate mortgage with minimum downpayment rules + CMHC insurance if <20%.
    """
    downpayment = price * downpayment_percent
    mortgage_amount = price - downpayment

    # CMHC insurance estimate (if <20% downpayment)
    cmhc_fee = cmhc_premium_rate(downpayment_percent) * mortgage_amount
    mortgage_amount += cmhc_fee

    monthly_rate = rate / 12
    n_payments = years * 12
    monthly_payment = mortgage_amount * (monthly_rate * (1 + monthly_rate) ** n_payments) / ((1 + monthly_rate) ** n_payments - 1)
    return monthly_payment, downpayment

# ===== STEP 3. Filter Listings =====
LEGAL_BASEMENT_KEYWORDS = [
    "legal basement", "separate entrance", "in-law suite",
    "second dwelling", "income potential", "finished basement"
]

def has_legal_basement(description: str) -> bool:
    description = description.lower()
    return any(kw in description for kw in LEGAL_BASEMENT_KEYWORDS)

CURRENT_YEAR = datetime.now().year

def has_legal_basement(description):
    """Check if the property description indicates a legal basement apartment."""
    keywords = [
        "legal basement", "second dwelling", "registered basement",
        "2nd unit", "legal second unit", "income suite", "dual dwelling"
    ]
    return any(k in description for k in keywords)

def parse_bedrooms(bedroom_str):
    """Convert a '3 + 2' style string into total integer bedrooms."""
    if not bedroom_str:
        return 0
    parts = bedroom_str.replace(" ", "").split("+")
    try:
        return sum(int(p) for p in parts if p.isdigit())
    except ValueError:
        return 0

def filter_properties(data):
    """Filter properties meeting specific conditions from the Realtor JSON file."""
    results = data.get("Results", [])
    filtered = []

    for prop in results:
        try:
            building = prop.get("Building", {})
            property_info = prop.get("Property", {})
            land = prop.get("Land", {})
            description = (prop.get("PublicRemarks", "")).lower()

            # Bedrooms and bathrooms
            bedrooms = parse_bedrooms(building.get("Bedrooms", "0"))
            bathrooms = int(building.get("BathroomTotal", 0))

            # Parking
            parking = int(property_info.get("ParkingSpaceTotal", 0))

            # Skip missing or incomplete data
            if bedrooms < 3 or bathrooms < 2 or parking < 2:
                continue

            # Filter for legal basement
            if not has_legal_basement(description):
                continue

            # Extract address info
            address_info = property_info.get("Address", {})
            address_text = address_info.get("AddressText", "")
            area = ""
            if "|" in address_text:
                area = address_text.split("|")[1].split(",")[0].strip()

            # Collect extra info
            price = float(property_info.get("PriceUnformattedValue", 0))
            amenities = property_info.get("AmmenitiesNearBy", "")
            lot_size = land.get("SizeTotal", "")
            basement_features = building.get("BasementFeatures", "")

            filtered.append({
                "mlsNumber": prop.get("MlsNumber", ""),
                "area": area,
                "bedrooms": bedrooms,
                "bathrooms": bathrooms,
                "parking": parking,
                "description": description,
                "price": price,
                "amenities": amenities,
                "lot_size": lot_size,
                "image": (
                    property_info.get("Photo", [{}])[0].get("HighResPath", "")
                    if property_info.get("Photo") else ""
                ),
                "url": "https://www.realtor.ca" + prop.get("RelativeURLEn", ""),
            })

        except Exception as e:
            continue

    return filtered

def _filter_properties(properties):
    filtered = []
    for prop in properties['Results']:
        print(f"Property details {prop['Property']}")
        try:
            building = prop.get("Building", {})
            property_info = prop.get("Property", {})

            # Bedrooms: sum of above and below ground
            bedrooms_above = int(building.get("BedroomsAboveGround", 0))
            bedrooms_below = int(building.get("BedroomsBelowGround", 0))
            bedrooms = bedrooms_above + bedrooms_below

            # Bathrooms
            bathrooms = int(building.get("BathroomTotal", 0))

            # Parking
            parking = int(property_info.get("ParkingSpaceTotal", 0))

            # Year built: not available, so skip this filter or use DisplayAsYears as age
            age = building.get("DisplayAsYears")
            year_built = CURRENT_YEAR - int(age) if age and age.isdigit() else CURRENT_YEAR

            # Description: use PublicRemarks and BasementFeatures
            description = (prop.get("PublicRemarks", "") + " " + building.get("BasementFeatures", "")).lower()

            if (bedrooms >= 3 and bathrooms >= 2 and parking >= 2 and 
                (CURRENT_YEAR - year_built) <= 35 and has_legal_basement(description)):
                address_text = property_info.get("Address", {}).get("AddressText", "")
                area = ""
                if "|" in address_text:
                    area = address_text.split("|")[1].split(",")[0].strip()
                amenities = property_info.get("AmmenitiesNearBy", "")
                lot_size = prop.get("Land", {}).get("SizeTotal", "")
                basement_features = building.get("BasementFeatures", "")
                if amenities and lot_size and basement_features:
                    filtered.append({
                        # "address": address_text,  # address removed from post
                        "area": area,
                        "bedrooms": bedrooms,
                        "bathrooms": bathrooms,
                        "parking": parking,
                        "yearBuilt": year_built,
                        "description": description,
                        "price": property_info.get("PriceUnformattedValue", 0),
                        "amenities": amenities,
                        "lot_size": lot_size,
                        "basement_features": basement_features,
                        "tax_amount": float(property_info.get("TaxAmount", "0").replace("$", "").replace(",", "").strip() or 0),
                        # "url": "https://www.realtor.ca" + prop.get("RelativeURLEn", "")
                    })
        except Exception:
            continue
    return filtered

# ===== STEP 4. Create WhatsApp Post =====
def format_whatsapp_post(prop):
    price = float(prop.get("price", 0))

    monthly_payment_10, downpayment_10 = calculate_monthly_payment(price, downpayment_percent=0.10)
    monthly_payment_20, downpayment_20 = calculate_monthly_payment(price, downpayment_percent=0.20)

    # Calculate monthly property tax from TaxAmount field
    monthly_tax = float(prop.get('tax_amount', 0)) / 12
    monthly_utilities = 300.0
    monthly_ins_misc = 200.0

    total_rent = BASEMENT_RENT + UPSTAIRS_RENT
    cashflow_10 = total_rent - (monthly_payment_10 + monthly_tax + monthly_utilities + monthly_ins_misc)
    cashflow_20 = total_rent - (monthly_payment_20 + monthly_tax + monthly_utilities + monthly_ins_misc)
    
    area_text = prop.get('area', '')
    area_line = f"🔥 *Investment Opportunity in {area_text}*" if area_text else "🔥 *Investment Opportunity*"

    # Extract highlights
    amenities = prop.get('amenities', '')
    lot_size = prop.get('lot_size', '')
    basement_features = prop.get('basement_features', '')
    highlights = []
    if amenities:
        highlights.append(f"🏷️ Nearby: {amenities}")
    if lot_size:
        highlights.append(f"📏 Lot Size: {lot_size}")
    if basement_features:
        highlights.append(f"🔑 Basement: {basement_features}")
    highlights_text = '\n'.join(highlights)

    stark_highlights_section = ""
    if highlights_text:
        stark_highlights_section = f"\n---\n*Property Stark Highlights*\n{highlights_text}\n---\n"

    disclaimer = (
        "\n"    
        "_*Assumptions based on Current Mortgage Rates and Estimates :*_\n"
        f"Purchase Price as is - ${price:,.0f}\n"
        f"Mortgage Rate - {MORTGAGE_RATE*100:.2f}% \n"
        f"{AMORTIZATION_YEARS} year amortization \n"
        f"Upstairs rent ${UPSTAIRS_RENT}, Basement rent ${BASEMENT_RENT}.\n"
    )
    
    first_time_section = f"""
*Scenario 1 - 🏠 For First Time Home Buyers*
    - Monthly Mortgage (10% down): ${monthly_payment_10:,.0f}
    - Monthly Property Tax: ${monthly_tax:,.0f}
    - Insurance + Misc: ${monthly_ins_misc:,.0f}
    - 💰Basement rent: ${BASEMENT_RENT:,.0f}   
    👉 Live in this house worth ${price:,.0f} for ${(monthly_payment_10 + monthly_tax + monthly_ins_misc - BASEMENT_RENT):,.0f}/month
    ---------- \n
    """
    investment_section = f"""
*Scenario 2 - 💼 For Investment Buyers*
    - Monthly Mortgage (20% down): ${monthly_payment_20:,.0f}
    - Monthly Property Tax: ${monthly_tax:,.0f}
    - Insurance + Misc: ${monthly_ins_misc:,.0f}
    - 💰 Net Rent: Upstairs 3BR = ${UPSTAIRS_RENT}, Basement 2BR = ${BASEMENT_RENT}
    📈 *Get a Monthly Cashflow* of : ${cashflow_20:,.0f} from the property
    ---------- \n
    """

    # Add exclusive property details section for soldbyTeamPumpkin clients
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

    return f"""{area_line}
*Property Details*
- List Price: ${price:,.0f} | Bedrooms: {prop.get('bedrooms')} | Bathrooms: {prop.get('bathrooms')} | Parking: {prop.get('parking')}
- Year Built: {prop.get('yearBuilt')}
- Basement: {prop.get('basement_features', '')}
- Lot Size: {prop.get('lot_size', '')}
- Amenities Nearby: {prop.get('amenities', '')}
{disclaimer}
{first_time_section.strip()}
{investment_section.strip()}
{exclusive_section}
    """

# ===== MAIN PIPELINE =====
if __name__ == "__main__":
    all_listings = fetch_latest_properties()
    print(f'Listings Fetched are {all_listings}')

    filtered = filter_properties(all_listings)

    print(f"Listings matching criteria: {len(filtered)}")

    # Take top N (sorted by cashflow estimate at 20% down)
    scored = []
    for prop in filtered:
        price = float(prop.get("price", 0))
        monthly_payment, _ = calculate_monthly_payment(price, downpayment_percent=0.20)
        total_rent = BASEMENT_RENT + UPSTAIRS_RENT
        cashflow = total_rent - monthly_payment
        scored.append((cashflow, prop))

    scored.sort(reverse=True, key=lambda x: x[0])
    top_props = [prop for _, prop in scored[:TOP_N]]

    # Output WhatsApp-style posts and write to file
    output_lines = []
    for idx, prop in enumerate(top_props, 1):
        output_lines.append(f"\n=== Property #{idx} ===")
        output_lines.append(format_whatsapp_post(prop))

    output_text = '\n'.join(output_lines)
    print(output_text)

    # Write output to file
    output_dir = r"C:\Workspace\pumpkinScrapper"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "output.txt")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(output_text)
