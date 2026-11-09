"""Build an unsigned, device-specific Leica camera APK from local inputs."""

from argparse import ArgumentParser
from hashlib import sha1, sha256
import json
from pathlib import Path
import struct
from zipfile import ZIP_STORED, ZipFile
from zlib import adler32


MANIFEST = Path(__file__).with_name("inputs.json")
LIB_PREFIX = "lib/arm64-v8a/"
SIGNATURE_SUFFIXES = (".SF", ".RSA", ".DSA", ".EC", "MANIFEST.MF")

# Offsets are valid only for the exact donor DEX hashes in inputs.json.
DEX_EDITS = {
    "classes.dex": (
        # ModuleDevice.k: use a regular Camera2 session for the 0x8001 branch.
        (0x6FAC42, bytes.fromhex("140100000000")),
        # SoundSetting.k/l: skip the paired global audio_headset_state writes.
        (0x6D468E, bytes(6)),
        (0x6D46F6, bytes(6)),
        # VideoModuleDevice.l: use a regular session for front video's 0x8009 branch.
        (0x6FB44E, bytes.fromhex("140000000000")),
    ),
    "classes2.dex": (
        # FunctionModuleSetup: log the exception and retain the original failure path.
        (0x64F292, bytes.fromhex("1a01ca5571308f061409").ljust(0x34, b"\0")),
    ),
    "classes7.dex": (
        # CameraCapabilities.u1: on a null vendor map, branch to the existing
        # public stream-map fallback. A successful vendor map still gets cached.
        (0x63D2C, bytes.fromhex(
            "0c10"          # move-result-object v16
            "02011300"      # move/from16 v1, v19 (operating mode)
            "1f10250013110100770ffd740300"
            "0c03"          # move-result-object v3
            "54022f00"
            "38034dff"      # if-eqz v3, standard map path
            "6e305b001203"  # SparseArray.put(v1, v3)
            "0000"          # fall through to the cached lookup
        )),
    ),
}


def verify(data, expected, label):
    if sha256(data).hexdigest() != expected:
        raise ValueError(f"SHA-256 mismatch for {label}")
    return data


def patch_dex(data, edits):
    patched = bytearray(data)
    for offset, replacement in edits:
        patched[offset:offset + len(replacement)] = replacement
    patched[12:32] = sha1(patched[32:]).digest()
    struct.pack_into("<I", patched, 8, adler32(patched[12:]))
    return patched


def build(donor_dir, libs_dir, output):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    donor_apk = donor_dir / manifest["donor_apk"]["path"]
    verify(donor_apk.read_bytes(), manifest["donor_apk"]["sha256"], donor_apk)

    jni = donor_dir / manifest["donor_jni"]["path"]
    extras = {jni.name: verify(jni.read_bytes(), manifest["donor_jni"]["sha256"], jni)}
    for name, digest in manifest["device_libraries"].items():
        library = libs_dir / name
        extras[name] = verify(library.read_bytes(), digest, library)

    with ZipFile(donor_apk) as source:
        if len(source.namelist()) != len(set(source.namelist())):
            raise ValueError("Duplicate ZIP entries in donor APK")
        patched_dex = {
            name: patch_dex(verify(source.read(name), manifest["dex"][name], name), edits)
            for name, edits in DEX_EDITS.items()
        }
        with ZipFile(output, "x") as destination:
            for entry in source.infolist():
                name = entry.filename
                if name.startswith("META-INF/") and name.upper().endswith(SIGNATURE_SUFFIXES):
                    continue
                if name.startswith(LIB_PREFIX) and name.removeprefix(LIB_PREFIX) in extras:
                    continue
                data = patched_dex[name] if name in patched_dex else source.read(entry)
                destination.writestr(entry, data)
            for name, data in sorted(extras.items()):
                destination.writestr(LIB_PREFIX + name, data, compress_type=ZIP_STORED)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--donor-dir", type=Path, required=True)
    parser.add_argument("--libs-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        build(args.donor_dir, args.libs_dir, args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Build failed: {error}\n")
    print(f"Unsigned APK written to {args.output}")


if __name__ == "__main__":
    main()
