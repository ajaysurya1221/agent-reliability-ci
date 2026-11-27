"""Identity of the installed model and the loaded model on the study endpoint."""

import hashlib
import http.client
import json
import re
from pathlib import Path

from descriptors import Row, read, validate_slot
from records import require


def metadata(endpoint: str, body: Row | None = None) -> Row:
    conn = http.client.HTTPConnection("127.0.0.1", 11434, timeout=10)
    try:
        conn.request(
            "GET" if body is None else "POST",
            "/api/" + endpoint,
            None if body is None else json.dumps(body),
            {"Content-Type": "application/json"},
        )
        response = conn.getresponse()
        require(response.status == 200, f"metadata HTTP status {response.status}: {endpoint}")
        return json.loads(response.read())
    finally:
        conn.close()


def expected(root: Path, model: Row) -> Row:
    return {
        "ollama": read(root / "models.json")["ollama"],
        "tag": model["tag"],
        "digest": model["digest"],
        "loaded_digest": model["digest"],
        "context": model["context"],
        "loaded_context": model["context"],
        "size": model["size"],
        "quantization": model["quantization"],
        "family": model["family"],
        "format": model["format"],
    }


def validate(root: Path, model: Row, actual: Row) -> None:
    for k, v in expected(root, model).items():
        require(actual.get(k) == v, f"server model {k} differs")
    validate_slot(root, model["slot"], actual)
    require(re.fullmatch("[a-f0-9]{64}", actual["template_sha256"]), "invalid template digest")


def inspect_model(
    root: Path, model: Row, standin: bool = False, *, allow_unloaded: bool = False
) -> Row:
    if standin:
        return expected(root, model) | {"template_sha256": hashlib.sha256(b"stand-in").hexdigest()}
    tag = model["tag"]
    version = metadata("version")["version"]
    tags = [t for t in metadata("tags")["models"] if t["name"] == tag]
    show = metadata("show", {"model": tag})
    active = [t for t in metadata("ps")["models"] if t["name"] == tag]
    require(
        len(tags) == 1 and (len(active) == 1 or (allow_unloaded and not active)),
        "registered model must be installed and loaded",
    )
    contexts = re.findall(r"(?m)^\s*num_ctx\s+(\d+)\s*$", show["parameters"])
    require(len(contexts) == 1 and show["template"], "missing context or template")
    details = show["details"]
    return dict(
        ollama=version,
        tag=tag,
        digest=tags[0]["digest"],
        loaded_digest=active[0]["digest"] if active else None,
        context=int(contexts[0]),
        loaded_context=active[0]["context_length"] if active else None,
        size=details["parameter_size"],
        quantization=details["quantization_level"],
        family=details["family"],
        format=details["format"],
        template_sha256=hashlib.sha256(show["template"].encode()).hexdigest(),
    )
