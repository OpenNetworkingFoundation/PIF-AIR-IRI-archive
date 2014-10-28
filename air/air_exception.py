"""
AIR exception definitions
"""

class AirValidationError(Exception):
    """
    Error validating some AIR representation
    """
    pass


class AriRefError(Exception):
    """
    Error referencing some AIR object
    """
    pass
