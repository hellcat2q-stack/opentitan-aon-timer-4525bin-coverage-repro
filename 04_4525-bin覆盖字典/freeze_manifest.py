#!/usr/bin/env python3
"""Freeze the Stage 04 AON Timer functional-bin manifest from URG text/XML.

The full URG report supplies the authoritative group/type and instance-score
totals. A second URG report made with ``-show brief group -group expand_bins``
supplies expanded names for uncovered auto bins; it is not used for totals.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SCHEMA = "opentitan-aon-timer-functional-4525-v1"
AON_GROUPS = {
    "aon_timer_env_pkg::aon_timer_env_cov::timer_cfg_cg",
    "aon_timer_env_pkg::aon_timer_env_cov::wake_up_timer_thold_hit_cg",
    "aon_timer_env_pkg::aon_timer_env_cov::watchdog_timer_bite_thold_hit_cg",
    "aon_timer_env_pkg::aon_timer_env_cov::watchdog_timer_bark_thold_hit_cg",
}
TABLE_TITLES = {"Bins", "Uncovered bins", "Covered bins", "Excluded/Illegal bins", "Element holes"}
SOURCE_PREFIXES = {
    "lowrisc_dv_aon_timer_env_0.1": "hw/ip/aon_timer/dv/env",
    "lowrisc_dv_cip_lib_0": "hw/dv/sv/cip_lib",
    "lowrisc_dv_tl_agent_0": "hw/dv/sv/tl_agent",
    "lowrisc_dv_alert_esc_agent_0": "hw/dv/sv/alert_esc_agent",
    "lowrisc_dv_dv_lib_0": "hw/dv/sv/dv_lib",
    "lowrisc_dv_dv_base_reg_0": "hw/dv/sv/dv_base_reg",
    "lowrisc_dv_sec_cm_0": "hw/dv/sv/sec_cm",
}


def need(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_id(key: list[object]) -> str:
    raw = json.dumps([SCHEMA, *key], ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    return "bin_" + hashlib.sha256(raw).hexdigest()


def clean_bin_name(name: str) -> str:
    value = name.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1]
        if inner.startswith("auto[") or " - auto[" in inner:
            value = inner
    return value


def parse_urg_totals(groups_text: str) -> tuple[dict, dict[str, dict]]:
    section = groups_text.split("Total Groups Coverage Summary", 1)
    need(len(section) == 2, "URG groups.txt has no total group summary")
    total = re.search(r"(?m)^\s*(\d+)\s+(\d+)\s+([\d.]+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+(\d+)\s*$", section[1])
    need(total is not None, "URG total group score row is missing")
    summary = {
        "urg_overall_covered": int(total.group(1)),
        "urg_overall_expected": int(total.group(2)),
        "urg_overall_score_percent": float(total.group(3)),
        "instance_score_covered": int(total.group(4)),
        "instance_score_expected": int(total.group(5)),
        "instance_score_percent": float(total.group(6)),
        "weight": int(total.group(7)),
    }
    header = re.search(r"(?m)^COVERED EXPECTED SCORE\s+INSTANCES WEIGHT.*?NAME\s*\r?\n", section[1])
    need(header is not None, "URG group detail table is missing")
    rows: dict[str, dict] = {}
    for line in section[1][header.end():].splitlines():
        fields = line.split()
        if len(fields) < 11 or not fields[0].isdigit() or not fields[1].isdigit():
            if rows and (not line.strip() or set(line.strip()) == {"-"}):
                break
            continue
        name = " ".join(fields[10:])
        rows[name] = {
            "covered": int(fields[0]), "type_expected": int(fields[1]),
            "type_score_percent": float(fields[2]),
            "instance_score_percent": float(fields[3]) if re.fullmatch(r"[\d.]+", fields[3]) else None,
            "weight": int(fields[4]), "goal": int(fields[5]),
            "at_least": int(fields[6]), "per_instance": int(fields[7]),
            "auto_bin_max": int(fields[8]), "print_missing": int(fields[9]),
        }
    need(len(rows) == 16, "Expected 16 URG group rows, found {}".format(len(rows)))
    summary["type_aggregate_covered"] = sum(row["covered"] for row in rows.values())
    summary["type_aggregate_expected"] = sum(row["type_expected"] for row in rows.values())
    summary["type_aggregate_score_percent"] = round(
        100.0 * summary["type_aggregate_covered"] / summary["type_aggregate_expected"], 2)
    return summary, rows


def read_xml(path: Path) -> ET.Element:
    with path.open("rb") as f:
        magic = f.read(2)
        f.seek(0)
        if magic == b"\x1f\x8b":
            with gzip.GzipFile(fileobj=f) as z:
                return ET.parse(z).getroot()
        return ET.parse(f).getroot()


def relative_source(path: str | None) -> str | None:
    if not path:
        return None
    normalized = path.replace("\\", "/")
    marker = "/src/"
    tail = normalized.split(marker, 1)[-1]
    package, slash, rest = tail.partition("/")
    if slash and package in SOURCE_PREFIXES:
        return SOURCE_PREFIXES[package] + "/" + rest
    return Path(tail).name


def attrs(element: ET.Element | None) -> dict[str, str]:
    return dict(element.attrib) if element is not None else {}


def xml_metadata(cumulative: Path, instance_xml: Path) -> tuple[dict[str, dict], dict[str, tuple[str, str, str]]]:
    root = read_xml(cumulative)
    definitions: dict[tuple[str, str, str], dict] = {}
    by_group: dict[str, dict] = {}
    for program in root.findall("./program"):
        program_id = program.get("id", "")
        for source in program.findall("./cg_src"):
            source_id = source.get("id", "")
            source_cps = {cp.get("id", ""): cp for cp in source.findall("./cp")}
            source_ccs = {cc.get("id", ""): cc for cc in source.findall("./cc")}
            source_loc = source.find("./srcloc")
            for covdef in source.findall("./cg_covdef"):
                covdef_id = covdef.get("id", "")
                scope = covdef.get("scope", program.get("name", ""))
                covname = covdef.get("name", source.get("name", ""))
                group_name = scope + "::" + covname
                group = {
                    "name": group_name,
                    "num_instances_declared": int(covdef.get("numinsts", "0")),
                    "source_file": relative_source(source_loc.get("file") if source_loc is not None else None),
                    "source_line": int(source_loc.get("lines", "0")) if source_loc is not None and source_loc.get("lines", "").isdigit() else None,
                    "group_options": attrs(covdef.find("./cg_option")) or attrs(source.find("./cg_option")),
                    "coverpoints": {}, "crosses": {}, "named_cross_bins": [],
                }
                for cp in covdef.findall("./cp"):
                    cp_id = cp.get("id", "")
                    source_cp = source_cps.get(cp_id)
                    cp_name = source_cp.get("exprname") if source_cp is not None else "cp_" + cp_id
                    loc = source_cp.find("./srcloc") if source_cp is not None else None
                    if loc is None:
                        loc = cp.find("./srcloc")
                    group["coverpoints"][cp_name] = {
                        "id": cp_id, "type": cp.get("type", "user"),
                        "width": int(cp.get("width", "0")),
                        "options": attrs(cp.find("./cp_option")),
                        "source_file": relative_source(loc.get("file") if loc is not None else None),
                        "source_line": int(loc.get("lines", "0")) if loc is not None and loc.get("lines", "").isdigit() else None,
                        "definitions": [dict(bn.attrib) for bn in cp.findall("./bn")],
                    }
                for cc in covdef.findall("./cc"):
                    cc_id = cc.get("id", "")
                    source_cc = source_ccs.get(cc_id)
                    cross_name = source_cc.get("name") if source_cc is not None else "cross_" + cc_id
                    loc = source_cc.find("./srcloc") if source_cc is not None else None
                    if loc is None:
                        loc = cc.find("./srcloc")
                    refs = cc.find("./crosspoints")
                    cp_ids = refs.get("covdefrefs", "").split() if refs is not None else []
                    group["crosses"][cross_name] = {
                        "id": cc_id,
                        "coverpoints": [group["coverpoints"].get(next((n for n, cp in group["coverpoints"].items() if cp["id"] == ref), ""), {}).get("name", "") for ref in cp_ids],
                        "coverpoint_ids": cp_ids,
                        "options": attrs(cc.find("./cc_option")),
                        "source_file": relative_source(loc.get("file") if loc is not None else None),
                        "source_line": int(loc.get("lines", "0")) if loc is not None and loc.get("lines", "").isdigit() else None,
                    }
                    # Preserve the exact cp names in order; the lookup above uses the
                    # separate ID below to avoid dependence on source order.
                    id_to_name = {meta["id"]: name for name, meta in group["coverpoints"].items()}
                    group["crosses"][cross_name]["coverpoints"] = [id_to_name.get(ref, "cp_" + ref) for ref in cp_ids]
                    for named in cc.findall("./named_cross_bins/n_cn_d"):
                        group["named_cross_bins"].append({
                            "cross": cross_name, "name": named.get("name", ""),
                            "illegal": named.get("illegal") == "1",
                            "excluded": named.get("excl") == "1",
                        })
                key = (program_id, source_id, covdef_id)
                definitions[key] = group
                by_group[group_name] = group

    instance_root = read_xml(instance_xml)
    instances: dict[str, tuple[str, str, str]] = {}
    for inst in instance_root.findall("./cg_inst"):
        key = (inst.get("prog", ""), inst.get("srcdef", ""), inst.get("covdef", ""))
        group = definitions.get(key)
        if group is None:
            continue
        name = inst.get("name", "").strip()
        options = attrs(inst.find("./cg_option"))
        for cp_inst in inst.findall("./cp"):
            cp_id = cp_inst.get("id", "")
            cp_name = next((n for n, cp in group["coverpoints"].items() if cp["id"] == cp_id), None)
            if cp_name:
                group["coverpoints"][cp_name].setdefault("instance_options", attrs(cp_inst.find("./cp_option")))
        for cc_inst in inst.findall("./cc"):
            cc_id = cc_inst.get("id", "")
            cc_name = next((n for n, cc in group["crosses"].items() if cc["id"] == cc_id), None)
            if cc_name:
                group["crosses"][cc_name].setdefault("instance_options", attrs(cc_inst.find("./cc_option")))
        group.setdefault("instance_paths", []).append(name)
        group.setdefault("instance_options", options)
        instances[name] = (group["name"], *key)
    for group in by_group.values():
        group["instance_paths"] = sorted(set(group.get("instance_paths", [])))
    return by_group, instances


def parse_group_entities(text: str, group_names: set[str], instance_to_group: dict[str, str]) -> dict[tuple[str, str | None], dict]:
    headings = list(re.finditer(r"(?m)^Group : (.+)$", text))
    starts: list[tuple[int, str]] = []
    last = None
    for heading in headings:
        name = heading.group(1).strip()
        if name != last:
            starts.append((heading.start(), name))
            last = name
    entities: dict[tuple[str, str | None], dict] = {}
    for i, (start, group_name) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        block = text[start:end]
        need(group_name in group_names, "URG detail group absent from group table: " + group_name)
        summaries = list(re.finditer(r"(?m)^Summary for Group( Instance)?\s+(.+)$", block))
        for j, summary in enumerate(summaries):
            next_pos = summaries[j + 1].start() if j + 1 < len(summaries) else len(block)
            body = block[summary.end():next_pos]
            instance_path = summary.group(2).strip() if summary.group(1) else None
            if instance_path is not None:
                need(instance_path in instance_to_group, "URG instance is absent from VCS instance XML: " + instance_path)
                need(instance_to_group[instance_path] == group_name,
                     "URG instance maps to a different covergroup: " + instance_path)
            entities[(group_name, instance_path)] = parse_sections(body)
    return entities


def parse_sections(body: str) -> dict:
    result = {"variables": {}, "crosses": {}, "expected": 0}
    matches = list(re.finditer(r"(?m)^Summary for (Variable|Cross) (.+)$", body))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        section = body[match.end():end]
        kind, name = match.group(1), match.group(2).strip()
        if kind == "Variable":
            categories = [int(m.group(1)) for m in re.finditer(
                r"(?m)^\s*(?:User Defined Bins|Automatically Generated Bins)\s+(\d+)\b", section)]
            expected = sum(categories)
            options = find_point_options(body, name, cross=False)
            result["variables"][name] = {"expected": expected, "options": options,
                                          "tables": parse_tables(section, cross=False)}
        else:
            expected_match = re.search(r"(?m)^\s*(?:Automatically Generated Cross Bins|TOTAL)\s+(\d+)\b", section)
            expected = int(expected_match.group(1)) if expected_match else 0
            options = find_point_options(body, name, cross=True)
            samples = re.search(r"(?m)^Samples crossed:\s*(.+)$", body)
            coverpoints = samples.group(1).split() if samples else []
            result["crosses"][name] = {"expected": expected, "options": options,
                                       "coverpoints": coverpoints,
                                       "tables": parse_tables(section, cross=True)}
        result["expected"] += expected
    return result


def find_point_options(body: str, point: str, cross: bool) -> dict:
    for line in body.splitlines():
        fields = line.split()
        if len(fields) < 8 or fields[0] != point:
            continue
        if not all(re.fullmatch(r"[\d.]+", field) for field in fields[1:5]):
            continue
        try:
            if cross:
                if len(fields) >= 8:
                    return {"goal": int(fields[5]), "weight": int(fields[6]),
                            "at_least": int(fields[7])}
            else:
                if len(fields) >= 9:
                    return {"goal": int(fields[5]), "weight": int(fields[6]),
                            "at_least": int(fields[7]), "auto_bin_max": int(fields[8])}
        except ValueError:
            continue
    return {"goal": 100, "weight": 1, "at_least": 1}


def parse_tables(section: str, cross: bool) -> list[dict]:
    lines = section.splitlines()
    out = []
    i = 0
    while i < len(lines):
        title = lines[i].strip()
        if title not in TABLE_TITLES:
            i += 1
            continue
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines) or "COUNT" not in lines[j]:
            i += 1
            continue
        header = lines[j]
        count_pos = header.find("COUNT")
        number_pos = header.find("NUMBER")
        status_pos = header.find("STATUS")
        columns = []
        if cross:
            tokens = list(re.finditer(r"\S+", header[:count_pos]))
            columns = [(m.start(), m.end()) for m in tokens]
        k = j + 1
        while k < len(lines) and lines[k].strip():
            line = lines[k]
            if cross:
                names = []
                for n, (col_start, _) in enumerate(columns):
                    stop = columns[n + 1][0] if n + 1 < len(columns) else count_pos
                    names.append(clean_bin_name(line[col_start:stop]))
                name: str | list[str] = names
            else:
                name = clean_bin_name(line[:count_pos])
            tail = line[count_pos:].strip().split()
            count_text = tail[0] if tail else "--"
            count = int(count_text) if count_text.isdigit() else 0
            number = 1
            if number_pos >= 0:
                numtail = line[number_pos:].strip().split()
                if numtail and numtail[0].isdigit():
                    number = int(numtail[0])
            else:
                number_match = re.search(r"\((\d+) bins\)", line)
                if number_match:
                    number = int(number_match.group(1))
            status = ""
            if status_pos >= 0:
                status_tail = line[status_pos:].strip().split()
                status = status_tail[0] if status_tail else ""
            out.append({"title": title, "name": name, "count": count,
                        "count_omitted": count_text == "--", "number": number,
                        "status": status})
            k += 1
        i = max(k, i + 1)
    return out


def is_covered_row(row: dict) -> bool:
    # URG prints a generic "Bins" table when a point has no separate covered /
    # uncovered tables. In that form, the COUNT column determines the status.
    return row["title"] == "Covered bins" or (row["title"] == "Bins" and row["count"] > 0)


def is_uncovered_row(row: dict) -> bool:
    return row["title"] == "Uncovered bins" or (row["title"] == "Bins" and row["count"] == 0)


def parse_expanded_entities(text: str, group_names: set[str], instance_to_group: dict[str, str], definitions: dict[str, dict]) -> dict:
    entities = parse_group_entities(text, group_names, instance_to_group)
    for (group_name, instance_path), entity in entities.items():
        # The ordinary detail tables from the brief report are ignored; only the
        # explicit Decompressed-uncovered tables are used to expand definitions.
        block_start = text.find("Group : " + group_name)
        del block_start
    result: dict[tuple[str, str | None], dict] = {}
    # Re-scan each block so all rows retain the corresponding instance context.
    headings = list(re.finditer(r"(?m)^Group : (.+)$", text))
    starts: list[tuple[int, str]] = []
    last = None
    for heading in headings:
        name = heading.group(1).strip()
        if name != last:
            starts.append((heading.start(), name))
            last = name
    for i, (start, group_name) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        block = text[start:end]
        summaries = list(re.finditer(r"(?m)^Summary for Group( Instance)?\s+(.+)$", block))
        for j, summary in enumerate(summaries):
            next_pos = summaries[j + 1].start() if j + 1 < len(summaries) else len(block)
            body = block[summary.end():next_pos]
            instance_path = summary.group(2).strip() if summary.group(1) else None
            if instance_path is not None:
                need(instance_to_group.get(instance_path) == group_name,
                     "Expanded URG instance does not match XML: " + instance_path)
            key = (group_name, instance_path)
            expanded = {"variables": {}, "crosses": {}}
            sections = list(re.finditer(r"(?m)^Decompressed uncovered bins for (.+)$", body))
            for sec_i, sec in enumerate(sections):
                sec_end = sections[sec_i + 1].start() if sec_i + 1 < len(sections) else len(body)
                lines = body[sec.end():sec_end].splitlines()
                jline = 0
                while jline < len(lines) and not lines[jline].strip():
                    jline += 1
                if jline >= len(lines):
                    continue
                header = lines[jline]
                point = sec.group(1).strip()
                group_meta = definitions[group_name]
                is_cross = point in group_meta["crosses"]
                rows = parse_decompressed_table(lines[jline:])
                target = expanded["crosses"] if is_cross else expanded["variables"]
                target[point] = rows
            result[key] = expanded
    return result


def parse_decompressed_table(lines: list[str]) -> list[dict]:
    while lines and not lines[0].strip():
        lines = lines[1:]
    if not lines:
        return []
    header = lines[0]
    count_pos = header.find("COUNT")
    if count_pos < 0:
        return []
    columns = [(m.start(), m.end()) for m in re.finditer(r"\S+", header[:count_pos])]
    is_cross = len(columns) > 1
    result = []
    for line in lines[1:]:
        if not line.strip():
            break
        count_tail = line[count_pos:].strip().split()
        count_text = count_tail[0] if count_tail else "--"
        count = int(count_text) if count_text.isdigit() else 0
        if is_cross:
            name = []
            for index, (start, _) in enumerate(columns):
                stop = columns[index + 1][0] if index + 1 < len(columns) else count_pos
                name.append(clean_bin_name(line[start:stop]))
        else:
            name = clean_bin_name(line[:count_pos])
        result.append({"name": name, "count": count, "count_omitted": count_text == "--"})
    return result


def generated_weight_zero_names(definition: dict, point: str, expected: int) -> list[str]:
    meta = definition["coverpoints"].get(point)
    need(meta is not None, "Weight-zero point is absent from VCS XML: " + point)
    explicit = [item.get("name", "") for item in meta["definitions"] if item.get("name")]
    if explicit:
        need(len(explicit) == expected, "Explicit weight-zero bins disagree with URG for " + point)
        return explicit
    count = int(meta["options"].get("auto_bin_max", "0"))
    need(count == expected, "Cannot enumerate weight-zero auto bins for {}: expected {}, auto_bin_max {}".format(
        point, expected, count))
    return ["auto[{}]".format(index) for index in range(count)]


def fallback_names(rows: list[dict], expected: int) -> list[dict]:
    result = []
    for row in rows:
        if row["title"] == "Excluded/Illegal bins":
            continue
        name = row["name"]
        if isinstance(name, list):
            continue
        if row["number"] == 1:
            result.append({"name": clean_bin_name(name), "count": row["count"],
                           "count_omitted": row["count_omitted"]})
            continue
        match = re.fullmatch(r"\[?auto\[(\d+)\]\s*-\s*auto\[(\d+)\]\]?", name)
        if match:
            lo, hi = int(match.group(1)), int(match.group(2))
            need(hi >= lo and hi - lo + 1 == row["number"], "Invalid URG auto index range: " + name)
            result.extend({"name": "auto[{}]".format(k), "count": row["count"],
                           "count_omitted": row["count_omitted"]} for k in range(lo, hi + 1))
            continue
        raise ValueError("Unexpanded URG bin range needs -group expand_bins: " + name)
    if expected:
        need(len(result) == expected, "Fallback URG rows contain {} bins, expected {}".format(len(result), expected))
    return result


def build_bins(groups: dict[str, dict], group_rows: dict[str, dict], full: dict,
               expanded: dict, instance_to_group: dict[str, str]) -> tuple[list[dict], list[dict], dict]:
    bins: list[dict] = []
    excluded: list[dict] = []
    type_defs: dict[tuple[str, str, str, str], dict] = {}
    for group_name, table_row in group_rows.items():
        group_meta = groups[group_name]
        per_instance = bool(table_row["per_instance"])
        entity_keys = [key for key in full if key[0] == group_name]
        if per_instance:
            need(entity_keys and all(key[1] is not None for key in entity_keys),
                 "Per-instance URG group has no instance detail pages: " + group_name)
            need({key[1] for key in entity_keys} == set(group_meta["instance_paths"]),
                 "URG and VCS instance lists disagree for " + group_name)
        else:
            entity_keys = [(group_name, None)]
            need(entity_keys[0] in full, "Type-level URG detail is missing: " + group_name)

        for entity_key in sorted(entity_keys, key=lambda item: item[1] or ""):
            entity = full[entity_key]
            exp_entity = expanded.get(entity_key, {"variables": {}, "crosses": {}})
            instance_path = entity_key[1]
            scope = "instance" if per_instance else "type_aggregate"
            need(set(entity["variables"]) == set(group_meta["coverpoints"]),
                 "URG/VCS coverpoint list differs for " + group_name + ": {} vs {}".format(
                     sorted(entity["variables"]), sorted(group_meta["coverpoints"])))
            need(set(entity["crosses"]) == set(group_meta["crosses"]),
                 "URG/VCS cross list differs for " + group_name)
            entity_bins: dict[str, list[dict]] = {}
            for point, record in entity["variables"].items():
                point_meta = group_meta["coverpoints"][point]
                weight = int(record["options"].get("weight", 1))
                if weight == 0:
                    names = generated_weight_zero_names(group_meta, point, record["expected"])
                    point_bins = [{"name": name, "count": 0, "count_omitted": True,
                                   "status": "Weight-zero"} for name in names]
                else:
                    missing = exp_entity.get("variables", {}).get(point, [])
                    if not missing:
                        missing = fallback_names([r for r in record["tables"] if is_uncovered_row(r)],
                                                 max(0, record["expected"] - sum(
                                                     r["number"] for r in record["tables"] if is_covered_row(r))))
                    covered = []
                    for row in record["tables"]:
                        if is_covered_row(row):
                            need(not isinstance(row["name"], list), "Variable bin is not scalar")
                            covered.append({"name": clean_bin_name(row["name"]), "count": row["count"],
                                            "count_omitted": row["count_omitted"], "status": "Covered"})
                    excluded_rows = [r for r in record["tables"] if r["title"] == "Excluded/Illegal bins"]
                    for row in excluded_rows:
                        excluded.append({"covergroup": group_name, "coverpoint_or_cross": point,
                                         "instance_path": instance_path, "bin_name": str(row["name"]),
                                         "status": row["status"] or "Excluded", "score_contributing": False})
                    point_bins = covered + [{"name": clean_bin_name(str(r["name"])), "count": r["count"],
                                             "count_omitted": r["count_omitted"], "status": "Uncovered"}
                                            for r in missing]
                dedup = {item["name"]: item for item in point_bins}
                need(len(dedup) == len(point_bins), "Duplicate coverpoint bin name in {}.{}".format(group_name, point))
                need(len(point_bins) == record["expected"],
                     "{} {}.{} bins extracted; URG expected {}".format(
                         len(point_bins), group_name, point, record["expected"]))
                entity_bins[point] = point_bins
                for item in point_bins:
                    score = weight != 0 and int(record["options"].get("at_least", 1)) > 0
                    key = (group_name, scope, instance_path or "type_aggregate", "coverpoint", point, item["name"])
                    bin_id = stable_id(list(key))
                    row = {
                        "id": bin_id, "covergroup": group_name, "coverage_scope": scope,
                        "covergroup_instance_path": instance_path,
                        "covergroup_instance_paths": group_meta["instance_paths"],
                        "coverpoint_or_cross": point, "bin_name": item["name"],
                        "bin_type": "coverpoint", "source_file": point_meta["source_file"] or group_meta["source_file"],
                        "source_line": point_meta["source_line"] or group_meta["source_line"],
                        "eligible_for_instance_score": score,
                        "exclusion_reason": None if score else "weight_zero",
                        "weight": weight, "at_least": int(record["options"].get("at_least", 1)),
                        "goal": int(record["options"].get("goal", 100)),
                    }
                    bins.append(row)
                    type_defs[(group_name, "coverpoint", point, item["name"])] = item

            for cross, record in entity["crosses"].items():
                cross_meta = group_meta["crosses"][cross]
                missing = exp_entity.get("crosses", {}).get(cross, [])
                covered = []
                for row in record["tables"]:
                    if is_covered_row(row):
                        need(isinstance(row["name"], list), "Cross report row has no tuple")
                        covered.append({"name": [clean_bin_name(x) for x in row["name"]], "count": row["count"],
                                        "count_omitted": row["count_omitted"], "status": "Covered"})
                    elif row["title"] == "Excluded/Illegal bins":
                        excluded.append({"covergroup": group_name, "coverpoint_or_cross": cross,
                                         "instance_path": instance_path, "bin_name": str(row["name"]),
                                         "status": row["status"] or "Illegal", "score_contributing": False})
                if not missing:
                    missing = []
                    for row in record["tables"]:
                        if is_uncovered_row(row) and isinstance(row["name"], list):
                            if row["number"] == 1:
                                missing.append({"name": row["name"], "count": 0, "count_omitted": True})
                cross_bins = covered + [{"name": [clean_bin_name(str(x)) for x in r["name"]],
                                         "count": r["count"], "count_omitted": r["count_omitted"],
                                         "status": "Uncovered"} for r in missing]
                cross_bins = [item for item in cross_bins if isinstance(item["name"], list)]
                dedup_cross = {tuple(item["name"]): item for item in cross_bins}
                need(len(dedup_cross) == len(cross_bins), "Duplicate cross tuple in {}.{}".format(group_name, cross))
                need(len(cross_bins) == record["expected"],
                     "{} {}.{} cross bins extracted; URG expected {}".format(
                         len(cross_bins), group_name, cross, record["expected"]))
                for item in cross_bins:
                    need(len(item["name"]) == len(record["coverpoints"]),
                         "Cross tuple arity mismatch for {}.{}".format(group_name, cross))
                    for cp_name, cp_bin in zip(record["coverpoints"], item["name"]):
                        if cp_name in entity_bins:
                            need(cp_bin in {p["name"] for p in entity_bins[cp_name]},
                                 "Cross bin references undefined coverpoint bin {}.{}={}".format(
                                     group_name, cp_name, cp_bin))
                    score = int(record["options"].get("weight", 1)) != 0 and int(record["options"].get("at_least", 1)) > 0
                    bin_name = " x ".join("{}={}".format(cp, val) for cp, val in zip(record["coverpoints"], item["name"]))
                    key = [group_name, scope, instance_path or "type_aggregate", "cross", cross, bin_name]
                    bins.append({
                        "id": stable_id(key), "covergroup": group_name, "coverage_scope": scope,
                        "covergroup_instance_path": instance_path,
                        "covergroup_instance_paths": group_meta["instance_paths"],
                        "coverpoint_or_cross": cross, "bin_name": bin_name,
                        "bin_type": "cross", "source_file": cross_meta["source_file"] or group_meta["source_file"],
                        "source_line": cross_meta["source_line"] or group_meta["source_line"],
                        "eligible_for_instance_score": score,
                        "exclusion_reason": None if score else "weight_zero",
                        "weight": int(record["options"].get("weight", 1)),
                        "at_least": int(record["options"].get("at_least", 1)),
                        "goal": int(record["options"].get("goal", 100)),
                    })
    return bins, excluded, {"unique_type_bin_definitions": type_defs}


def make(args: argparse.Namespace) -> None:
    full_groups_text = args.groups.read_text(encoding="utf-8", errors="replace")
    full_text = args.grpinfo.read_text(encoding="utf-8", errors="replace")
    expanded_text = args.expanded_grpinfo.read_text(encoding="utf-8", errors="replace")
    totals, group_rows = parse_urg_totals(full_groups_text)
    definitions, instance_map = xml_metadata(args.cumulative_xml, args.instance_xml)
    instance_to_group = {name: value[0] for name, value in instance_map.items()}
    need(set(group_rows) == set(definitions), "URG group table and VCS XML group definitions differ")
    for name, row in group_rows.items():
        if row["per_instance"]:
            need(definitions[name]["num_instances_declared"] == len(definitions[name]["instance_paths"]),
                 "VCS instance XML count mismatch for per-instance group " + name)
    full = parse_group_entities(full_text, set(group_rows), instance_to_group)
    expanded = parse_expanded_entities(expanded_text, set(group_rows), instance_to_group, definitions)
    bins, excluded, _ = build_bins(definitions, group_rows, full, expanded, instance_to_group)

    eligible = [item for item in bins if item["eligible_for_instance_score"]]
    type_keys = {(item["covergroup"], item["bin_type"], item["coverpoint_or_cross"], item["bin_name"]) for item in bins}
    weight_zero = len(bins) - len(eligible)
    aon = [item for item in eligible if item["covergroup"] in AON_GROUPS]
    generic = [item for item in eligible if item["covergroup"] not in AON_GROUPS]
    by_group = {}
    for name in group_rows:
        type_bins = [item for item in bins if item["covergroup"] == name]
        instance_bins = [item for item in eligible if item["covergroup"] == name]
        by_group[name] = {
            "type_expected": group_rows[name]["type_expected"],
            "instance_score_expected": len(instance_bins),
            "instance_count": definitions[name]["num_instances_declared"],
            "per_instance": bool(group_rows[name]["per_instance"]),
        }
    need(len(group_rows) == 16, "Expected 16 covergroups")
    need(sum(row["type_expected"] for row in group_rows.values()) == totals["type_aggregate_expected"],
         "URG group type rows do not sum to the type-aggregate summary")
    need(len(bins) == 4533, "Expanded report bins do not equal 4,533; found {}".format(len(bins)))
    need(weight_zero == 8, "Expected 8 weight-zero bins, found {}".format(weight_zero))
    need(len(eligible) == totals["instance_score_expected"] == 4525,
         "Instance-score manifest total does not match URG")
    need(len(aon) == 4279, "AON Timer score-bin count is not 4,279")
    need(len(generic) == 246, "Generic functional score-bin count is not 246")
    need(len(type_keys) == totals["type_aggregate_expected"],
         "Unique type-scoped bin definitions do not match URG type total")

    # Compare the parsed active bin hits to both totals from the full report.
    full_hits = sum(item.get("_hit", 0) for item in bins if item["eligible_for_instance_score"])
    # Hit counts are kept in the source entity objects; attach the score counts
    # after structural IDs have been frozen, without including them in the manifest.
    hit_counts = {}
    for (group_name, instance_path), entity in full.items():
        for point, record in entity["variables"].items():
            for row in record["tables"]:
                if is_covered_row(row):
                    key = (group_name, instance_path, "coverpoint", point, clean_bin_name(str(row["name"])))
                    hit_counts[key] = row["count"]
        for cross, record in entity["crosses"].items():
            for row in record["tables"]:
                if is_covered_row(row) and isinstance(row["name"], list):
                    name = " x ".join("{}={}".format(cp, clean_bin_name(val)) for cp, val in zip(record["coverpoints"], row["name"]))
                    hit_counts[(group_name, instance_path, "cross", cross, name)] = row["count"]
    for item in bins:
        key = (item["covergroup"], item["covergroup_instance_path"], item["bin_type"],
               item["coverpoint_or_cross"], item["bin_name"])
        item["_hit_count"] = hit_counts.get(key, 0)
    hit_bins = sum(item["_hit_count"] > 0 for item in eligible)
    type_hit_bins = len({(item["covergroup"], item["bin_type"], item["coverpoint_or_cross"], item["bin_name"])
                         for item in bins if item["_hit_count"] > 0})
    need(hit_bins == totals["instance_score_covered"] == 45,
         "Manifest hit count does not match URG instance score")
    need(type_hit_bins == totals["type_aggregate_covered"] == 46,
         "Manifest type-aggregate hit count does not match URG")

    static_bins = [{key: value for key, value in item.items() if not key.startswith("_")} for item in bins]
    static_bins.sort(key=lambda item: item["id"])
    raw_hashes = {path.name: sha256(path) for path in (
        args.groups, args.grpinfo, args.expanded_groups, args.expanded_grpinfo,
        args.cumulative_xml, args.instance_xml,
    )}
    manifest = {
        "schema_version": SCHEMA,
        "source": {"open_titan_commit": args.source_commit, "source_tree_sha1": args.source_tree_sha1},
        "tools": {"simulator": "VCS P-2019.06-SP1", "reporter": "URG P-2019.06-SP1", "covdb": "13.1"},
        "coverage_scope": "official functional group coverage; per_instance groups expanded by VCS instance; weight-zero bins are retained as metadata but excluded from the instance-score bin universe",
        "report_configuration": ["-metric group", "-group ratio", "-group lrm_bin_name", "-group instcov_for_score"],
        "primary_denominator": {"definition": "URG overall instance-score denominator", "expected_bins": len(eligible),
                                "hit_bins": hit_bins, "percent": round(100.0 * hit_bins / len(eligible), 6)},
        "type_aggregate_reference": {"expected_bins": totals["type_aggregate_expected"],
                                     "hit_bins": type_hit_bins,
                                     "percent": totals["type_aggregate_score_percent"]},
        "counts": {"covergroups": len(group_rows), "instance_expanded_records_including_weight_zero": len(bins),
                   "score_contributing_bins": len(eligible), "weight_zero_bins": weight_zero,
                   "aon_timer_bins": len(aon), "generic_testbench_bins": len(generic),
                   "unique_type_bin_definitions": len(type_keys),
                   "illegal_or_excluded_named_bins_outside_expected": len(excluded)},
        "covergroups": by_group,
        "excluded_named_bins": excluded,
        "raw_report_sha256": raw_hashes,
        "bins": static_bins,
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    if args.output_dir.exists():
        raise FileExistsError("Refusing to overwrite output: " + str(args.output_dir))
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "coverage_manifest.v1.json").write_bytes(manifest_bytes)
    smoke = {
        "schema_version": SCHEMA, "run_id": args.run_id,
        "source_commit": args.source_commit, "manifest_sha256": manifest_hash,
        "urg_type_aggregate": {"covered": totals["type_aggregate_covered"],
                                "expected": totals["type_aggregate_expected"],
                                "score_percent": totals["type_aggregate_score_percent"]},
        "urg_instance_score": {"covered": totals["instance_score_covered"],
                                "expected": totals["instance_score_expected"],
                                "score_percent": totals["instance_score_percent"]},
        "expanded_instance_bin_records": len(bins), "weight_zero_exclusions": weight_zero,
        "aon_timer_eligible_bins": len(aon), "generic_eligible_bins": len(generic),
        "raw_report_sha256": raw_hashes,
    }
    (args.output_dir / "smoke_validation.json").write_text(json.dumps(smoke, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    with (args.output_dir / "group_scope_summary.tsv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(["covergroup", "type_expected", "instance_score_expected", "instance_count", "per_instance"])
        for name, row in sorted(by_group.items()):
            writer.writerow([name, row["type_expected"], row["instance_score_expected"], row["instance_count"], int(row["per_instance"])])
    hashes = []
    for path in sorted(args.output_dir.iterdir()):
        hashes.append("{}  {}\n".format(sha256(path), path.name))
    (args.output_dir / "SHA256SUMS").write_text("".join(hashes), encoding="utf-8")
    print(json.dumps({"verification": "PASS", "schema_version": SCHEMA,
                      "instance_score_bins": len(eligible), "expanded_records": len(bins),
                      "weight_zero_bins": weight_zero, "aon_timer_bins": len(aon),
                      "generic_bins": len(generic), "hit_bins": hit_bins,
                      "manifest_sha256": manifest_hash}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--groups", type=Path, required=True, help="Full URG groups.txt")
    parser.add_argument("--grpinfo", type=Path, required=True, help="Full URG grpinfo.txt")
    parser.add_argument("--expanded-groups", type=Path, required=True, help="URG brief+expand_bins groups.txt")
    parser.add_argument("--expanded-grpinfo", type=Path, required=True, help="URG brief+expand_bins grpinfo.txt")
    parser.add_argument("--cumulative-xml", type=Path, required=True)
    parser.add_argument("--instance-xml", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-commit", default="9f20940d494a223cc950a5b98f748fb28109d458")
    parser.add_argument("--source-tree-sha1", default="4229b5d334cf7c02996856ddbdf625989b5a6b58")
    args = parser.parse_args()
    try:
        make(args)
    except (ValueError, OSError, ET.ParseError) as exc:
        print("STAGE04_FREEZE_FAILED: " + str(exc), file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
