#!/usr/bin/env python3
"""
Maintenance-Eye — Synthetic Data Seeder
Populates Firestore (or emulator) with realistic transit maintenance data.

Generates:
- 80 Assets across 6 departments
- 60 EAM codes (problem, fault, action)
- 150 Work orders
- 40 Inspection records with findings
- 25 Knowledge base entries

Run:
    # With emulator running:
    FIRESTORE_EMULATOR_HOST=localhost:8081 python scripts/seed_data.py

    # Against cloud Firestore:
    python scripts/seed_data.py
"""

import os
import sys
import json
import random
import argparse
from datetime import datetime, timedelta

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# ============================================================================
# Configuration
# ============================================================================

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "maintenance-eye")
EMULATOR_HOST = os.getenv("FIRESTORE_EMULATOR_HOST", "localhost:8081")

# Firestore client is created lazily in main() — not needed for --dry-run
db = None

# ============================================================================
# Reference Data — Real SkyTrain-inspired station & department structure
# ============================================================================

STATIONS = [
    {"name": "Waterfront", "code": "WF", "zone": "Zone 1"},
    {"name": "Burrard", "code": "BU", "zone": "Zone 1"},
    {"name": "Granville", "code": "GV", "zone": "Zone 1"},
    {"name": "Stadium-Chinatown", "code": "SC", "zone": "Zone 1"},
    {"name": "Main Street-Science World", "code": "MS", "zone": "Zone 1"},
    {"name": "Commercial-Broadway", "code": "CB", "zone": "Zone 1"},
    {"name": "Metrotown", "code": "MT", "zone": "Zone 2"},
    {"name": "Joyce-Collingwood", "code": "JC", "zone": "Zone 2"},
    {"name": "Patterson", "code": "PA", "zone": "Zone 2"},
    {"name": "Royal Oak", "code": "RO", "zone": "Zone 2"},
    {"name": "Edmonds", "code": "ED", "zone": "Zone 2"},
    {"name": "New Westminster", "code": "NW", "zone": "Zone 2"},
    {"name": "Columbia", "code": "CO", "zone": "Zone 2"},
    {"name": "Scott Road", "code": "SR", "zone": "Zone 3"},
    {"name": "Gateway", "code": "GW", "zone": "Zone 3"},
    {"name": "Surrey Central", "code": "SU", "zone": "Zone 3"},
    {"name": "King George", "code": "KG", "zone": "Zone 3"},
    {"name": "Lougheed Town Centre", "code": "LO", "zone": "Zone 2"},
    {"name": "Production Way-University", "code": "PW", "zone": "Zone 2"},
    {"name": "Lake City Way", "code": "LC", "zone": "Zone 2"},
]

DEPARTMENTS = {
    "elevating_devices": {
        "asset_types": ["escalator", "elevator"],
        "manufacturers": ["KONE", "Schindler", "Otis", "Thyssen"],
        "prefix": "ESC" if True else "ELV",  # replaced per-type below
    },
    "guideway": {
        "asset_types": ["switch_machine", "rail_section", "track_bed"],
        "manufacturers": ["Bombardier", "Alstom", "Siemens", "Voestalpine"],
        "prefix": "GW",
    },
    "rolling_stock": {
        "asset_types": ["train_car", "bogie", "door_system", "hvac_unit"],
        "manufacturers": ["Bombardier", "Hyundai Rotem", "CAF"],
        "prefix": "RS",
    },
    "power": {
        "asset_types": ["transformer", "rectifier", "power_cable", "third_rail"],
        "manufacturers": ["ABB", "Siemens", "Schneider Electric", "Eaton"],
        "prefix": "PW",
    },
    "signal_telecom": {
        "asset_types": ["signal_controller", "track_circuit", "radio_unit", "cctv_camera"],
        "manufacturers": ["Thales", "Siemens", "Alstom", "Motorola"],
        "prefix": "ST",
    },
    "facilities": {
        "asset_types": ["hvac_station", "lighting_panel", "fire_suppression", "platform_door"],
        "manufacturers": ["Carrier", "Trane", "Honeywell", "Johnson Controls"],
        "prefix": "FA",
    },
}

INSPECTORS = [
    "J. Chen", "M. Singh", "R. Patel", "K. Williams",
    "A. Thompson", "D. Lee", "S. Martinez", "T. Brown",
]

CONDITIONS = ["good", "requires_attention", "requires_immediate_action", "out_of_service"]


# ============================================================================
# EAM Codes — Realistic Problem / Fault / Action Codes
# ============================================================================

