#!/usr/bin/env bash
# ============================================================
# build_deb.sh — Build a .deb package for HealthPro
# Usage: ./linux/build_deb.sh [version]
# Example: ./linux/build_deb.sh 8.4.0
# ============================================================
set -euo pipefail

VERSION_INPUT="${1:-}"
ARCH="amd64"
PKG_NAME="healthpro"
PKG_DIR=""
DIST_DIR="dist/healthpro"

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

VERSION="${VERSION/rc/~rc}"
PKG_DIR="build/${PKG_NAME}_${VERSION}_${ARCH}"
echo "📦 Packaging .deb v${VERSION}..."

# ----------------------------------------------------------
# Step 2: Create Debian directory structure
# ----------------------------------------------------------
rm -rf "${PKG_DIR}"
mkdir -p "${PKG_DIR}/DEBIAN"
mkdir -p "${PKG_DIR}/opt/healthpro"
mkdir -p "${PKG_DIR}/usr/share/applications"
mkdir -p "${PKG_DIR}/usr/share/icons/hicolor/256x256/apps"
mkdir -p "${PKG_DIR}/usr/share/icons/hicolor/512x512/apps"
mkdir -p "${PKG_DIR}/usr/bin"

# ----------------------------------------------------------
# Step 3: Copy files
# ----------------------------------------------------------
cp -r "${DIST_DIR}/"* "${PKG_DIR}/opt/healthpro/"
cp linux/healthpro.desktop "${PKG_DIR}/usr/share/applications/"
cp icon.png "${PKG_DIR}/usr/share/icons/hicolor/256x256/apps/healthpro.png"
cp linux/healthpro_512.png "${PKG_DIR}/usr/share/icons/hicolor/512x512/apps/healthpro.png"

# Fix .desktop Exec path
sed -i 's|^Exec=healthpro|Exec=/opt/healthpro/healthpro|' \
    "${PKG_DIR}/usr/share/applications/healthpro.desktop"
sed -i 's|^Icon=healthpro|Icon=/usr/share/icons/hicolor/256x256/apps/healthpro.png|' \
    "${PKG_DIR}/usr/share/applications/healthpro.desktop"

# Create symlink launcher
ln -sf /opt/healthpro/healthpro "${PKG_DIR}/usr/bin/healthpro"

# ----------------------------------------------------------
# Step 4: Calculate installed size
# ----------------------------------------------------------
INSTALLED_SIZE=$(du -sk "${PKG_DIR}/opt" | cut -f1)

# ----------------------------------------------------------
# Step 5: Write DEBIAN/control
# ----------------------------------------------------------
cat > "${PKG_DIR}/DEBIAN/control" <<CTRL
Package: ${PKG_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Installed-Size: ${INSTALLED_SIZE}
Depends: libxcb-cursor0, libxcb-xinerama0, libxcb-icccm4, libxcb-keysyms1, libxcb-shape0, libxcb-render-util0, libxkbcommon0, libegl1, libgl1, libfontconfig1, libfreetype6, libtiff5 | libtiff6
Maintainer: LEEcDiang <leecdiang@users.noreply.github.com>
Homepage: https://github.com/leecdiang/Apple-Health-Pro
Description: Studio-Grade Data Engine for Apple Health Export
 Apple Health Pro is a high-performance cross-platform desktop tool
 designed for data analysts, health enthusiasts, and developers.
 It efficiently parses massive Apple Health XML export archives and
 transforms them into organized, analysis-ready professional datasets.
CTRL

# ----------------------------------------------------------
# Step 6: Post-install script (update icon cache)
# ----------------------------------------------------------
cat > "${PKG_DIR}/DEBIAN/postinst" <<'POSTINST'
#!/bin/bash
set -e
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database /usr/share/applications || true
fi
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor || true
fi
POSTINST
chmod 755 "${PKG_DIR}/DEBIAN/postinst"

# ----------------------------------------------------------
# Step 7: Fix permissions & build
# ----------------------------------------------------------
find "${PKG_DIR}/opt/healthpro" -type f -exec chmod 644 {} \;
find "${PKG_DIR}/opt/healthpro" -type d -exec chmod 755 {} \;
chmod 755 "${PKG_DIR}/opt/healthpro/healthpro"

dpkg-deb --build --root-owner-group "${PKG_DIR}"

DEB_FILE="${PKG_DIR}.deb"
echo ""
echo "✅ Done! Package created:"
echo "   ${DEB_FILE}"
echo ""
echo "Install with:"
echo "   sudo dpkg -i ${DEB_FILE}"
echo "   sudo apt-get install -f   # fix dependencies if needed"

