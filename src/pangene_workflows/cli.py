"""Strict TOML/sample validation and logged Bash/Docker workflow execution."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import tomllib
import uuid

from .spec import NAME, DEFAULTS, FIELDS, STAGES, SAMPLE_FIELDS


class ConfigError(ValueError):
    pass


def assets():
    root = Path(__file__).resolve().parents[2]
    return root / "workflows" if (root / "pyproject.toml").is_file() else Path(__file__).parent / "workflows"


def safe_text(value):
    if not isinstance(value, (str, int, float, bool)) or any(c in str(value) for c in "\0\n\r"):
        raise ConfigError("Configuration values must be single-line scalars")
    return str(value).lower() if isinstance(value, bool) else str(value)


class Config:
    def __init__(self, path, executor="docker"):
        self.path = Path(path).expanduser().resolve()
        self.executor = executor
        with self.path.open("rb") as stream:
            document = tomllib.load(stream)
        if set(document) - {"pipeline", "docker"}:
            raise ConfigError("Unknown TOML section")
        self.values = dict(DEFAULTS)
        settings = document.get("pipeline", {})
        if not isinstance(settings, dict) or not isinstance(document.get("docker", {}), dict):
            raise ConfigError("pipeline and docker must be TOML tables")
        if set(settings) - set(DEFAULTS):
            raise ConfigError("Unknown pipeline keys: " + ", ".join(sorted(set(settings) - set(DEFAULTS))))
        self.values.update(settings)
        for key, value in self.values.items():
            safe_text(value)
            if isinstance(DEFAULTS[key], str) and not isinstance(value, str):
                raise ConfigError(key + " must be a string")
            if isinstance(DEFAULTS[key], (int, float)) and (isinstance(value, bool) or not isinstance(value, (int, float))):
                raise ConfigError("Expected a TOML numeric value: " + key)
        self.docker = document.get("docker", {})
        if set(self.docker) - {"host_workdir", "host_data", "host_database", "image", "annotation_image"}:
            raise ConfigError("Unknown Docker key")
        for key, value in self.docker.items():
            if not isinstance(value, str):
                raise ConfigError("Docker values must be strings: " + key)
            safe_text(value)
        self.mounts = []
        for key, target, readonly in [("host_workdir", "/work", False), ("host_data", "/data", True),
                                      ("host_database", "/database", True)]:
            value = self.docker.get(key, "./results" if key == "host_workdir" else "")
            if value:
                self.mounts.append((self.host(value), target, readonly))
        for i, (host, target, _) in enumerate(self.mounts):
            for other, other_target, _ in self.mounts[:i]:
                if host == other or host in other.parents or other in host.parents:
                    raise ConfigError(f"Overlapping host mounts: {target} and {other_target}")
        self.samples = []
        sample_file = self.host(self.values["SAMPLES_TSV"])
        with sample_file.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, delimiter="\t")
            if not reader.fieldnames or "sample" not in reader.fieldnames:
                raise ConfigError("Samples TSV must have a sample header")
            if len(reader.fieldnames) != len(set(reader.fieldnames)) or set(reader.fieldnames) - {"sample", *SAMPLE_FIELDS}:
                raise ConfigError("Duplicate or unknown samples TSV columns")
            seen = set()
            for row in reader:
                if None in row or None in row.values():
                    raise ConfigError("Malformed samples TSV row")
                sample = row["sample"]
                if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", sample) or sample in seen:
                    raise ConfigError("Invalid or duplicate sample ID: " + sample)
                seen.add(sample)
                self.samples.append({k: safe_text(v) for k, v in row.items()})
        if not self.samples:
            raise ConfigError("Samples TSV has no samples")
        for key, value in self.values.items():
            safe_text(value)
            kind = FIELDS.get(key, "text")
            if kind in {"positive", "nonnegative", "fraction", "real"}:
                if isinstance(value, bool):
                    raise ConfigError(key + " must be numeric")
                try:
                    number = float(value)
                    invalid = not math.isfinite(number) or (not (0 <= number <= 1) if kind == "fraction" else
                        number <= 0 if kind == "real" else
                        (number != int(number) or number < (1 if kind == "positive" else 0)))
                except (TypeError, ValueError, OverflowError):
                    invalid = True
                if invalid:
                    raise ConfigError("Invalid numeric parameter: " + key)
            if kind == "boolean" and not isinstance(value, bool):
                raise ConfigError(key + " must be true or false")
            if kind in {"path", "prefix", "output"} and value:
                self.data_path(value)
        for key in {"QUALITY", "UNQUALIFIED", "CONTAM_IDENTITY", "CONTAM_COVERAGE", "MIN_IDENTITY"} & set(self.values):
            if not 0 <= float(self.values[key]) <= (93 if key == "QUALITY" else 100):
                raise ConfigError("Out-of-range parameter: " + key)
        for key in {"BLAST_EVALUE", "HMM_REPORT_EVALUE", "DOMAIN_EVALUE"} & set(self.values):
            try:
                number = float(self.values[key])
            except (TypeError, ValueError):
                raise ConfigError("Invalid E-value: " + key) from None
            if not math.isfinite(number) or number <= 0:
                raise ConfigError("E-values must be positive and finite: " + key)
        for key in {"MEGAHIT_MEMORY", "CLUSTER_IDENTITY", "SOFTCORE", "DOMAIN_COVERAGE"} & set(self.values):
            if float(self.values[key]) == 0:
                raise ConfigError(key + " must be greater than zero")
        if "BOOTSTRAPS" in self.values and self.values["BOOTSTRAPS"] < 1000:
            raise ConfigError("IQ-TREE ultrafast BOOTSTRAPS must be at least 1000")
        if "HMM_REPORT_EVALUE" in self.values and self.values["HMM_REPORT_EVALUE"] < self.values["DOMAIN_EVALUE"]:
            raise ConfigError("HMM_REPORT_EVALUE must be >= DOMAIN_EVALUE")
        if "MEME_MODEL" in self.values and self.values["MEME_MODEL"] not in {"zoops", "oops", "anr"}:
            raise ConfigError("MEME_MODEL must be zoops, oops or anr")
        if "ASM_PRESET" in self.values and self.values["ASM_PRESET"] not in {"asm5", "asm10", "asm20"}:
            raise ConfigError("ASM_PRESET must be asm5, asm10 or asm20")
        if "MOTIF_MIN_WIDTH" in self.values and self.values["MOTIF_MIN_WIDTH"] > self.values["MOTIF_MAX_WIDTH"]:
            raise ConfigError("MOTIF_MIN_WIDTH exceeds MOTIF_MAX_WIDTH")
        if self.values["REFERENCE"] and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", self.values["REFERENCE"]):
            raise ConfigError("Invalid REFERENCE identifier")
        for row in self.samples:
            for key in SAMPLE_FIELDS:
                if row.get(key):
                    row[key] = self.data_path(row[key], sample_file.parent)

    def host(self, value):
        path = Path(value).expanduser()
        return (path if path.is_absolute() else self.path.parent / path).resolve()

    def data_path(self, value, base=None):
        safe_text(value)
        if self.executor == "local":
            path = Path(value).expanduser()
            return str((path if path.is_absolute() else (base or self.path.parent) / path).resolve()).replace("\\", "/")
        path = PurePosixPath(value)
        if not path.is_absolute() or ".." in path.parts or "\\" in value:
            raise ConfigError("Docker pipeline paths must be absolute POSIX paths: " + value)
        return str(path)

    def mapped_host(self, value):
        if self.executor == "local":
            return Path(value)
        path = PurePosixPath(value)
        for host, target, _ in self.mounts:
            try:
                return host.joinpath(*path.relative_to(target).parts)
            except ValueError:
                pass
        raise ConfigError("Input path has no Docker bind mount: " + value)

    def validate(self, names, check_files=False):
        if len(names) != len(set(names)):
            raise ConfigError("Do not repeat stages")
        if "search" in names and "finalize" in names:
            raise ConfigError("Run search and finalize separately after reviewing candidate genes")
        for name in names:
            if name not in STAGES:
                raise ConfigError("Unknown stage: " + name)
            stage = STAGES[name]
            if stage.get("reference_sample") and self.values["REFERENCE"] not in {r["sample"] for r in self.samples}:
                raise ConfigError(name + " requires REFERENCE to match an assembly sample ID")
            for key in stage.get("required", []):
                if not self.values[key]:
                    raise ConfigError(name + " requires " + key)
                if check_files and FIELDS.get(key) in {"path", "prefix"}:
                    value = self.data_path(self.values[key])
                    host = self.mapped_host(value)
                    exists = host.exists() or (FIELDS[key] == "prefix" and any(host.parent.glob(host.name + ".*")))
                    if not exists:
                        raise ConfigError("Missing input: " + value)
            for key in stage.get("samples", []):
                for row in self.samples:
                    if not row.get(key):
                        raise ConfigError(name + " requires sample column " + key + " for " + row["sample"])
                    if check_files and not self.mapped_host(row[key]).is_file():
                        raise ConfigError("Missing sample input: " + row[key])
            if stage.get("min_samples", 1) > len(self.samples):
                raise ConfigError(name + " needs more independent samples")
        if self.executor == "docker":
            for _, target, _ in self.mounts:
                if target == "/work":
                    break
            else:
                raise ConfigError("Docker host_workdir is required")
            if check_files:
                for host, target, _ in self.mounts:
                    if target != "/work" and not host.is_dir():
                        raise ConfigError("Missing Docker mount directory: " + str(host))

    def shell(self):
        values = dict(self.values)
        values.pop("SAMPLES_TSV")
        values["WORKDIR"] = "/work" if self.executor == "docker" else self.data_path(values["WORKDIR"])
        lines = ["# Generated from validated TOML; values are quoted, never evaluated."]
        for key, value in values.items():
            if FIELDS.get(key) in {"path", "prefix", "output"} and value:
                value = self.data_path(value)
            lines.append(key + "=" + shlex.quote(safe_text(value)))
        lines.append("SAMPLES=(" + " ".join(shlex.quote(row["sample"]) for row in self.samples) + ")")
        for key in SAMPLE_FIELDS:
            lines.append("declare -A " + key.upper() + "=()")
            for row in self.samples:
                lines.append(key.upper() + "[" + shlex.quote(row["sample"]) + "]=" + shlex.quote(row.get(key, "")))
        return "\n".join(lines) + "\n"


def command(config, stage, shell_config, bash="bash", container_name=""):
    source = assets()
    if config.executor == "local":
        return [bash, (source / (stage + ".sh")).as_posix()]
    result = ["docker", "run", "--rm", "--init"]
    if container_name:
        result += ["--name", container_name]
    bindings = [(source, "/opt/workflows", True), (Path(shell_config), "/opt/config.sh", True), *config.mounts]
    for host, target, readonly in bindings:
        if any(c in host.as_posix() + target for c in ',\n\r"'):
            raise ConfigError("Unsupported Docker mount punctuation")
        result += ["--mount", f"type=bind,src={host.as_posix()},dst={target}" + (",readonly" if readonly else "")]
    image_key = "annotation_image" if STAGES[stage].get("annotation") else "image"
    image = config.docker.get(image_key, DEFAULTS["ANNOTATION_IMAGE"] if image_key == "annotation_image" else DEFAULTS["IMAGE"])
    if not image or image.startswith("-") or any(c.isspace() for c in image):
        raise ConfigError("Invalid Docker image")
    return result + ["--env", "WORKFLOW_CONFIG=/opt/config.sh", "--workdir", "/work",
                     "--entrypoint", "/bin/bash", image, "/opt/workflows/" + stage + ".sh"]


def stream(argv, env, cwd, log):
    with log.open("w", encoding="utf-8") as output:
        with subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding="utf-8", errors="replace",
                              start_new_session=os.name != "nt") as process:
            try:
                for line in process.stdout:
                    print(line, end="", flush=True)
                    output.write(line)
                    output.flush()
                return process.wait()
            except BaseException:
                if process.poll() is None:
                    if os.name == "nt":
                        process.terminate()
                    else:
                        os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                raise


def run(config, names, bash):
    config.validate(names)
    executable = "docker" if config.executor == "docker" else bash
    if not shutil.which(executable):
        raise ConfigError("Executable unavailable: " + executable)
    config.validate([], check_files=True)
    for host, target, _ in config.mounts if config.executor == "docker" else []:
        if target == "/work":
            host.mkdir(parents=True, exist_ok=True)
    identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    logs = config.path.parent / ("." + NAME) / "runs" / identifier
    logs.mkdir(parents=True)
    metadata = {"status": "running", "config_sha256": hashlib.sha256(config.path.read_bytes()).hexdigest(),
                "samples": [row["sample"] for row in config.samples], "executor": config.executor, "stages": []}
    report = logs / "run.json"
    def save():
        report.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    save()
    try:
        with tempfile.TemporaryDirectory(prefix=NAME + "-") as temporary:
            shell_config = Path(temporary) / "config.sh"
            shell_config.write_text(config.shell(), encoding="utf-8", newline="\n")
            env = dict(os.environ, WORKFLOW_CONFIG=shell_config.as_posix())
            for name in names:
                config.validate([name], check_files=True)
                container_name = NAME + "-" + uuid.uuid4().hex[:10] if config.executor == "docker" else ""
                argv = command(config, name, shell_config, bash, container_name)
                log = logs / (name + ".log")
                entry = {"stage": name, "status": "running", "argv": argv, "log": str(log)}
                metadata["stages"].append(entry)
                save()
                print("[" + name + "] " + str(log), flush=True)
                try:
                    code = stream(argv, env, config.path.parent, log)
                except BaseException as error:
                    entry["status"] = "interrupted" if isinstance(error, KeyboardInterrupt) else "failed"
                    if container_name:
                        try:
                            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, timeout=30)
                        except (OSError, subprocess.TimeoutExpired):
                            pass
                    raise
                entry.update(returncode=code, status="complete" if code == 0 else "failed")
                save()
                if code:
                    raise ConfigError(f"Stage {name} failed ({code}); see {log}")
        metadata["status"] = "complete"
    except BaseException as error:
        metadata.update(status="interrupted" if isinstance(error, KeyboardInterrupt) else "failed", error=str(error))
        raise
    finally:
        save()
    print("Run report: " + str(report))


def main(argv=None):
    parser = argparse.ArgumentParser(prog=NAME)
    parser.add_argument("--version", action="version", version="0.1.0")
    commands = parser.add_subparsers(dest="action", required=True)
    init = commands.add_parser("init", help="Create a configuration and samples template without overwriting")
    init.add_argument("directory", nargs="?", default=".")
    commands.add_parser("stages")
    data = commands.add_parser("data", help="Portable FASTA/GFF/PAV/VCF data utilities")
    data.add_argument("arguments", nargs=argparse.REMAINDER)
    for action in ("validate", "run"):
        sub = commands.add_parser(action)
        sub.add_argument("stages", nargs="+", choices=list(STAGES))
        sub.add_argument("--config", default="config.toml")
        sub.add_argument("--executor", choices=["docker", "local"], default="docker")
        sub.add_argument("--check-files", action="store_true")
        sub.add_argument("--bash", default="bash")
        if action == "run":
            sub.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action == "init":
            target = Path(args.directory).resolve()
            if any((target / name).exists() for name in ["config.toml", "samples.tsv"]):
                raise ConfigError("config.toml or samples.tsv exists; choose a new directory")
            target.mkdir(parents=True, exist_ok=True)
            for name, source in [("config.toml", "config.example.toml"), ("samples.tsv", "samples.example.tsv")]:
                shutil.copyfile(assets() / source, target / name)
            print(str(target))
        elif args.action == "data":
            return subprocess.call([sys.executable, str(assets() / "data.py"), *args.arguments])
        elif args.action == "stages":
            for name, stage in STAGES.items():
                print(name + "\t" + stage["description"])
        else:
            config = Config(args.config, args.executor)
            config.validate(args.stages, args.check_files)
            if args.action == "validate":
                print("Valid: " + ", ".join(args.stages))
            elif args.dry_run:
                print(json.dumps([{"stage": name, "argv": command(config, name, "<generated-config.sh>", args.bash),
                                   "script": (assets() / (name + ".sh")).read_text(encoding="utf-8")}
                                  for name in args.stages], ensure_ascii=False, indent=2))
            else:
                run(config, args.stages, args.bash)
        return 0
    except (ConfigError, OSError, tomllib.TOMLDecodeError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted; processes/container stopped. Review run.json.", file=sys.stderr)
        return 130
