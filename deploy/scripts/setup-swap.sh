#!/usr/bin/env bash
# One-time 1 GB swap file for small DigitalOcean droplets (see DEPLOY.md).
# Run with sudo on the VM if containers OOM during startup spikes.
set -euo pipefail

SWAPFILE="${1:-/swapfile}"
SIZE="${2:-1G}"

if swapon --show | grep -q "$SWAPFILE"; then
  echo "swap_already_active path=$SWAPFILE"
  exit 0
fi

fallocate -l "$SIZE" "$SWAPFILE"
chmod 600 "$SWAPFILE"
mkswap "$SWAPFILE"
swapon "$SWAPFILE"
grep -q "$SWAPFILE" /etc/fstab || echo "$SWAPFILE none swap sw 0 0" >> /etc/fstab
echo "swap_ok path=$SWAPFILE size=$SIZE"
