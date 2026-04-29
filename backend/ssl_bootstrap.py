"""Self-healing SSL trust-store bootstrap.

Some Python installations (notably Homebrew Python on macOS) point OpenSSL at
a system CA bundle that may not actually exist on the host (dangling symlink,
empty cert dir). When that happens *every* HTTPS call fails with
``CERTIFICATE_VERIFY_FAILED``, including Demucs / Torch / HuggingFace model
downloads.

We detect the broken state at process start and, when ``certifi`` is
available, redirect ``SSL_CERT_FILE`` / ``REQUESTS_CA_BUNDLE`` to certifi's
bundled roots. This must run *before* any module establishes an SSL
connection, so import this module first from ``backend/main.py``.

Setting an env var here (rather than mutating ``ssl`` defaults) ensures
subprocesses (e.g. anything Demucs / huggingface-cli might spawn) inherit the
fix as well.
"""

from __future__ import annotations

import logging
import os
import ssl
from pathlib import Path

logger = logging.getLogger(__name__)


def _system_bundle_usable() -> bool:
    """Return True iff the OS-default CA bundle exists and is non-empty."""
    paths = ssl.get_default_verify_paths()
    cafile = paths.cafile
    if cafile and Path(cafile).is_file() and Path(cafile).stat().st_size > 0:
        return True
    capath = paths.capath
    if capath and Path(capath).is_dir():
        try:
            for entry in Path(capath).iterdir():
                if entry.is_file() and entry.stat().st_size > 0 and entry.name != ".keepme":
                    return True
        except OSError:
            pass
    return False


def ensure_ssl_cert_bundle() -> None:
    """Heal the SSL trust store if the OS bundle is missing.

    Idempotent: respects an explicitly-set ``SSL_CERT_FILE``, and is a no-op
    when the system bundle already works.
    """
    if os.environ.get("SSL_CERT_FILE"):
        return

    if _system_bundle_usable():
        return

    try:
        import certifi  # type: ignore
    except ImportError:
        logger.warning(
            "SSL trust-store appears broken (no usable CA bundle in default verify paths) "
            "and certifi is not installed; HTTPS-based model downloads will fail. "
            "Run `brew install ca-certificates` or `pip install certifi` to fix."
        )
        return

    bundle = certifi.where()
    if not Path(bundle).is_file():
        logger.warning("certifi reports bundle at %s but the file is missing.", bundle)
        return

    os.environ["SSL_CERT_FILE"] = bundle
    os.environ.setdefault("REQUESTS_CA_BUNDLE", bundle)
    os.environ.setdefault("CURL_CA_BUNDLE", bundle)
    logger.info(
        "System CA bundle missing; redirected SSL_CERT_FILE/REQUESTS_CA_BUNDLE to certifi at %s",
        bundle,
    )
