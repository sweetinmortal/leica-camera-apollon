"""Collect the pinned native dependencies from the owner's matching device."""

from argparse import ArgumentParser
import json
from pathlib import Path
import subprocess

from build import MANIFEST, verify


SEARCH_DIRS = (
    "/system/lib64", "/system_ext/lib64", "/product/lib64",
    "/vendor/lib64", "/odm/lib64", "/apex/com.android.runtime/lib64",
)


def collect(adb, output):
    properties = subprocess.check_output(
        [*adb, "shell", "getprop ro.product.device; getprop ro.build.version.sdk"],
        text=True,
    ).splitlines()
    if len(properties) != 2 or properties[0] not in ("apollo", "apollon") or properties[1] != "37":
        raise ValueError("Expected an apollo/apollon device running Android SDK 37")

    libraries = json.loads(MANIFEST.read_text(encoding="utf-8"))["device_libraries"]
    output.mkdir(parents=True, exist_ok=True)
    for name, digest in libraries.items():
        destination = output / name
        if destination.exists():
            verify(destination.read_bytes(), digest, destination)
            continue
        for directory in SEARCH_DIRS:
            remote = f"{directory}/{name}"
            result = subprocess.run([*adb, "exec-out", "cat", remote], capture_output=True)
            if result.returncode == 0 and result.stdout:
                try:
                    verify(result.stdout, digest, remote)
                except ValueError:
                    continue
                with destination.open("xb") as file:
                    file.write(result.stdout)
                break
        else:
            raise ValueError(f"No matching copy of {name}. Check the LineageOS build.")


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--serial", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        collect([args.adb, "-s", args.serial], args.output)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Collection failed: {error}\n")
    print(f"Verified libraries in {args.output}")


if __name__ == "__main__":
    main()
