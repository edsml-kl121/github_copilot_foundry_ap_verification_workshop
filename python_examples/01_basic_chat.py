"""Basic multi-turn chat using the Microsoft Foundry Responses API."""

try:
    from .common import client_for, config
except ImportError:
    from common import client_for, config


def main() -> None:
    cfg = config()
    client = client_for(cfg)
    first = client.responses.create(
        model=cfg["chat_deployment"],
        input="In two sentences, what is AP invoice verification?",
    )
    print("[assistant]", first.output_text)
    second = client.responses.create(
        model=cfg["chat_deployment"],
        previous_response_id=first.id,
        input="Now explain the three-way match as 3 bullets: PO, Goods Receipt, Invoice.",
    )
    print("[assistant]", second.output_text)


if __name__ == "__main__":
    main()
