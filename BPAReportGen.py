#{"complianceJob.complianceJobName":"Consultative hardening Job"}
import xlwt
import datetime
from pymongo import MongoClient
import json
import re

dateNow = datetime.datetime.now()
fontBoldRed = xlwt.easyfont('bold true, color_index red')           # used for missing config
fontGreen = xlwt.easyfont('color_index green')                      # used for addtional lines

fontDefault = xlwt.easyfont('')
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
def strDiffConfig(data, indentLevel=0):
    outputLines = []
    indentPrefix = " " * (indentLevel * 2) # 2 spaces per indent level
    if isinstance(data, dict):
        # If the input is a dictionary (representing a config node)
        if "config_line" in data:
            #if len (data["children"]) == 0 and (data["severity"]) != "info":
                if len (data["violations"]) > 0 and "<<MissingConfig>>" in data["violations"] :
                    cLine = f"\015{indentPrefix}{data['config_line']}"
                    outputLines.append((cLine,fontBoldRed))
                elif len (data["violations"]) > 0 and "<<AdditionalConfig>>" in data["violations"] :
                    aLine = f"\015{indentPrefix}{data['config_line']}"
                    outputLines.append((aLine,fontGreen))
                else: 
                    mLine = f"\015{indentPrefix}{data['config_line']}"
                    outputLines.append((mLine, fontDefault))

        # Recursively process the 'children' list if it exists and is a list
        if "children" in data and isinstance(data["children"], list):
            # Call recursively for children, increasing the indent level
            transformedChildrenLines = strDiffConfig(data["children"], indentLevel + 1)
            # Extend the current node's output with the transformed children lines
            outputLines.extend(transformedChildrenLines)

    elif isinstance(data, list):
        # If the input is a list (representing a collection of config nodes)
        for item in data:
            processed_item_lines = strDiffConfig(item, indentLevel)
            outputLines.extend(processed_item_lines)
    else:
        outputLines.append(f"{indentPrefix}Unexpected Data: {data}")
    return outputLines  

# Variables required to Conenct to MongoDB   
def fetchMongoDB(jobName):
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
                summaryMetrics[transformed["blockName"]]={"blockRowIndex": 1,"complianceDevicesCount": 0,"nonComplianceDevicesCount": 0}
                metricsObject= summaryMetrics [transformed["blockName"]]
                
                sheet = workbook.add_sheet(sheet_name)
                # Header
                sheet.write(1, 1, "Rule name")
                sheet.write(1, 2, "Severity")
                sheet.write(1, 3, "Device Identifier")
                sheet.write(1, 4, "Missing Configurations")
                # Add column
                sheet.write(2, 1, transformed["blockName"])

            if transformed["complianceStatus"] !="compliant":
                metricsObject ["nonComplianceDevicesCount"] +=1
            else:
                metricsObject ["complianceDevicesCount"] +=1 

            if(len(transformed["deviceConfigBlocks"]) > 0):
                for i in range (len(transformed["deviceConfigBlocks"])):
                    deviceConfigBlock=transformed["deviceConfigBlocks"][i]
                    blockRowIndex = metricsObject ["blockRowIndex"] + 1
                    metricsObject ["blockRowIndex"] = blockRowIndex
                    #print (sheet_name, i, blockRowIndex, metricsObject ["blockRowIndex"])
                    if (deviceConfigBlock["deviceConfig"]) == "" and deviceConfigBlock["complianceStatus"] !="info":
                        sheet.write(blockRowIndex, 2, deviceConfigBlock["complianceStatus"])
                        if (i ==0):
                            sheet.write(blockRowIndex, 3, transformed["deviceIdentifier"])
                        sheet.write(blockRowIndex, 4, transformed["blockConfig"])
                    else:
                        diffConfigs=strDiffConfig(deviceConfigBlock["diff_config"])
                        #diffConfigs= "\015".join(strdiffConfigs)
                        if len (diffConfigs) > 0:
                            sheet.write(blockRowIndex, 2, deviceConfigBlock["complianceStatus"])
                            if (i ==0):
                                sheet.write(blockRowIndex, 3, transformed["deviceIdentifier"])
                            sheet.write_rich_text(blockRowIndex, 4, diffConfigs)

        for summaryRowIndex, blockName in enumerate (summaryMetrics, start=2):
            summarySheet.write(summaryRowIndex, 1, blockName)
            summarySheet.write(summaryRowIndex, 2, summaryMetrics[blockName]["complianceDevicesCount"])
            summarySheet.write(summaryRowIndex, 3, summaryMetrics[blockName]["nonComplianceDevicesCount"])

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
    fetchMongoDB(userInput)
