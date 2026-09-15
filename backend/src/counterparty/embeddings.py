"""Worker-only local ONNX inference and verified public artifact cache."""

import fcntl
import hashlib
import os
from pathlib import Path

import httpx

from counterparty.embedding_config import ARTIFACTS, CONFIG, MODEL_ID, REVISION


class EmbeddingError(RuntimeError):
    """Safe application error; never includes downloader URLs or source text."""


def ensure_artifact(directory: Path, name: str, spec: dict, client: httpx.Client) -> Path:
    target = directory / name
    if target.is_file() and target.stat().st_size == spec["bytes"]:
        with target.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() == spec["sha256"]:
                return target
    partial = directory / (name + ".part")
    try:
        digest = hashlib.sha256()
        size = 0
        url = f"https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/onnx/{name}"
        with client.stream("GET", url) as response, partial.open("wb") as stream:
            response.raise_for_status()
            for block in response.iter_bytes(1024 * 1024):
                size += len(block)
                if size > spec["bytes"]:
                    raise EmbeddingError("Model artifact size mismatch")
                digest.update(block)
                stream.write(block)
            stream.flush()
            os.fsync(stream.fileno())
        if size != spec["bytes"] or digest.hexdigest() != spec["sha256"]:
            raise EmbeddingError("Model artifact integrity check failed")
        partial.replace(target)
        return target
    except Exception as error:
        raise EmbeddingError(
            "Model cache preparation failed; check network and cache space"
        ) from error
    finally:
        partial.unlink(missing_ok=True)


def token_windows(content, prefix, *, start_id, end_id):
    """Never decode/re-encode: each original content token survives at least once."""
    capacity = CONFIG["max_tokens"] - len(prefix) - 2
    step = capacity - CONFIG["window_overlap"]
    if step <= 0:
        raise EmbeddingError("Invalid token window configuration")
    result = []
    for start in range(0, max(1, len(content)), step):
        result.append([start_id, *prefix, *content[start : start + capacity], end_id])
        if start + capacity >= len(content):
            break
    return result


def validate_vectors(vectors, expected_count):
    import numpy as np

    values = np.asarray(vectors, dtype=np.float32)
    if values.shape != (expected_count, CONFIG["dimension"]) or not np.isfinite(values).all():
        raise EmbeddingError("Invalid embedding shape or values")
    if not np.allclose(np.linalg.norm(values, axis=1), 1, atol=1e-4):
        raise EmbeddingError("Embedding must have unit length")
    return values


class LocalEmbedder:
    def __init__(self, cache_path: str):
        # Heavy libraries and model initialization are confined to the spawned worker.
        import onnxruntime as ort
        from tokenizers import Tokenizer

        directory = Path(cache_path) / REVISION
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / ".prepare.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with httpx.Client(
                follow_redirects=True, timeout=httpx.Timeout(30, connect=10)
            ) as client:
                for name, spec in ARTIFACTS.items():
                    ensure_artifact(directory, name, spec, client)
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        self.pad_id = self.tokenizer.token_to_id("<pad>")
        self.start_id = self.tokenizer.token_to_id("<s>")
        self.end_id = self.tokenizer.token_to_id("</s>")
        if None in (self.pad_id, self.start_id, self.end_id):
            raise EmbeddingError("Required tokenizer special tokens missing")
        self.prefixes = {
            role: self.tokenizer.encode(prefix.rstrip(), add_special_tokens=False).ids
            for role, prefix in CONFIG["prefixes"].items()
        }
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.add_session_config_entry("session.intra_op.allow_spinning", "0")
        options.add_session_config_entry("session.inter_op.allow_spinning", "0")
        self.session = ort.InferenceSession(
            str(directory / "model.onnx"), options, providers=["CPUExecutionProvider"]
        )
        self.window_count = 0
        self.embed(["model readiness"], "query")

    def windows(self, text, role):
        content = self.tokenizer.encode(text, add_special_tokens=False).ids
        return token_windows(
            content, self.prefixes[role], start_id=self.start_id, end_id=self.end_id
        )

    def embed(self, texts: list[str], role: str) -> list[list[float]]:
        import numpy as np

        if role not in CONFIG["prefixes"]:
            raise EmbeddingError("Unknown embedding role")
        if not texts:
            return []
        windows, owners = [], []
        for index, value in enumerate(texts):
            parts = self.windows(value, role)
            windows.extend(parts)
            owners.extend([index] * len(parts))
        self.window_count += len(windows)
        sums = np.zeros((len(texts), CONFIG["dimension"]), dtype=np.float32)
        for start in range(0, len(windows), 8):
            batch = windows[start : start + 8]
            width = max(map(len, batch))
            ids = np.full((len(batch), width), self.pad_id, dtype=np.int64)
            mask = np.zeros_like(ids)
            for index, tokens in enumerate(batch):
                ids[index, : len(tokens)] = tokens
                mask[index, : len(tokens)] = 1
            hidden = self.session.run(
                ["last_hidden_state"],
                {"input_ids": ids, "attention_mask": mask, "token_type_ids": np.zeros_like(ids)},
            )[0]
            if hidden.shape != (*ids.shape, CONFIG["dimension"]):
                raise EmbeddingError("Unexpected ONNX output shape")
            pooled = (hidden * mask[..., None]).sum(axis=1) / mask.sum(axis=1)[:, None]
            norms = np.linalg.norm(pooled, axis=1, keepdims=True)
            if not np.isfinite(pooled).all() or (norms == 0).any():
                raise EmbeddingError("Invalid ONNX output")
            pooled = (pooled / norms).astype(np.float32)
            for index, vector in enumerate(pooled):
                sums[owners[start + index]] += vector
        norms = np.linalg.norm(sums, axis=1, keepdims=True)
        if (norms == 0).any():
            raise EmbeddingError("Empty pooled embedding")
        return validate_vectors(sums / norms, len(texts)).tolist()
