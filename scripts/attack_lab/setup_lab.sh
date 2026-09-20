#!/usr/bin/env bash
# ==============================================================================
# NetWatch Attack Lab — Network Namespace & Virtual Interface Setup
# ==============================================================================
#
# Creates an isolated virtual network environment for live attack simulation:
#   - Network namespace: "attacker"
#   - Attacker endpoint: 10.0.0.1/24 (veth-attacker inside "attacker" netns)
#   - Host endpoint:     10.0.0.2/24 (lab-veth0 on host)
#   - Target service:    10.0.0.2:8080 (Flask target web server)
#
# Usage:
#   sudo ./scripts/attack_lab/setup_lab.sh           # Setup environment
#   sudo ./scripts/attack_lab/setup_lab.sh clean     # Teardown & cleanup
#   sudo ./scripts/attack_lab/setup_lab.sh status    # Check status
# ==============================================================================

set -euo pipefail

NETNS="attacker"
VETH_HOST="lab-veth0"
VETH_PEER="veth-attacker"
HOST_IP="10.0.0.2/24"
ATTACKER_IP="10.0.0.1/24"
HOST_ADDR="10.0.0.2"
ATTACKER_ADDR="10.0.0.1"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${CYAN}[AttackLab]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[AttackLab ✓]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[AttackLab !]${NC} $1"
}

log_error() {
    echo -e "${RED}[AttackLab ✗]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)."
        exit 1
    fi
}

teardown_lab() {
    log_info "Tearing down Attack Lab network namespace and virtual interfaces..."
    
    # Remove host veth (removes peer inside netns automatically)
    if ip link show "$VETH_HOST" &>/dev/null; then
        ip link delete "$VETH_HOST" 2>/dev/null || true
        log_info "Deleted interface $VETH_HOST"
    fi

    # Delete network namespace
    if ip netns list | grep -q "^$NETNS\b"; then
        ip netns delete "$NETNS" 2>/dev/null || true
        log_info "Deleted netns $NETNS"
    fi

    log_success "Cleanup complete."
}

status_lab() {
    echo "========================================"
    echo "NETWATCH ATTACK LAB NETWORK STATUS"
    echo "========================================"
    
    # Check namespace
    if ip netns list | grep -q "^$NETNS\b"; then
        echo -e "Network Namespace:  ${GREEN}ACTIVE ($NETNS)${NC}"
    else
        echo -e "Network Namespace:  ${RED}NOT FOUND ($NETNS)${NC}"
    fi

    # Check host veth
    if ip link show "$VETH_HOST" &>/dev/null; then
        STATE=$(ip -br link show "$VETH_HOST" | awk '{print $2}')
        IP=$(ip -br addr show "$VETH_HOST" | awk '{print $3}')
        echo -e "Host Interface:     ${GREEN}$VETH_HOST (State: $STATE, IP: $IP)${NC}"
    else
        echo -e "Host Interface:     ${RED}NOT FOUND ($VETH_HOST)${NC}"
    fi

    # Check attacker veth inside namespace
    if ip netns list | grep -q "^$NETNS\b"; then
        if ip netns exec "$NETNS" ip link show "$VETH_PEER" &>/dev/null; then
            STATE=$(ip netns exec "$NETNS" ip -br link show "$VETH_PEER" | awk '{print $2}')
            IP=$(ip netns exec "$NETNS" ip -br addr show "$VETH_PEER" | awk '{print $3}')
            echo -e "Attacker Interface: ${GREEN}$VETH_PEER (State: $STATE, IP: $IP inside $NETNS)${NC}"
        else
            echo -e "Attacker Interface: ${RED}NOT FOUND ($VETH_PEER)${NC}"
        fi
        
        # Test ping
        echo -n "Connectivity Test (10.0.0.1 -> 10.0.0.2): "
        if ip netns exec "$NETNS" ping -c 1 -W 1 "$HOST_ADDR" &>/dev/null; then
            echo -e "${GREEN}REACHABLE${NC}"
        else
            echo -e "${RED}UNREACHABLE${NC}"
        fi
    fi

    # Check dumpcap capabilities
    DUMPCAP_BIN=$(command -v dumpcap 2>/dev/null || echo "/usr/bin/dumpcap")
    if [[ -f "$DUMPCAP_BIN" ]]; then
        CAPS=$(getcap "$DUMPCAP_BIN" 2>/dev/null || true)
        echo "Dumpcap Binary:     $DUMPCAP_BIN ($CAPS)"
    fi
    echo "========================================"
}

setup_lab() {
    check_root
    log_info "Initializing NetWatch Attack Lab..."

    # 1. Clean previous state if present
    if ip link show "$VETH_HOST" &>/dev/null || ip netns list | grep -q "^$NETNS\b"; then
        log_warn "Existing configuration found. Cleaning up first..."
        teardown_lab
    fi

    # 2. Create network namespace
    log_info "Creating network namespace: $NETNS"
    ip netns add "$NETNS"

    # 3. Create veth pair
    log_info "Creating veth pair: $VETH_HOST <---> $VETH_PEER"
    ip link add "$VETH_HOST" type veth peer name "$VETH_PEER"

    # 4. Move peer into attacker namespace
    log_info "Moving $VETH_PEER into namespace $NETNS"
    ip link set "$VETH_PEER" netns "$NETNS"

    # 5. Configure Host side interface
    log_info "Configuring host interface $VETH_HOST -> $HOST_IP"
    ip addr add "$HOST_IP" dev "$VETH_HOST"
    ip link set "$VETH_HOST" up

    # 6. Configure Attacker side interface
    log_info "Configuring attacker interface $VETH_PEER -> $ATTACKER_IP"
    ip netns exec "$NETNS" ip addr add "$ATTACKER_IP" dev "$VETH_PEER"
    ip netns exec "$NETNS" ip link set "$VETH_PEER" up
    ip netns exec "$NETNS" ip link set lo up

    # 7. Grant packet capture capabilities to dumpcap if available
    DUMPCAP_BIN=$(command -v dumpcap 2>/dev/null || echo "/usr/bin/dumpcap")
    if [[ -f "$DUMPCAP_BIN" ]]; then
        log_info "Setting packet capture capabilities on $DUMPCAP_BIN"
        setcap cap_net_raw,cap_net_admin=eip "$DUMPCAP_BIN" 2>/dev/null || log_warn "Could not setcap on $DUMPCAP_BIN (root execution will still work)"
    fi

    # 8. Verify connectivity
    log_info "Verifying virtual link connectivity..."
    if ip netns exec "$NETNS" ping -c 2 -W 1 "$HOST_ADDR" &>/dev/null; then
        log_success "Link verified: 10.0.0.1 (Attacker) <===> 10.0.0.2 (Host $VETH_HOST)"
    else
        log_error "Ping test failed between 10.0.0.1 and 10.0.0.2"
        exit 1
    fi

    log_success "Attack Lab environment is READY!"
    echo ""
    echo "Topology:"
    echo "  Attacker Namespace: 10.0.0.1 ($NETNS)"
    echo "  Host / Target App:  10.0.0.2 ($VETH_HOST)"
    echo "  Target Port:        8080"
    echo ""
    echo "To run attacks manually from the namespace:"
    echo "  sudo ip netns exec attacker python scripts/attack_lab/attack_runner.py --attack recon"
    echo ""
}

ACTION="${1:-setup}"

case "$ACTION" in
    setup)
        setup_lab
        ;;
    clean|teardown)
        check_root
        teardown_lab
        ;;
    status)
        status_lab
        ;;
    *)
        echo "Usage: $0 {setup|clean|status}"
        exit 1
        ;;
esac
