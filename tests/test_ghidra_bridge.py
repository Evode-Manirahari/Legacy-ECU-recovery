import json

import pytest

from ecu_recovery.ghidra.bridge import GhidraExportError, load_functions


def test_loads_valid_function_export(tmp_path):
    export = tmp_path / "functions.json"
    export.write_text(
        json.dumps({"functions": [{"address": "0x923A", "name": "FUN_923a", "size": 14}]}),
        encoding="utf-8",
    )

    functions = load_functions(export)

    assert functions[0].address == 0x923A
    assert functions[0].name == "FUN_923a"


def test_rejects_malformed_export(tmp_path):
    export = tmp_path / "functions.json"
    export.write_text('{"wrong": []}', encoding="utf-8")

    with pytest.raises(GhidraExportError, match="functions array"):
        load_functions(export)
