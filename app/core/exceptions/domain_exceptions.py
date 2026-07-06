class DomainError(Exception):
    pass


class UserNotFoundError(DomainError):
    pass


class InvalidCredentialsError(DomainError):
    pass


class InvalidRefreshTokenError(DomainError):
    pass


class ValidationError(DomainError):
    def __init__(self, fields: dict[str, str]):
        self.fields = fields
        super().__init__(self.fields)


class InvalidTokenError(DomainError):
    pass


class ExpiredTokenError(DomainError):
    pass
