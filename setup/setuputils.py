#!/usr/bin/env python3
"""
Setup utilities for Chronicle quickstart script.
Provides port checking, Redis database validation, and other setup helpers.
"""

import sys
import socket
import subprocess
import json
from typing import Optional, List, Tuple


def check_port_in_use(port: int) -> bool:
    """
    Check if a TCP port is already in use.

    Args:
        port: Port number to check

    Returns:
        True if port is in use, False if available
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            result = sock.connect_ex(('127.0.0.1', port))
            return result == 0
    except Exception:
        return False


def check_redis_db_has_data(db_num: int, container_name: str = "redis") -> bool:
    """
    Check if a Redis database has any keys.

    Args:
        db_num: Redis database number (0-15)
        container_name: Name of the Redis Docker container

    Returns:
        True if database has data, False if empty or Redis unavailable
    """
    try:
        # Check if Redis container is running
        ps_result = subprocess.run(
            ["docker", "ps", "--filter", f"name={container_name}",
             "--filter", "status=running", "-q"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if not ps_result.stdout.strip():
            # Redis not running - consider database empty
            return False

        # Check database size
        dbsize_result = subprocess.run(
            ["docker", "exec", container_name, "redis-cli", "-n", str(db_num), "DBSIZE"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if dbsize_result.returncode == 0:
            output = dbsize_result.stdout.strip()
            # Extract number from output like "(integer) 0"
            if ")" in output:
                count = int(output.split(")")[-1].strip())
            else:
                count = int(output)
            return count > 0

        return False

    except Exception:
        return False


def get_redis_db_env_marker(db_num: int, container_name: str = "redis") -> Optional[str]:
    """
    Get the environment marker stored in a Redis database.

    Args:
        db_num: Redis database number (0-15)
        container_name: Name of the Redis Docker container

    Returns:
        Environment name if marker exists, None otherwise
    """
    try:
        # Check if Redis container is running
        ps_result = subprocess.run(
            ["docker", "ps", "--filter", f"name={container_name}",
             "--filter", "status=running", "-q"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if not ps_result.stdout.strip():
            return None

        # Get environment marker
        result = subprocess.run(
            ["docker", "exec", container_name, "redis-cli", "-n", str(db_num),
             "GET", "chronicle:env:name"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            env_name = result.stdout.strip()
            # Redis returns "(nil)" for non-existent keys
            if env_name and env_name != "(nil)":
                return env_name

        return None

    except Exception:
        return None


def set_redis_db_env_marker(db_num: int, env_name: str, container_name: str = "redis") -> bool:
    """
    Set the environment marker in a Redis database.

    Args:
        db_num: Redis database number (0-15)
        env_name: Environment name to store
        container_name: Name of the Redis Docker container

    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if Redis container is running
        ps_result = subprocess.run(
            ["docker", "ps", "--filter", f"name={container_name}",
             "--filter", "status=running", "-q"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if not ps_result.stdout.strip():
            return False

        # Set environment marker (no expiration)
        result = subprocess.run(
            ["docker", "exec", container_name, "redis-cli", "-n", str(db_num),
             "SET", "chronicle:env:name", env_name],
            capture_output=True,
            text=True,
            timeout=5
        )

        return result.returncode == 0

    except Exception:
        return False


def find_available_redis_db(preferred_db: int = 0, env_name: Optional[str] = None,
                            container_name: str = "redis") -> int:
    """
    Find an available Redis database (0-15) for the given environment.

    First checks if any database already has this environment's marker.
    If not, tries preferred database, then finds an empty one.

    Args:
        preferred_db: Preferred database number to try first
        env_name: Environment name to match against stored markers
        container_name: Name of the Redis Docker container

    Returns:
        Available database number, or preferred_db if all checks fail
    """
    # If environment name provided, check for existing database with this marker
    if env_name:
        for db in range(16):
            marker = get_redis_db_env_marker(db, container_name)
            if marker == env_name:
                # Found database already used by this environment
                return db

    # Try preferred database first if empty
    if not check_redis_db_has_data(preferred_db, container_name):
        return preferred_db

    # Try all databases 0-15 for empty one
    for db in range(16):
        if not check_redis_db_has_data(db, container_name):
            return db

    # All databases have data or Redis unavailable - return preferred
    return preferred_db


def validate_ports(ports: List[int]) -> Tuple[bool, List[int]]:
    """
    Validate that a list of ports are available.

    Args:
        ports: List of port numbers to check

    Returns:
        Tuple of (all_available, list_of_conflicts)
    """
    conflicts = [port for port in ports if check_port_in_use(port)]
    return (len(conflicts) == 0, conflicts)


def main():
    """CLI interface for setup utilities."""
    if len(sys.argv) < 2:
        print("Usage: setuputils.py <command> [args...]", file=sys.stderr)
        print("\nCommands:", file=sys.stderr)
        print("  check-port <port>                      - Check if port is in use", file=sys.stderr)
        print("  check-redis-db <db_num>                - Check if Redis DB has data", file=sys.stderr)
        print("  find-redis-db <preferred_db> [env_name] - Find available Redis DB", file=sys.stderr)
        print("  set-redis-marker <db_num> <env_name>   - Set environment marker in Redis DB", file=sys.stderr)
        print("  get-redis-marker <db_num>              - Get environment marker from Redis DB", file=sys.stderr)
        print("  validate-ports <port1> [port2...]      - Check multiple ports", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    try:
        if command == "check-port":
            if len(sys.argv) < 3:
                print("Error: Port number required", file=sys.stderr)
                sys.exit(1)
            port = int(sys.argv[2])
            in_use = check_port_in_use(port)
            print(json.dumps({"in_use": in_use, "port": port}))
            sys.exit(0 if not in_use else 1)

        elif command == "check-redis-db":
            if len(sys.argv) < 3:
                print("Error: Database number required", file=sys.stderr)
                sys.exit(1)
            db_num = int(sys.argv[2])
            has_data = check_redis_db_has_data(db_num)
            print(json.dumps({"has_data": has_data, "db_num": db_num}))
            sys.exit(0 if not has_data else 1)

        elif command == "find-redis-db":
            preferred_db = int(sys.argv[2]) if len(sys.argv) > 2 else 0
            env_name = sys.argv[3] if len(sys.argv) > 3 else None
            available_db = find_available_redis_db(preferred_db, env_name)

            # Check if we matched an existing environment
            existing_marker = get_redis_db_env_marker(available_db) if env_name else None
            matched_env = existing_marker == env_name if existing_marker else False

            print(json.dumps({
                "db_num": available_db,
                "preferred": preferred_db,
                "changed": available_db != preferred_db,
                "matched_env": matched_env,
                "env_marker": existing_marker
            }))
            sys.exit(0)

        elif command == "set-redis-marker":
            if len(sys.argv) < 4:
                print("Error: Database number and environment name required", file=sys.stderr)
                sys.exit(1)
            db_num = int(sys.argv[2])
            env_name = sys.argv[3]
            success = set_redis_db_env_marker(db_num, env_name)
            print(json.dumps({"success": success, "db_num": db_num, "env_name": env_name}))
            sys.exit(0 if success else 1)

        elif command == "get-redis-marker":
            if len(sys.argv) < 3:
                print("Error: Database number required", file=sys.stderr)
                sys.exit(1)
            db_num = int(sys.argv[2])
            marker = get_redis_db_env_marker(db_num)
            print(json.dumps({"db_num": db_num, "env_marker": marker}))
            sys.exit(0 if marker else 1)

        elif command == "validate-ports":
            if len(sys.argv) < 3:
                print("Error: At least one port required", file=sys.stderr)
                sys.exit(1)
            ports = [int(p) for p in sys.argv[2:]]
            all_available, conflicts = validate_ports(ports)
            print(json.dumps({
                "available": all_available,
                "conflicts": conflicts,
                "ports": ports
            }))
            sys.exit(0 if all_available else 1)

        else:
            print(f"Error: Unknown command '{command}'", file=sys.stderr)
            sys.exit(1)

    except ValueError as e:
        print(f"Error: Invalid number - {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
