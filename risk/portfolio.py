# risk/portfolio.py

class PortfolioGuard:
    """
    Controls exposure at portfolio level.
    """

    def __init__(self, max_exposure_pct: float = 0.25):
        self.max_exposure_pct = max_exposure_pct
        self.current_exposure = 0.0

    def can_add_position(self, balance: float, position_value: float) -> bool:
        return (self.current_exposure + position_value) <= balance * self.max_exposure_pct

    def register_position(self, position_value: float):
        self.current_exposure += position_value

    def unregister_position(self, position_value: float):
        self.current_exposure = max(0.0, self.current_exposure - position_value)
