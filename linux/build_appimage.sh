#!/usr/bin/env bash
# ============================================================
# build_appimage.sh — Build an AppImage for HealthPro
# Usage: ./linux/build_appimage.sh [version]
# Example: ./linux/build_appimage.sh 8.4.0
# ============================================================
set -euo pipefail

VERSION_INPUT="${1:-}"
PKG_NAME="HealthPro"
DIST_DIR="dist/healthpro"
APPDIR="build/${PKG_NAME}.AppDir"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"
VERSION="$(python3 -c 'from healthpro import __version__; print(__version__)')"
if [ -n "${VERSION_INPUT}" ] && [ "${VERSION_INPUT}" != "${VERSION}" ]; then
    echo "Version must match healthpro/version.txt (${VERSION})" >&2
    exit 1
fi

# ----------------------------------------------------------
# Step 1: Build binary with PyInstaller (if not already built)
# ----------------------------------------------------------
if [ ! -d "${DIST_DIR}" ]; then
    echo "🔨 Building binary with PyInstaller..."
    pip install -r requirements-linux.txt
    pyinstaller HealthPro_linux.spec --clean --noconfirm
fi

echo "📦 Creating AppImage v${VERSION}..."

# ----------------------------------------------------------
# Step 2: Download appimagetool if not present
# ----------------------------------------------------------
APPIMAGETOOL="build/appimagetool"
if [ ! -f "${APPIMAGETOOL}" ]; then
    echo "⬇️  Downloading appimagetool..."
    mkdir -p build
    TOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    curl -fSL "${TOOL_URL}" -o "${APPIMAGETOOL}"
    chmod +x "${APPIMAGETOOL}"
fi

# ----------------------------------------------------------
# Step 3: Create AppDir structure
# ----------------------------------------------------------
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin"
mkdir -p "${APPDIR}/usr/share/applications"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"

# Copy PyInstaller output
cp -r "${DIST_DIR}/"* "${APPDIR}/usr/bin/"

# Desktop file (AppImage needs it at root)
cp linux/healthpro.desktop "${APPDIR}/healthpro.desktop"
cp linux/healthpro.desktop "${APPDIR}/usr/share/applications/"

# Fix Exec for AppImage (use relative path)
sed -i 's|^Exec=healthpro|Exec=usr/bin/healthpro|' "${APPDIR}/healthpro.desktop"
sed -i 's|^Exec=healthpro|Exec=usr/bin/healthpro|' "${APPDIR}/usr/share/applications/healthpro.desktop"

# Icon
cp icon.png "${APPDIR}/healthpro.png"
cp icon.png "${APPDIR}/usr/share/icons/hicolor/256x256/apps/healthpro.png"
cp icon.png "${APPDIR}/.DirIcon"

# ----------------------------------------------------------
# Step 4: Create AppRun entry point
# ----------------------------------------------------------
cat > "${APPDIR}/AppRun" <<'APPRUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
export LD_LIBRARY_PATH="${HERE}/usr/bin:${LD_LIBRARY_PATH:-}"
export QT_PLUGIN_PATH="${HERE}/usr/bin/PyQt6/Qt6/plugins:${QT_PLUGIN_PATH:-}"
exec "${HERE}/usr/bin/healthpro" "$@"
APPRUN
chmod +x "${APPDIR}/AppRun"

# ----------------------------------------------------------
# Step 5: Build the AppImage
# ----------------------------------------------------------
export ARCH=x86_64
OUTPUT_FILE="dist/${PKG_NAME}-${VERSION}-x86_64.AppImage"

# appimagetool may need FUSE; try --appimage-extract-and-run as fallback
"${APPIMAGETOOL}" --appimage-extract-and-run "${APPDIR}" "${OUTPUT_FILE}" \
    2>/dev/null \
    || "${APPIMAGETOOL}" "${APPDIR}" "${OUTPUT_FILE}"

chmod +x "${OUTPUT_FILE}"

echo ""
echo "✅ Done! AppImage created:"
echo "   ${OUTPUT_FILE}"
echo ""
echo "Run with:"
echo "   chmod +x ${OUTPUT_FILE}"
echo "   ./${OUTPUT_FILE}"

