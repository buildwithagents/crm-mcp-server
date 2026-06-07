import os
import httpx
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

_port = int(os.environ.get("PORT", 8000))
mcp = FastMCP("CRM Lead Creator", host="0.0.0.0", port=_port)

BASE_URL = os.environ["CRM_BASE_URL"].rstrip("/")
ACCOUNT_BASE_URL = os.environ.get("CRM_ACCOUNT_BASE_URL", "https://presales.businessbywire.com/restapigts").rstrip("/")
CRM_USERNAME = os.environ["CRM_USERNAME"]
CRM_PASSWORD = os.environ["CRM_PASSWORD"]


async def _get_token(base: str = None) -> str:
    url = f"{base or BASE_URL}/oauth2/token"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            json={"userName": CRM_USERNAME, "password": CRM_PASSWORD},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        token = (
            data.get("access_token")
            or data.get("token")
            or data.get("accessToken")
        )
        if not token:
            raise ValueError(f"Token not found in auth response: {list(data.keys())}")
        return token


@mcp.tool()
async def create_lead(
    name: str,
    last_name: str,
    mobile_phone: str,
    product: str = "Personal Loan for Salaried Customers",
    rating: str = "Warm",
    product_category: str = "Loans",
    lead_owner_name: str = "Mr. James May",
    layout_id: int = 102796,
    process_id: int = 10000893,
) -> dict:
    """
    Create a new lead in the CRM.

    Args:
        name: First name of the lead
        last_name: Last name of the lead
        mobile_phone: Mobile phone number
        product: Product the lead is interested in
        rating: Lead rating (e.g. Warm, Hot, Cold)
        product_category: Category of the product
        lead_owner_name: Name of the lead owner
        layout_id: CRM layout ID (default 102796)
        process_id: CRM process ID (default 10000893)
    """
    token = await _get_token()

    payload = [
        {
            "ItemId": "0",
            "ItemType": "Lead",
            "ProcessMode": "Create",
            "OutputFieldList": ["CustomObjectId", "ItemId"],
            "ObjectData": {
                "LayoutID": layout_id,
                "ProcessID": process_id,
                "Name": name,
                "LastName": last_name,
                "Product": product,
                "Rating": rating,
                "LeadOwnerName": lead_owner_name,
                "MobilePhone": mobile_phone,
                "ProductCategory": product_category,
            },
        }
    ]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/crmWebApi/saveObject",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()


ACCOUNT_FIELD_MAP = {
    "StatusCode": "Status Code",
    "Name": "Account Name",
    "ParentAccountName": "Parent Account Name",
    "acc_ex4_54": "CIF",
    "Industry": "Industry",
    "AccountID": "Account ID",
    "Acc_ex2_68": "Branch",
    "Acc_ex2_87": "Incorporation Date",
    "Acc_ex1_52": "Employee Strength",
    "Acc_ex4_40": "Long Term Rating Agency",
    "Acc_ex4_41": "Long Term Rating",
    "Acc_ex4_44": "Short Term Rating Agency",
    "Acc_ex4_45": "Short Term Rating",
    "Acc_ex1_43": "Customer Rating",
    "Acc_ex5_23": "Checklist Complete",
    "Acc_ex1_49": "Customer Band",
    "Acc_ex4_1": "Account Type",
    "Acc_ex4_28": "Moody Rating",
    "Acc_ex1_8": "Customer Since",
    "AccountType": "Account Category",
    "Phone": "Phone",
    "MobilePhone": "Mobile Phone",
    "OfficePhone": "Office Phone",
    "Email": "Email",
    "Acc_ex2_45": "Team Leader",
    "AssignedToName": "Relationship Manager (RM)",
    "Acc_ex8_24": "Trade Finance Relationship Manager",
    "Acc_ex8_25": "Trade Finance RM",
    "Acc_ex8_23": "Corporate RM",
    "HtmlText_2870": "Past Experience",
    "Acc_ex5_97": "Nature of Business",
    "HtmlText_2871": "Key Strengths and Weaknesses",
    "HtmlText_2872": "Promoter Information",
}


@mcp.tool()
async def get_account(account_id: str) -> dict:
    """
    Fetch detailed account information from the CRM by Account ID.

    Returns a structured account profile with human-readable field names covering:
    basic info, contact details, ratings, team assignments, and business background.

    Args:
        account_id: The CRM Account ID (e.g. "2463")
    """
    token = await _get_token(base=ACCOUNT_BASE_URL)

    output_fields = list(ACCOUNT_FIELD_MAP.keys())

    payload = {
        "outputFieldList": output_fields,
        "objectSearchCondition": [
            {"FieldName": "AccountId", "Value": account_id, "Operation": "equal"}
        ],
        "queryOptions": {
            "advanceFilterExpression": "",
            "PageSize": "50",
            "Index": "1",
            "OrderByFieldName": "",
            "VisibilityOption": "AllRecords",
        },
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{ACCOUNT_BASE_URL}/crmWebApi/fetchobject?objectType=7&itemId={account_id}&viewid=0",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()

    # Remap raw field names to human-readable names
    records = raw if isinstance(raw, list) else raw.get("records") or raw.get("data") or [raw]
    renamed = []
    for record in records:
        renamed_record = {}
        for raw_key, value in record.items():
            label = ACCOUNT_FIELD_MAP.get(raw_key, raw_key)
            renamed_record[label] = value
        renamed.append(renamed_record)

    return {
        "account_id": account_id,
        "total_records": len(renamed),
        "account": renamed[0] if len(renamed) == 1 else renamed,
    }


@mcp.tool()
async def test_connection() -> dict:
    """Test connectivity to the CRM by checking auth and the test API endpoint."""
    results = {}

    # Test auth
    try:
        token = await _get_token()
        results["auth"] = "ok" if token else "no token returned"
    except Exception as e:
        results["auth"] = f"error: {e}"

    # Test API endpoint
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BASE_URL}/testapi", timeout=10)
            results["testapi"] = f"HTTP {resp.status_code}"
    except Exception as e:
        results["testapi"] = f"error: {e}"

    return results


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