def generate_eam_codes():
    """Generate 60 EAM classification codes."""
    codes = []

    # Problem codes (20)
    problem_codes = [
        ("ME-001", "Structural Damage", "Physical damage to structural components", ["escalator", "elevator", "platform_door"]),
        ("ME-002", "Corrosion", "Rust or corrosion on metal surfaces", ["escalator", "elevator", "rail_section", "third_rail"]),
        ("ME-003", "Surface Wear", "Normal wear on contact surfaces", ["escalator", "elevator", "switch_machine", "rail_section"]),
        ("ME-004", "Electrical Fault", "Electrical system malfunction", ["signal_controller", "transformer", "rectifier", "lighting_panel"]),
        ("ME-005", "Mechanical Failure", "Mechanical component breakdown", ["escalator", "elevator", "switch_machine", "door_system"]),
        ("ME-006", "Fluid Leak", "Hydraulic or lubricant leak", ["escalator", "elevator", "switch_machine"]),
        ("ME-007", "Alignment Issue", "Component misalignment", ["switch_machine", "rail_section", "track_bed", "escalator"]),
        ("ME-008", "Noise/Vibration", "Unusual noise or vibration", ["escalator", "elevator", "bogie", "door_system"]),
        ("ME-009", "Safety Hazard", "Identified safety concern", ["escalator", "elevator", "platform_door", "fire_suppression"]),
        ("ME-010", "Contamination", "Foreign material or contamination", ["switch_machine", "track_circuit", "signal_controller"]),
        ("ME-011", "Temperature Anomaly", "Abnormal temperature reading", ["transformer", "rectifier", "hvac_unit", "hvac_station"]),
        ("ME-012", "Signal Degradation", "Degraded signal quality", ["track_circuit", "radio_unit", "signal_controller"]),
        ("ME-013", "Water Ingress", "Water penetration into equipment", ["signal_controller", "lighting_panel", "power_cable"]),
        ("ME-014", "Insulation Failure", "Electrical insulation deterioration", ["power_cable", "transformer", "third_rail"]),
        ("ME-015", "Control System Error", "PLC or control system fault", ["escalator", "elevator", "signal_controller"]),
        ("ME-016", "Fastener Loosening", "Bolts, nuts, or fasteners loosening", ["rail_section", "track_bed", "escalator"]),
        ("ME-017", "Seal Deterioration", "Gaskets or seals degrading", ["door_system", "hvac_unit", "elevator"]),
        ("ME-018", "Lighting Failure", "Light fixture or LED failure", ["lighting_panel", "cctv_camera"]),
        ("ME-019", "Communication Failure", "Network or comm system fault", ["radio_unit", "cctv_camera", "signal_controller"]),
        ("ME-020", "Ventilation Issue", "Air flow or ventilation problem", ["hvac_unit", "hvac_station"]),
    ]

    for code, label, desc, types in problem_codes:
        dept = _infer_department(types[0])
        codes.append({
            "code_type": "problem_code",
            "code": code,
            "label": label,
            "department": dept,
            "asset_types": types,
            "description": desc,
            "related_codes": [],
            "hexagon_mapping": f"HX-P-{code.split('-')[1]}",
        })

    # Fault codes (20)
    fault_codes = [
        ("COR-GAL", "Galvanic Corrosion", "Electrochemical corrosion at dissimilar metal junction"),
        ("COR-ATM", "Atmospheric Corrosion", "Surface oxidation from environmental exposure"),
        ("COR-CRV", "Crevice Corrosion", "Corrosion in confined spaces and gaps"),
        ("WEAR-SUR", "Surface Wear", "Abrasive wear on contact surfaces"),
        ("WEAR-FAT", "Fatigue Wear", "Material fatigue from cyclic loading"),
        ("WEAR-ERO", "Erosion Wear", "Material loss from fluid or particle flow"),
        ("CRACK-STR", "Stress Crack", "Crack from mechanical stress concentration"),
        ("CRACK-FAT", "Fatigue Crack", "Propagating crack from cyclic stress"),
        ("CRACK-THR", "Thermal Crack", "Crack from thermal expansion/contraction"),
        ("ELEC-SHT", "Short Circuit", "Unintended electrical path"),
        ("ELEC-OPN", "Open Circuit", "Broken electrical connection"),
        ("ELEC-GND", "Ground Fault", "Unintended current path to ground"),
        ("MECH-BRK", "Broken Component", "Mechanical component fracture"),
        ("MECH-JAM", "Jammed Mechanism", "Mechanism seized or stuck"),
        ("MECH-MIS", "Misalignment", "Component out of specified alignment"),
        ("HYD-LK", "Hydraulic Leak", "Pressurized fluid leak"),
        ("HYD-CON", "Contaminated Fluid", "Hydraulic fluid contamination"),
        ("SEAL-DET", "Seal Deterioration", "Seal material degradation"),
        ("CTRL-PLC", "PLC Fault", "Logic controller malfunction"),
        ("CTRL-SNS", "Sensor Fault", "Sensor reading error or failure"),
    ]

    dept_cycle = list(DEPARTMENTS.keys())
    all_types = []
    for d in DEPARTMENTS.values():
        all_types.extend(d["asset_types"])

    for i, (code, label, desc) in enumerate(fault_codes):
        dept = dept_cycle[i % len(dept_cycle)]
        types = DEPARTMENTS[dept]["asset_types"][:2]
        codes.append({
            "code_type": "fault_code",
            "code": code,
            "label": label,
            "department": dept,
            "asset_types": types,
            "description": desc,
            "related_codes": [problem_codes[i % len(problem_codes)][0]],
            "hexagon_mapping": f"HX-F-{code}",
        })

    # Action codes (20)
    action_codes = [
        ("REPLACE", "Replace Component", "Remove and replace with new/refurbished part"),
        ("REPAIR", "Repair In-Place", "Fix component without full replacement"),
        ("LUBRICATE", "Lubricate", "Apply lubricant to moving parts"),
        ("CLEAN", "Clean/Decontaminate", "Remove contaminants and clean surfaces"),
        ("ADJUST", "Adjust/Calibrate", "Re-align or calibrate to specification"),
        ("INSPECT-DET", "Detailed Inspection", "Perform detailed follow-up inspection"),
        ("MONITOR", "Monitor/Observe", "Continue monitoring, no immediate action"),
        ("TIGHTEN", "Tighten Fasteners", "Re-torque bolts and fasteners to spec"),
        ("PAINT", "Surface Treatment", "Apply paint, coating, or surface protection"),
        ("SEAL", "Re-Seal", "Replace seals, gaskets, or apply sealant"),
        ("DRAIN", "Drain/Flush", "Drain and flush fluid system"),
        ("TEST", "Functional Test", "Perform operational test to verify function"),
        ("ISOLATE", "Isolate/LOTO", "Lock-out/tag-out for safety isolation"),
        ("REWIRE", "Rewire/Reconnect", "Replace or reconnect electrical wiring"),
        ("UPGRADE", "Upgrade Component", "Replace with upgraded version"),
        ("OVERHAUL", "Major Overhaul", "Complete disassembly, inspection, and rebuild"),
        ("WELD", "Weld Repair", "Structural welding repair"),
        ("GRIND", "Grinding/Profiling", "Surface grinding or rail profiling"),
        ("BALANCE", "Dynamic Balance", "Balance rotating components"),
        ("RESET", "System Reset", "Reset control system parameters"),
    ]

    for i, (code, label, desc) in enumerate(action_codes):
        dept = dept_cycle[i % len(dept_cycle)]
        types = DEPARTMENTS[dept]["asset_types"]
        codes.append({
            "code_type": "action_code",
            "code": code,
            "label": label,
            "department": dept,
            "asset_types": types,
            "description": desc,
            "related_codes": [],
            "hexagon_mapping": f"HX-A-{code}",
        })

    return codes


