#!/usr/bin/env bash
# ==============================================================================
# NetWatch Cloud Sync & Push Utility
# Pushes local code changes to GitHub so Google Colab / Cloud runner re-executes
# ==============================================================================

set -e

MSG="${1:-Auto-sync: update code for cloud testing $(date '+%Y-%m-%d %H:%M:%S')}"

echo "========================================================"
echo "🚀 NetWatch — Pushing changes to Cloud..."
echo "========================================================"

# Add all changes
git add -A

# Check if there are changes to commit
if git diff-index --quiet HEAD --; then
    echo "ℹ️ No uncommitted local changes detected."
else
    git commit -m "$MSG"
    echo "✓ Changes committed: '$MSG'"
fi

# Push to origin
echo "Pushing to GitHub..."
git push origin $(git rev-parse --abbrev-ref HEAD)

echo "========================================================"
echo "✅ Code is synced with GitHub!"
echo "👉 In Google Colab, run the 'Live Pull & Test' cell."
echo "========================================================"
