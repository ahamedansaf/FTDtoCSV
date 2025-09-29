# v2 interface nat route acl, single file with multiple sheets.
# required modules for v5: "python3 -m pip install pandas openpyxl"
# how to run : python3 ./script.py , this will look for config files 
# in the directory and you can select the config file from the drop down.


import os
import re
import csv
import pandas as pd

# ---------------------------
# Interface Parser
# ---------------------------
def parse_interfaces(config_lines):
    interfaces = []
    current = {}

    for line in config_lines:
        line = line.strip()

        if line.startswith("interface "):
            if current:
                interfaces.append(current)
            current = {"Interface": line.split()[1],
                       "Name": "",
                       "Security Level": "",
                       "IP Address": "",
                       "Subnet Mask": "",
                       "Standby IP": "",
                       "VLAN": ""}

        elif line.startswith("nameif"):
            current["Name"] = line.split()[1]

        elif line.startswith("security-level"):
            current["Security Level"] = line.split()[1]

        elif line.startswith("ip address"):
            parts = line.split()
            current["IP Address"] = parts[2]
            current["Subnet Mask"] = parts[3]
            if "standby" in line:
                current["Standby IP"] = parts[-1]

        elif line.startswith("vlan"):
            current["VLAN"] = line.split()[1]

        elif line == "!" and current:
            interfaces.append(current)
            current = {}

    if current:
        interfaces.append(current)

    return interfaces

# ---------------------------
# Route Parser
# ---------------------------
def parse_routes(config_lines):
    route_entries = []
    route_pattern = re.compile(r'^route (\S+) (\S+) (\S+) (\S+)(?: (\d+))?')

    for line in config_lines:
        match = route_pattern.match(line.strip())
        if match:
            route_entries.append({
                "interface": match.group(1),
                "destination": match.group(2),
                "netmask": match.group(3),
                "gateway": match.group(4),
                "metric": match.group(5) if match.group(5) else ""
            })
    return route_entries

# ---------------------------
# Object NAT Parser
# ---------------------------
def parse_object_nat(config_lines):
    nat_entries = []
    current_object = None

    for line in config_lines:
        line = line.strip()
        if line.startswith("object network"):
            current_object = line.split("object network")[1].strip()
        elif line.startswith("nat (") and current_object:
            match = re.match(r'nat \((\S+),(\S+)\) static (\S+)', line)
            if match:
                nat_entries.append({
                    "object_name": current_object,
                    "source_interface": match.group(1),
                    "destination_interface": match.group(2),
                    "nat_type": "static",
                    "translated_object": match.group(3),
                    "raw": line
                })
            current_object = None  # reset after use

    return nat_entries

# ---------------------------
# ACL Parser
# ---------------------------
def parse_acl_line(line):
    result = {
        "acl_name": "", "action": "", "protocol": "",
        "source_zone": "", "source_type": "", "source_value": "",
        "source_port": "", "destination_zone": "", "destination_type": "", "destination_value": "",
        "destination_port": "", "rule_id": "", "raw": line.strip()
    }

    tokens = line.strip().split()
    if not tokens or tokens[0] != "access-list":
        return None

    try:
        result["acl_name"] = tokens[1]
        result["action"] = tokens[3]
        result["protocol"] = tokens[4]

        idx = 5
        if tokens[idx] == "ifc":
            result["source_zone"] = tokens[idx + 1]
            idx += 2

        if tokens[idx] in ["object", "object-group", "host"]:
            result["source_type"] = tokens[idx]
            result["source_value"] = tokens[idx + 1]
            idx += 2
        else:
            result["source_type"] = "any"
            result["source_value"] = tokens[idx]
            idx += 1

        if idx < len(tokens) and tokens[idx] in ["eq", "range", "gt", "lt", "neq"]:
            if tokens[idx] == "range":
                result["source_port"] = f"{tokens[idx + 1]}-{tokens[idx + 2]}"
                idx += 3
            else:
                result["source_port"] = tokens[idx + 1]
                idx += 2

        if idx < len(tokens) and tokens[idx] == "ifc":
            result["destination_zone"] = tokens[idx + 1]
            idx += 2

        if idx < len(tokens) and tokens[idx] in ["object", "object-group", "host"]:
            result["destination_type"] = tokens[idx]
            result["destination_value"] = tokens[idx + 1]
            idx += 2
        elif idx < len(tokens):
            result["destination_type"] = "any"
            result["destination_value"] = tokens[idx]
            idx += 1

        if idx < len(tokens) and tokens[idx] in ["eq", "range", "gt", "lt", "neq"]:
            if tokens[idx] == "range":
                result["destination_port"] = f"{tokens[idx + 1]}-{tokens[idx + 2]}"
                idx += 3
            else:
                result["destination_port"] = tokens[idx + 1]
                idx += 2

        if "rule-id" in tokens:
            rule_idx = tokens.index("rule-id")
            result["rule_id"] = tokens[rule_idx + 1]

    except Exception as e:
        result["raw"] += f"  # Parse error: {e}"

    return result

