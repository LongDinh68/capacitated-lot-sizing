import os


def load_instance(filepath):
    
    # Read the file, strip whitespace, and ignore empty lines
    with open(filepath) as f:
        lines = [line.strip() for line in f if line.strip()] 

    # __________
    # Dimensions
    # __________

    idx = lines.index("NumberOfPeriods,Items,Resources") # Find the index of the line containing the dimensions

    nb_period, nb_items, nb_resources = map(int,
        lines[idx + 1].split()) # Read the numbers of periods, items, and resources

    # _______________
    # Item Parameters
    # ________________
    # List to store setup costs, holding costs, lead times, initial inventory, and item names for each item

    setup_cost = [] 
    holding_cost = [] 
    lead_time = [] 
    initial_inventory = [] 
    item_name = [] 

    idx = lines.index("SetupCost,HoldingCost,LeadTime,InitialInventory,NameOfItem") + 1 

    for i in range(nb_items):
        row = lines[idx + i].split() # Split the line into components for item i
        # extract and append the setup cost, holding cost, lead time, initial inventory, and item name for item i
        setup_cost.append(float(row[0])) 
        holding_cost.append(float(row[1])) 
        lead_time.append(float(row[2]))
        initial_inventory.append(float(row[3]))
        item_name.append(row[4])

    # ______________
    # BOM/ Bill of Materials 
    # bom[i][j] = number of units of component i required to produce one unit of item j
    # (i = component/predecessor, j = parent/successor)
    # ______________

    bom = []
    # Find the index of the line containing the BOM matrix
    idx = lines.index(
        "BOM(c_ij=NumberOfItems_i_NecessaryToProduceItem_j)") + 1 

    for i in range(nb_items):
        row = list(map(float, lines[idx + i].split()))
        bom.append(row) # Append row i: units of component i needed per unit of each item j

    # ______________
    # Demand
    # ______________

    demand = []
    # Find the index of the line containing the demand matrix
    idx = lines.index(
        "ExternalDemandForEachItemAndPeriod"
    ) + 1 

    for i in range(nb_items):
        row = list(map(float, lines[idx + i].split()))
        demand.append(row) # Append the row of the demand matrix for item i to the demand list

    # ______________
    # Capacity Limits
    # ______________

    capacity = []

    idx = lines.index(
        "CapacityLimitsForEachResourceAndPeriod"
    ) + 1 # Find the index of the line containing the capacity limits matrix

    for m in range(nb_resources):
        row = list(map(float, lines[idx + m].split()))
        capacity.append(row) # Append row m: available capacity limit of resource m in each period
        
    # _____________________________________________
    # Processing-Time / Capacity Consumption Matrix
    # _____________________________________________

    prod_cap = []

    idx = lines.index(
        "CapacityNeedsForProductionForEachResourceAndItem"
    ) + 1 # Find the index of the line containing the production capacity needs matrix

    for m in range(nb_resources):
        row = list(map(float, lines[idx + m].split()))
        prod_cap.append(row) # Append row m of the processing-time (capacity consumption) matrix for production of item i on resource m

    # _______________________________________
    # Setup-Time / Capacity Consumption Matrix
    # _______________________________________

    setup_cap = []

    idx = lines.index("CapacityNeedsForSetupForEachResourceAndItem"
                      ) + 1  # Find the index of the line containing the setup capacity needs matrix

    for m in range(nb_resources):
        row = list(map(float, lines[idx + m].split()))
        setup_cap.append(row) # Setup time (capacity consumption) required when resource m is set up for item i

    # _____________________
    # Overtime Costs
    # _____________________
    idx = lines.index("OverTimeCostsForEachResource") + 1
    overtime_cost = list(map(float, lines[idx].split())) # Extract the overtime costs for each resource from the line following the "OverTimeCostsForEachResource" header

    # _____________________
    # Return Data
    # _____________________

    return {
        "nb_items": nb_items,
        "nb_period": nb_period,
        "nb_resources": nb_resources,

        "setup_cost": setup_cost,
        "holding_cost": holding_cost,
        "lead_time": lead_time,
        "initial_inventory": initial_inventory,
        "item_name": item_name,

        "bom": bom,
        "demand": demand,
        "capacity": capacity,
        "prod_cap": prod_cap,
        "setup_cap": setup_cap,
        "overtime_cost": overtime_cost
    } # Return a dictionary containing all the extracted data


# 
# LOOP THROUGH ALL FILES
# 
# This code loops through all .dat files in the specified data folder, 
# loads the data from each file, 
# and prints out the contents in a structured format for validation purposes.
folder = os.path.join(os.path.dirname(__file__), "..", "data")

for filename in os.listdir(folder):

    if filename.endswith(".dat"):

        path = os.path.join(folder, filename)

        data = load_instance(path)

        print("\n" + "=" * 80)
        print("FILE:", filename)
        print("=" * 80)

        print("\nDIMENSIONS")
        print("Items:", data["nb_items"])
        print("Periods:", data["nb_period"])
        print("Resources:", data["nb_resources"])

        print("\nSETUP COST")
        print(data["setup_cost"])

        print("\nHOLDING COST")
        print(data["holding_cost"])

        print("\nLEAD TIME")
        print(data["lead_time"])

        print("\nINITIAL INVENTORY")
        print(data["initial_inventory"])

        print("\nITEM NAMES")
        print(data["item_name"])

        print("\nBOM MATRIX")
        for row in data["bom"]:
            print(row)

        print("\nDEMAND")
        for row in data["demand"]:
            print(row)

        print("\nCAPACITY")
        for row in data["capacity"]:
            print(row)

        print("\nPRODUCTION CAPACITY REQUIREMENTS")
        for row in data["prod_cap"]:
            print(row)

        print("\nSETUP CAPACITY REQUIREMENTS")
        for row in data["setup_cap"]:
            print(row)

        print("\nOVERTIME COST")
        print(data["overtime_cost"])

        print("\nEND OF FILE")
        print("_" * 30)