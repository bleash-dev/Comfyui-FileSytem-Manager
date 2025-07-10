from .api import CivitAIDownloadAPI
from .progress import civitai_progress_store

# Import model config integration
try:
    from ..model_config_integration import model_config_manager
    MODEL_CONFIG_AVAILABLE = True
except ImportError:
    print("Model config integration not available")
    MODEL_CONFIG_AVAILABLE = False

__all__ = ['CivitAIDownloadAPI', 'civitai_progress_store', 'MODEL_CONFIG_AVAILABLE']