# ============================================================================
# Assets — 80 realistic transit assets
# ============================================================================

def generate_assets():
    """Generate 80 assets across all departments."""
    assets = []
    asset_counter = 0

    for dept_name, dept_info in DEPARTMENTS.items():
        for asset_type in dept_info["asset_types"]:
            # 3 assets per type (some types get 4)
            count = 4 if asset_type in ("escalator", "elevator", "switch_machine") else 3
            for i in range(count):
                station = random.choice(STATIONS)
                prefix = _get_prefix(dept_name, asset_type)
                asset_id = f"{prefix}-{station['code']}-{i+1:03d}"
                asset_counter += 1

                install_year = random.randint(2002, 2022)
                last_insp = (datetime.utcnow() - timedelta(days=random.randint(5, 180))).strftime("%Y-%m-%d")

                status = random.choices(
                    ["operational", "degraded", "out_of_service"],
                    weights=[0.75, 0.20, 0.05],
                )[0]

                manufacturer = random.choice(dept_info["manufacturers"])
                model_suffix = random.choice(["X200", "Pro", "Mark IV", "S-Type", "2000", "Elite", "V3"])

                assets.append({
                    "asset_id": asset_id,
                    "name": f"{station['name']} {asset_type.replace('_', ' ').title()} #{i+1}",
                    "type": asset_type,
                    "department": dept_name,
                    "location": {
                        "station": station["name"],
                        "station_code": station["code"],
                        "zone": station["zone"],
                        "gps": {
                            "lat": round(49.18 + random.uniform(0, 0.15), 6),
                            "lng": round(-122.85 - random.uniform(0, 0.20), 6),
                        },
                    },
                    "equipment_code": f"EQ-{dept_name[:3].upper()}-{asset_counter:04d}",
                    "manufacturer": manufacturer,
                    "model": f"{manufacturer} {model_suffix}",
                    "install_date": f"{install_year}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
                    "asset_hierarchy": [
                        f"BCRTC-{station['zone'].replace(' ', '')}",
                        f"{station['name']}",
                        f"{dept_name.replace('_', ' ').title()}",
                        f"{asset_type.replace('_', ' ').title()} #{i+1}",
                    ],
                    "last_inspection": last_insp,
                    "status": status,
                })

    return assets


# ============================================================================
# Work Orders — 150 with realistic distribution
# ============================================================================

def generate_work_orders(assets, eam_codes):
    """Generate 150 work orders linked to assets."""
    problem_codes = [c for c in eam_codes if c["code_type"] == "problem_code"]
    fault_codes = [c for c in eam_codes if c["code_type"] == "fault_code"]
    action_codes = [c for c in eam_codes if c["code_type"] == "action_code"]

    work_orders = []
    for i in range(150):
        asset = random.choice(assets)
        priority = random.choices(
            ["P1", "P2", "P3", "P4", "P5"],
            weights=[0.05, 0.15, 0.35, 0.30, 0.15],
        )[0]
        status = random.choices(
            ["open", "in_progress", "completed", "on_hold", "cancelled"],
            weights=[0.25, 0.15, 0.45, 0.10, 0.05],
        )[0]

        # Pick codes compatible with asset type
        pc = _pick_code(problem_codes, asset["type"])
        fc = _pick_code(fault_codes, asset["type"])
        ac = _pick_code(action_codes, asset["type"])

        created = datetime.utcnow() - timedelta(days=random.randint(1, 365))
        inspector = random.choice(INSPECTORS)

        descriptions = [
            f"Found {fc['label'].lower()} on {asset['name']}",
            f"{pc['label']} detected during routine inspection",
            f"Technician reported {fc['label'].lower()} — action required",
            f"{asset['type'].replace('_', ' ').title()} showing signs of {pc['label'].lower()}",
        ]

        work_orders.append({
            "wo_id": f"WO-{created.strftime('%Y')}-{i+1:04d}",
            "asset_id": asset["asset_id"],
            "status": status,
            "priority": priority,
            "problem_code": pc["code"],
            "fault_code": fc["code"],
            "action_code": ac["code"],
            "failure_class": random.choice(["MECHANICAL", "ELECTRICAL", "STRUCTURAL", "ENVIRONMENTAL"]),
            "description": random.choice(descriptions),
            "created_by": random.choice(["maintenance-eye-agent", inspector]),
            "created_at": created.isoformat(),
            "assigned_to": inspector,
            "photos": [],
            "ai_confidence": round(random.uniform(0.65, 0.98), 2) if random.random() > 0.3 else 0.0,
            "technician_confirmed": status in ("completed", "in_progress"),
            "notes": [f"Created during inspection on {created.strftime('%Y-%m-%d')}"],
        })

    return work_orders


