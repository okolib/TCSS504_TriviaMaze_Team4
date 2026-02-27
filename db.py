# db.py
# Persistence Owner: JSON I/O ONLY.
# Constraints:
# - Do NOT import maze or main
# - Store JSON-safe primitives only (dict/list/str/int/float/bool/None)

import json
import os
from typing import Optional, Dict, Any


class Repository:
    """
    Mock ORM / JSON repository for the walking skeleton.

    Contract (per docs/interface-tests.md):
    - save(data, filepath) writes JSON to disk (overwrites)
    - load(filepath) returns dict, None if missing
      raises ValueError if file exists but is empty or invalid JSON
    """

    def save(self, data: Dict[str, Any], filepath: str = "save_game.json") -> None:
        """
        Persist a JSON-safe dict to disk.

        Raises:
            IOError / OSError if the OS can't write the file.
            TypeError if data contains non-JSON-serializable values.
        """
        # Ensure parent folder exists if filepath includes directories
        parent = os.path.dirname(filepath)
        if parent:
            os.makedirs(parent, exist_ok=True)

        # json.dump will raise TypeError if non-serializable values exist
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self, filepath: str = "save_game.json") -> Optional[Dict[str, Any]]:
        """
        Load JSON dict from disk.

        Returns:
            dict if loaded successfully
            None if file does not exist

        Raises:
            ValueError if file exists but is empty or not valid JSON
        """
        if not os.path.exists(filepath):
            return None

        # Empty file should raise ValueError (per tests)
        if os.path.getsize(filepath) == 0:
            raise ValueError("Save file is empty.")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError("Save file is corrupt or not valid JSON.") from e

        # The contract tests expect a dict back (they save dicts)
        # If someone saved something else, treat as invalid.
        if not isinstance(data, dict):
            raise ValueError("Save file JSON must be an object/dict.")

        return data