def parse_acls(config_lines):
    parsed = []
    for line in config_lines:
        if line.startswith("access-list") and "advanced" in line:
            acl = parse_acl_line(line)
            if acl:
                parsed.append(acl)
    return parsed

# ---------------------------
# Loader
# ---------------------------
def load_config(file_path):
    with open(file_path, 'r') as f:
        return f.readlines()

# ---------------------------
# Main
# ---------------------------
def main():
    files = [f for f in os.listdir('.') if os.path.isfile(f)]
    print("Available files:")
    for i, f in enumerate(files, 1):
        print(f"{i}. {f}")

    choice = int(input("Select a file number to parse: "))
    config_path = files[choice - 1]

    print(f"\nParsing config from: {config_path}\n")
    config_lines = load_config(config_path)

    # Parse all components
    interfaces = parse_interfaces(config_lines)
    routes = parse_routes(config_lines)
    nat_rules = parse_object_nat(config_lines)
    acl_rules = parse_acls(config_lines)

    # Convert to DataFrames
    df_interfaces = pd.DataFrame(interfaces)
    df_routes = pd.DataFrame(routes)
    df_nat = pd.DataFrame(nat_rules)
    df_acls = pd.DataFrame(acl_rules)

    # Write to single Excel file with multiple sheets
    with pd.ExcelWriter("FTD_Parsed_Config.xlsx", engine="openpyxl") as writer:
        df_interfaces.to_excel(writer, sheet_name="Interfaces", index=False)
        df_routes.to_excel(writer, sheet_name="Routes", index=False)
        df_nat.to_excel(writer, sheet_name="NAT", index=False)
        df_acls.to_excel(writer, sheet_name="ACLs", index=False)

    print("✅ All parsed data saved to FTD_Parsed_Config.xlsx (multiple sheets)")

if __name__ == "__main__":
    main()


# # v1 interface nat route acl, seperate csv files.
# import os
# import re
# import csv

# # ---------------------------
# # Interface Parser
# # ---------------------------
# def parse_interfaces(config_lines):
#     interfaces = []
#     current = {}

#     for line in config_lines:
#         line = line.strip()

#         if line.startswith("interface "):
#             if current:
#                 interfaces.append(current)
#             current = {"Interface": line.split()[1],
#                        "Name": "",
#                        "Security Level": "",
#                        "IP Address": "",
#                        "Subnet Mask": "",
#                        "Standby IP": "",
#                        "VLAN": ""}

#         elif line.startswith("nameif"):
#             current["Name"] = line.split()[1]

#         elif line.startswith("security-level"):
#             current["Security Level"] = line.split()[1]

#         elif line.startswith("ip address"):
#             parts = line.split()
#             current["IP Address"] = parts[2]
#             current["Subnet Mask"] = parts[3]
#             if "standby" in line:
#                 current["Standby IP"] = parts[-1]

#         elif line.startswith("vlan"):
#             current["VLAN"] = line.split()[1]

#         elif line == "!" and current:
#             interfaces.append(current)
#             current = {}

#     if current:
#         interfaces.append(current)

#     return interfaces

# # ---------------------------
# # Route Parser
# # ---------------------------
# def parse_routes(config_lines):
#     route_entries = []
#     route_pattern = re.compile(r'^route (\S+) (\S+) (\S+) (\S+)(?: (\d+))?')

#     for line in config_lines:
#         match = route_pattern.match(line.strip())
#         if match:
#             route_entries.append({
#                 "interface": match.group(1),
#                 "destination": match.group(2),
#                 "netmask": match.group(3),
#                 "gateway": match.group(4),
#                 "metric": match.group(5) if match.group(5) else ""
#             })
#     return route_entries

# # ---------------------------
# # Object NAT Parser
# # ---------------------------
# def parse_object_nat(config_lines):
#     nat_entries = []
#     current_object = None

#     for line in config_lines:
#         line = line.strip()
#         if line.startswith("object network"):
#             current_object = line.split("object network")[1].strip()
#         elif line.startswith("nat (") and current_object:
#             match = re.match(r'nat \((\S+),(\S+)\) static (\S+)', line)
#             if match:
#                 nat_entries.append({
#                     "object_name": current_object,
#                     "source_interface": match.group(1),
#                     "destination_interface": match.group(2),
#                     "nat_type": "static",
#                     "translated_object": match.group(3),
#                     "raw": line
#                 })
#             current_object = None  # reset after use

#     return nat_entries

# # ---------------------------
# # ACL Parser
# # ---------------------------
# def parse_acl_line(line):
#     result = {
#         "acl_name": "", "action": "", "protocol": "",
#         "source_zone": "", "source_type": "", "source_value": "",
#         "source_port": "", "destination_zone": "", "destination_type": "", "destination_value": "",
#         "destination_port": "", "rule_id": "", "raw": line.strip()
#     }

