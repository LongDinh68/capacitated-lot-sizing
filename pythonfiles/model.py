from gurobipy import *
from parser import load_instance


def define_model(data):
    
    # dimensions
    
    nb_items = data["nb_items"]
    nb_period = data["nb_period"]
    nb_resources = data["nb_resources"]
    setup_cost = data["setup_cost"]
    holding_cost = data["holding_cost"]
    lead_time = data["lead_time"]
    initial_inventory = data["initial_inventory"]
    item_name = data["item_name"]
    demand = data["demand"]
    bom = data["bom"]
    capacity = data["capacity"]
    prod_cap = data["prod_cap"]
    setup_cap = data["setup_cap"]
    overtime_cost = data["overtime_cost"]

    # _____________
    # NORMALIZATION
    # Each machine-period capacity is scaled to 1
    # ____________________________________________
    
    L_orig = [capacity[m][0] for m in range(nb_resources)] # original machine capacities (before normalization)

    for m in range(nb_resources):
        base_capacity = capacity[m][0] # we can take any period's capacity since they are the same for all periods
        for i in range(nb_items):
            prod_cap[m][i] /= base_capacity  # normalize production capacity of item i on machine m
            setup_cap[m][i] /= base_capacity # normalize setup capacity of item i on machine m
        for t in range(nb_period):
            capacity[m][t] = 1 
    
    
    # build helper data structures for model formulation
    # __________________________________________________
    
    # p[i]: the production time of item i, 
    # which is the production capacity of item i on the unique assigned machine that can produce it (after normalization)
    p = {}
    for i in range(nb_items):
        for m in range(nb_resources):
            if prod_cap[m][i] > 0:
                p[i] = prod_cap[m][i]
                break
        else:
            p[i] = None 
            
    # s[j]: the setup time of item j, 
    # which is the setup capacity of item j on the unique assigned machine that can produce it (after normalization)
    s = {}
    for j in range(nb_items):
        for m in range(nb_resources):
            if prod_cap[m][j] > 0:
                s[j] = setup_cap[m][j]
                break
        else:
            s[j] = None


    # ϕ(m): set of items that can be produced on machine m
    phi = {}
    for m in range(nb_resources):
        phi[m] = [i for i in range(nb_items) if prod_cap[m][i] > 0]
        
    # Γ(i): set of items that are direct successors of item i in the BOM 
    gamma = {} 
    
    for i in range(nb_items):
        gamma[i] = []
        for j in range(nb_items):
            if bom[i][j] > 0:
                gamma[i].append(j)

    # _____
    # MODEL
    # _____

    model = Model("Multi-level capacitated lot-sizing with lot streaming")
    
    # ____________________
    # decision variables
    #_____________________

    I     = model.addVars(nb_items, nb_period, vtype=GRB.CONTINUOUS, lb=0, name="inventory")
    
    mu    = model.addVars(nb_items, nb_period, vtype=GRB.CONTINUOUS, lb=0, ub=1, name="start_time") 
    # mu[i,t] represents the start time of production of item i in period t, normalized by the period length (so it is between 0 and 1)
    
    X     = model.addVars(nb_items, nb_period, vtype=GRB.CONTINUOUS, lb=0, name="production")
    
    alpha = model.addVars(nb_items, nb_period + 1, nb_resources, vtype=GRB.BINARY, name="machine_setup") 
    #   alpha has nb_period + 1 periods to capture the setup at the end of the last period.
    
    T     = model.addVars(nb_items, nb_items, nb_period, nb_resources, vtype=GRB.BINARY, name="Change_Over")
    
    # T_iitm = 0: no changeover from an item to itself
    for m in range(nb_resources):
        for i in phi[m]:
            for t in range(nb_period):
                T[i, i, t, m].ub = 0 # execute i =! j 
                
    # ____________________
    # Objective Function
    # ____________________

    model.setObjective(
        quicksum(holding_cost[i] * I[i, t]
                 for i in range(nb_items) for t in range(nb_period))
        + quicksum(setup_cost[j] * T[i, j, t, m]
                   for i in range(nb_items) for j in range(nb_items)
                   for t in range(nb_period) for m in range(nb_resources)),
        GRB.MINIMIZE) 
    
    # __________________________
    # PROBLEM CONSTRAINTS   
    # __________________________

    # (7) Inventory balance
    for i in range(nb_items):
        for t in range(nb_period):
            prev = initial_inventory[i] if t == 0 else I[i, t-1] # consider the initial inventory for the first period
            model.addConstr(
                I[i, t] - prev - X[i, t]
                + quicksum(bom[i][j] * X[j, t] for j in gamma[i])
                + demand[i][t] == 0,
                name=f"inventory_balance_{i}_{t}")

    # (8) Production-setup linking constraint
    # The limit of capacity is the limit of time; 
    # capacity need is the time required(prod_cap) to produce the amount of item i (X[i,t]) 
    for m in range(nb_resources):
        for i in phi[m]:
            for t in range(nb_period):
                model.addConstr(
                    p[i] * X[i, t] <= quicksum(T[j, i, t, m] for j in phi[m]) + alpha[i, t, m],
                    name=f"prod_setup_link_{i}_{t}_{m}")

    # (9) Each machine is setup for exactly one item
    # alpha has nb_period + 1 periods to capture the setup state at the end of the last period. 
    # because Constraint (10) references alpha[i, t+1, m] to satisfy setup-flow conservation in the last period.
    
    model.addConstrs(
        (quicksum(alpha[i, t, m] for i in phi[m]) == 1
         for t in range(nb_period + 1) for m in range(nb_resources)), 
    
        name="one_setup_per_resource") 


    # (10) Setup flow conservation
    # t + 1 is still within the time horizon since alpha has nb_period + 1 periods

    for m in range(nb_resources):
        for i in phi[m]:
            for t in range(nb_period):
                model.addConstr(
                    quicksum(T[j, i, t, m] for j in phi[m]) + alpha[i, t, m]
                    == quicksum(T[i, j, t, m] for j in phi[m]) + alpha[i, t+1, m],
                    name=f"setup_flow_{i}_{t}_{m}")

    # (11) At most one changeover into item i
    for m in range(nb_resources):
        for i in phi[m]:
            for t in range(nb_period):
                model.addConstr(
                    quicksum(T[j, i, t, m] for j in phi[m]) <= 1,
                    name=f"one_changeover_into_item_{i}_{t}_{m}")

    # (12) Timing for consecutive products
    # t + 1 is still within the time horizon since alpha has nb_period + 1 periods
    for m in range(nb_resources):
        for i in phi[m]:
            for j in phi[m]:
                if i == j:
                    continue # skip the case of consecutive production of the same item, which is already prevented by T[i, i, t, m].ub = 0
                for t in range(nb_period): 
                    model.addConstr(
                        mu[i, t] + p[i] * X[i, t] + s[j] * T[i, j, t, m]
                        + T[i, j, t, m] - 1 - alpha[j, t + 1, m] <= mu[j, t], 
                        name=f"timing_consecutive_product_{i}_{j}_{t}_{m}")

    # (13) Timing for last product in sequence
    # t + 1 is still within the time horizon since alpha has nb_period + 1 periods 
    for m in range(nb_resources):
        for i in phi[m]:
            for j in phi[m]:
                if i == j:
                    continue # skip the case of consecutive production of the same item, which is already prevented by T[i, i, t, m].ub = 0
                for t in range(nb_period):  
                    model.addConstr(
                        mu[i, t] + p[i] * X[i, t] + s[j] * T[i, j, t, m]
                        + alpha[j, t+1, m] - 1 - alpha[j, t, m] <= mu[j, t],
                        name=f"timing_last_product_{i}_{j}_{t}_{m}")

    # (14) Capacity constraint - 
    # Capacity is in terms of time
    # The total time used on machine m in period t, 
    # includes the production time of all items
    # and the setup time for all changeovers, 
    # cannot exceed the normalized capacity of 1.
    
    for m in range(nb_resources):
        for i in phi[m]:
            for t in range(nb_period):
                model.addConstr(
                    mu[i, t] + p[i] * X[i, t]
                    + quicksum(s[j] * T[i, j, t, m] for j in phi[m]) <= 1,
                    name=f"time_capacity_{i}_{t}_{m}")
                
    
       
    # ______________________
    # LINEARIZATION CONSTRAINTS
    # ______________________
    
    
    # ______________________
    # Lot Streaming constraints (21) and (22)
    # Gurobi general constraints (min/max)
    # ______________________

    def min_term(i, t, ref_expr, tag):
        # min( X[i,t], (1/p_i)*(ref_expr - mu[i,t])^+ )
        z = model.addVar(lb=-GRB.INFINITY, name=f"z_{tag}") # auxiliary variable for the max(0, ref_expr - mu[i,t]) term
        model.addConstr(z == ref_expr - mu[i, t]) # z captures the difference (ref_expr - mu[i,t])
        zp = model.addVar(lb=0.0, name=f"zp_{tag}") # auxiliary variable for the positive part of z
        model.addGenConstrMax(zp, [z], constant=0.0) # zp = max(z, 0) captures the positive part of z
        scaled = model.addVar(lb=0.0, name=f"sc_{tag}") 
        model.addConstr(scaled == (1.0 / p[i]) * zp) # scale zp by 1/p[i] to get the second term in the min expression
        term = model.addVar(lb=0.0, name=f"term_{tag}") # auxiliary variable for the min term
        model.addGenConstrMin(term, [X[i, t], scaled]) # term = min(X[i,t], scaled)
        return term


    
    # (21): at the start of item i (LHS min-term = 0)
    for i in range(nb_items):
        for t in range(nb_period):
            prev_int = initial_inventory[i] if t == 0 else I[i, t - 1]
            ref = mu[i, t] # the start time of predecessor i in period t
            rhs = quicksum(bom[i][j] * min_term(j, t, ref, f"21RHS_{i}_{j}_{t}")
                           for j in gamma[i])
            model.addConstr(prev_int >= rhs, name=f"constr21_{i}_{t}")

    # (22): at the end of each successor k
    for i in range(nb_items):
        for t in range(nb_period):
            prev_int = initial_inventory[i] if t == 0 else I[i, t - 1]
            for k in gamma[i]:
                ref = mu[k, t] + p[k] * X[k, t] # the end time of successor k in period t
                lhs = min_term(i, t, ref, f"22LHS_{i}_{k}_{t}")
                rhs = quicksum(bom[i][j] * min_term(j, t, ref, f"22RHS_{i}_{j}_{k}_{t}")
                               for j in gamma[i])
                model.addConstr(prev_int + lhs >= rhs, name=f"constr22_{i}_{k}_{t}")

            
    model.update() # update the model to integrate new variables and constraints
    return (model, I, X, mu, alpha, T, phi, p, s, gamma, L_orig)

    