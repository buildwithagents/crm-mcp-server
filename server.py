import os
import httpx
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

_port = int(os.environ.get("PORT", 8000))
mcp = FastMCP("CRM Lead Creator", host="0.0.0.0", port=_port)

BASE_URL = os.environ["CRM_BASE_URL"].rstrip("/")
CRM_USERNAME = os.environ["CRM_USERNAME"]
CRM_PASSWORD = os.environ["CRM_PASSWORD"]


async def _get_token() -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/oauth2/token",
            json={"userName": CRM_USERNAME, "password": CRM_PASSWORD},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        # Try common token field names
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
