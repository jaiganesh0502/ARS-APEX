import logging
from typing import Dict
from app.models.ambulance_dispatch import AmbulanceStatus

logger = logging.getLogger(__name__)


class ETAService:
    """
    Computes simulated or live telemetry ETAs for ambulance dispatch and patient transit.
    """

    AVERAGE_SPEED_KMH = 35.0
    EMERGENCY_BUFFER_MINUTES = 4
    STANDARD_BUFFER_MINUTES = 8

    def __init__(self, mode: str = "simulation"):
        self.mode = mode

    def calculate_initial_eta(self, distance_km: float, emergency: bool = False) -> Dict[str, int]:
        """
        Calculate deterministic simulated duration and initial ETA.
        """
        travel_duration = max(1, round((distance_km / self.AVERAGE_SPEED_KMH) * 60.0))
        dispatch_buffer = self.EMERGENCY_BUFFER_MINUTES if emergency else self.STANDARD_BUFFER_MINUTES
        estimated_total = travel_duration + dispatch_buffer

        return {
            "travel_duration_minutes": travel_duration,
            "dispatch_buffer_minutes": dispatch_buffer,
            "estimated_duration_minutes": estimated_total,
            "current_eta_minutes": estimated_total,
        }

    def compute_current_eta(
        self,
        status: AmbulanceStatus,
        distance_km: float,
        emergency: bool = False,
    ) -> int:
        """
        Calculate the remaining simulated ETA based on the current transit milestone.
        """
        travel_duration = max(1, round((distance_km / self.AVERAGE_SPEED_KMH) * 60.0))
        dispatch_buffer = self.EMERGENCY_BUFFER_MINUTES if emergency else self.STANDARD_BUFFER_MINUTES

        if status == AmbulanceStatus.REQUESTED:
            return travel_duration + dispatch_buffer
        elif status == AmbulanceStatus.EN_ROUTE:
            return travel_duration + max(1, dispatch_buffer // 2)
        elif status in (AmbulanceStatus.ARRIVED_PICKUP, AmbulanceStatus.PATIENT_ONBOARD):
            return travel_duration
        elif status == AmbulanceStatus.IN_TRANSIT:
            return max(1, round(travel_duration * 0.5))
        elif status in (AmbulanceStatus.ARRIVED_DESTINATION, AmbulanceStatus.COMPLETED, AmbulanceStatus.CANCELLED):
            return 0
        return travel_duration
