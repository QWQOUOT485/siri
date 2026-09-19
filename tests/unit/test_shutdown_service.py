from app.services.shutdown_service import ShutdownConfirmationService


class Clock:
    value = 100.0

    def __call__(self):
        return self.value


def test_shutdown_token_is_expiring_and_one_time():
    clock = Clock()
    service = ShutdownConfirmationService(15, clock=clock)
    token, ttl = service.request()
    assert ttl == 15
    assert service.consume(token) == (True, "")
    assert service.consume(token) == (False, "SHUTDOWN_TOKEN_REUSED")
    clock.value += 16
    expired, code = service.consume("not-a-real-token")
    assert expired is False and code == "SHUTDOWN_TOKEN_INVALID"


def test_invalid_and_expired_token_do_not_consume_another_token():
    clock = Clock()
    service = ShutdownConfirmationService(15, clock=clock)
    token, _ = service.request()
    assert service.consume("wrong") == (False, "SHUTDOWN_TOKEN_INVALID")
    clock.value += 16
    assert service.consume(token) == (False, "SHUTDOWN_TOKEN_EXPIRED")


def test_expired_requested_token_reports_expired_not_invalid():
    clock = Clock()
    service = ShutdownConfirmationService(15, clock=clock)
    token, _ = service.request()

    clock.value += 16

    assert service.consume(token) == (False, "SHUTDOWN_TOKEN_EXPIRED")