# ============================================================================
# Inspection Records — 40 with findings
# ============================================================================

def generate_inspections(assets, eam_codes):
    """Generate 40 inspection records with findings."""
    problem_codes = [c for c in eam_codes if c["code_type"] == "problem_code"]
    fault_codes = [c for c in eam_codes if c["code_type"] == "fault_code"]
    inspections = []

    # Pick 40 random assets to have inspections
    inspected_assets = random.sample(assets, min(40, len(assets)))

    for idx, asset in enumerate(inspected_assets):
        insp_date = datetime.utcnow() - timedelta(days=random.randint(1, 120))
        inspector = random.choice(INSPECTORS)

        # Generate 1-4 findings per inspection
        num_findings = random.randint(1, 4)
        findings = []
        for f_idx in range(num_findings):
            pc = _pick_code(problem_codes, asset["type"])
            fc = _pick_code(fault_codes, asset["type"])
            severity = random.choices(
                ["P1", "P2", "P3", "P4"],
                weights=[0.05, 0.20, 0.45, 0.30],
            )[0]

            finding_descriptions = [
                f"{fc['label']} observed at {random.choice(['base', 'top', 'left side', 'right side', 'center', 'handrail entry', 'drive unit'])}",
                f"Minor {pc['label'].lower()} — no immediate safety concern",
                f"Visible {fc['label'].lower()} requiring {random.choice(['monitoring', 'follow-up', 'repair'])}",
                f"{pc['label']} detected on {asset['type'].replace('_', ' ')} — confidence {random.randint(75, 98)}%",
            ]

            findings.append({
                "finding_id": f"F-{idx+1:03d}-{f_idx+1}",
                "description": random.choice(finding_descriptions),
                "severity": severity,
                "problem_code": pc["code"],
                "fault_code": fc["code"],
                "photo_url": None,
                "ai_confidence": round(random.uniform(0.70, 0.97), 2),
                "technician_confirmed": random.random() > 0.2,
            })

        condition = random.choices(
            CONDITIONS,
            weights=[0.40, 0.35, 0.20, 0.05],
        )[0]

        next_due = (insp_date + timedelta(days=random.choice([30, 60, 90, 180]))).strftime("%Y-%m-%d")

        inspections.append({
            "inspection_id": f"INSP-{insp_date.strftime('%Y%m%d')}-{idx+1:03d}",
            "asset_id": asset["asset_id"],
            "inspector": inspector,
            "date": insp_date.strftime("%Y-%m-%d"),
            "findings": findings,
            "overall_condition": condition,
            "next_inspection_due": next_due,
            "work_orders_created": [],
        })

    return inspections


# ============================================================================
# Knowledge Base — 25 maintenance procedure entries
# ============================================================================

