class GateHardwareInterface:
    """
    Abstracts hardware control for gates/doors. Replace methods with real hardware integration as needed.
    """
    def open_gate(self, location):
        # TODO: Integrate with real hardware (relay, API, etc.)
        print(f"Gate at {location} opened.")
        return True

    def close_gate(self, location):
        # TODO: Integrate with real hardware (relay, API, etc.)
        print(f"Gate at {location} closed.")
        return True

    def get_status(self, location):
        # TODO: Query hardware for status
        print(f"Queried status for gate at {location}.")
        return "unknown"
