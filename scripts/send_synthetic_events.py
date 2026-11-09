"""Send two clearly synthetic product events to a local Atlas CX workspace."""

import argparse
import getpass
import json
from datetime import datetime, timedelta
from http.client import HTTPConnection, HTTPSConnection
from urllib.parse import urlsplit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--customer-external-id", required=True)
    parser.add_argument(
        "--occurred-at", required=True, help="ISO timestamp with an explicit offset"
    )
    parser.add_argument(
        "--namespace", required=True, help="Unique synthetic run ID, up to 80 chars"
    )
    parser.add_argument("--origin", default="http://localhost:8080")
    args = parser.parse_args()
    try:
        origin = urlsplit(args.origin)
        port = origin.port
        instant = datetime.fromisoformat(args.occurred_at)
        if (
            instant.tzinfo is None
            or len(args.namespace) > 80
            or origin.scheme not in {"http", "https"}
            or origin.hostname not in {"localhost", "127.0.0.1", "::1"}
            or origin.username
            or origin.password
            or origin.query
            or origin.fragment
            or origin.path not in {"", "/"}
        ):
            raise ValueError
    except ValueError:
        parser.error("Use an offset timestamp, short run ID, and a loopback origin")
    # The key is entered privately. It is never placed in shell history.
    key = getpass.getpass("Local ingestion key ")
    connection_class = HTTPSConnection if origin.scheme == "https" else HTTPConnection
    connection = connection_class(origin.hostname, port=port, timeout=10)

    def event(suffix: str, stamp: datetime) -> dict[str, object]:
        return {
            "external_event_id": f"synthetic-{args.namespace}-{suffix}",
            "customer_external_id": args.customer_external_id,
            "event_name": "feature_used",
            "occurred_at": stamp.isoformat(),
            "properties": {"feature": "Synthetic report"},
        }

    latest = event("latest", instant)
    late = event("late", instant - timedelta(hours=1))
    try:
        for batch in ([latest], [late, latest]):
            connection.request(
                "POST",
                "/api/v1/events/batch",
                body=json.dumps({"events": batch}),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + key,
                },
            )
            with connection.getresponse() as response:
                if response.status != 200:
                    parser.exit(1, f"Ingestion returned HTTP {response.status}.\n")
                result = json.load(response)["data"]
            print(
                f"Synthetic batch inserted {result['inserted_count']}, duplicates {result['duplicate_count']}"
            )
    finally:
        connection.close()


if __name__ == "__main__":
    main()