def generate_knowledge_base():
    """Generate 25 knowledge base entries for maintenance procedures."""
    entries = [
        {
            "doc_id": "KB-001",
            "title": "Escalator Handrail Inspection Procedure",
            "asset_types": ["escalator"],
            "department": "elevating_devices",
            "content": "1. Visually inspect handrail surface for wear, cracks, or separation. 2. Check handrail tension at drive unit and return end. 3. Verify handrail speed matches step speed (±2%). 4. Inspect handrail entry guards for proper clearance (4-8mm). 5. Check for contamination or foreign objects in handrail guide. Normal wear depth: <2mm acceptable, 2-4mm monitor, >4mm replace.",
            "tags": ["escalator", "handrail", "inspection", "wear"],
            "source": "OEM Manual - KONE Escalator Maintenance Guide",
        },
        {
            "doc_id": "KB-002",
            "title": "Escalator Step Chain Lubrication Schedule",
            "asset_types": ["escalator"],
            "department": "elevating_devices",
            "content": "Step chain lubrication must be performed every 3 months. Use synthetic chain lubricant SAE 68. Apply to roller chain links while running at slow speed. Check chain tension: 25-30mm deflection at mid-span. Inspect chain for elongation >2% (requires replacement). Log lubrication date on asset maintenance tag.",
            "tags": ["escalator", "lubrication", "chain", "preventive"],
            "source": "BCRTC Maintenance Standard MP-ESC-003",
        },
        {
            "doc_id": "KB-003",
            "title": "Elevator Door System Troubleshooting",
            "asset_types": ["elevator"],
            "department": "elevating_devices",
            "content": "Common issues: 1. Door not closing fully - check door operator belt tension, inspect door rollers for wear, verify detector alignment. 2. Slow door operation - check power supply voltage, lubricate guide rails. 3. Door reversal - clean photo-eye sensors, check edge sensor pressure setting (60-80 N). 4. Excessive noise - replace rollers if flat spots visible, adjust guide clearance.",
            "tags": ["elevator", "door", "troubleshooting"],
            "source": "OEM Manual - Schindler Door System Guide",
        },
        {
            "doc_id": "KB-004",
            "title": "Switch Machine Alignment Verification",
            "asset_types": ["switch_machine"],
            "department": "guideway",
            "content": "1. Verify switch point gap: 0mm at tip (tight), max 4mm at heel. 2. Check throw distance: 115-120mm for standard gauge. 3. Inspect locking bar engagement: minimum 10mm engagement depth. 4. Test detection circuit: verify indication within 2 seconds. 5. Check switch machine motor current draw: normal 2-4A (>6A indicates obstruction). LOTO REQUIRED before hands-on inspection.",
            "tags": ["switch_machine", "alignment", "guideway", "loto"],
            "source": "BCRTC Maintenance Standard MP-GW-007",
        },
        {
            "doc_id": "KB-005",
            "title": "Rail Visual Inspection Guidelines",
            "asset_types": ["rail_section", "track_bed"],
            "department": "guideway",
            "content": "Inspect for: 1. Head wear - measure with profile gauge, max 8mm vertical wear. 2. Gauge face wear - check for lipping and shelling. 3. Surface defects - squats, head checks, corrugation. 4. Joint conditions - check fishplate bolts (torque 350-400 Nm). 5. Rail fastener condition - verify clips engagement. 6. Sleeper/tie condition - check for cracking, displacement. Record any defects on rail chart by kilometer marker.",
            "tags": ["rail", "inspection", "track", "visual"],
            "source": "Transport Canada Rail Safety Standards",
        },
        {
            "doc_id": "KB-006",
            "title": "Transformer Thermal Inspection Protocol",
            "asset_types": ["transformer"],
            "department": "power",
            "content": "Monthly thermal scan: 1. Use IR camera (minimum 320x240 resolution). 2. Scan all bushings, connections, and cooling equipment. 3. Temperature limits: bushing <85°C, winding hot spot <110°C. 4. Check oil level in sight glass. 5. Listen for abnormal hum (indicates core issue). 6. Record all readings in transformer log. Alert threshold: >20°C above baseline on any component.",
            "tags": ["transformer", "thermal", "inspection", "power"],
            "source": "IEEE C57.140 Transformer Inspection Guide",
        },
        {
            "doc_id": "KB-007",
            "title": "Signal Controller Cabinet Inspection",
            "asset_types": ["signal_controller"],
            "department": "signal_telecom",
            "content": "Quarterly inspection: 1. Check cabinet seal integrity - no water ingress. 2. Verify all LED indicators match expected state. 3. Check fan operation and filter cleanliness. 4. Inspect cable terminations for corrosion. 5. Record battery backup voltage (min 24V). 6. Run self-diagnostic test from maintenance panel. 7. Verify time sync with master clock (<50ms offset). Do NOT reset any safety relays without authorization.",
            "tags": ["signal", "controller", "cabinet", "inspection"],
            "source": "Thales Signal Maintenance Manual",
        },
        {
            "doc_id": "KB-008",
            "title": "CCTV Camera Maintenance Procedure",
            "asset_types": ["cctv_camera"],
            "department": "signal_telecom",
            "content": "Monthly: 1. Clean lens with microfiber cloth and lens cleaner. 2. Verify focus and zoom operation. 3. Check pan/tilt range against specification. 4. Verify recording quality at control center. 5. Check housing seal and drainage holes. 6. Verify IR illumination (night mode). 7. Test network connectivity and stream quality. Replace cameras showing >20% image degradation.",
            "tags": ["cctv", "camera", "maintenance", "video"],
            "source": "BCRTC Standard MP-ST-012",
        },
        {
            "doc_id": "KB-009",
            "title": "Station HVAC Filter Replacement Guide",
            "asset_types": ["hvac_station", "hvac_unit"],
            "department": "facilities",
            "content": "Bi-monthly replacement: 1. Isolate AHU power supply. 2. Remove access panels (document panel orientation). 3. Remove spent filters — note size and MERV rating. 4. Install new filters matching exact specifications. 5. Verify filter frame seating — no bypass gaps. 6. Reset filter differential pressure gauge. 7. Restore power and verify fan operation. Use MERV-13 minimum for station air handlers.",
            "tags": ["hvac", "filter", "replacement", "facilities"],
            "source": "ASHRAE Standard 62.1",
        },
        {
            "doc_id": "KB-010",
            "title": "Fire Suppression System Annual Test",
            "asset_types": ["fire_suppression"],
            "department": "facilities",
            "content": "Annual testing (certified personnel only): 1. Inspect all sprinkler heads for obstruction and corrosion. 2. Flow test: verify minimum 25 GPM at most remote head. 3. Check fire pump start on pressure drop. 4. Test manual pull stations. 5. Verify fire alarm panel communication with monitoring. 6. Inspect standpipe connections and caps. 7. Record all results in fire safety log. Non-conformances require immediate remediation.",
            "tags": ["fire", "suppression", "safety", "annual"],
            "source": "NFPA 25 Inspection Standard",
        },
        {
            "doc_id": "KB-011",
            "title": "Escalator Comb Plate Safety Inspection",
            "asset_types": ["escalator"],
            "department": "elevating_devices",
            "content": "Weekly visual check: 1. Verify all comb teeth are intact (no broken teeth). 2. Check comb-step clearance: 3-6mm at mesh point. 3. Inspect step demarcation lines visibility. 4. Test comb plate safety switch activation. 5. Check for debris accumulation in comb fingers. Any missing teeth or switch malfunction requires immediate out-of-service. NEVER bypass comb plate safety switch.",
            "tags": ["escalator", "comb plate", "safety", "weekly"],
            "source": "ASME A17.1 Safety Code",
        },
        {
            "doc_id": "KB-012",
            "title": "Track Circuit Testing Procedure",
            "asset_types": ["track_circuit"],
            "department": "signal_telecom",
            "content": "Monthly: 1. Measure track circuit voltage: receive end 1-5V AC. 2. Verify shunt sensitivity with calibrated test shunt (0.06 ohm). 3. Check rail insulation resistance (min 2 ohm/km dry). 4. Inspect bond wires for corrosion or breaks. 5. Test vital relay drop-away time (<1.5 seconds). 6. Record all measurements against baseline. Deviation >15% from baseline requires investigation.",
            "tags": ["track circuit", "signal", "testing", "monthly"],
            "source": "AREMA Signal Manual Ch.11",
        },
        {
            "doc_id": "KB-013",
            "title": "Rectifier Inspection and Maintenance",
            "asset_types": ["rectifier"],
            "department": "power",
            "content": "Quarterly: 1. Check rectifier output voltage: 750VDC ±5%. 2. Measure ripple voltage: <5% acceptable. 3. Thermal scan all diode stacks and bus bars. 4. Check cooling fan operation and filter cleanliness. 5. Inspect DC disconnect switch contacts. 6. Verify protective relay settings match coordination study. 7. Test ground fault detection circuit. Record ammeter readings for load trending.",
            "tags": ["rectifier", "power", "maintenance", "quarterly"],
            "source": "IEEE 1653 Traction Power Standard",
        },
        {
            "doc_id": "KB-014",
            "title": "Bogie Inspection — Rolling Stock",
            "asset_types": ["bogie"],
            "department": "rolling_stock",
            "content": "Every 80,000 km: 1. Inspect wheel profile with laser gauge. 2. Measure wheel diameter: replace at 660mm minimum. 3. Check axle box bearing temperature history. 4. Inspect primary and secondary suspension springs. 5. Check yaw damper for leaks. 6. Verify motor mount bolt torque (800 Nm). 7. Inspect gear unit oil level and condition. Mark wheels with location stamp after profiling.",
            "tags": ["bogie", "wheel", "rolling stock", "periodic"],
            "source": "Bombardier MK-II Maintenance Manual",
        },
        {
            "doc_id": "KB-015",
            "title": "Train Door System Daily Check",
            "asset_types": ["door_system"],
            "department": "rolling_stock",
            "content": "Daily pre-service: 1. Cycle all doors 3 times — verify smooth operation. 2. Check door closing force: 67-90 N at closing edge. 3. Verify sensitive edge operation — reversal within 25mm. 4. Check door-closed indicator on operator console. 5. Inspect rubber seals for tears or gaps. 6. Verify emergency release handle accessibility. Report any door >5 seconds to close.",
            "tags": ["door", "train", "daily", "check"],
            "source": "BCRTC Pre-Service Checklist RS-001",
        },
        {
            "doc_id": "KB-016",
            "title": "Third Rail Inspection Standards",
            "asset_types": ["third_rail"],
            "department": "power",
            "content": "Monthly visual: 1. Check collector shoe wear indicators. 2. Inspect cover boards for damage or displacement. 3. Verify ramp clearances at gaps. 4. Check expansion joints for proper gap (10-15mm). 5. Inspect insulator condition — no cracks or flashover marks. DANGER: 750VDC — LOTO mandatory. Minimum approach distance: 1 meter without LOTO.",
            "tags": ["third rail", "power", "safety", "loto"],
            "source": "BCRTC Power Standard MP-PW-004",
        },
        {
            "doc_id": "KB-017",
            "title": "Platform Screen Door Maintenance",
            "asset_types": ["platform_door"],
            "department": "facilities",
            "content": "Weekly: 1. Test door open/close cycle aligned with train doors. 2. Verify obstruction detection — door must reopen within 2 seconds. 3. Check door motor current draw: normal 1.5-3A. 4. Inspect rubber seals and guide tracks. 5. Clean optical sensors with dry cloth. 6. Test emergency release from both platform and track sides. 7. Verify interlock with train detection system.",
            "tags": ["platform door", "weekly", "safety", "interlock"],
            "source": "OEM Manual - Faiveley PSD System",
        },
        {
            "doc_id": "KB-018",
            "title": "Power Cable Thermographic Survey",
            "asset_types": ["power_cable"],
            "department": "power",
            "content": "Annual survey: 1. Use calibrated IR camera (accuracy ±2°C). 2. Scan all terminations and splices under load. 3. Temperature classifications: <10°C rise = normal, 10-35°C = investigate, >35°C = urgent. 4. Document photos with temperature overlay. 5. Check cable tray support integrity. 6. Verify cable markings and labeling. Emergency limit: any termination >90°C absolute.",
            "tags": ["power cable", "thermal", "infrared", "annual"],
            "source": "NETA ATS-2021 Testing Standard",
        },
        {
            "doc_id": "KB-019",
            "title": "Corrosion Assessment and Classification",
            "asset_types": ["escalator", "elevator", "rail_section", "third_rail"],
            "department": "elevating_devices",
            "content": "Classification scale: Grade 1 (Surface rust): Light surface oxidation, easily removed. No structural effect. Action: Clean and apply rust inhibitor. Grade 2 (Moderate): Measurable metal loss <1mm. Pitting present. Action: Wire brush, measure depth, apply protective coating. Grade 3 (Severe): Metal loss >1mm, structural compromise possible. Action: Engineering assessment required, may need replacement. Grade 4 (Critical): Perforation or section loss >25%. Action: Immediate out-of-service, replace component.",
            "tags": ["corrosion", "assessment", "classification", "structural"],
            "source": "BCRTC Engineering Standard ES-003",
        },
        {
            "doc_id": "KB-020",
            "title": "Radio Communication System Checks",
            "asset_types": ["radio_unit"],
            "department": "signal_telecom",
            "content": "Monthly: 1. Verify signal strength at all test points (min -85 dBm). 2. Check antenna VSWR: <1.5:1 acceptable. 3. Test emergency call functionality. 4. Verify talkgroup assignments match configuration. 5. Check base station power output matches license. 6. Inspect antenna cable connectors for moisture. 7. Test handoff between coverage zones. Document coverage gaps for engineering review.",
            "tags": ["radio", "communication", "testing", "monthly"],
            "source": "Motorola TETRA Maintenance Manual",
        },
        {
            "doc_id": "KB-021",
            "title": "Lighting Panel Emergency Circuit Test",
            "asset_types": ["lighting_panel"],
            "department": "facilities",
            "content": "Monthly: 1. Simulate power failure to test emergency lighting transfer. 2. Verify battery backup provides minimum 90 minutes illumination. 3. Check emergency exit sign visibility from 30 meters. 4. Test photometric levels: min 10 lux on escape routes. 5. Inspect battery condition and electrolyte level. 6. Verify automatic recharge after test. 7. Record test results in station safety log for fire code compliance.",
            "tags": ["lighting", "emergency", "safety", "monthly"],
            "source": "BC Building Code Part 3",
        },
        {
            "doc_id": "KB-022",
            "title": "Galvanic Corrosion Prevention Guide",
            "asset_types": ["escalator", "elevator", "rail_section"],
            "department": "elevating_devices",
            "content": "Prevention: 1. Avoid direct contact between dissimilar metals (e.g., copper-steel, aluminum-steel). 2. Use isolating gaskets or bushings at joints. 3. Apply dielectric compound at connections. 4. Use sacrificial anodes in high-moisture areas. Identification: Look for white/green deposits at metal interfaces. Steel turns orange-brown, aluminum shows white powder. More active metal (anode) corrodes preferentially.",
            "tags": ["galvanic", "corrosion", "prevention", "dissimilar metals"],
            "source": "BCRTC Materials Engineering Guide",
        },
        {
            "doc_id": "KB-023",
            "title": "LOTO Procedures for Escalator Maintenance",
            "asset_types": ["escalator"],
            "department": "elevating_devices",
            "content": "Mandatory LOTO steps: 1. Notify control center of planned work. 2. Apply key switch to OFF position. 3. Apply lock on main disconnect (red lock = maintenance). 4. Apply personal lock and tag (one per worker). 5. Try-start to verify isolation. 6. Test emergency stop button — must NOT re-energize. 7. Post barrier tape and 'Equipment Under Maintenance' sign. Release: Reverse order. Verify all personnel clear before re-energizing. NEVER work on energized escalator.",
            "tags": ["loto", "lockout", "tagout", "safety", "escalator"],
            "source": "WorkSafeBC OHS Regulation Part 10",
        },
        {
            "doc_id": "KB-024",
            "title": "Elevator Hydraulic System Inspection",
            "asset_types": ["elevator"],
            "department": "elevating_devices",
            "content": "Quarterly: 1. Check hydraulic oil level in reservoir. 2. Inspect cylinder and piping for leaks. 3. Check oil temperature: operating range 30-55°C. 4. Sample oil for contamination analysis (annual lab test). 5. Inspect hydraulic hoses for bulging or cracking. 6. Check pressure relief valve setting. 7. Verify lowering valve operation. 8. Test manual lowering valve for emergency descent. Replace hoses every 5 years regardless of condition.",
            "tags": ["elevator", "hydraulic", "oil", "quarterly"],
            "source": "CSA B44 Elevator Safety Code",
        },
        {
            "doc_id": "KB-025",
            "title": "Train HVAC System Maintenance",
            "asset_types": ["hvac_unit"],
            "department": "rolling_stock",
            "content": "Monthly: 1. Clean condenser and evaporator coils with approved solvent. 2. Check refrigerant charge and pressure readings. 3. Inspect blower motor belt tension and condition. 4. Clean or replace return air filters. 5. Check condensate drain for blockage. 6. Verify thermostat operation: ±2°C of setpoint. 7. Test heating elements for continuity. Seasonal: Changeover from cooling to heating mode. Document all refrigerant handling per Environmental Canada requirements.",
            "tags": ["hvac", "train", "climate", "monthly"],
            "source": "Bombardier Climate System Manual",
        },
    ]

    return entries


