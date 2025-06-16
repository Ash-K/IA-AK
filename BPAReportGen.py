#{"complianceJob.complianceJobName":"Consultative hardening Job"}
import xlwt
import datetime
from pymongo import MongoClient
import json
import re

dateNow = datetime.datetime.now()

def sanitizeSheetName(name):
    # Excel sheet names must be <= 31 characters, no special characters like : \ / ? * [ ]
    name = re.sub(r'[\\/*?:[\]]', '', name)
    return name[:31]

def transformJSON(originalJSON, fieldsToKeep):
    try:
        return {field: originalJSON.get(field, "FIELD_NOT_FOUND") for field in fieldsToKeep}
    except Exception as e:
        print(f"An error occurred while transforming the JSON: {e}")
        return {}

#Extract configuration
def strDiffConfig(data, indent_level=0):
    outputLines = []
    indentPrefix = " " * (indent_level * 2) # 2 spaces per indent level
    if isinstance(data, dict):
        # If the input is a dictionary (representing a config node)
        if "config_line" in data:
            if len (data["children"]) ==0 and (data["severity"]) != "info":
                    outputLines.append(f"{indentPrefix}{data['config_line']}")
            elif len (data["children"]) > 0:
                outputLines.append(f"{indentPrefix}{data['config_line']}")
        # Recursively process the 'children' list if it exists and is a list
        if "children" in data and isinstance(data["children"], list):
            # Call recursively for children, increasing the indent level
            transformed_children_lines = strDiffConfig(data["children"], indent_level + 1)
            # Extend the current node's output with the transformed children lines
            outputLines.extend(transformed_children_lines)

    elif isinstance(data, list):
        # If the input is a list (representing a collection of config nodes)
        for item in data:
            processed_item_lines = strDiffConfig(item, indent_level)
            outputLines.extend(processed_item_lines)
    else:
        outputLines.append(f"{indentPrefix}Unexpected Data: {data}")

    return outputLines  
# Variables required to Conenct to MongoDB   
def getBlockExecutions(jobName):
    username = "admin"
    password = "Chan5eAfter!n!t"
    cluster_address = "10.150.150.235:27017"
    database_name = "compliance_remediation_db"
    collection_name = "compliance_block_executions"
    connection_string = f"mongodb://{username}:{password}@{cluster_address}"

