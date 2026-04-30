from common.core.tools.EpaySpecification import EpaySpecification

secret_hide_mark: str = '•'

spec: EpaySpecification = EpaySpecification()


def mask_secret(value: str) -> str:
    return secret_hide_mark * len(value)


def mask_pan(pan: str):
    length = len(pan)

    head: int = 6
    tail: int = 4

    if length < head + tail:
        return pan

    hide: int = length - head - tail
    head: str = pan[:head]
    tail: str = pan[-tail:]
    hide: str = secret_hide_mark * hide

    return f"{head}{hide}{tail}"
