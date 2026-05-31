from fastapi import APIRouter, HTTPException
import httpx

router = APIRouter()

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "EventFinder/2.0 (thunderbee732@gmail.com)"


@router.get("/geocode")
async def geocode(q: str):
    if len(q) < 3:
        return []
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                NOMINATIM_URL,
                params={"q": q, "format": "json", "addressdetails": 1, "limit": 5},
                headers={"User-Agent": USER_AGENT},
                timeout=8.0,
            )
            resp.raise_for_status()
            results = resp.json()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Geocoding failed: {e}")

    return [
        {
            "display_name": r.get("display_name", ""),
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
            "bundesland": _extract_bundesland(r.get("address", {})),
        }
        for r in results
        if "lat" in r and "lon" in r
    ]


def _extract_bundesland(address: dict) -> str:
    iso = address.get("ISO3166-2-lvl4", "")
    if iso.startswith("DE-"):
        return iso[3:]
    _NAME_TO_CODE = {
        "Bayern": "BY", "Baden-Württemberg": "BW", "Berlin": "BE",
        "Brandenburg": "BB", "Bremen": "HB", "Hamburg": "HH",
        "Hessen": "HE", "Mecklenburg-Vorpommern": "MV",
        "Niedersachsen": "NI", "Nordrhein-Westfalen": "NW",
        "Rheinland-Pfalz": "RP", "Saarland": "SL", "Sachsen": "SN",
        "Sachsen-Anhalt": "ST", "Schleswig-Holstein": "SH", "Thüringen": "TH",
    }
    return _NAME_TO_CODE.get(address.get("state", ""), "")
