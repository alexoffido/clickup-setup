#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fido Ticketing – ClickUp Scaffolding (final)
- Idempotent creation/reuse of Space → Folder → Lists
- Applies per-list statuses: Open → In Progress → Resolved → Closed
- Creates/reuses custom fields with existence checks
- Uses compatible field types (short_text for Slack Permalink)
- Collects dropdown OPTION IDs (label -> id) for Slack mapping
- Ensures Custom Fields ClickApp is enabled (fails fast if not)
- Dry run support (--dry-run or DRY_RUN=true)
- Exports:
    config/clickupFields.json        (full detail)
    config/clickupFields-adapted.json (lists/fields/options map for Slack)
    clickup-config.json               (human summary)
    clickup-env-vars.txt              (ENV lines)
"""

import os, sys, json, time, argparse
from typing import Dict, Any, List, Optional
import requests

API_TOKEN = os.getenv("CLICKUP_API_TOKEN")
TEAM_ID   = os.getenv("CLICKUP_TEAM_ID")
DRY_ENV   = os.getenv("DRY_RUN", "false").lower() == "true"

SPACE_NAME  = "Fido Operations"
FOLDER_NAME = "CX Tickets"
LISTS = {
    "issues":    "Service Issues",
    "inquiries": "Customer Inquiries",
    "units":     "Unit Management",
}

STATUS_WORKFLOW = [
    {"status": "Open",        "type": "open",   "color": "#6f6f6f"},
    {"status": "In Progress", "type": "custom", "color": "#1f75fe"},
    {"status": "Resolved",    "type": "custom", "color": "#2ecc71"},
    {"status": "Closed",      "type": "closed", "color": "#6b7280"},
]

MARKET_CODES = [
    "ATX","ANA","CHS","CLT","DEN","DFW","FLL","GEG","HOT","JAX","LAX","LIT",
    "PHX","PIE","SAN","SAT","SDX","SEA","SLC","SRQ","STA","STS","VPS","MISC"
]

COMMON_FIELDS = [
    {"name": "Slack Ticket ID",             "type": "short_text"},
    {"name": "Slack Permalink",             "type": "short_text"},  # URL can be plan-limited
    {"name": "Submitted By (Slack User)",   "type": "short_text"},
    {"name": "Customer Name",               "type": "short_text"},
    {"name": "Market Code",                 "type": "dropdown", "options": MARKET_CODES},
    {"name": "Property/Unit",               "type": "short_text"},
    {"name": "Notes",                       "type": "text"},
]

ISSUE_FIELDS = [
    {"name": "Issue Type",      "type": "dropdown", "options": [
        "bin_placement","access_problem","schedule_conflict","property_logistics",
        "service_quality","customer_complaint","equipment_issue","other"
    ]},
    {"name": "Priority Level",  "type": "dropdown", "options": ["urgent","high","normal","low"]},
]

INQUIRY_FIELDS = [
    {"name": "Inquiry Type",        "type": "dropdown", "options": [
        "schedule_question","service_status","billing_question","service_details",
        "new_service","pause_resume","property_update","general_info","other"
    ]},
    {"name": "Response Priority",   "type": "dropdown", "options": ["urgent","high","normal","low"]},
]

UNIT_FIELDS = [
    {"name": "Change Type",         "type": "dropdown", "options": ["new_unit","cancellation","pause","restart","modify"]},
    {"name": "Trash Pickup Day",    "type": "dropdown", "options": ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]},
    {"name": "Recycling Day",       "type": "dropdown", "options": ["same_as_trash","monday","tuesday","wednesday","thursday","friday","saturday","sunday","none"]},
    {"name": "Effective Date",      "type": "date"},
]

LIST_TO_FIELDS = {
    "issues":    COMMON_FIELDS + ISSUE_FIELDS,
    "inquiries": COMMON_FIELDS + INQUIRY_FIELDS,
    "units":     COMMON_FIELDS + UNIT_FIELDS,
}

# ------------- HTTP helpers -------------

def hdrs(token: str) -> Dict[str, str]:
    return {"Authorization": token, "Content-Type": "application/json"}

def _sleep(i=1): time.sleep(0.2 * i)

def get_json(url: str, token: str) -> Any:
    r = requests.get(url, headers=hdrs(token), timeout=30)
    _sleep()
    r.raise_for_status()
    return r.json()

def post_json(url: str, token: str, payload: Dict[str, Any]) -> Any:
    r = requests.post(url, headers=hdrs(token), data=json.dumps(payload), timeout=30)
    _sleep()
    if not (200 <= r.status_code < 300):
        raise requests.HTTPError(f"{r.status_code} {r.text}", response=r)
    return r.json() if r.text else {}

def put_json(url: str, token: str, payload: Dict[str, Any]) -> Any:
    r = requests.put(url, headers=hdrs(token), data=json.dumps(payload), timeout=30)
    _sleep()
    if not (200 <= r.status_code < 300):
        raise requests.HTTPError(f"{r.status_code} {r.text}", response=r)
    return r.json() if r.text else {}

def print_step(msg: str): print(f"\n=== {msg}")
def die(msg: str):
    print(f"\n❌ {msg}")
    sys.exit(1)

# ------------- Guards -------------

def ensure_env():
    if not API_TOKEN:
        die("Missing CLICKUP_API_TOKEN")
    if not TEAM_ID:
        die("Missing CLICKUP_TEAM_ID")
    if not API_TOKEN.startswith("pk_"):
        die("CLICKUP_API_TOKEN must start with 'pk_'")

def ensure_custom_fields_enabled(space_id: str, token: str, dry: bool):
    if dry:
        print("• DRY RUN: would verify Custom Fields ClickApp"); return
    data = get_json(f"https://api.clickup.com/api/v2/space/{space_id}", token)
    enabled = data.get("features", {}).get("custom_fields", {}).get("enabled", False)
    if not enabled:
        die("Custom Fields ClickApp is disabled for this Space. "
            "Enable in ClickUp → Space settings → ClickApps → Custom Fields.")

# ------------- Find/Create -------------

def find_or_create_space(team_id: str, token: str, name: str, dry: bool) -> Dict[str, str]:
    print_step(f"Space: lookup '{name}'")
    if dry:
        print(f"• DRY RUN: would create/reuse space '{name}'")
        return {"id": "DRY_SPACE_ID", "name": name}
    spaces = get_json(f"https://api.clickup.com/api/v2/team/{team_id}/space", token).get("spaces", [])
    for s in spaces:
        if s.get("name") == name:
            print(f"• Reusing space '{name}' ({s['id']})")
            return {"id": s["id"], "name": s["name"]}
    res = post_json(f"https://api.clickup.com/api/v2/team/{team_id}/space", token, {"name": name, "multiple_assignees": True})
    print(f"• Created space '{name}' ({res['id']})")
    return {"id": res["id"], "name": res["name"]}

def find_or_create_folder(space_id: str, token: str, name: str, dry: bool) -> Dict[str, str]:
    print_step(f"Folder: lookup '{name}'")
    if dry:
        print(f"• DRY RUN: would create/reuse folder '{name}'")
        return {"id": "DRY_FOLDER_ID", "name": name}
    folders = get_json(f"https://api.clickup.com/api/v2/space/{space_id}/folder", token).get("folders", [])
    for f in folders:
        if f.get("name") == name:
            print(f"• Reusing folder '{name}' ({f['id']})")
            return {"id": f["id"], "name": f["name"]}
    res = post_json(f"https://api.clickup.com/api/v2/space/{space_id}/folder", token, {"name": name})
    print(f"• Created folder '{name}' ({res['id']})")
    return {"id": res["id"], "name": res["name"]}

def find_or_create_list(folder_id: str, token: str, name: str, dry: bool) -> Dict[str, str]:
    print_step(f"List: lookup '{name}'")
    if dry:
        print(f"• DRY RUN: would create/reuse list '{name}'")
        return {"id": f"DRY_{name.upper().replace(' ','_')}", "name": name}
    lists = get_json(f"https://api.clickup.com/api/v2/folder/{folder_id}/list", token).get("lists", [])
    for l in lists:
        if l.get("name") == name:
            print(f"• Reusing list '{name}' ({l['id']})")
            return {"id": l["id"], "name": l["name"]}
    res = post_json(f"https://api.clickup.com/api/v2/folder/{folder_id}/list", token, {"name": name})
    print(f"• Created list '{name}' ({res['id']})")
    return {"id": res["id"], "name": res["name"]}

# ------------- Status workflow -------------

def apply_status_workflow(list_id: str, token: str, dry: bool):
    if dry:
        print(f"• DRY RUN: would set statuses on {list_id}: {[s['status'] for s in STATUS_WORKFLOW]}")
        return
    payload = {"override_statuses": True, "statuses": STATUS_WORKFLOW}
    put_json(f"https://api.clickup.com/api/v2/list/{list_id}", token, payload)
    print(f"• Applied statuses on list {list_id}")

# ------------- Field helpers -------------

def get_list_fields(list_id: str, token: str) -> List[Dict[str, Any]]:
    data = get_json(f"https://api.clickup.com/api/v2/list/{list_id}/field", token)
    return data.get("fields", [])

def find_existing_field(fields: List[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
    for f in fields:
        if f.get("name") == name:
            return f
    return None

def create_field_payload(field_def: Dict[str, Any]) -> Dict[str, Any]:
    payload = {"name": field_def["name"], "type": field_def["type"]}
    if field_def["type"] == "dropdown":
        opts = field_def.get("options", [])
        payload["type_config"] = {"options": [{"name": o} for o in opts]}
    return payload

def create_or_reuse_field(list_id: str, token: str, field_def: Dict[str, Any], dry: bool) -> Dict[str, Any]:
    """Returns API field object with id; raises if API returns no id on create."""
    if dry:
        dummy = {"id": f"DRY_CF_{field_def['name']}", "name": field_def["name"], "type": field_def["type"]}
        if field_def["type"] == "dropdown":
            dummy["type_config"] = {"options": [{"name": o, "id": f"DRY_OPT_{o}"} for o in field_def.get("options", [])]}
        print(f"• DRY RUN: would create/reuse field '{field_def['name']}'")
        return dummy

    existing = get_list_fields(list_id, token)
    found    = find_existing_field(existing, field_def["name"])
    if found:
        print(f"• Reusing field '{field_def['name']}' ({found['id']})")
        return found

    payload = create_field_payload(field_def)
    try:
        res = post_json(f"https://api.clickup.com/api/v2/list/{list_id}/field", token, payload)
    except requests.HTTPError as e:
        raise SystemExit(f"❌ Failed to create field '{field_def['name']}' on list {list_id}: {e.response.text}") from e

    fid = res.get("id")
    if not fid:
        raise SystemExit(
            "❌ ClickUp did not return an 'id' for field creation.\n"
            f"   Field: {field_def['name']} ({field_def['type']}) list={list_id}\n"
            f"   Response: {json.dumps(res, indent=2)}\n"
            "   Tip: Use 'short_text' instead of unsupported types."
        )
    print(f"• Created field '{field_def['name']}' ({fid})")
    return res

# ------------- Orchestration -------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    dry = DRY_ENV or args.dry_run

    ensure_env()

    print("\nFido ClickUp Scaffolding")
    print("========================")
    print(f"Team: {TEAM_ID} | Dry run: {dry}")

    # Space → Folder → Lists
    space  = find_or_create_space(TEAM_ID, API_TOKEN, SPACE_NAME, dry)
    ensure_custom_fields_enabled(space["id"], API_TOKEN, dry)
    folder = find_or_create_folder(space["id"], API_TOKEN, FOLDER_NAME, dry)

    list_ids: Dict[str, str] = {}
    for key, name in LISTS.items():
        l = find_or_create_list(folder["id"], API_TOKEN, name, dry)
        list_ids[key] = l["id"]
        apply_status_workflow(l["id"], API_TOKEN, dry)

    # Fields
    full_cfg   = {"lists": {k: {"id": list_ids[k], "name": LISTS[k]} for k in list_ids},
                  "fields": {}, "options": {}}
    adapted    = {"lists": {k: list_ids[k] for k in list_ids}, "fields": {}, "options": {}}

    # normalize map for Slack usage
    def norm(name: str) -> str:
        mapping = {
            "Slack Ticket ID": "slack_ticket_id",
            "Slack Permalink": "slack_permalink",
            "Submitted By (Slack User)": "submitted_by",
            "Customer Name": "customer_name",
            "Market Code": "market_code",
            "Property/Unit": "property_unit",
            "Notes": "notes",
            "Issue Type": "issue_type",
            "Priority Level": "priority",
            "Inquiry Type": "inquiry_type",
            "Response Priority": "response_priority",
            "Change Type": "change_type",
            "Trash Pickup Day": "trash_day",
            "Recycling Day": "recycling",
            "Effective Date": "effective_date",
        }
        return mapping.get(name, name)

    for key in ["issues", "inquiries", "units"]:
        fields_def = LIST_TO_FIELDS[key]
        lid        = list_ids[key]

        print_step(f"Custom fields for '{LISTS[key]}'")
        for fdef in fields_def:
            field_obj = create_or_reuse_field(lid, API_TOKEN, fdef, dry)

            fname = norm(fdef["name"])
            full_cfg["fields"].setdefault(key, {})[fname] = field_obj["id"]
            adapted["fields"].setdefault(key, {})[fname]  = field_obj["id"]

            # capture dropdown option IDs
            if fdef["type"] == "dropdown":
                opts = (field_obj.get("type_config") or {}).get("options", [])
                name_to_id = { (o.get("name") or o.get("label")): o.get("id") for o in opts if o.get("id") }
                full_cfg["options"].setdefault(key, {})[fname] = name_to_id
                adapted["options"].setdefault(key, {})[fname]  = name_to_id

    # Outputs
    os.makedirs("config", exist_ok=True)
    with open("config/clickupFields.json", "w", encoding="utf-8") as f:
        json.dump({
            "team_id": TEAM_ID,
            "space": {"id": space["id"], "name": SPACE_NAME},
            "folder": {"id": folder["id"], "name": FOLDER_NAME},
            **full_cfg
        }, f, indent=2)

    with open("config/clickupFields-adapted.json", "w", encoding="utf-8") as f:
        json.dump(adapted, f, indent=2)

    with open("clickup-config.json", "w", encoding="utf-8") as f:
        json.dump({
            "space": {"id": space["id"], "name": SPACE_NAME},
            "folder": {"id": folder["id"], "name": FOLDER_NAME},
            "lists": {k: {"id": list_ids[k], "name": LISTS[k]} for k in list_ids},
            "statuses": [s["status"] for s in STATUS_WORKFLOW]
        }, f, indent=2)

    with open("clickup-env-vars.txt", "w", encoding="utf-8") as f:
        f.write(f"CLICKUP_TEAM_ID={TEAM_ID}\n")
        f.write(f"CLICKUP_SPACE_ID={space['id']}\n")
        f.write(f"CLICKUP_FOLDER_ID={folder['id']}\n")
        f.write(f"CLICKUP_LIST_ID_ISSUES={list_ids['issues']}\n")
        f.write(f"CLICKUP_LIST_ID_INQUIRIES={list_ids['inquiries']}\n")
        f.write(f"CLICKUP_LIST_ID_UNITS={list_ids['units']}\n")

    print("\n✅ Scaffolding complete (idempotent). Safe to re-run anytime.")

if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as e:
        die(f"HTTPError: {e}")
    except SystemExit:
        raise
    except Exception as e:
        die(f"Error: {e}")
