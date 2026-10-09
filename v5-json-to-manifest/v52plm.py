#!/usr/bin/env python3
"""
v52plm - convert F5 WAF for NGINX (v5) JSON files to PLM custom resources, and back.

WHY THIS EXISTS
---------------
WAF v5 and PLM (Policy Lifecycle Management) use the same declarative policy
language. The only thing that changes is the packaging:

  * v5 without PLM: you keep plain JSON files and compile them into .tgz bundles
    with the waf-compiler image.
  * v5 with PLM:    you put the same JSON content into Kubernetes custom
    resources (CRDs). The PLM Policy Controller compiles them inside the cluster.

So "converting" means wrapping the JSON in a Kubernetes envelope
(apiVersion / kind / metadata / spec). No policy setting is added, removed or
renamed. To prove that, every conversion is verified: the output is parsed back
and compared, setting by setting, with the input. Any difference fails the run.

WHAT GOES WHERE
---------------
  JSON -> CRD : policy.json   -> APPolicy   (the JSON becomes spec, so its
                                              "policy" key becomes spec.policy)
                log.json      -> APLogConf  (spec.filter / spec.content)
                usersigs.json -> APUserSig  (spec.tag / spec.signatures)
  CRD -> JSON : the reverse, for any of the three kinds

API VERSIONS
------------
  appprotect.f5.com/v1       PLM (WAF v5)            <- default
  appprotect.f5.com/v1beta1  old NIC integration (WAF v4)

Requires: Python 3.8+, PyYAML (pip install pyyaml)

EXAMPLES
--------
  v52plm.py to-crd policies/default-policy.json -n security
  v52plm.py to-crd policies/ -o plm/ -n security
  v52plm.py to-crd policy.json --api-version appprotect.f5.com/v1beta1   # old NIC + WAF v4
  v52plm.py to-json plm/default-policy-appolicy.yaml -o json/
  v52plm.py check policies/                                               # validate only

EXIT CODES
----------
  0  every file converted (or checked) and verified
  1  at least one file failed; the reason is printed to stderr
"""
import argparse
import json
import re
import sys
from pathlib import Path

# PyYAML is the only third-party dependency. Fail early with a clear message
# instead of a stack trace if it is missing.
try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install pyyaml")

# PLM owns the appprotect.f5.com/v1 CRDs, so that is the default target.
DEFAULT_API = "appprotect.f5.com/v1"

# The three resource kinds this tool handles, and the suffix used in output
# file names (e.g. default-policy-appolicy.yaml). The suffix keeps a policy and
# a log profile with the same name from overwriting each other.
KIND_SUFFIX = {"APPolicy": "appolicy", "APLogConf": "aplogconf", "APUserSig": "apusersig"}


# =============================================================================
# JSON input
# =============================================================================

def strip_trailing_commas(text):
    """
    Remove trailing commas that appear right before a closing ] or }.

    Example of what gets fixed (this was in the real default-policy.json):

        { "name": "Low Accuracy Signatures", ... },   <- this comma
      ],

    Standard JSON forbids that comma, so both Python and the WAF compiler
    reject the file. Editors and hand edits leave it behind easily.

    Why a small scanner instead of a single regex:
    a regex would also "fix" commas inside string values. User-defined
    signature rules can legitimately contain text like  "a,]"  and must not be
    touched. The scanner therefore tracks whether it is inside a string
    (including escaped quotes like \\") and only acts outside strings.

    The whitespace after a removed comma is kept, so line numbers in error
    messages still match the original file.

    Returns: (cleaned_text, list_of_line_numbers_where_a_comma_was_removed)
    """
    out, fixes, i, n = [], [], 0, len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            # A backslash escapes the next character (e.g. \" or \\).
            # Copy both and skip ahead so an escaped quote does not end the string.
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
        elif c == '"':
            in_str = True
            out.append(c)
        elif c == ",":
            # Outside a string: is this comma followed only by whitespace and
            # then a closing bracket/brace? If so, it is a trailing comma.
            m = re.match(r",(\s*)([\]}])", text[i:])
            if m:
                fixes.append(text.count("\n", 0, i) + 1)  # 1-based line number
                out.append(m.group(1))                      # keep the whitespace
                i += 1 + len(m.group(1))                    # skip comma + whitespace
                continue
            out.append(c)
        else:
            out.append(c)
        i += 1
    return "".join(out), fixes


