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
# Step 1: Rebuild from this checkout, never reuse an unverified dist directory.
# ----------------------------------------------------------
echo "🔨 Building binary from current source with PyInstaller..."
python3 -m pip install -r requirements-linux.txt
python3 -m PyInstaller HealthPro_linux.spec --clean --noconfirm

echo "📦 Creating AppImage v${VERSION}..."

# ----------------------------------------------------------
# Step 2: Pin and verify the official release tool, including cached copies.
# Digest: GitHub release asset metadata for AppImage/appimagetool 1.9.1.
# ----------------------------------------------------------
TOOL_VERSION="1.9.1"
TOOL_SHA256="ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"
APPIMAGETOOL="build/appimagetool-${TOOL_VERSION}-x86_64.AppImage"
mkdir -p build
if [ ! -f "${APPIMAGETOOL}" ]; then
    TOOL_DOWNLOAD="${APPIMAGETOOL}.download.$$"
    trap 'rm -f "${TOOL_DOWNLOAD}"' EXIT
    curl -fSL "https://github.com/AppImage/appimagetool/releases/download/${TOOL_VERSION}/appimagetool-x86_64.AppImage" -o "${TOOL_DOWNLOAD}"
    echo "${TOOL_SHA256}  ${TOOL_DOWNLOAD}" | sha256sum --check --status
    mv "${TOOL_DOWNLOAD}" "${APPIMAGETOOL}"
    trap - EXIT
fi
echo "${TOOL_SHA256}  ${APPIMAGETOOL}" | sha256sum --check --status
chmod +x "${APPIMAGETOOL}"

# Pin the runtime too: appimagetool otherwise downloads a moving default runtime.
# Digest: GitHub AppImage/type2-runtime 20251108 release asset 326011592.
RUNTIME_SHA256="2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d"
RUNTIME="build/runtime-x86_64-${RUNTIME_SHA256}"
if [ ! -f "${RUNTIME}" ]; then
    RUNTIME_DOWNLOAD="${RUNTIME}.download.$$"
    trap 'rm -f "${RUNTIME_DOWNLOAD}"' EXIT
    curl -fSL "https://github.com/AppImage/type2-runtime/releases/download/20251108/runtime-x86_64" -o "${RUNTIME_DOWNLOAD}"
    echo "${RUNTIME_SHA256}  ${RUNTIME_DOWNLOAD}" | sha256sum --check --status
    mv "${RUNTIME_DOWNLOAD}" "${RUNTIME}"
    trap - EXIT
fi
echo "${RUNTIME_SHA256}  ${RUNTIME}" | sha256sum --check --status

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
"${APPIMAGETOOL}" --appimage-extract-and-run --runtime-file "${RUNTIME}" "${APPDIR}" "${OUTPUT_FILE}" \
    2>/dev/null \
    || "${APPIMAGETOOL}" --runtime-file "${RUNTIME}" "${APPDIR}" "${OUTPUT_FILE}"

chmod +x "${OUTPUT_FILE}"

echo ""
echo "✅ Done! AppImage created:"
echo "   ${OUTPUT_FILE}"
echo ""
echo "Run with:"
echo "   chmod +x ${OUTPUT_FILE}"
echo "   ./${OUTPUT_FILE}"