# ============================================================================
# Helper Functions
# ============================================================================

def _get_prefix(dept, asset_type):
    """Get asset ID prefix based on department and type."""
    prefixes = {
        "escalator": "ESC",
        "elevator": "ELV",
        "switch_machine": "SWM",
        "rail_section": "RAL",
        "track_bed": "TRK",
        "train_car": "TC",
        "bogie": "BOG",
        "door_system": "DOR",
        "hvac_unit": "HVT",
        "transformer": "TRF",
        "rectifier": "RCT",
        "power_cable": "PCB",
        "third_rail": "3RD",
        "signal_controller": "SIG",
        "track_circuit": "TRC",
        "radio_unit": "RAD",
        "cctv_camera": "CAM",
        "hvac_station": "HVS",
        "lighting_panel": "LIT",
        "fire_suppression": "FIR",
        "platform_door": "PSD",
    }
    return prefixes.get(asset_type, DEPARTMENTS[dept]["prefix"])


def _infer_department(asset_type):
    """Infer department from asset type."""
    for dept, info in DEPARTMENTS.items():
        if asset_type in info["asset_types"]:
            return dept
    return "facilities"


def _pick_code(codes, asset_type):
    """Pick a code compatible with the given asset type, or fall back to any."""
    compatible = [c for c in codes if asset_type in c["asset_types"]]
    if compatible:
        return random.choice(compatible)
    return random.choice(codes)


