#{"complianceJob.complianceJobName":"Consultative hardening Job"}
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
    
def strDiffConfig(data, indent_level=0):
    output_lines = []
    indent_prefix = " " * (indent_level * 2) # 2 spaces per indent level
    if isinstance(data, dict):
        # If the input is a dictionary (representing a config node)
        if "config_line" in data:
            if len (data["children"]) ==0 and (data["severity"]) != "info":

                    output_lines.append(f"{indent_prefix}{data['config_line']}")
            elif len (data["children"]) > 0:
                output_lines.append(f"{indent_prefix}{data['config_line']}")
        # Recursively process the 'children' list if it exists and is a list
        if "children" in data and isinstance(data["children"], list):
            # Call recursively for children, increasing the indent level
            transformed_children_lines = strDiffConfig(data["children"], indent_level + 1)
            # Extend the current node's output with the transformed children lines
            output_lines.extend(transformed_children_lines)

    elif isinstance(data, list):
        # If the input is a list (representing a collection of config nodes)
        for item in data:
            processed_item_lines = strDiffConfig(item, indent_level)
            output_lines.extend(processed_item_lines)
    else:
        output_lines.append(f"{indent_prefix}Unexpected Data: {data}")

    return output_lines     
def getBlockExecutions(jobName):
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
        executionCollection=db["compliance_executions"]
        jobExecution=executionCollection.find_one({"complianceJob.complianceJobName":jobName})#.sort({"updatedAt":-1})
        print(jobExecution["_id"])
        documents = list(collection.find({"executionId":str (jobExecution["_id"])}))  # Fetch all documents
        fields_to_keep = ["deviceIdentifier", "blockName", "deviceConfigBlocks", "complianceStatus", "blockConfig"]

        workbook = xlwt.Workbook()

        # === Sheet: Compliance Details ===
        detailsSheet = workbook.add_sheet("Compliance Details")
        headers = ["","Device Identifier", "Block Name", "Compliance Status", "Block Config"]
        for col, header in enumerate(headers):
            detailsSheet.write(1, col, header)

        for row_index, doc in enumerate(documents, start=2):
            transformed = transform_json(doc, fields_to_keep)
            detailsSheet.write(row_index, 1, transformed["deviceIdentifier"])
            detailsSheet.write(row_index, 2, transformed["blockName"])
            detailsSheet.write(row_index, 3, transformed["complianceStatus"])
            if(len(transformed["deviceConfigBlocks"]) > 0):
                deviceConfigBlock=transformed["deviceConfigBlocks"][0]
                if (deviceConfigBlock["deviceConfig"]) == "" and deviceConfigBlock["complianceStatus"] !="info":
                    detailsSheet.write(row_index, 4, transformed["blockConfig"])
                else:
                    strdiffConfigs=strDiffConfig(deviceConfigBlock["diff_config"])
                    diffConfigs= "\015".join(strdiffConfigs)
                    #print(transformed["deviceIdentifier"],transformed["blockName"],transformed["complianceStatus"],strdiffConfigs)
                    detailsSheet.write(row_index, 4, diffConfigs)

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
            sheet.write(1, 0, "Rule name")
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
    userInput=input("Please Enter Job name:")
    getBlockExecutions(userInput)
