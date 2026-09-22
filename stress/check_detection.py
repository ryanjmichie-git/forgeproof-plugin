"""Prove the opt-in detection files under share/ against the real tools (CI only).

Runs shared-mime-info (`update-mime-database`), GLib (`gio info`) and
file(1) over the four frozen fixtures and one fresh bundle built by
stress/make_bundle.py with the actual engine, each in every layout a bundle
can reach a disk in: as written, CRLF, key-sorted (indented and canonical),
compact in insertion order, and BOM-prefixed — named `issue-N.rpack` and,
for content-only sniffing, named `noext`.

The documented limits are ASSERTED, not hidden: plain `file` prints
application/json (its built-in JSON detector runs before soft magic); a
key-sorted or BOM-prefixed copy is text/plain to content sniffing and is
recognized by the *.rpack glob only.

Usage: python stress/check_detection.py

Python stdlib only. A missing tool is a failure, never a skip. Everything is
written under one temporary directory (inside $RUNNER_TEMP when set): the XML
and the magic file are COPIED there first, because update-mime-database
writes globs2, magic, mime.cache and more beside the XML and `file -C`
writes <name>.mgc into its working directory. ForgeProof itself never runs
any of these tools (PRIVACY.md); this driver is the only place they appear.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MIME_XML = REPO / "share" / "mime" / "packages" / "forgeproof-rpack.xml"
MAGIC = REPO / "share" / "magic" / "forgeproof"
FIXTURES = REPO / "skills" / "run" / "scripts" / "fixtures"
MAKE_BUNDLE = REPO / "stress" / "make_bundle.py"
OURS = "application/vnd.forgeproof.rpack+json"
JSON = "application/json"
PLAIN = "text/plain"
OCTETS = "application/octet-stream"
BOM = b"\xef\xbb\xbf"
TIMEOUT = 600

# layout -> (named *.rpack under gio, named `noext` under gio,
#            `file -e json -m share/magic/forgeproof`)
LAYOUTS = {
    "as-written": (OURS, OURS, OURS),
    "crlf": (OURS, OURS, OURS),
    "compact": (OURS, OURS, OURS),
    "sorted": (OURS, PLAIN, PLAIN),
    "canonical": (OURS, PLAIN, PLAIN),
    "bom": (OURS, PLAIN, PLAIN),
}


def run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, capture_output=True, encoding="utf-8", errors="replace",
        timeout=TIMEOUT, stdin=subprocess.DEVNULL, **kwargs,
    )


def layouts(raw: bytes) -> dict[str, bytes]:
    doc = json.loads(raw.decode("utf-8"))
    lf = raw.replace(b"\r\n", b"\n")
    return {
        "as-written": raw,
        "crlf": lf.replace(b"\n", b"\r\n"),
        "compact": json.dumps(doc, separators=(",", ":")).encode("ascii"),
        "sorted": (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("ascii"),
        "canonical": json.dumps(
            doc, sort_keys=True, separators=(",", ":")).encode("ascii"),
        "bom": BOM + raw,
    }


def main() -> None:
    for tool in ("update-mime-database", "gio", "file"):
        if shutil.which(tool) is None:
            raise SystemExit(f"{tool} not found on PATH — this driver never skips")
    versions = []
    for args in (["update-mime-database", "-v"], ["gio", "version"],
                 ["file", "--version"]):
        p = run(args)
        first = (p.stdout + p.stderr).splitlines()[0]
        versions.append(first if first[:1].isalpha() else f"{args[0]} {first}")
    print("tools: " + "; ".join(versions))

    results: list[bool] = []

    def check(label: str, got: str, want: str) -> None:
        results.append(got == want)
        print(f"{'ok  ' if got == want else 'FAIL'} {label}: {got}"
              + ("" if got == want else f" (want {want})"))

    with tempfile.TemporaryDirectory(
            prefix="fp-detect-", dir=os.environ.get("RUNNER_TEMP")) as tmp:
        work = Path(tmp)

        sources = {p.parent.name: p.read_bytes()
                   for p in sorted(FIXTURES.glob("v*/issue-*.rpack"))}
        if len(sources) != 4:
            raise SystemExit(f"expected four frozen fixtures, found {len(sources)}")
        p = run([sys.executable, str(MAKE_BUNDLE), str(work / "project")])
        if p.returncode != 0:
            sys.stderr.write(p.stdout + p.stderr)
            raise SystemExit(f"make_bundle failed with rc={p.returncode}")
        sources["fresh"] = Path(json.loads(p.stdout)["rpack"]).read_bytes()

        # shared-mime-info: compile a COPY of the XML under an isolated
        # XDG_DATA_HOME. rc alone proves nothing — update-mime-database exits
        # 0 on an XML it failed to parse — so its output must be empty and
        # the compiled database must carry the glob and the subclass.
        xdg = work / "xdg"
        packages = xdg / "mime" / "packages"
        packages.mkdir(parents=True)
        shutil.copy(MIME_XML, packages / MIME_XML.name)
        env = {**os.environ, "XDG_DATA_HOME": str(xdg)}
        p = run(["update-mime-database", str(xdg / "mime")], env=env)
        check("update-mime-database: rc, output",
              repr((p.returncode, (p.stdout + p.stderr).strip())), repr((0, "")))
        for name, want in (("globs2", f"50:{OURS}:*.rpack"),
                           ("subclasses", f"{OURS} {JSON}")):
            compiled = xdg / "mime" / name
            lines = (compiled.read_text(encoding="utf-8", errors="replace")
                     .splitlines() if compiled.is_file() else [])
            check(f"update-mime-database: {name}",
                  want if want in lines else "(absent)", want)

        # libmagic: compile a COPY of the magic file, in the temp dir.
        magic_dir = work / "magic"
        magic_dir.mkdir()
        shutil.copy(MAGIC, magic_dir / MAGIC.name)
        p = run(["file", "-C", "-m", MAGIC.name], cwd=magic_dir)
        check("file -C -m: rc, compiled",
              repr((p.returncode, (magic_dir / f"{MAGIC.name}.mgc").is_file())),
              repr((0, True)))

        def gio(path: Path, data_home: Path = xdg) -> str:
            p = run(["gio", "info", "-a", "standard::content-type", str(path)],
                    env={**os.environ, "XDG_DATA_HOME": str(data_home)})
            for line in p.stdout.splitlines():
                if "standard::content-type:" in line:
                    return line.split("standard::content-type:", 1)[1].strip()
            return f"(no content type; rc={p.returncode}: {p.stderr.strip()})"

        def file_mime(path: Path, *flags: str) -> str:
            p = run(["file", "-b", *flags, "--mime-type", str(path)])
            return p.stdout.strip() if p.returncode == 0 else (
                f"(rc={p.returncode}: {(p.stdout + p.stderr).strip()})")

        ours = ("-e", "json", "-m", str(MAGIC))
        for label, raw in sources.items():
            for layout, data in layouts(raw).items():
                by_name, by_content, by_magic = LAYOUTS[layout]
                case = work / "cases" / label / layout
                case.mkdir(parents=True)
                named, noext = case / "issue-1.rpack", case / "noext"
                named.write_bytes(data)
                noext.write_bytes(data)
                check(f"gio   {label}/{layout} issue-1.rpack", gio(named), by_name)
                check(f"gio   {label}/{layout} noext", gio(noext), by_content)
                check(f"file  {label}/{layout} -e json -m", file_mime(named, *ours),
                      by_magic)
            # The documented precedence: without `-e json`, file(1)'s built-in
            # JSON detector answers first — with or without our magic file.
            written = work / "cases" / label / "as-written" / "issue-1.rpack"
            check(f"file  {label}/as-written (default)", file_mime(written), JSON)
            check(f"file  {label}/as-written -m, no -e json",
                  file_mime(written, "-m", str(MAGIC)), JSON)

        # Control: the type comes from the shipped XML, not from the host.
        empty = work / "xdg-empty"
        empty.mkdir()
        check("gio   control, XML not installed: fresh/as-written issue-1.rpack",
              gio(work / "cases" / "fresh" / "as-written" / "issue-1.rpack", empty),
              PLAIN)

        others = work / "cases" / "others"
        others.mkdir()
        unrelated = others / "unrelated.json"
        unrelated.write_text(json.dumps(
            {"version": "1.0.0", "format": "something-else"}, indent=2) + "\n",
            encoding="utf-8")
        check("gio   unrelated.json", gio(unrelated), JSON)
        check("file  unrelated.json -e json -m", file_mime(unrelated, *ours), PLAIN)
        archive = others / "noext"
        archive.write_bytes(b"RP6L" + bytes(range(32)) * 8)
        check("gio   RP6L bytes, noext", gio(archive), OCTETS)

    # Nothing may have been written beside the shipped files.
    shipped = sorted(p.relative_to(REPO).as_posix()
                     for p in (REPO / "share").rglob("*") if p.is_file())
    check("share/ holds the two shipped files only", repr(shipped), repr(sorted(
        p.relative_to(REPO).as_posix() for p in (MIME_XML, MAGIC))))

    failures = results.count(False)
    print(f"{len(results)} checks, {failures} mismatches ({'; '.join(versions)})")
    if failures or not results:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
