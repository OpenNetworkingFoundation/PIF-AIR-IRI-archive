"""
IRI exception definitions
"""

class IriParamError(Exception):
    """
    Error validating some AIR representation
    """
    pass

class IriPacketModError(Exception):
    """
    Error during some packet modification
    Examples:
      A header didn't exist that should, 
      A header existed on add
      A header stack overflowed
      Incompatible field value assignment
    """
    pass

class IriReferenceError(Exception):
    """
    Error refencing some IRI object
    """
    pass

class IriImplementationError(Exception):
    """
    Implementation error in IRI; for example, uninstantiated pure
    virtual function.
    """
    pass
