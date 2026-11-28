"""Connection management and helper functions for oVirt and OLVM SDK."""

import logging
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import ovirtsdk4 as sdk

from ovirt_mcp.config import OvirtConfig, get_config

from .exceptions import (
    NotFoundError,
    OvirtAuthError,
    OvirtConnectionError,
    OvirtValidationError,
)

logger = logging.getLogger(__name__)


class OvirtClient:
    """Manages the connection lifecycle to oVirt / OLVM Engine."""

    def __init__(self, config: OvirtConfig | None = None) -> None:
        self.config = config or get_config()
        self._connection: sdk.Connection | None = None

    @property
    def is_connected(self) -> bool:
        """Check if an active connection instance exists."""
        return self._connection is not None

    def _resolve_ca_certificate(self) -> str | None:
        """Resolve or automatically download the CA certificate for TLS verification."""
        if self.config.ovirt_insecure:
            return None

        if self.config.ovirt_ca_file and self.config.ovirt_ca_file.exists():
            return str(self.config.ovirt_ca_file)

        if self.config.ovirt_auto_download_ca:
            downloaded = self.download_ca_cert()
            if downloaded:
                return str(downloaded)

        return None

    def download_ca_cert(self) -> Path | None:
        """Download the engine CA certificate from standard oVirt/OLVM PKI service endpoint."""
        parsed = urlparse(self.config.ovirt_url)
        pki_url = f"{parsed.scheme}://{parsed.netloc}/ovirt-engine/services/pki-resource?resource=ca-certificate&format=X509-PEM-CA"

        cache_dir = Path.home() / ".config" / "ovirt-mcp" / "certs"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cert_path = cache_dir / f"{parsed.hostname}_ca.pem"

        if cert_path.exists():
            logger.debug("Using cached CA certificate from %s", cert_path)
            return cert_path

        try:
            logger.info("Attempting to download engine CA certificate from %s", pki_url)
            # Use verify=False only for initial CA cert retrieval if explicitly needed
            with httpx.Client(verify=False, timeout=10.0) as client:
                resp = client.get(pki_url)
                if resp.status_code == 200 and "-----BEGIN CERTIFICATE-----" in resp.text:
                    cert_path.write_text(resp.text, encoding="utf-8")
                    logger.info("CA certificate successfully cached at %s", cert_path)
                    return cert_path
                logger.warning(
                    "Failed to fetch CA certificate from %s: HTTP %s",
                    pki_url,
                    resp.status_code,
                )
        except Exception as exc:
            logger.warning("Error downloading CA certificate from %s: %s", pki_url, exc)

        return None

    def get_connection(self) -> sdk.Connection:
        """Return the active SDK connection or create a new one with automatic retry.

        If the engine is restarting or temporarily unreachable, retries with exponential backoff
        up to `ovirt_max_retries` (default: 3 attempts).
        """
        if self._connection is not None:
            return self._connection

        ca_file = self._resolve_ca_certificate()
        insecure = self.config.ovirt_insecure or (ca_file is None)
        max_retries = max(1, self.config.ovirt_max_retries)
        last_exc: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    "Connecting to oVirt/OLVM at %s (attempt %d/%d, insecure=%s, ca_file=%s)",
                    self.config.sanitized_url(),
                    attempt,
                    max_retries,
                    insecure,
                    ca_file,
                )
                conn = sdk.Connection(
                    url=self.config.sanitized_url(),
                    username=self.config.ovirt_username,
                    password=self.config.ovirt_password.get_secret_value(),
                    ca_file=ca_file,
                    insecure=insecure,
                    timeout=self.config.ovirt_timeout,
                )
                self._connection = conn
                return self._connection
            except sdk.AuthError as exc:
                logger.error(
                    "Authentication failed for user %s: %s", self.config.ovirt_username, exc
                )
                raise OvirtAuthError(f"Authentication failed: {exc}") from exc
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Connection attempt %d/%d to oVirt failed: %s. Retrying in %ds...",
                    attempt,
                    max_retries,
                    exc,
                    attempt * 2,
                )
                if attempt < max_retries:
                    time.sleep(attempt * 2)

        logger.error("All %d connection attempts to oVirt failed: %s", max_retries, last_exc)
        raise OvirtConnectionError(
            f"Failed to connect to oVirt/OLVM after {max_retries} attempts: {last_exc}"
        ) from last_exc

    def execute_with_retry(
        self,
        operation_name: str,
        func: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute an oVirt API operation with automatic retry on transient network/engine restart errors."""
        max_retries = max(1, self.config.ovirt_max_retries)
        last_exc: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                return func(*args, **kwargs)
            except (sdk.AuthError, OvirtAuthError):
                raise
            except Exception as exc:
                last_exc = exc
                err_str = str(exc).lower()
                is_transient = any(
                    sig in err_str
                    for sig in (
                        "503",
                        "502",
                        "connection refused",
                        "timeout",
                        "timed out",
                        "broken pipe",
                        "reset by peer",
                    )
                )
                if not is_transient or attempt >= max_retries:
                    break

                backoff = attempt * 2
                logger.warning(
                    "Operation '%s' failed due to transient engine error: %s (attempt %d/%d). Retrying in %ds...",
                    operation_name,
                    exc,
                    attempt,
                    max_retries,
                    backoff,
                )
                time.sleep(backoff)
                # Invalidate stale connection so next attempt reconnects cleanly
                self.close()

        if last_exc:
            raise last_exc

    def test_connection(self) -> dict[str, Any]:
        """Test the connection and return engine system information."""
        conn = self.get_connection()
        try:
            system_service = conn.system_service()
            api_summary = system_service.get()
            product_info = (
                api_summary.product_info if hasattr(api_summary, "product_info") else None
            )

            version_str = "unknown"
            name_str = "oVirt / OLVM Engine"
            if product_info:
                version_str = getattr(product_info.version, "full_version", "unknown")
                name_str = getattr(product_info, "name", name_str)

            return {
                "status": "connected",
                "product_name": name_str,
                "version": version_str,
                "url": self.config.sanitized_url(),
                "username": self.config.ovirt_username,
            }
        except sdk.AuthError as exc:
            raise OvirtAuthError(f"Authentication failed during health check: {exc}") from exc
        except Exception as exc:
            raise OvirtConnectionError(f"Health check failed: {exc}") from exc

    def close(self) -> None:
        """Close the active connection."""
        if self._connection is not None:
            try:
                self._connection.close()
            except Exception as exc:
                logger.debug("Error while closing oVirt connection: %s", exc)
            finally:
                self._connection = None

    def find_resource_by_id_or_name(
        self,
        service: Any,
        identifier: str,
        resource_type_name: str = "resource",
    ) -> Any:
        """Find a resource by UUID or by exact name search.

        Avoids duplication across tools and extension modules.
        """
        # 1. Try finding by direct UUID get
        single_service_fn = getattr(service, f"{resource_type_name}_service", None)
        if single_service_fn is None and resource_type_name in ("vm_pool", "pool"):
            single_service_fn = getattr(service, "pool_service", None) or getattr(
                service, "vm_pool_service", None
            )
        if single_service_fn is None and resource_type_name in ("vnic_profile", "vnic profile", "profile"):
            single_service_fn = getattr(service, "profile_service", None) or getattr(
                service, "vnic_profile_service", None
            )
        if single_service_fn:
            try:
                item_service = single_service_fn(identifier)
                item = item_service.get()
                if item is not None:
                    return item
            except Exception:
                # Expected when identifier is not a valid UUID
                pass

        # 2. Try searching by name
        clean_name = identifier.replace("'", "").replace('"', "")
        if hasattr(service, "list"):
            matching_items: list[Any] = []
            seen_ids: set[str] = set()

            def _add_match(item: Any) -> None:
                i_id = str(getattr(item, "id", id(item)))
                if i_id not in seen_ids:
                    seen_ids.add(i_id)
                    matching_items.append(item)

            try:
                results = service.list(search=f"name={clean_name}")
                if results:
                    for r in results:
                        if getattr(r, "name", None) in (identifier, clean_name) or getattr(
                            r, "user_name", None
                        ) in (identifier, clean_name):
                            _add_match(r)
            except Exception as exc:
                logger.debug(
                    "Search by name '%s' on %s failed: %s",
                    identifier,
                    resource_type_name,
                    exc,
                )

            # Fallback: exact in-memory match over all items if search query is unsupported or ignored
            if not matching_items:
                try:
                    all_items = service.list()
                    if all_items:
                        for item in all_items:
                            if getattr(item, "name", None) in (identifier, clean_name) or getattr(
                                item, "user_name", None
                            ) in (identifier, clean_name):
                                _add_match(item)
                except Exception:
                    pass

            if len(matching_items) == 1:
                return matching_items[0]
            if len(matching_items) > 1:
                matching_ids = [str(getattr(m, "id", "unknown")) for m in matching_items]
                raise OvirtValidationError(
                    f"Ambiguous {resource_type_name} identifier '{identifier}': found {len(matching_items)} "
                    f"resources sharing this identical name (UUIDs: {', '.join(matching_ids)}). "
                    f"To prevent accidental operations on the wrong resource, please specify the exact UUID.",
                    details={
                        "identifier": identifier,
                        "resource_type": resource_type_name,
                        "matching_count": len(matching_items),
                        "matching_ids": matching_ids,
                    },
                )

        raise NotFoundError(resource_type_name, identifier)


_client: OvirtClient | None = None


def get_client() -> OvirtClient:
    """Get the global OvirtClient instance."""
    global _client
    if _client is None:
        _client = OvirtClient()
    return _client
