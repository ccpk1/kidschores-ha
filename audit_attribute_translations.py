#!/usr/bin/env python3
"""
Comprehensive Entity Attribute Translation Audit Tool
Analyzes KidsChores integration for missing attribute translations
"""

import json
import re
from pathlib import Path


def load_const_attributes():
    """Load all ATTR_ constants from const.py"""
    const_path = Path("/workspaces/kidschores-ha/custom_components/kidschores/const.py")
    with open(const_path, "r") as f:
        content = f.read()

    # Extract ATTR_ constants with their values
    attr_pattern = r'ATTR_([A-Z_]+):\s*Final\s*=\s*"([^"]+)"'
    matches = re.findall(attr_pattern, content)

    return {const_name: attr_value for const_name, attr_value in matches}


def load_translations():
    """Load current translations from en.json"""
    trans_path = Path(
        "/workspaces/kidschores-ha/custom_components/kidschores/translations/en.json"
    )
    with open(trans_path, "r") as f:
        return json.load(f)


def analyze_sensor_attributes():
    """Analyze sensor.py for exposed attributes"""
    sensor_path = Path(
        "/workspaces/kidschores-ha/custom_components/kidschores/sensor.py"
    )
    with open(sensor_path, "r") as f:
        content = f.read()

    # Find all extra_state_attributes methods and extract attribute keys
    pattern = r"def extra_state_attributes.*?return\s*{(.*?)}"
    matches = re.findall(pattern, content, re.DOTALL)

    exposed_attrs = set()
    for match in matches:
        # Extract const.ATTR_ references
        attr_refs = re.findall(r"const\.ATTR_([A-Z_]+)", match)
        for attr_ref in attr_refs:
            exposed_attrs.add(attr_ref)

    return exposed_attrs


def find_missing_translations():
    """Find missing attribute translations"""
    # Load data
    const_attrs = load_const_attributes()
    translations = load_translations()
    exposed_attrs = analyze_sensor_attributes()

    # Get all state_attributes from entity translations
    entity_translations = translations.get("entity", {})
    all_translated_attrs = set()

    for platform_name, platform_entities in entity_translations.items():
        for entity_key, entity_data in platform_entities.items():
            state_attrs = entity_data.get("state_attributes", {})
            all_translated_attrs.update(state_attrs.keys())

    # Find missing translations
    missing_translations = {}

    for const_name in exposed_attrs:
        if const_name in const_attrs:
            attr_value = const_attrs[const_name]
            if attr_value not in all_translated_attrs:
                missing_translations[const_name] = attr_value

    return {
        "const_attributes": const_attrs,
        "exposed_attributes": exposed_attrs,
        "translated_attributes": all_translated_attrs,
        "missing_translations": missing_translations,
        "total_const_attrs": len(const_attrs),
        "total_exposed": len(exposed_attrs),
        "total_translated": len(all_translated_attrs),
        "total_missing": len(missing_translations),
    }


def main():
    """Main analysis function"""
    print("🔍 KidsChores Attribute Translation Audit")
    print("=" * 50)

    results = find_missing_translations()

    print(f"📊 Summary:")
    print(f"  • Total ATTR constants: {results['total_const_attrs']}")
    print(f"  • Exposed in sensors: {results['total_exposed']}")
    print(f"  • Currently translated: {results['total_translated']}")
    print(f"  • Missing translations: {results['total_missing']}")

    if results["missing_translations"]:
        print(f"\n❌ Missing Attribute Translations ({results['total_missing']}):")
        print("-" * 40)
        for const_name, attr_value in sorted(results["missing_translations"].items()):
            print(f"  • {const_name:30} → '{attr_value}'")

        print(f"\n🔧 Suggested Translation Entries:")
        print("-" * 40)
        for const_name, attr_value in sorted(results["missing_translations"].items()):
            friendly_name = attr_value.replace("_", " ").title()
            print(f'          "{attr_value}": {{')
            print(f'            "name": "{friendly_name}"')
            print(f"          }},")
    else:
        print(f"\n✅ All exposed attributes have translations!")

    print(f"\n📋 Exposed Attributes Not in Constants:")
    print("-" * 40)
    # Find attributes used directly without constants
    sensor_path = Path(
        "/workspaces/kidschores-ha/custom_components/kidschores/sensor.py"
    )
    with open(sensor_path, "r") as f:
        content = f.read()

    # Find direct string keys in return statements
    direct_attrs = re.findall(r'"([a-z_]+)":\s*[^{]', content)
    direct_attrs_set = set(direct_attrs)

    const_values = set(results["const_attributes"].values())
    direct_no_const = direct_attrs_set - const_values - {"true", "false"}

    if direct_no_const:
        for attr in sorted(direct_no_const):
            print(f"  • '{attr}' (used directly without ATTR constant)")
    else:
        print("  ✅ All attributes use proper ATTR constants")


if __name__ == "__main__":
    main()
