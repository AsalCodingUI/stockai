"""Backward compatibility shim — routes have been split into web/routers/."""
from stockai.web.routers.system import router as api_router  # noqa: F401
from stockai.web.routers.pages import router as pages_router  # noqa: F401
from stockai.web.utils import _WEB_RUNTIME  # noqa: F401

# Missing imports for backward compatibility in mock patches
from stockai.data.sources.idx import IDXIndexSource  # noqa: F401
from stockai.data.sources.yahoo import YahooFinanceSource  # noqa: F401
from stockai.data.database import init_database  # noqa: F401
from stockai.web.utils import _get_index_symbols, _build_signal_event  # noqa: F401
from stockai.core.foreign_flow import ForeignFlowMonitor  # noqa: F401
from stockai.core.volume_detector import UnusualVolumeDetector  # noqa: F401
from stockai.core.sentiment.stockbit import StockbitSentiment  # noqa: F401
from stockai.core.ml.probability import ProbabilityEngine  # noqa: F401
from stockai.core.predictor.ensemble import EnsemblePredictor  # noqa: F401
from stockai.config import get_settings  # noqa: F401
