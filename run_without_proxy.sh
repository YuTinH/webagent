#!/bin/bash
# Complete proxy bypass script for testing

# Unset all proxy environment variables
unset http_proxy
unset https_proxy
unset HTTP_PROXY
unset HTTPS_PROXY
unset ftp_proxy
unset FTP_PROXY
unset all_proxy
unset ALL_PROXY

# Set NO_PROXY to bypass everything
export NO_PROXY="*"
export no_proxy="*"

echo "=== Proxy Environment Check ==="
env | grep -i proxy || echo "✅ No proxy variables set"
echo ""

# Run the command passed as arguments
echo "=== Running: $@ ==="
exec "$@"
