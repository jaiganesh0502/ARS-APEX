from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any


class MapsClientInterface(ABC):
    """
    Abstract interface for distance matrix, hospital routing, and ambulance ETA calculation.
    """

    @abstractmethod
    async def calculate_eta(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float]
    ) -> Dict[str, Any]:
        """Calculate travel duration (minutes) and distance (meters) between two coordinates."""
        pass
