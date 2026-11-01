"""Build the small AppKit adapter with the local macOS SDK, without extra packages."""
import platform
from pathlib import Path
import subprocess
import sys


def build(root):
    if sys.platform != "darwin":
        return None
    output = root / "build/native/libhealthpro_glass.dylib"
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["xcrun", "clang", "-dynamiclib", "-fobjc-arc", "-O2",
                    "-arch", platform.machine(), "-mmacosx-version-min=10.15",
                    "-framework", "Cocoa", "-framework", "QuartzCore",
                    "-weak_framework", "UniformTypeIdentifiers",
                    "-install_name", "@rpath/libhealthpro_glass.dylib",
                    str(root / "native/glass.m"), "-o", str(output)], check=True)
    return output


if __name__ == "__main__":
    print(build(Path(__file__).resolve().parent.parent))
