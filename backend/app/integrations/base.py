from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseServiceClient(ABC):
    """
    Abstract base for all third-party integrations (SAT, Shipping, WhatsApp).
    Ensures that every integration can authenticate and handle API calls consistently.
    """
    
    def __init__(self, api_key: str, api_secret: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = None # To be defined by subclasses
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """Logic to verify if the key is valid with the provider."""
        pass
        
    @abstractmethod
    async def push_data(self, endpoint: str, data: Dict[str, Any]):
        """General method to send data to the aggregated API."""
        pass
        
    @abstractmethod
    async def fetch_data(self, endpoint: str):
        """General method to query data from the aggregated API."""
        pass