def load_json(path, fix):
    """
    Read and parse a JSON file.

    Strategy: try strict JSON first. Only if that fails, and fixing is allowed,
    remove trailing commas and try again. This way valid files are never
    modified, and the report only mentions fixes that were really needed.

    Returns: (parsed_data, list_of_fixed_lines)
    Raises:  ValueError with line/column if the file is still invalid.
    """
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text), []
    except json.JSONDecodeError as err:
        if not fix:
            raise ValueError(f"invalid JSON at line {err.lineno}, column {err.colno}: {err.msg} "
                             "(trailing commas are fixed automatically unless --no-fix is set)")
        cleaned, fixes = strip_trailing_commas(text)
        try:
            return json.loads(cleaned), fixes
        except json.JSONDecodeError as err2:
            # Something other than a trailing comma is wrong (missing bracket,
            # missing quote, ...). Report it; do not guess further.
            raise ValueError(f"invalid JSON at line {err2.lineno}, column {err2.colno}: {err2.msg}")


def detect_kind(data):
    """
    Decide which CRD a JSON file belongs to, based on its top-level keys.

      {"policy": {...}}                     -> APPolicy
      {"tag": ..., "signatures": [...]}     -> APUserSig
      {"filter": {...}, "content": {...}}   -> APLogConf

    The order matters: "signatures" is checked before "filter"/"content" so a
    signature file is never mistaken for a log profile. Use --kind to override.
    """
    if not isinstance(data, dict):
        raise ValueError("top level must be a JSON object")
    if "policy" in data:
        return "APPolicy"
    if "signatures" in data:
        return "APUserSig"
    if "filter" in data or "content" in data:
        return "APLogConf"
    raise ValueError("cannot tell the file type: expected a 'policy', 'filter'/'content' "
                     "or 'signatures' key at the top level (use --kind)")


def k8s_name(raw):
    """
    Turn any string into a valid Kubernetes resource name (RFC 1123 subdomain):
    lowercase letters, digits and '-', at most 253 characters, no leading or
    trailing '-'.

      "Default_Policy"  -> "default-policy"
      "telco_sigs"      -> "telco-sigs"

    Only metadata.name is changed. policy.name inside the spec stays exactly as
    written, because that is the name the WAF shows in its logs.
    """
    name = re.sub(r"[^a-z0-9-]+", "-", str(raw).lower()).strip("-")
    name = re.sub(r"-{2,}", "-", name)[:253].strip("-")
    if not name:
        raise ValueError(f"cannot derive a Kubernetes name from {raw!r} (use --name)")
    return name


# =============================================================================
# YAML output
# =============================================================================

class Dumper(yaml.SafeDumper):
    """
    SafeDumper with two tweaks for readable, diff-friendly manifests.

    SafeDumper already quotes values that YAML would otherwise misread:
    "*" (wildcards), "<%TS.request.ID()%>" (response pages), "yes"/"no",
    numeric-looking strings, and so on. Those stay strings after a round trip,
    which the verification step confirms.
    """


def _str(dumper, value):
    # Multi-line strings (e.g. HTML response pages) are written as YAML block
    # scalars (|) instead of one long line full of \n escapes.
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


Dumper.add_representer(str, _str)

# By default PyYAML writes list items flush with their parent key:
#     violations:
#     - name: ...
# Most linters (yamllint, kubeconform setups) prefer them indented:
#     violations:
#       - name: ...
Dumper.increase_indent = lambda self, flow=False, indentless=False: \
    yaml.SafeDumper.increase_indent(self, flow, False)


def to_yaml(doc):
    """
    Serialize one Kubernetes document.

      sort_keys=False    keep the original key order, so the YAML reads like
                         the JSON and reviews/diffs stay small
      allow_unicode=True keep non-ASCII text readable instead of \\u escapes
      width=4096         avoid wrapping long values such as signature rules
    """
    return yaml.dump(doc, Dumper=Dumper, sort_keys=False, allow_unicode=True, width=4096)


# =============================================================================
# Verification
# =============================================================================

def flatten(node, path="", out=None):
    """
    Turn a nested structure into a flat dict: path -> (type_name, value).

    Example:
      {"policy": {"methods": [{"name": "GET"}]}}
    becomes
      {"policy.methods[0:GET].name": ("str", "GET")}

    Details:
      * List items get their index AND their name/description in the path
        ("[3:VIOL_METHOD]"). The index keeps two entries with the same name
        apart (the http and https "*" URL wildcards). The name makes failure
        messages readable.
      * The type is stored with the value. This catches silent YAML type
        changes, such as the string "true" turning into the boolean true or
        "10" turning into the number 10.
      * Empty dicts and lists are recorded too (e.g. "customXffHeaders": []),
        so a dropped empty section would also be reported.
    """
    out = {} if out is None else out
    if isinstance(node, dict):
        if not node:
            out[path] = ("{}", {})
        for k, v in node.items():
            flatten(v, f"{path}.{k}" if path else str(k), out)
    elif isinstance(node, list):
        if not node:
            out[path] = ("[]", [])
        for i, v in enumerate(node):
            label = v.get("name") or v.get("description") if isinstance(v, dict) else None
            flatten(v, f"{path}[{i}{':' + str(label) if label else ''}]", out)
    else:
        out[path] = (type(node).__name__, node)
    return out


