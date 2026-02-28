#!/bin/bash
# Helper script: Install Java 21, Node.js, firebase-tools, start emulator, and seed data.
set -e

echo "=== Step 1: Load nvm ==="
export NVM_DIR="/home/avisaha/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

if ! command -v nvm &> /dev/null; then
    echo "ERROR: nvm not found. Install it first:"
    echo "  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash"
    exit 1
fi

echo "=== Step 2: Ensure Node.js 20 ==="
nvm use 20 2>/dev/null || nvm install 20
echo "Node: $(node --version)"
echo "npm: $(npm --version)"

echo "=== Step 3: Install firebase-tools ==="
npm ls -g firebase-tools >/dev/null 2>&1 || npm install -g firebase-tools 2>&1 | tail -3
echo "firebase: $(firebase --version)"

echo "=== Step 4: Check Java version ==="
JAVA_VERSION=$(java -version 2>&1 | head -1 | awk -F '"' '{print $2}' | cut -d. -f1)
echo "Java major version: $JAVA_VERSION"
if [ "$JAVA_VERSION" -lt 21 ]; then
    echo ""
    echo "⚠️  Firebase emulator requires Java 21+. You have Java $JAVA_VERSION."
    echo ""
    echo "To install Java 21 (requires sudo):"
    echo "  sudo apt-get update && sudo apt-get install -y openjdk-21-jdk"
    echo ""
    echo "Or using SDKMAN (no sudo):"
    echo "  curl -s https://get.sdkman.io | bash"
    echo "  source ~/.sdkman/bin/sdkman-init.sh"
    echo "  sdk install java 21.0.2-open"
    echo ""
    echo "After installing Java 21, run this script again."
    exit 1
fi

echo "=== Step 5: Start Firestore emulator (background) ==="
cd /home/avisaha/Maintenance-Eye
firebase emulators:start --only firestore &
EMULATOR_PID=$!
echo "Emulator PID: $EMULATOR_PID"

# Wait for emulator to be ready
echo "Waiting for emulator to start..."
sleep 8

echo "=== Step 6: Run seed_data.py ==="
source backend/venv/bin/activate
FIRESTORE_EMULATOR_HOST=localhost:8081 python scripts/seed_data.py

echo ""
echo "=== Done! ==="
echo "Emulator is running in background (PID: $EMULATOR_PID)"
echo "View data at: http://localhost:4000/firestore"
echo "Press Ctrl+C to stop the emulator."

# Keep emulator running
wait $EMULATOR_PID
