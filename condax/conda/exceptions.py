from condax.exceptions import CondaxError


class NoPackageMetadata(CondaxError):
    def __init__(self, package: str):
        super().__init__(201, f"Could not determine package files: {package}.")