def compare(a, b):
    """
    Compare two structures setting by setting.

    Returns: (number_of_settings_in_a, list_of_difference_messages)
    An empty list means the two are identical in keys, values and types.
    """
    fa, fb = flatten(a), flatten(b)
    diffs = []
    for p in sorted(set(fa) | set(fb)):
        if p not in fa:
            diffs.append(f"  only in output: {p} = {fb[p][1]!r}")
        elif p not in fb:
            diffs.append(f"  missing in output: {p} = {fa[p][1]!r}")
        elif fa[p] != fb[p]:
            diffs.append(f"  changed: {p}: {fa[p][1]!r} ({fa[p][0]}) -> {fb[p][1]!r} ({fb[p][0]})")
    return len(fa), diffs


# =============================================================================
# Conversions
# =============================================================================

def json_to_crd(path, args):
    """
    Convert one v5 JSON file into one CRD YAML document.

    Steps:
      1. Parse the JSON (fixing trailing commas if allowed).
      2. Detect the kind (or use --kind).
      3. Pick metadata.name: --name, else policy.name for policies,
         else the file name for log profiles and user signatures.
      4. Wrap the unchanged JSON as spec. For a policy file that gives
         spec.policy, which is exactly what APPolicy expects.
      5. Serialize to YAML, parse it back, and compare with the input.

    Returns: (yaml_text, output_file_name, kind, settings_count, notes)
    """
    data, fixes = load_json(path, args.fix_trailing_commas)
    kind = args.kind or detect_kind(data)

    if kind == "APPolicy":
        pname = data["policy"].get("name")
        if not pname:
            # The WAF requires policy.name, so catch it here rather than
            # letting PLM report it later as a compile error.
            raise ValueError("policy.name is missing")
        default_name = pname
    else:
        default_name = path.stem
    name = k8s_name(args.name or default_name)

    metadata = {"name": name}
    if args.namespace:
        metadata["namespace"] = args.namespace
    if args.label:
        # -l app=waf -l team=sec  ->  {"app": "waf", "team": "sec"}
        metadata["labels"] = dict(l.split("=", 1) for l in args.label)

    # No "status" is written: PLM fills status.bundle.* itself after compiling.
    doc = {"apiVersion": args.api_version, "kind": kind, "metadata": metadata, "spec": data}
    text = to_yaml(doc)

    # Verification: what Kubernetes will read back as spec must equal the input.
    count, diffs = compare(data, yaml.safe_load(text)["spec"])
    if diffs:
        raise ValueError("verification failed, output differs from input:\n" + "\n".join(diffs))

    # Informational notes; they do not fail the run.
    notes = []
    if fixes:
        notes.append(f"removed trailing comma(s) on line(s) {', '.join(map(str, fixes))}")
    if kind == "APPolicy" and name != data["policy"]["name"]:
        notes.append(f"metadata.name '{name}' differs from policy.name '{data['policy']['name']}'")
    return text, f"{name}-{KIND_SUFFIX[kind]}.yaml", kind, count, notes


def crd_to_json(path, args):
    """
    Convert CRD YAML back into v5 JSON files (e.g. to feed waf-compiler, or to
    recover the JSON source from what is running in the cluster).

    One YAML file may contain several documents separated by '---'
    (for example the output of `kubectl get appolicy -o yaml` split per item,
    or a bundle of manifests). Each supported document becomes one JSON file.
    Other kinds (Policy, VirtualServer, ...) are skipped with a note.

    The JSON is simply the spec. For APPolicy that is {"policy": {...}}, which
    is the format waf-compiler expects with -p.

    Returns: list of (json_text, output_file_name, kind, settings_count, notes)
             json_text is None for skipped documents.
    """
    docs = [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]
    results = []
    for doc in docs:
        kind = doc.get("kind")
        if kind not in KIND_SUFFIX:
            results.append((None, None, kind, 0, [f"skipped document of kind {kind!r}"]))
            continue
        spec = doc.get("spec")
        if not isinstance(spec, dict):
            raise ValueError(f"{kind} {doc.get('metadata', {}).get('name')}: spec is missing")

        # status, metadata.uid, resourceVersion etc. are ignored on purpose:
        # only spec is policy content.
        text = json.dumps(spec, indent=2, ensure_ascii=False) + "\n"

        count, diffs = compare(spec, json.loads(text))
        if diffs:
            raise ValueError("verification failed:\n" + "\n".join(diffs))

        # Policies keep the plain <name>.json that waf-compiler users expect;
        # log profiles and signatures get a suffix to avoid name clashes.
        name = doc.get("metadata", {}).get("name") or path.stem
        fname = f"{name}.json" if kind == "APPolicy" else f"{name}-{KIND_SUFFIX[kind]}.json"
        results.append((text, fname, kind, count, []))
    return results


