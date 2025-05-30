import xlwt
import datetime
from pymongo import MongoClient
import json
import re

dateNow = datetime.datetime.now()

def sanitize_sheet_name(name):
    # Excel sheet names must be <= 31 characters, no special characters like : \ / ? * [ ]
    name = re.sub(r'[\\/*?:[\]]', '', name)
    return name[:31]

def transform_json(original_json, fields_to_keep):
    try:
        return {field: original_json.get(field, "FIELD_NOT_FOUND") for field in fields_to_keep}
    except Exception as e:
        print(f"An error occurred while transforming the JSON: {e}")
        return {}
def transformDiffConfig(data):
    if isinstance(data, dict):
        transformed_node = {}
        if "config_line" in data:
            transformed_node["cl"] = data["config_line"]
        if "children" in data:            
            # The recursive call for the list handles all its elements
            transformed_children = transformDiffConfig(data["children"])
            if len(transformed_children) > 0:
                # Extend the current node's children with the transformed children
                transformed_node["ch"] = []
                transformed_node["ch"].extend(transformed_children)
        return transformed_node
    elif isinstance(data, list):
        transformed_list = []
        # Iterate through each item in the list
        for item in data:
            processed_item = transformDiffConfig(item)
            transformed_list.append(processed_item)
        return transformed_list
    else:
        print(f"Warning: Unexpected data type encountered: {type(data)} with value {data}")
        return data # Or {} if you want to discard it
    
def getBlockExecutions():
    username = "admin"
    password = "Chan5eAfter!n!t"
    cluster_address = "10.150.150.235:27017"
    database_name = "compliance_remediation_db"
    collection_name = "compliance_block_executions"
    connection_string = f"mongodb://{username}:{password}@{cluster_address}"

    try:
        client = MongoClient(connection_string)
        print("Connected to MongoDB successfully!")

        db = client[database_name]
        collection = db[collection_name]

        documents = list(collection.find())  # Fetch all documents
        fields_to_keep = ["deviceIdentifier", "blockName", "deviceConfigBlocks", "complianceStatus"]
        workbook = xlwt.Workbook()

        # === Sheet: Compliance Details ===
        detailsSheet = workbook.add_sheet("Compliance Details")
        headers = ["Device Identifier", "Block Name", "Compliance Status", "Block Config"]
        for col, header in enumerate(headers):
            detailsSheet.write(0, col, header)

        for row_index, doc in enumerate(documents, start=1):
            transformed = transform_json(doc, fields_to_keep)
            detailsSheet.write(row_index, 1, transformed["deviceIdentifier"])
            detailsSheet.write(row_index, 2, transformed["blockName"])
            detailsSheet.write(row_index, 3, transformed["complianceStatus"])
            if(len(transformed["deviceConfigBlocks"]) > 0):
                deviceConfigBlock=transformed["deviceConfigBlocks"][0]
                diffConfigs=(transformDiffConfig(deviceConfigBlock["diff_config"]))
                print(diffConfigs)
                detailsSheet.write(row_index, 4, json.dumps(diffConfigs))

        # === Non-compliant device grouping by rule ===
        rule_to_devices = {}
        for doc in documents:
            status = doc.get("complianceStatus", "").lower()
            if status != "compliant":
                rule = doc.get("blockName", "Unknown Rule")
                device = doc.get("deviceIdentifier", "Unknown Device")
                rule_to_devices.setdefault(rule, []).append(device)

        # Create one sheet per rule with list of devices
        for rule_name, devices in rule_to_devices.items():
            sheet_name = sanitize_sheet_name(rule_name)
            sheet = workbook.add_sheet(sheet_name)

            # Header
            sheet.write(0, 0, "Rule name")
            sheet.write(0, 1, "Device Identifier")

            for idx, device in enumerate(devices, start=1):
                sheet.write(idx, 1, device)

        # Save workbook
        filename = f"BPAReport_{dateNow.strftime('%Y%m%d_%H%M%S')}.xls"
        workbook.save(filename)
        print(f"Report saved as {filename}")

    except Exception as e:
        print("An error occurred:", e)
    finally:
        client.close()
        print("Connection to MongoDB closed.")

if __name__ == "__main__":
    getBlockExecutions()
