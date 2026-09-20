"""
Synthetic scenario traffic generator.

Produces clearly-labelled SYNTHETIC traffic for the Scenario / Demo screen.
This is NOT real network data and is only ever displayed with the
"SYNTHETIC DATA" source badge in the UI.

Each scenario builds a list of PacketRecord-like dicts that flow through the
exact same ingestion -> feature extraction -> world model pipeline as a real
uploaded PCAP, so every displayed number is still computed, never fabricated.
"""

import random
from datetime import datetime, timedelta

from netwatch.ingestion.parser import PacketRecord

_SCENARIO_HOSTS = [
    ("10.10.10.5", "internal-host-05"),
    ("10.10.10.17", "internal-host-17"),
    ("10.10.10.23", "internal-host-23"),
    ("10.10.20.10", "internal-host-10"),
    ("10.10.20.41", "internal-host-41"),
]

_ATTACKER = "172.16.88.100"
_SERVICES = [(22, "ssh"), (80, "http"), (443, "https"), (3306, "mysql"), (3389, "rdp"), (25, "smtp")]


def _mk(index: int, src: str, dst: str, sport: int, dport: int, protocol: str, flags: str,
        payload: int, ttl: int, window: int) -> dict:
    ts = datetime.now().replace(microsecond=0) + timedelta(milliseconds=index * 40)
    return {
        "timestamp": ts.isoformat(),
        "src_ip": src,
        "dst_ip": dst,
        "src_port": sport,
        "dst_port": dport,
        "protocol": protocol,
        "flags": flags,
        "bytes_sent": payload + (window % 128),
        "packets": 1,
        "ttl": ttl,
        "payload_size": payload,
        "tcp_window": window,
        "duration": 0.001,
        "label": 0,
        "stage": None,
    }


def _benign_flow(index, host_ip, attacker_prob=0.0):
    dport, _service = _SERVICES[index % len(_SERVICES)]
    flags = random.choice(["SA", "A", "A", "PA", "FA"])
    return _mk(index, host_ip, "172.16.90." + str(random.randint(1, 20)), random.randint(1024, 60000), dport,
               "TCP", flags, random.randint(32, 1200), 64, random.randint(4096, 65535))


def _scan(index, host, dport, stage="Reconnaissance"):
    return _mk(index, _ATTACKER, host, random.randint(1024, 65000), dport, "TCP", "S", 0, 128,
               random.randint(512, 4096)) | {"label": 1, "stage": stage}


def _bruteforce(index, host, dport, stage="Credential Access"):
    return _mk(index, _ATTACKER, host, random.randint(1024, 65000), dport, "TCP", "SA", 96, 128,
               random.randint(512, 4096)) | {"label": 1, "stage": stage}


def _dos(index, host, dport, stage="Impact"):
    return _mk(index, _ATTACKER, host, random.randint(1024, 65000), dport, "TCP", "S", 0, 128,
               random.randint(256, 1024)) | {"label": 1, "stage": stage}


def generate_scenario(name: str, seed: int = 42) -> list:
    """Generate a labelled synthetic traffic list for the named scenario."""
    records = []

    if name == "benign":
        for i in range(4000):
            rec = _benign_flow(i, _SCENARIO_HOSTS[i % len(_SCENARIO_HOSTS)][0])
            records.append(rec)
    elif name == "recon":
        for i in range(1800):
            records.append(_benign_flow(i, _SCENARIO_HOSTS[i % len(_SCENARIO_HOSTS)][0]))
        base = 1800
        target = _SCENARIO_HOSTS[0][0]
        for j in range(1200):
            records.append(_scan(base + j, target, random.choice([p for p, _ in _SERVICES])))
    elif name == "bruteforce":
        for i in range(1800):
            records.append(_benign_flow(i, _SCENARIO_HOSTS[i % len(_SCENARIO_HOSTS)][0]))
        base = 1800
        target = _SCENARIO_HOSTS[0][0]
        for j in range(1400):
            records.append(_bruteforce(base + j, target, 22))
    elif name == "dos":
        for i in range(1500):
            records.append(_benign_flow(i, _SCENARIO_HOSTS[i % len(_SCENARIO_HOSTS)][0]))
        base = 1500
        target = _SCENARIO_HOSTS[2][0]
        for j in range(3000):
            records.append(_dos(base + j, target, 80))
    elif name == "mixed":
        for i in range(1600):
            records.append(_benign_flow(i, _SCENARIO_HOSTS[i % len(_SCENARIO_HOSTS)][0]))
        base = 1600
        target = _SCENARIO_HOSTS[0][0]
        for j in range(800):
            records.append(_scan(base + j, target, random.choice([p for p, _ in _SERVICES])))
        base += 800
        for j in range(600):
            records.append(_bruteforce(base + j, target, 22))
        base += 600
        for j in range(900):
            records.append(_dos(base + j, _SCENARIO_HOSTS[2][0], 80))
    else:
        raise ValueError(f"Unknown scenario: {name}")

    records.sort(key=lambda r: r["timestamp"])
    return [PacketRecord(**r) for r in records]


def scenario_manifest() -> list:
    """Return the list of supported demo scenarios with real descriptions."""
    return [
        {"id": "benign", "name": "Benign Traffic", "attack_types": [],
         "description": "Normal corporate client-server traffic with no attack behaviour."},
        {"id": "recon", "name": "Reconnaissance / Port Scan", "attack_types": ["PortScan"],
         "description": "Hostile host sweeps a target across a range of service ports."},
        {"id": "bruteforce", "name": "Brute Force Login", "attack_types": ["BruteForce"],
         "description": "Repeated credential-guessing attempts against the SSH service."},
        {"id": "dos", "name": "Denial of Service", "attack_types": ["DoS"],
         "description": "High-rate SYN flood targeting the public web service."},
        {"id": "mixed", "name": "Multi-Stage Attack", "attack_types": ["PortScan", "BruteForce", "DoS"],
         "description": "Progression from reconnaissance through brute force to denial of service."},
    ]
