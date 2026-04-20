# FILE: backend/app/vpn/amneziawg.py
# VERSION: 1.0.0
# ROLE: RUNTIME
# MAP_MODE: EXPORTS
# START_MODULE_CONTRACT
#   PURPOSE: AmneziaWG integration — key generation, peer management, config generation, obfuscation parameter handling
#   SCOPE: Low-level WireGuard operations via `awg` CLI; server config file management; peer stats from `awg show dump`; capacity-aware client IP allocation
#   DEPENDS: M-001 (core config, security), M-032 (vpn-network-addressing-capacity), stdlib (asyncio, re, pathlib), httpx, loguru
#   LINKS: M-003 (vpn), M-032, V-M-003, V-M-023, V-M-032
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   AmneziaWGManager - Manager class for AWG CLI operations (generate_keypair, generate_preshared_key, get_server_public_key, get_server_endpoint, get_next_client_ip, create_client_config, add_peer, remove_peer, get_peer_stats, is_service_running, restart_service, update_obfuscation)
#   wg_manager - Global singleton instance
# END_MODULE_MAP
#
# START_CHANGE_SUMMARY
#   LAST_CHANGE: v3.2.0 - Made client IP allocation subnet-explicit and capacity-aware for 500/1000-device pools
#   LAST_CHANGE: v3.0.0 - Load deploy-time AWG CLIENT_PROFILE, render optional PresharedKey, and avoid raw profile logs
#   LAST_CHANGE: v2.8.0 - Converted to full GRACE MODULE_CONTRACT/MAP format with START/END blocks
# END_CHANGE_SUMMARY
#
"""
AmneziaWG integration module.
Handles WireGuard key generation, peer management, and config generation.

LEGACY SOURCE: krot-prod-main/backend/amneziawg.py
PROTOCOL: AmneziaWG parameters MUST remain unchanged for compatibility.
"""
# <!-- GRACE: module="M-003" contract="amneziawg-integration" -->
# <!-- GRACE: legacy-source="krot-prod-main/backend/amneziawg.py" -->

import asyncio
import os
import re
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import httpx
from loguru import logger

from app.core.config import settings
from app.core.vpn_network import next_client_ip
from app.vpn.obfuscation import (
    AWGObfuscationProfile,
    AWGProfileError,
    parse_awg_profile_file,
    profile_from_mapping,
)


