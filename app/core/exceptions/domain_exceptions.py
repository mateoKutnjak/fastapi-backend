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


class InvalidVerificationTokenError(DomainError):
    pass


class ExpiredVerificationTokenError(DomainError):
    pass


class AccountLinkingError(DomainError):
    pass


class InvalidOAuthTokenError(DomainError):
    pass


class RoleNotFoundError(DomainError):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Role not found: {self.name}")


class InvalidPasswordResetTokenError(DomainError):
    pass


class ExpiredPasswordResetTokenError(DomainError):
    pass
