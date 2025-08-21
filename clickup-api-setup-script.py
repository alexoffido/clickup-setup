#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClickUp Scaffolding for Fido Ticketing System
- Idempotent creation of Space, Folder, Lists, and Custom Fields
- Exports IDs for use by the Slack Ticketing app
- Works locally or in GitHub Actions (secrets via env)

USAGE (local):
  export CLICKUP_API_TOKEN=pk_xxx
  export CLICKUP_TEAM_ID=9013484736
  python3 clickup-api-setup-script.py

USAGE (Actions/CI):
  # See provided workflow, inject secrets as env

Helpful flags:
  --dry-run            : do not create; only print actions
  --discover-team      : fetch teams and print IDs; exit
  --space-name "Fido Operations"  : override space name (default below)
"""

import os
import sys
import json
import time
import argparse
from typing import Dict, Any, List, Optional

import requests

# ------------- Configuration (edit names if you need to) -----------------

SPACE_NAME   = "Fido Operations"
FOLDER_NAME  = "CX Tickets"

LISTS = {
    "issues":    "Service Issues",
    "inquiries": "Customer Inquiries",
    "units":     "Unit Management",
}

# Custom fields to create on each list. Keyed by "list key" in LISTS.
# NOTE: For dropdowns, we can seed options here.
COMMON_FIELDS = [
    {"name": "Slack Ticket ID", "type": "short_text"},
    {"name": "Slack Permalink", "type": "url"},
    {"name": "Submitted By (Slack User)", "type": "short_text"},
    {"name": "Customer Name", "type": "short_text"},
    {"name": "Market Code", "type": "dropdown", "options": [
        "ATX","ANA","CHS","CLT","DEN","DFW","FLL","GEG","HOT","JAX","LAX","LIT",
        "PHX","PIE","SAN","SAT","SDX","SEA","SLC","SRQ","STA","STS","VPS","MISC"
    ]},
    {"name": "Property/Unit", "type": "short_text"},
    {"name": "Notes", "type": "text"}
]

ISSUE_FIELDS = [
    {"name": "Issue Type", "type": "dropdown", "options": [
        "bin_placement","access_problem","schedule_conflict","property_logistics",
        "service_quality","customer_complaint","equipment_issue","other"
    ]},
    {"name": "Priority Level", "type": "dropdown", "options": [
        "urgent","high","normal","low"
    ]}
]

INQUIRY_FIELDS = [
    {"name": "Inquiry Type", "type": "dropdown", "options": [
        "schedule_question","service_status","billing_question","service_details",
        "new_service","pause_resume","property_update","general_info","other"
    ]},
    {"name": "Response Priority", "type": "dropdown", "options": [
        "urgent","high","normal","low"
    ]}
]

UNIT_FIELDS = [
    {"name": "Change Type", "type": "dropdown", "options": [
        "new_unit","cancellation","pause","restart","modify"
    ]},
    {"name": "Trash Pickup Day", "type": "dropdown", "options": [
        "monday","tuesday","wednesday","thursday","friday","saturday","sunday"
    ]},
    {"name": "Recycling Day", "type": "dropdown", "options": [
        "same_as_trash","monday","tuesday","wednesday","thursday","friday","saturday","sunday","none"
    ]},
    {"name": "Effective Date", "type": "date"}
]

LIST_TO_FIELDS = {
    "issues":    COMMON_FIELDS + ISSUE_FIELDS,
    "inquiries": COMMON_FIELDS + INQUIRY_FIELDS,
    "units":     COMMON_FIELDS + UNIT_FIELDS
}

# ---------------------- Helpers / HTTP ----------------------

def env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name, default)
    return v.strip() if isinstance(v, str) else v

def http_headers(token: str) -> Dict[str, str]:
    return {"Authorization": token, "Content-Type": "application/json"}

def get_json(url: str, token: str, retry=3) -> Any:
    for i in range(retry):
        r = requests.get(url, headers=http_headers(token), timeout=30)
        if r.status_code == 429:
            time.sleep(2 + i)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"GET failed after retries: {url}")

def post_json(url: str, token: str, payload: Dict[str, Any], retry=3) -> Any:
    for i in range(retry):
        r = requests.post(url, headers=http_headers(token), data=json.dumps(payload), timeout=30)
        if r.status_code in (429, 409):
            time.sleep(2 + i)
            continue
        if 200 <= r.status_code < 300:
            return r.json() if r.text else {}
        # ClickUp returns 200/201/202 mostly; raise otherwise
        try:
            r.raise_for_status()
        except Exception as e:
            # print body for debug
            print(f"POST {url} failed ({r.status_code}): {r.text}")
            raise e
    raise RuntimeError(f"POST failed after retries: {url}")

def print_step(msg: str):
    print(f"\n=== {msg}")

# --------------------- Idempotent creators ---------------------

def discover_teams(token: str) -> List[Dict[str, Any]]:
    data = get_json("https://api.clickup.com/api/v2/team", token)
    return data.get("teams", [])

def find_or_create_space(team_id: str, token: str, space_name: str, dry: bool) -> Dict[str, Any]:
    print_step(f"Space: lookup '{space_name}'")
    teams = get_json("https://api.clickup.com/api/v2/team", token)["teams"]
    for t in teams:
        if str(t["id"]) == str(team_id):
            for s in t.get("spaces", []):
                if s["name"] == space_name:
                    print(f"• Reusing space '{space_name}' ({s['id']})")
                    return {"id": s["id"], "name": s["name"]}

    if dry:
        print(f"• DRY RUN: would create space '{space_name}'")
        return {"id": "DRY_SPACE_ID", "name": space_name}

    payload = {"name": space_name, "multiple_assignees": True}
    # NOTE: Create Space uses POST /team/{team_id}/space
    url = f"https://api.clickup.com/api/v2/team/{team_id}/space"
    res = post_json(url, token, payload)
    print(f"• Created space '{space_name}' ({res['id']})")
    return {"id": res["id"], "name": res["name"]}

def find_or_create_folder(space_id: str, token: str, folder_name: str, dry: bool) -> Dict[str, Any]:
    print_step(f"Folder: lookup '{folder_name}'")
    url = f"https://api.clickup.com/api/v2/space/{space_id}/folder"
    folders = get_json(url, token).get("folders", [])
    for f in folders:
        if f["name"] == folder_name:
            print(f"• Reusing folder '{folder_name}' ({f['id']})")
            return {"id": f["id"], "name": f["name"]}

    if dry:
        print(f"• DRY RUN: would create folder '{folder_name}'")
        return {"id": "DRY_FOLDER_ID", "name": folder_name}

    create_url = f"https://api.clickup.com/api/v2/space/{space_id}/folder"
    res = post_json(create_url, token, {"name": folder_name})
    print(f"• Created folder '{folder_name}' ({res['id']})")
    return {"id": res["id"], "name": res["name"]}

def find_or_create_list(folder_id: str, token: str, list_name: str, dry: bool) -> Dict[str, Any]:
    print_step(f"List: lookup '{list_name}'")
    url = f"https://api.clickup.com/api/v2/folder/{folder_id}/list"
    lists = get_json(url, token).get("lists", [])
    for l in lists:
        if l["name"] == list_name:
            print(f"• Reusing list '{list_name}' ({l['id']})")
            return {"id": l["id"], "name": l["name"]}

    if dry:
        print(f"• DRY RUN: would create list '{list_name}'")
        return {"id": f"DRY_{list_name.upper().replace(' ', '_')}", "name": list_name}

    create_url = f"https://api.clickup.com/api/v2/folder/{folder_id}/list"
    res = post_json(create_url, token, {"name": list_name})
    print(f"• Created list '{list_name}' ({res['id']})")
    return {"id": res["id"], "name": res["name"]}

def get_list_fields(list_id: str, token: str) -> List[Dict[str, Any]]:
    url = f"https://api.clickup.com/api/v2/list/{list_id}/field"
    data = get_json(url, token)
    return data.get("fields", [])

def find_field_by_name(fields: List[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
    for f in fields:
        if f.get("name") == name:
            return f
    return None

def create_custom_field(list_id: str, token: str, field_def: Dict[str, Any], dry: bool) -> Dict[str, Any]:
    """
    Create a custom field on the list.
    Uses POST /list/{list_id}/field
    """
    if dry:
        print(f"• DRY RUN: would create field '{field_def['name']}' ({field_def['type']}) on list {list_id}")
        dummy = {"id": f"DRY_CF_{field_def['name']}", "name": field_def["name"], "type": field_def["type"]}
        # Fabricate options IDs if needed
        if field_def["type"] == "dropdown":
            dummy["type_config"] = {"options": [{"name": o, "id": f"DRY_OPT_{o}"} for o in field_def.get("options", [])]}
        return dummy

    url = f"https://api.clickup.com/api/v2/list/{list_id}/field"
    payload = {"name": field_def["name"], "type": field_def["type"]}
    if field_def["type"] == "dropdown" and field_def.get("options"):
        payload["type_config"] = {"options": [{"name": o} for o in field_def["options"]]}
    res = post_json(url, token, payload)
    print(f"• Created field '{field_def['name']}' ({res['id']})")
    return res

# ----------------------- Main orchestration -----------------------

def main():
    parser = argparse.ArgumentParser(description="ClickUp Scaffolding for Fido")
    parser.add_argument("--token", default=env("CLICKUP_API_TOKEN"))
    parser.add_argument("--team",  default=env("CLICKUP_TEAM_ID"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--discover-team", action="store_true")
    parser.add_argument("--space-name", default=SPACE_NAME)
    args = parser.parse_args()

    if args.discover_team:
        tok = args.token
        if not tok:
            print("Set CLICKUP_API_TOKEN first.")
            sys.exit(1)
        teams = discover_teams(tok)
        print(json.dumps(teams, indent=2))
        print("\nTip: choose the 'id' for the workspace you want and set CLICKUP_TEAM_ID.")
        sys.exit(0)

    token = args.token
    team_id = args.team
    dry = args.dry_run

    if not token:
        print("❌ Missing CLICKUP_API_TOKEN (env or --token).")
        sys.exit(1)
    if not team_id:
        print("❌ Missing CLICKUP_TEAM_ID (env or --team).")
        sys.exit(1)

    print("\nClickUp Fido Ticketing System Setup")
    print("===================================")
    print(f"Team ID: {team_id}")
    print(f"Dry run: {dry}")

    # Space
    space = find_or_create_space(team_id, token, args.space_name, dry)
    space_id = space["id"]

    # Folder
    folder = find_or_create_folder(space_id, token, FOLDER_NAME, dry)
    folder_id = folder["id"]

    # Lists
    list_ids: Dict[str, str] = {}
    for key, name in LISTS.items():
        l = find_or_create_list(folder_id, token, name, dry)
        list_ids[key] = l["id"]

    # Fields per list (idempotent)
    fields_cfg = {"lists": {}, "fields": {}, "options": {}}
    fields_cfg["lists"] = {
        "issues": list_ids["issues"],
        "inquiries": list_ids["inquiries"],
        "units": list_ids["units"]
    }

    # We'll collect field IDs by canonical names -> IDs
    field_name_map: Dict[str, str] = {}
    option_map: Dict[str, Dict[str, str]] = {"market_code": {}, "priority": {}, "issue_type": {},
                                             "inquiry_type": {}, "change_type": {}, "recycling": {}}

    for key in ["issues", "inquiries", "units"]:
        print_step(f"Custom fields for list: {LISTS[key]}")
        lid = list_ids[key]
        existing = get_list_fields(lid, token) if not dry else []

        for fdef in LIST_TO_FIELDS[key]:
            already = find_field_by_name(existing, fdef["name"]) if not dry else None
            if already:
                print(f"• Reusing field '{fdef['name']}' ({already['id']})")
                field = already
            else:
                field = create_custom_field(lid, token, fdef, dry)

            # Save field id under a stable key we use in app code
            normalized = (
                "slack_ticket_id" if fdef["name"] == "Slack Ticket ID" else
                "slack_permalink" if fdef["name"] == "Slack Permalink" else
                "submitted_by" if fdef["name"] == "Submitted By (Slack User)" else
                "customer_name" if fdef["name"] == "Customer Name" else
                "market_code" if fdef["name"] == "Market Code" else
                "property_unit" if fdef["name"] == "Property/Unit" else
                "notes" if fdef["name"] == "Notes" else
                "issue_type" if fdef["name"] == "Issue Type" else
                "priority" if fdef["name"] in ("Priority Level","Response Priority") else
                "inquiry_type" if fdef["name"] == "Inquiry Type" else
                "change_type" if fdef["name"] == "Change Type" else
                "trash_day" if fdef["name"] == "Trash Pickup Day" else
                "recycling" if fdef["name"] == "Recycling Day" else
                "effective_date" if fdef["name"] == "Effective Date" else
                fdef["name"]
            )
            fields_cfg["fields"][normalized] = field["id"]

            # Capture dropdown option IDs
            if fdef["type"] == "dropdown":
                opts = (field.get("type_config") or {}).get("options", [])
                # Build label -> option_id map
                m = {}
                for o in opts:
                    name = o.get("name") or o.get("label")
                    oid = o.get("id")
                    if name and oid:
                        m[name] = oid
                # Put into the right namespace if we know it
                if normalized in option_map:
                    option_map[normalized].update(m)

    # Trim only relevant option maps
    # Priority appears twice (issues/inquiries); merged above
    fields_cfg["options"] = {
        "market_code": option_map["market_code"],
        "issue_type": option_map["issue_type"],
        "inquiry_type": option_map["inquiry_type"],
        "priority": option_map["priority"],
        "change_type": option_map["change_type"],
        "recycling": option_map["recycling"],  # only used on Unit list
    }

    # Write outputs
    os.makedirs("config", exist_ok=True)
    cfg_path = "config/clickupFields.json"
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(fields_cfg, f, indent=2)
    print_step(f"Wrote {cfg_path}")

    # Optional: .env helper for list IDs
    env_lines = [
        f"CLICKUP_SPACE_ID={space_id}",
        f"CLICKUP_FOLDER_ID={folder_id}",
        f"CLICKUP_LIST_ID_ISSUES={list_ids['issues']}",
        f"CLICKUP_LIST_ID_INQUIRIES={list_ids['inquiries']}",
        f"CLICKUP_LIST_ID_UNITS={list_ids['units']}",
        "CLICKUP_TEAM_ID=" + str(team_id),
    ]
    with open("clickup-env-vars.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(env_lines) + "\n")
    print("• Wrote clickup-env-vars.txt")

    # Also dump a pretty combined file for humans
    with open("clickup-config.json", "w", encoding="utf-8") as f:
        json.dump({
            "space": {"id": space_id, "name": SPACE_NAME},
            "folder": {"id": folder_id, "name": FOLDER_NAME},
            "lists": {k: {"id": v, "name": LISTS[k]} for k, v in list_ids.items()},
            "fields": fields_cfg["fields"],
            "options": fields_cfg["options"]
        }, f, indent=2)
    print("• Wrote clickup-config.json")

    print("\n✅ Scaffolding complete (idempotent). You can safely re-run anytime.")

if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as e:
        print(f"\n❌ HTTPError: {e.response.status_code} {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