# =============================================================================
# CLI plumbing
# =============================================================================

def collect(inputs, patterns):
    """
    Expand the command-line inputs into a list of files.
    Directories are searched recursively for the given patterns
    (*.json for to-crd/check, *.yaml and *.yml for to-json).
    Results are sorted so runs are reproducible, which keeps CI logs stable.
    """
    files = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            for pat in patterns:
                files.extend(sorted(p.rglob(pat)))
        elif p.is_file():
            files.append(p)
        else:
            raise SystemExit(f"not found: {item}")
    return files


def emit(text, filename, args):
    """
    Write one converted document.

    * No -o: print to stdout. Documents are separated with '---', so the
      output can be piped straight into `kubectl apply -f -`.
    * With -o: write <dir>/<filename>. Existing files are protected unless
      --force is given, so a typo cannot silently overwrite reviewed manifests.

    Returns where the document went, for the log line.
    """
    if args.output is None:
        sys.stdout.write(("---\n" if emit.count else "") + text)
        emit.count += 1
        return "stdout"
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / filename
    if target.exists() and not args.force:
        raise ValueError(f"{target} exists (use --force to overwrite)")
    target.write_text(text, encoding="utf-8")
    return str(target)


# Counts documents already written to stdout, so the first one gets no '---'.
emit.count = 0


def log(msg, args):
    """
    Progress messages go to stderr, so stdout stays clean YAML/JSON when piping.
    --quiet hides them; errors are always printed.
    """
    if not args.quiet:
        print(msg, file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    # Options shared by to-crd and to-json.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("inputs", nargs="+", help="files or directories")
    common.add_argument("-o", "--output", help="output directory (default: stdout)")
    common.add_argument("-f", "--force", action="store_true", help="overwrite existing files")
    common.add_argument("-q", "--quiet", action="store_true", help="only print errors")

    # to-crd: v5 JSON -> PLM (or v1beta1) custom resources
    tc = sub.add_parser("to-crd", parents=[common], help="v5 JSON -> PLM CRD YAML")
    tc.add_argument("-n", "--namespace", help="metadata.namespace")
    tc.add_argument("--name", help="metadata.name (single input only)")
    tc.add_argument("--kind", choices=list(KIND_SUFFIX), help="override kind detection")
    tc.add_argument("--api-version", default=DEFAULT_API,
                    help=f"default {DEFAULT_API}; use appprotect.f5.com/v1beta1 for old NIC + WAF v4")
    tc.add_argument("-l", "--label", action="append", metavar="KEY=VALUE", help="add a label (repeatable)")
    tc.add_argument("--no-fix", dest="fix_trailing_commas", action="store_false",
                    help="fail on trailing commas instead of removing them")

    # to-json: custom resources -> v5 JSON
    sub.add_parser("to-json", parents=[common], help="PLM CRD YAML -> v5 JSON")

    # check: run the full to-crd pipeline (parse, detect, wrap, verify) but
    # write nothing. Meant as a CI lint job.
    ck = sub.add_parser("check", help="validate JSON files and report fixes, write nothing")
    ck.add_argument("inputs", nargs="+")
    ck.add_argument("-q", "--quiet", action="store_true")

    args = ap.parse_args()
    failed = 0  # one bad file does not stop the others; the exit code reports it

    if args.cmd in ("to-crd", "check"):
        files = collect(args.inputs, ["*.json"])
        if args.cmd == "to-crd" and args.name and len(files) > 1:
            # One fixed name for many files would make them overwrite each other.
            sys.exit("--name only works with a single input file")
        if args.cmd == "check":
            # check reuses json_to_crd, so give it the defaults to-crd would use.
            args.fix_trailing_commas, args.kind, args.name = True, None, None
            args.namespace, args.label, args.api_version = None, None, DEFAULT_API
        for f in files:
            try:
                text, fname, kind, count, notes = json_to_crd(f, args)
                where = "ok" if args.cmd == "check" else emit(text, fname, args)
                log(f"OK    {f} -> {kind} ({count} settings verified) -> {where}", args)
                for n in notes:
                    log(f"      note: {n}", args)
            except (ValueError, KeyError) as err:
                failed += 1
                print(f"FAIL  {f}: {err}", file=sys.stderr)

    elif args.cmd == "to-json":
        for f in collect(args.inputs, ["*.yaml", "*.yml"]):
            try:
                for text, fname, kind, count, notes in crd_to_json(f, args):
                    if text is None:
                        log(f"SKIP  {f}: {notes[0]}", args)
                        continue
                    where = emit(text, fname, args)
                    log(f"OK    {f} -> {kind} ({count} settings verified) -> {where}", args)
            except (ValueError, yaml.YAMLError) as err:
                failed += 1
                print(f"FAIL  {f}: {err}", file=sys.stderr)

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