#     tokens = line.strip().split()
#     if not tokens or tokens[0] != "access-list":
#         return None

#     try:
#         result["acl_name"] = tokens[1]
#         result["action"] = tokens[3]
#         result["protocol"] = tokens[4]

#         idx = 5
#         # Optional source zone
#         if tokens[idx] == "ifc":
#             result["source_zone"] = tokens[idx + 1]
#             idx += 2

#         # Source type and value
#         if tokens[idx] in ["object", "object-group", "host"]:
#             result["source_type"] = tokens[idx]
#             result["source_value"] = tokens[idx + 1]
#             idx += 2
#         else:
#             result["source_type"] = "any"
#             result["source_value"] = tokens[idx]
#             idx += 1

#         # Optional source port
#         if idx < len(tokens) and tokens[idx] in ["eq", "range", "gt", "lt", "neq"]:
#             if tokens[idx] == "range":
#                 result["source_port"] = f"{tokens[idx + 1]}-{tokens[idx + 2]}"
#                 idx += 3
#             else:
#                 result["source_port"] = tokens[idx + 1]
#                 idx += 2

#         # Optional destination zone
#         if idx < len(tokens) and tokens[idx] == "ifc":
#             result["destination_zone"] = tokens[idx + 1]
#             idx += 2

#         # Destination type and value
#         if idx < len(tokens) and tokens[idx] in ["object", "object-group", "host"]:
#             result["destination_type"] = tokens[idx]
#             result["destination_value"] = tokens[idx + 1]
#             idx += 2
#         elif idx < len(tokens):
#             result["destination_type"] = "any"
#             result["destination_value"] = tokens[idx]
#             idx += 1

#         # Optional destination port
#         if idx < len(tokens) and tokens[idx] in ["eq", "range", "gt", "lt", "neq"]:
#             if tokens[idx] == "range":
#                 result["destination_port"] = f"{tokens[idx + 1]}-{tokens[idx + 2]}"
#                 idx += 3
#             else:
#                 result["destination_port"] = tokens[idx + 1]
#                 idx += 2

#         # Optional rule-id
#         if "rule-id" in tokens:
#             rule_idx = tokens.index("rule-id")
#             result["rule_id"] = tokens[rule_idx + 1]

#     except Exception as e:
#         result["raw"] += f"  # Parse error: {e}"

#     return result

# def parse_acls(config_lines):
#     parsed = []
#     for line in config_lines:
#         if line.startswith("access-list") and "advanced" in line:
#             acl = parse_acl_line(line)
#             if acl:
#                 parsed.append(acl)
#     return parsed

# # ---------------------------
# # CSV Writer
# # ---------------------------
# def write_csv(filename, data, headers):
#     with open(filename, mode='w', newline='') as f:
#         writer = csv.DictWriter(f, fieldnames=headers)
#         writer.writeheader()
#         for row in data:
#             writer.writerow(row)

# # ---------------------------
# # Loader
# # ---------------------------
# def load_config(file_path):
#     with open(file_path, 'r') as f:
#         return f.readlines()

# # ---------------------------
# # Main
# # ---------------------------
# def main():
#     # List files in current folder
#     files = [f for f in os.listdir('.') if os.path.isfile(f)]
#     print("Available files:")
#     for i, f in enumerate(files, 1):
#         print(f"{i}. {f}")

#     # Ask user to select one
#     choice = int(input("Select a file number to parse: "))
#     config_path = files[choice - 1]

#     print(f"\nParsing config from: {config_path}\n")

#     config_lines = load_config(config_path)

#     # Interfaces
#     interfaces = parse_interfaces(config_lines)
#     interface_headers = ["Interface", "Name", "Security Level", "IP Address", "Subnet Mask", "Standby IP", "VLAN"]
#     write_csv("parsed_interfaces.csv", interfaces, interface_headers)

#     # Routes
#     routes = parse_routes(config_lines)
#     route_headers = ["interface", "destination", "netmask", "gateway", "metric"]
#     write_csv("parsed_routes.csv", routes, route_headers)

#     # NAT
#     nat_rules = parse_object_nat(config_lines)
#     nat_headers = ["object_name", "source_interface", "destination_interface", "nat_type", "translated_object", "raw"]
#     write_csv("parsed_object_nat.csv", nat_rules, nat_headers)

#     # ACLs
#     acl_rules = parse_acls(config_lines)
#     acl_headers = [
#         "acl_name", "action", "protocol",
#         "source_zone", "source_type", "source_value", "source_port",
#         "destination_zone", "destination_type", "destination_value", "destination_port",
#         "rule_id", "raw"
#     ]
#     write_csv("parsed_acls.csv", acl_rules, acl_headers)

#     print("✅ Interfaces saved to parsed_interfaces.csv")
#     print("✅ Routes saved to parsed_routes.csv")
#     print("✅ NAT rules saved to parsed_object_nat.csv")
#     print("✅ ACLs saved to parsed_acls.csv")

# if __name__ == "__main__":
#     main()
