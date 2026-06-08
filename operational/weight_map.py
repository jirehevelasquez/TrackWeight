# weight_map.py
# Formula-based weight calculator for Track Weight.
# Uses home TOF distance, plate thickness, starting weight, and weight step.

class WeightMap:
    def __init__(
        self,
        home_distance_mm,
        plate_thickness_mm,
        start_weight_lbs,
        weight_step_lbs,
        max_slots=None,
        direction="down_increases_distance"
    ):
        self.home_distance_mm = home_distance_mm
        self.plate_thickness_mm = plate_thickness_mm
        self.start_weight_lbs = start_weight_lbs
        self.weight_step_lbs = weight_step_lbs
        self.max_slots = max_slots
        self.direction = direction

        if self.plate_thickness_mm <= 0:
            raise ValueError("plate_thickness_mm must be greater than 0")

    def get_slot(self, distance_mm):
        if self.direction == "down_increases_distance":
            distance_from_home = distance_mm - self.home_distance_mm
        else:
            distance_from_home = self.home_distance_mm - distance_mm

        slot = int(round(distance_from_home / self.plate_thickness_mm))

        if slot < 0:
            slot = 0

        if self.max_slots is not None and slot > self.max_slots:
            slot = self.max_slots

        return slot

    def get_weight(self, distance_mm):
        slot = self.get_slot(distance_mm)
        weight = self.start_weight_lbs + (slot * self.weight_step_lbs)
        return weight

    def get_weight_with_error(self, distance_mm):
        slot = self.get_slot(distance_mm)
        weight = self.get_weight(distance_mm)

        if self.direction == "down_increases_distance":
            matched_distance = self.home_distance_mm + (slot * self.plate_thickness_mm)
        else:
            matched_distance = self.home_distance_mm - (slot * self.plate_thickness_mm)

        error_mm = abs(distance_mm - matched_distance)

        return weight, error_mm, matched_distance, slot