# START_BLOCK: AmneziaWGManager
class AmneziaWGManager:
    """
    Manager for AmneziaWG VPN operations.

    IMPORTANT: Obfuscation parameters (Jc, Jmin, Jmax, S1, S2, H1-H4)
    must match between server and client for successful connection.
    """

    def __init__(
        self,
        config_dir: str = "/etc/amnezia/amneziawg",
        interface: str = "awg0",
    ):
        self.config_dir = Path(config_dir)
        self.interface = interface
        self.server_config = self.config_dir / f"{self.interface}.conf"

        # CLIENT_PROFILE is preferred, server config parsing preserves upgrades,
        # and legacy AWG_* stays as the final no-rotation fallback.
        self.obfuscation_profile: AWGObfuscationProfile | None = None
        self.obfuscation = self._load_obfuscation_params()

        logger.info(f"[VPN] AmneziaWGManager initialized with interface {interface}")
        logger.debug("[VPN] AWG obfuscation parameters loaded without dumping profile values")

    # START_BLOCK: _load_obfuscation_params
    def _load_obfuscation_params(self) -> dict[str, int]:
        """Load client-facing obfuscation params without rotating existing installs."""
        try:
            client_profile = settings.awg_client_obfuscation_params
            if client_profile is not None:
                profile = profile_from_mapping(client_profile)
                self.obfuscation_profile = profile
                return profile.as_dict()
        except AWGProfileError as e:
            raise ValueError(f"Invalid AWG_CLIENT profile: {e}") from e

        try:
            parsed_profile = parse_awg_profile_file(self.server_config)
            if parsed_profile is not None:
                self.obfuscation_profile = parsed_profile
                logger.info("[VPN][config][AWG_PROFILE_PRESERVED] Loaded obfuscation profile from awg0.conf")
                return parsed_profile.as_dict()
        except AWGProfileError:
            logger.warning(
                "[VPN][config][AWG_PROFILE_PRESERVED] Existing awg0.conf profile is outside new bounds; "
                "falling back to legacy AWG_* settings"
            )

        try:
            profile = profile_from_mapping(settings.awg_obfuscation_params)
            self.obfuscation_profile = profile
            return profile.as_dict()
        except AWGProfileError:
            # Legacy deployments may still contain old AmneziaWG examples such
            # as Jc=120/Jmax=1000. Keep them for compatibility until rotation.
            return settings.awg_obfuscation_params
    # END_BLOCK: _load_obfuscation_params

    # START_BLOCK: generate_keypair
    async def generate_keypair(self) -> Tuple[str, str]:
        """
        Generate a new WireGuard keypair.

        Returns:
            Tuple of (private_key, public_key)
        """
        try:
            # Generate private key
            private_proc = await asyncio.create_subprocess_exec(
                "awg", "genkey",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            private_stdout, private_stderr = await private_proc.communicate()
            if private_proc.returncode != 0:
                raise RuntimeError(private_stderr.decode().strip() or "awg genkey failed")

            private_key = private_stdout.decode().strip()

            # Derive public key
            public_proc = await asyncio.create_subprocess_exec(
                "awg", "pubkey",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            public_stdout, public_stderr = await public_proc.communicate(private_key.encode())
            if public_proc.returncode != 0:
                raise RuntimeError(public_stderr.decode().strip() or "awg pubkey failed")

            public_key = public_stdout.decode().strip()

            logger.debug(f"[VPN] Generated keypair: public={public_key[:20]}...")
            return private_key, public_key

        except Exception as e:
            logger.error(f"[VPN] Error generating keypair: {e}")
            raise
    # END_BLOCK: generate_keypair

    # START_BLOCK: generate_preshared_key
    async def generate_preshared_key(self) -> str:
        """Generate a new AmneziaWG preshared key for one client peer."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "awg", "genpsk",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(stderr.decode().strip() or "awg genpsk failed")

            return stdout.decode().strip()
        except Exception as e:
            logger.error(f"[VPN] Error generating preshared key: {e}")
            raise
    # END_BLOCK: generate_preshared_key

    def get_server_public_key(self) -> Optional[str]:
        """
        Get server's public key from config directory.
        
        Returns:
            Server public key or None if not found.
        """
        try:
            key_file = self.config_dir / "vpn_pub"
            if key_file.exists():
                return key_file.read_text().strip()
        except Exception as e:
            logger.error(f"[VPN] Error reading server public key: {e}")
        return None

    async def get_server_endpoint(self) -> Optional[str]:
        """
        Get server's external IP address.
        
        Returns:
            External IP or None if detection fails.
        """
        endpoints = [
            "https://api.ipify.org",
            "https://ifconfig.me",
            "https://api4.my-ip.io/ip",
        ]
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            for ep in endpoints:
                try:
                    response = await client.get(ep)
                    if response.status_code == 200:
                        return response.text.strip()
                except Exception:
                    continue
        
        logger.warning("[VPN] Could not detect external IP")
        return None

    def get_next_client_ip(
        self,
        used_ips: set[str],
        *,
        subnet: str | None = None,
        gateway_address: str | None = None,
    ) -> str:
        """
        Get the next available IP address in the VPN subnet.
        
        Args:
            used_ips: Set of already used IP addresses
            subnet: Optional explicit client subnet, otherwise settings.vpn_network is used
            gateway_address: Optional explicit gateway address to reserve
            
        Returns:
            Next available IP address
        """
        network = settings.vpn_network
        if gateway_address is not None:
            resolved_gateway = gateway_address
        elif subnet is None:
            resolved_gateway = network.client_gateway
        else:
            resolved_gateway = None
        return next_client_ip(
            used_ips,
            client_subnet=subnet or network.client_subnet,
            gateway_address=resolved_gateway,
            capacity_profile=settings.vpn_capacity_profile,
        )

    # START_BLOCK: create_client_config
    def create_client_config(
        self,
        private_key: str,
        address: str,
        server_public_key: str,
        endpoint: str,
        preshared_key: str | None = None,
    ) -> str:
        """
        Create a client configuration file content.

        Args:
            private_key: Client's private key
            address: Client's VPN IP address
            server_public_key: Server's public key
            endpoint: Server's endpoint (IP:port)
            preshared_key: Optional AmneziaWG preshared key for this peer

        Returns:
            Configuration file content as string
        """
        preshared_key_line = f"PresharedKey = {preshared_key}\n" if preshared_key else ""
        config = f"""[Interface]
PrivateKey = {private_key}
Address = {address}/32
DNS = {settings.vpn_dns}
MTU = {settings.vpn_mtu}
Jc = {self.obfuscation['jc']}
Jmin = {self.obfuscation['jmin']}
Jmax = {self.obfuscation['jmax']}
S1 = {self.obfuscation['s1']}
S2 = {self.obfuscation['s2']}
H1 = {self.obfuscation['h1']}
H2 = {self.obfuscation['h2']}
H3 = {self.obfuscation['h3']}
H4 = {self.obfuscation['h4']}

[Peer]
PublicKey = {server_public_key}
{preshared_key_line}Endpoint = {endpoint}:{settings.vpn_port}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
"""
        return config
    # END_BLOCK: create_client_config

    # START_BLOCK: add_peer
    async def add_peer(self, public_key: str, address: str, preshared_key: str | None = None) -> bool:
        """
        Add a peer to the VPN server.

        Args:
            public_key: Client's public key
            address: Client's VPN IP address
            preshared_key: Optional preshared key stored for this peer

        Returns:
            True if successful, False otherwise
        """
        try:
            # Add peer config to file
            preshared_key_line = f"PresharedKey = {preshared_key}\n" if preshared_key else ""
            peer_config = (
                "\n\n[Peer]\n"
                f"PublicKey = {public_key}\n"
                f"{preshared_key_line}"
                f"AllowedIPs = {address}/32\n"
            )

            # Append to server config
            if self.server_config.exists():
                with open(self.server_config, "a") as f:
                    f.write(peer_config)
            else:
                raise FileNotFoundError(f"Server config not found: {self.server_config}")

            # Apply peer to running interface
            try:
                psk_file = None
                try:
                    command = ["awg", "set", self.interface, "peer", public_key]
                    if preshared_key:
                        psk_file = tempfile.NamedTemporaryFile("w", delete=False)
                        psk_file.write(f"{preshared_key}\n")
                        psk_file.close()
                        os.chmod(psk_file.name, 0o600)
                        command.extend(["preshared-key", psk_file.name])
                    command.extend(["allowed-ips", f"{address}/32"])

                    proc = await asyncio.create_subprocess_exec(
                        *command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await asyncio.wait_for(proc.wait(), timeout=5)
                finally:
                    if psk_file is not None:
                        Path(psk_file.name).unlink(missing_ok=True)

                if proc.returncode != 0:
                    stderr = await proc.stderr.read() if proc.stderr else b""
                    logger.warning(
                        "[VPN] Failed to add peer dynamically, relying on host-managed sync: "
                        f"{stderr.decode().strip() or proc.returncode}"
                    )

            except asyncio.TimeoutError:
                logger.warning("[VPN] Timeout adding peer dynamically, relying on host-managed sync")

            logger.info(f"[VPN] Added peer: {public_key[:20]}... -> {address}")
            return True

        except Exception as e:
            logger.error(f"[VPN] Error adding peer: {e}")
            return False
    # END_BLOCK: add_peer

    # START_BLOCK: remove_peer
    async def remove_peer(self, public_key: str) -> bool:
        """
        Remove a peer from the VPN server.

        Args:
            public_key: Client's public key

        Returns:
            True if successful, False otherwise
        """
        try:
            # Remove from running interface
            proc = await asyncio.create_subprocess_exec(
                "awg", "set", self.interface,
                "peer", public_key, "remove",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()

            # Remove from config file
            if self.server_config.exists():
                content = self.server_config.read_text()
                # Remove peer section
                pattern = (
                    rf'\n\[Peer\]\n'
                    rf'(?:(?!\n\[).)*?PublicKey\s*=\s*{re.escape(public_key)}\n'
                    rf'(?:(?!\n\[).)*?(?=\n\[|$)'
                )
                new_content = re.sub(pattern, '', content, flags=re.DOTALL)
                self.server_config.write_text(new_content)

            if proc.returncode != 0:
                stderr = await proc.stderr.read() if proc.stderr else b""
                logger.warning(
                    "[VPN] Failed to remove peer dynamically, relying on host-managed sync: "
                    f"{stderr.decode().strip() or proc.returncode}"
                )

            logger.info(f"[VPN] Removed peer: {public_key[:20]}...")
            return True

        except Exception as e:
            logger.error(f"[VPN] Error removing peer: {e}")
            return False
    # END_BLOCK: remove_peer

    # START_BLOCK: get_peer_stats
    async def get_peer_stats(self) -> dict:
        """
        Get statistics for all peers.

        Returns:
            Dict mapping public_key to stats dict
        """
        stats = {}

        try:
            proc = await asyncio.create_subprocess_exec(
                "awg", "show", self.interface, "dump",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            if proc.returncode != 0:
                return stats

            # Parse dump output
            # Format: private-key public-key listen-port fwmark
            # For each peer: public-key preshared-key endpoint allowed-ips latest-handshake transfer-rx transfer-tx
            lines = stdout.decode().strip().split('\n')

            if len(lines) < 2:
                return stats

            # Skip first line (interface info)
            for line in lines[1:]:
                parts = line.split('\t')
                if len(parts) >= 8:
                    peer_key = parts[0]
                    handshake = int(parts[4]) if parts[4].isdigit() else 0
                    rx_bytes = int(parts[5]) if parts[5].isdigit() else 0
                    tx_bytes = int(parts[6]) if parts[6].isdigit() else 0

                    from datetime import datetime, timezone
                    stats[peer_key] = {
                        "last_handshake": (
                            datetime.fromtimestamp(handshake, tz=timezone.utc)
                            if handshake > 0 else None
                        ),
                        "endpoint": parts[2] if len(parts) > 2 and parts[2] and parts[2] != "(none)" else None,
                        "upload": tx_bytes,  # tx = sent by client = upload
                        "download": rx_bytes,  # rx = received by client = download
                    }

        except Exception as e:
            logger.error(f"[VPN] Error getting peer stats: {e}")

        return stats
    # END_BLOCK: get_peer_stats

    async def is_service_running(self) -> bool:
        """Check if the VPN service is running."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "systemctl", "is-active", f"awg-quick@{self.interface}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return stdout.decode().strip() == "active"
        except Exception:
            return False

    async def restart_service(self) -> bool:
        """Restart the VPN service."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "systemctl", "restart", f"awg-quick@{self.interface}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()
            logger.info(f"[VPN] Service restarted: {self.interface}")
            return proc.returncode == 0
        except Exception as e:
            logger.error(f"[VPN] Error restarting service: {e}")
            return False

    # START_BLOCK: update_obfuscation
    def update_obfuscation(self, params: dict) -> bool:
        """
        Update obfuscation parameters in server config.

        WARNING: This will require all clients to update their configs!

        Args:
            params: Dict with obfuscation parameters

        Returns:
            True if successful, False otherwise
        """
        if not self.server_config.exists():
            return False

        try:
            content = self.server_config.read_text()

            for key, val in params.items():
                # Capitalize key name (Jc, Jmin, Jmax, S1, S2, H1-H4)
                k = key.capitalize() if key.lower() not in ("jmin", "jmax") else key.capitalize()
                if key.lower() == "jmin":
                    k = "Jmin"
                elif key.lower() == "jmax":
                    k = "Jmax"

                content = re.sub(rf'{k}\s*=\s*\d+', f'{k} = {val}', content, flags=re.IGNORECASE)
                self.obfuscation[key] = int(val)

            self.server_config.write_text(content)
            try:
                self.obfuscation_profile = profile_from_mapping(self.obfuscation)
            except AWGProfileError:
                self.obfuscation_profile = None
            logger.warning("[VPN] Obfuscation params updated; clients must refresh configs")
            return True

        except Exception as e:
            logger.error(f"[VPN] Error updating obfuscation: {e}")
            return False
    # END_BLOCK: update_obfuscation
# END_BLOCK: AmneziaWGManager


# Global instance
wg_manager = AmneziaWGManager()
