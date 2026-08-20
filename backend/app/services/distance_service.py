import math
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def calculate_haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on the Earth's surface
    using the Haversine formula (in kilometers).
    """
    # Earth radius in kilometers
    r = 6371.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    )
    # Clip value to [0, 1] to avoid math domain errors due to floating-point imprecision
    a = min(1.0, max(0.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    distance = r * c

    return round(distance, 1)


class DistanceService:
    """
    Distance calculation service with offline local Haversine computation
    and future external Maps API extensibility.
    """

    def __init__(self, mode: str = "local"):
        self.mode = mode

    def calculate_distance_km(
        self, origin: Tuple[float, float], destination: Tuple[float, float]
    ) -> float:
        """
        Calculate straight-line distance in kilometers between origin (lat, lon)
        and destination (lat, lon).
        """
        lat1, lon1 = origin
        lat2, lon2 = destination
        return calculate_haversine_distance_km(lat1, lon1, lat2, lon2)
