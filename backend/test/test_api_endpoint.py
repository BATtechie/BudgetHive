import sys
import json
from pathlib import Path
from dotenv import load_dotenv

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

load_dotenv(dotenv_path=backend_dir / ".env")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_api_fashion_and_tech():
    print("=" * 80)
    print("👕 TEST 1: SEARCHING FASHION ITEM ('Oversized Black Cotton T-Shirt')")
    print("=" * 80)

    payload_tshirt = {
        "product_input": "Oversized Black Cotton T-Shirt",
        "user_banks": ["HDFC Bank", "ICICI Bank"],
        "max_budget": 1200.0,
    }

    response1 = client.post("/api/v1/deal-hunter/evaluate", json=payload_tshirt)
    data1 = response1.json()

    print(f"Detected Category : {data1.get('category')}")
    print(f"Scanned Stores    : {[d['platform'] for d in data1.get('scanned_deals', [])]}")
    print(f"Best Platform     : {data1.get('best_platform')}\n")
    print(data1["ai_recommendation"])
    print("\n" + "=" * 80)
    print("🎧 TEST 2: SEARCHING ELECTRONICS ITEM ('Sony WH-1000XM5 Headphones')")
    print("=" * 80)

    payload_tech = {
        "product_input": "Sony WH-1000XM5 Wireless Headphones",
        "user_banks": ["HDFC Bank", "ICICI Bank"],
        "max_budget": 26000.0,
    }

    response2 = client.post("/api/v1/deal-hunter/evaluate", json=payload_tech)
    data2 = response2.json()

    print(f"Detected Category : {data2.get('category')}")
    print(f"Scanned Stores    : {[d['platform'] for d in data2.get('scanned_deals', [])]}")
    print(f"Best Platform     : {data2.get('best_platform')}\n")
    print(data2["ai_recommendation"])
    print("=" * 80)


if __name__ == "__main__":
    test_api_fashion_and_tech()