# Conencting to MondoDB 
    try:
        client = MongoClient(connection_string)
        print("Connected to MongoDB successfully!")
        db = client[database_name]
        collection = db[collection_name]
        executionCollection=db["compliance_executions"]
        jobExecution=executionCollection.find_one({"complianceJob.complianceJobName":jobName})#.sort({"updatedAt":-1})
        print(jobExecution["_id"])
        documents = list(collection.find({"executionId":str (jobExecution["_id"])}))  # Fetch all documents
        fieldsToKeep = ["deviceIdentifier", "blockName", "deviceConfigBlocks", "complianceStatus", "blockConfig"]
        
        workbook = xlwt.Workbook()

        # AK Modified Sheet: Compliance Summary 
        summarySheet = workbook.add_sheet("Compliance Summary")
        summaryHeaders = ["","Block Name","Number of devices in compliance", "Number of devices in Violation"]
        for summaryCol, summaryHeader in enumerate(summaryHeaders):
            summarySheet.write(1, summaryCol, summaryHeader)
        summaryMetrics={}
        for summaryRowIndex, summaryDoc in enumerate(documents, start=2):
            transformed = transformJSON(summaryDoc, fieldsToKeep)
            sheet_name = sanitizeSheetName(transformed["blockName"])
            if transformed["blockName"] in summaryMetrics:
                metricsObject= summaryMetrics [transformed["blockName"]]
                sheet=workbook.get_sheet(sheet_name)
            else: 
                summaryMetrics[transformed["blockName"]]={"complianceDevicesCount": 0,"nonComplianceDevicesCount": 0}
                metricsObject= summaryMetrics [transformed["blockName"]]
                
                sheet = workbook.add_sheet(sheet_name, cell_overwrite_ok=True)
                #print("Adding :", sheet_name)
                # Header
                sheet.write(1, 1, "Rule name")
                sheet.write(1, 2, "Severity")
                sheet.write(1, 3, "Device Identifier")
                sheet.write(1, 4, "Missing Configurations")
                # Add column
                sheet.write(2, 1, transformed["blockName"])

            if transformed["complianceStatus"] !="compliant":
                metricsObject ["nonComplianceDevicesCount"] =+1
            else:
                metricsObject ["complianceDevicesCount"] =+1
            blockRowIndex = metricsObject ["nonComplianceDevicesCount"] + metricsObject ["complianceDevicesCount"] + 1
            if(len(transformed["deviceConfigBlocks"]) > 0):
                deviceConfigBlock=transformed["deviceConfigBlocks"][0]
                if (deviceConfigBlock["deviceConfig"]) == "" and deviceConfigBlock["complianceStatus"] !="info":
                    sheet.write(blockRowIndex, 2, deviceConfigBlock["complianceStatus"])
                    sheet.write(blockRowIndex, 3, transformed["deviceIdentifier"])
                    sheet.write(blockRowIndex, 4, transformed["blockConfig"])
                else:
                    strdiffConfigs=strDiffConfig(deviceConfigBlock["diff_config"])
                    diffConfigs= "\015".join(strdiffConfigs)
                    if diffConfigs != "":

                        #print (blockRowIndex, transformed["blockName"], diffConfigs)
                        sheet.write(blockRowIndex, 2, deviceConfigBlock["complianceStatus"])
                        sheet.write(blockRowIndex, 3, transformed["deviceIdentifier"])
                        sheet.write(blockRowIndex, 4, diffConfigs)

        for summaryRowIndex, blockName in enumerate (summaryMetrics, start=2):
            summarySheet.write(summaryRowIndex, 1, blockName)
            summarySheet.write(summaryRowIndex, 2, summaryMetrics[blockName]["complianceDevicesCount"])
            summarySheet.write(summaryRowIndex, 3, summaryMetrics[blockName]["nonComplianceDevicesCount"])
        #Eo AK-Mobified
        
        # === Sheet: Compliance Details ===
    #    detailsSheet = workbook.add_sheet("Compliance Details")
    #    headers = ["","Device Identifier", "Block Name", "Compliance Status", "Missing configuration"]
    #    for col, header in enumerate(headers):
    #        detailsSheet.write(1, col, header)
    #    for row_index, doc in enumerate(documents, start=2):
    #        transformed = transformJSON(doc, fieldsToKeep)
    #        detailsSheet.write(row_index, 1, transformed["deviceIdentifier"])
    #        detailsSheet.write(row_index, 2, transformed["blockName"])
    #        if transformed["blockName"] in summaryMetrics:
    #            metricsObject= summaryMetrics [transformed["blockName"]]
    #        else: 
    #            summaryMetrics[transformed["blockName"]]={"complianceDevicesCount": 0,"nonComplianceDevicesCount": 0}
    #            metricsObject= summaryMetrics [transformed["blockName"]]
    #        if transformed["complianceStatus"] !="compliant":
    #            metricsObject ["nonComplianceDevicesCount"] =+1
    #        else:
    #            metricsObject ["complianceDevicesCount"] =+1
    #        detailsSheet.write(row_index, 3, transformed["complianceStatus"])
    #        if(len(transformed["deviceConfigBlocks"]) > 0):
    #            deviceConfigBlock=transformed["deviceConfigBlocks"][0]
    #            if (deviceConfigBlock["deviceConfig"]) == "" and deviceConfigBlock["complianceStatus"] !="info":
    #                detailsSheet.write(row_index, 4, transformed["blockConfig"])
    #            else:
    #                strdiffConfigs=strDiffConfig(deviceConfigBlock["diff_config"])
    #                diffConfigs= "\015".join(strdiffConfigs)
    #                #print(transformed["deviceIdentifier"],transformed["blockName"],transformed["complianceStatus"],strdiffConfigs)
    #                detailsSheet.write(row_index, 4, diffConfigs)
    #        #print (summaryMetrics)

        # === Non-compliant device grouping by rule ===
    #    rule_to_devices = {}
    #    for doc in documents:
    #        status = doc.get("complianceStatus", "").lower()
    #        if status != "compliant":
    #            rule = doc.get("blockName", "Unknown Rule")
    #            device = doc.get("deviceIdentifier", "Unknown Device")
    #            rule_to_devices.setdefault(rule, []).append(device)

        # Create one sheet per rule with list of devices
    #    for rule_name, devices in rule_to_devices.items():
    #        sheet_name = sanitizeSheetName(rule_name)
    #        sheet = workbook.add_sheet(sheet_name)
#
    #        # Header
    #        sheet.write(1, 1, "Rule name")
    #        sheet.write(1, 2, "Severity")
    #        sheet.write(1, 3, "Device Identifier")
    #        sheet.write(1, 4, "Missing Configurations")
    #        sheet.write(2, 1, rule_name)
    #        for idx, device in enumerate(devices, start=2):
    #            sheet.write(idx, 3, device)
    #        #AK Modified
    #        for ruleSheetIndex, ruleDoc in enumerate(documents, start=2):
    #            ruleTransformed = transformJSON(ruleDoc, fieldsToKeep)
    #            if(len(ruleTransformed["deviceConfigBlocks"]) > 0):
    #                deviceConfigBlock=ruleTransformed["deviceConfigBlocks"][0]
    #                if (deviceConfigBlock["deviceConfig"]) == "" and deviceConfigBlock["complianceStatus"] !="info":
    #                    sheet.write(ruleSheetIndex, 4, ruleTransformed["blockConfig"])
    #                else:
    #                    strdiffConfigs=strDiffConfig(deviceConfigBlock["diff_config"])
    #                    diffConfigs= "\015".join(strdiffConfigs)
    #                    #print(ruleTransformed["deviceIdentifier"],ruleTransformed["blockName"],ruleTransformed["complianceStatus"],strdiffConfigs)
    #                    sheet.write(ruleSheetIndex, 4, diffConfigs)
        #Eo AK Modified

        # Save workbook
        filename = f"BPAReport_{dateNow.strftime('%Y%m%d_%H%M%S')}_{userInput}.xls"
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