# ============================================================================
# Seed Firestore
# ============================================================================

def seed_collection(collection_name, documents, id_field):
    """Write documents to Firestore collection using batch operations."""
    global db
    print(f"  📝 Seeding {collection_name}: {len(documents)} documents...", end=" ", flush=True)

    # Firestore batch limit is 500
    batch_size = 450
    for start in range(0, len(documents), batch_size):
        chunk = documents[start : start + batch_size]
        batch = db.batch()
        for doc in chunk:
            doc_id = doc[id_field]
            ref = db.collection(collection_name).document(doc_id)
            batch.set(ref, doc)
        batch.commit()

    print(f"✅")


def main():
    parser = argparse.ArgumentParser(description="Seed Firestore with synthetic maintenance data")
    parser.add_argument("--dry-run", action="store_true",
                        help="Generate and validate data without writing to Firestore")
    parser.add_argument("--export-json", type=str, default="",
                        help="Export generated data to a JSON file")
    args = parser.parse_args()

    print("=" * 60)
    print("🔧 Maintenance-Eye — Synthetic Data Seeder")
    print("=" * 60)

    if args.dry_run:
        print("🧪 DRY RUN MODE — no Firestore connection needed")
    else:
        emulator = os.getenv("FIRESTORE_EMULATOR_HOST")
        if emulator:
            print(f"📡 Using Firestore emulator at: {emulator}")
        else:
            print(f"☁️  Using Cloud Firestore (project: {PROJECT_ID})")
    print()

    # Generate data
    print("🏭 Generating synthetic data...")
    eam_codes = generate_eam_codes()
    print(f"  ✅ {len(eam_codes)} EAM codes (problem/fault/action)")

    assets = generate_assets()
    print(f"  ✅ {len(assets)} assets across {len(DEPARTMENTS)} departments")

    work_orders = generate_work_orders(assets, eam_codes)
    print(f"  ✅ {len(work_orders)} work orders")

    inspections = generate_inspections(assets, eam_codes)
    print(f"  ✅ {len(inspections)} inspection records")

    knowledge = generate_knowledge_base()
    print(f"  ✅ {len(knowledge)} knowledge base entries")

    total = len(eam_codes) + len(assets) + len(work_orders) + len(inspections) + len(knowledge)

    # Validate data integrity
    print()
    print("🔍 Validating data integrity...")
    errors = 0

    # Check asset IDs are unique
    asset_ids = [a["asset_id"] for a in assets]
    if len(asset_ids) != len(set(asset_ids)):
        print("  ❌ Duplicate asset IDs found!")
        errors += 1
    else:
        print(f"  ✅ All {len(asset_ids)} asset IDs are unique")

    # Check WO IDs are unique
    wo_ids = [w["wo_id"] for w in work_orders]
    if len(wo_ids) != len(set(wo_ids)):
        print("  ❌ Duplicate work order IDs found!")
        errors += 1
    else:
        print(f"  ✅ All {len(wo_ids)} work order IDs are unique")

    # Check all WOs reference valid assets
    asset_id_set = set(asset_ids)
    invalid_wo_refs = [w for w in work_orders if w["asset_id"] not in asset_id_set]
    if invalid_wo_refs:
        print(f"  ❌ {len(invalid_wo_refs)} work orders reference non-existent assets!")
        errors += 1
    else:
        print(f"  ✅ All work orders reference valid assets")

    # Check all inspections reference valid assets
    invalid_insp_refs = [i for i in inspections if i["asset_id"] not in asset_id_set]
    if invalid_insp_refs:
        print(f"  ❌ {len(invalid_insp_refs)} inspections reference non-existent assets!")
        errors += 1
    else:
        print(f"  ✅ All inspections reference valid assets")

    # Check departments coverage
    dept_counts = {}
    for a in assets:
        dept_counts[a["department"]] = dept_counts.get(a["department"], 0) + 1
    print(f"  ✅ Department distribution: {dept_counts}")

    # Check EAM code type distribution
    code_type_counts = {}
    for c in eam_codes:
        code_type_counts[c["code_type"]] = code_type_counts.get(c["code_type"], 0) + 1
    print(f"  ✅ EAM code distribution: {code_type_counts}")

    # Print sample data
    print()
    print("📋 Sample data preview:")
    sample_asset = assets[0]
    print(f"  Asset: {sample_asset['asset_id']} — {sample_asset['name']}")
    print(f"         Dept: {sample_asset['department']}, Station: {sample_asset['location']['station']}")
    sample_wo = work_orders[0]
    print(f"  WO:    {sample_wo['wo_id']} — {sample_wo['description'][:60]}...")
    sample_kb = knowledge[0]
    print(f"  KB:    {sample_kb['doc_id']} — {sample_kb['title']}")

    if errors > 0:
        print(f"\n❌ {errors} validation error(s) found!")
        sys.exit(1)

    # Export to JSON if requested
    if args.export_json:
        export_path = args.export_json
        all_data = {
            "eam_codes": eam_codes,
            "assets": assets,
            "work_orders": work_orders,
            "inspections": inspections,
            "knowledge_base": knowledge,
        }
        with open(export_path, "w") as f:
            json.dump(all_data, f, indent=2, default=str)
        print(f"\n📁 Exported all data to: {export_path}")

    # Seed Firestore if not dry-run
    if not args.dry_run:
        global db
        from google.cloud import firestore

        # Set emulator env var so the Firestore client auto-connects
        if EMULATOR_HOST:
            os.environ["FIRESTORE_EMULATOR_HOST"] = EMULATOR_HOST

        db = firestore.Client(project=PROJECT_ID)

        print()
        print("💾 Writing to Firestore...")
        seed_collection("eam_codes", eam_codes, "code")
        seed_collection("assets", assets, "asset_id")
        seed_collection("work_orders", work_orders, "wo_id")
        seed_collection("inspections", inspections, "inspection_id")
        seed_collection("knowledge_base", knowledge, "doc_id")

        # Set WO counter
        db.collection("_counters").document("work_orders").set({"count": 150})
        print("  📝 Set work order counter to 150 ✅")

    print()
    print("=" * 60)
    print(f"✅ Done! {'Validated' if args.dry_run else 'Seeded'} {total} documents total.")
    if not args.dry_run:
        emulator = os.getenv("FIRESTORE_EMULATOR_HOST")
        if emulator:
            print(f"🖥️  View data at: http://localhost:4000/firestore")
    print("=" * 60)


if __name__ == "__main__":
    main()
