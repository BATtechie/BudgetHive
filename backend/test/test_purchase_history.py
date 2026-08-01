import importlib.util
import sys
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

module_path = BACKEND_DIR / "app" / "api" / "purchase_history.py"
module_spec = importlib.util.spec_from_file_location("purchase_history_module", module_path)
purchase_history_module = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = purchase_history_module
module_spec.loader.exec_module(purchase_history_module)

from app.schemas.purchase_history import PurchaseCheckIn, PurchaseHistoryCreate


def test_purchase_history_create_maps_status_to_flags():
    payload = PurchaseHistoryCreate(
        product_name="Samsung Galaxy S25 FE",
        product_category="Smartphones",
        purchase_price=55000.0,
        status="RETURNED",
        days_used_before_losing_interest=12,
        regret_score=72,
    )

    history = purchase_history_module.build_purchase_history_from_create(payload, user_id=uuid.uuid4())

    assert history.product_name == "Samsung Galaxy S25 FE"
    assert history.product_category == "Smartphones"
    assert history.purchase_price == 55000.0
    assert history.usage_duration_days == 12
    assert history.is_returned is True
    assert history.is_resold is False
    assert history.regret_score == 72


def test_purchase_checkin_thumbs_up_uses_low_regret_defaults():
    payload = PurchaseCheckIn(action="UP")
    data = payload.model_dump()

    assert data["action"] == "UP"
    assert payload.regret_score is None


def test_resolve_category_tier_assigns_high_ticket_delay_to_phones():
    tier, delay_days = purchase_history_module.resolve_category_tier("Smartphones")
    assert tier == "HIGH_TICKET"
    assert delay_days == 55
