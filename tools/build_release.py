"""Package the saved add-on without importing bpy or changing its contents."""

import ast
import hashlib
from pathlib import Path
import zipfile


def main():
    root = Path(__file__).resolve().parents[1]
    source = root / "addon" / "perceptual_pathv1.6.py"
    raw = source.read_bytes()
    text = raw.decode("utf-8-sig")
    compile(text, str(source), "exec")
    tree = ast.parse(text)
    metadata = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "bl_info"
                for target in node.targets)
    )
    version = ".".join(str(part) for part in metadata["version"])
    output = root / "dist"
    output.mkdir(exist_ok=True)
    asset = output / f"perceptual_path-{version}.zip"
    entry = zipfile.ZipInfo("perceptual_path/__init__.py", (2026, 1, 1, 0, 0, 0))
    entry.compress_type = zipfile.ZIP_DEFLATED
    entry.external_attr = 0o644 << 16
    with zipfile.ZipFile(asset, "w") as archive:
        archive.writestr(entry, raw)
    with zipfile.ZipFile(asset) as archive:
        assert archive.namelist() == [entry.filename]
        assert archive.read(entry.filename) == raw
    digest = hashlib.sha256(asset.read_bytes()).hexdigest()
    checksum = output / f"perceptual_path-{version}.sha256"
    checksum.write_text(f"{digest}  {asset.name}\n", encoding="utf-8")
    print(f"Created {asset}")
    print(f"SHA256 {digest}")


if __name__ == "__main__":
    main()
