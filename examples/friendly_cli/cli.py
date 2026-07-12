from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="friendly", description="A small CLI used by Witness integration tests"
    )
    parser.add_argument("name", nargs="?", default="world")
    parser.add_argument("--shout", action="store_true")
    args = parser.parse_args()
    message = f"Hello, {args.name}!"
    print(message.upper() if args.shout else message)


if __name__ == "__main__":
    main()
