"""Export without connecting to the database or running migrations."""

import json
from pathlib import Path

from app.main import create_app

application = create_app()
destination = Path(__file__).parents[2] / "docs" / "contracts" / "openapi.json"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(
    json.dumps(application.openapi(), indent=2) + "\n", encoding="utf-8", newline="\n"
)
application.state.engine.dispose()
