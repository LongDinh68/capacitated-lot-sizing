
from parser import load_instance
from model import define_model
import os
from gurobipy import GRB

data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
result_dir = os.path.join(os.path.dirname(__file__), "..", "result")
os.makedirs(result_dir, exist_ok=True)

instances = [
    "A_G001545_MLCLS.dat",
    "B_G511541_MLCLS.dat",
    "C_K805132_MLCLS.dat",
    "D_G819321_MLCLS.dat",
]


for filename in instances:
    print("\n" + "=" * 60)
    print("Solving:", filename)
    print("=" * 60)
    # Load benchmark instance from .dat file
    data = load_instance(os.path.join(data_dir, filename))
    # Extract basic instance information
    nb_items = data["nb_items"]
    nb_period = data["nb_period"]
    nb_resources = data["nb_resources"]
    holding_cost = data["holding_cost"]
    setup_cost = data["setup_cost"]
    
    # Build the Gurobi model and retrieve decision variables
    # phi, p, s, gamma, and L_orig are preprocessed structures/parameters
    instance_name = filename.replace(".dat", "")
    (model, I, X, mu, alpha, T, phi, p, s, gamma, L_orig) = define_model(data) # 
    nb_period = max(t for (i, t) in X.keys()) + 1

    # # Export LP model for debugging and verification
    model.write(os.path.join(result_dir, f"model_{instance_name}.lp"))

    model.setParam("MIPFocus", 1)
    model.setParam("Heuristics", 0.5)
    model.setParam("Presolve", 2)
    model.setParam("Cuts", 2)
    model.setParam("TimeLimit", 1800)
    model.optimize()

    # status classification
    if model.SolCount > 0:
        status_text = "Feasible - solution found"
    elif model.Status == GRB.INFEASIBLE:
        status_text = "Infeasible - proven no solution"
    else:
        status_text = f"Unknown - not proven infeasible (status {model.Status})"
    print(status_text)

    if model.Status == GRB.INFEASIBLE:
        model.computeIIS()
        model.write(os.path.join(result_dir, f"{instance_name}.ilp"))
        print("IIS written for", filename)

    # machine of each item (to de-normalize times back to original units)
    machine_of = {}
    for m in range(nb_resources):
        for i in phi[m]:
            machine_of[i] = m

    lines = []
    lines.append(f"Instance: {filename}")
    lines.append(f"Items: {nb_items}   Periods: {nb_period}   Machines: {nb_resources}")
    lines.append(f"Original machine capacities L_orig: {L_orig}")
    lines.append(f"Status: {model.Status}   ({status_text})")

    if model.SolCount > 0:
        lines.append(f"Objective (total cost): {model.ObjVal:.4f}")
        lines.append(f"Best bound: {model.ObjBound:.4f}")
        lines.append(f"MIP gap: {model.MIPGap * 100:.4f}%")
        lines.append(f"Runtime: {model.Runtime:.2f} s")
        lines.append(f"Solutions found: {model.SolCount}")

        # cost breakdown
        hold_total = sum(holding_cost[i] * I[i, t].X for i in range(nb_items) for t in range(nb_period))
        setup_total = sum(setup_cost[j] * T[i, j, t, m].X
                          for m in range(nb_resources) for i in phi[m] for j in phi[m] if i != j
                          for t in range(nb_period) if T[i, j, t, m].X > 0.5)
        lines.append(f"  - holding cost: {hold_total:.4f}")
        lines.append(f"  - setup/changeover cost: {setup_total:.4f}")

        # schedule per period / machine (times de-normalized: * L_orig[machine])
        # NOTE: item and machine indices are printed 1-based to match the data file
        
        # Start of AI-generated code modified

        lines.append("")
        lines.append("SCHEDULE with de-normalized start/finish times to original capacity units)")

        for t in range(nb_period):
            lines.append(f"_____Period {t + 1}____")

            for m in range(nb_resources):
                Lm = L_orig[m]

                setup_item = [i + 1 for i in phi[m] if alpha[i, t, m].X > 0.5] 
                # Identify the item (if any) that is being set up on machine m in period t based on the alpha variables
                changeovers = [(i + 1, j + 1) for i in phi[m] for j in phi[m]
                            if i != j and T[i, j, t, m].X > 0.5] # Identify any changeovers occurring on machine m in period t based on the T variables, and list them as pairs of item indices (i, j) that are changing over from item i to item j

                lines.append(
                    f"  Machine {m + 1} (cap={Lm}): "
                    f"setup_for={setup_item}  changeovers={changeovers}"
                ) # Print the machine number (1-based), its capacity, setup item state, and any changeovers occurring in that period

                load = 0.0 # Initialize the production load for this machine and period to zero

                for i in phi[m]:
                    qty = X[i, t].X # Get the production quantity for item i in period t from the X variables
                    if qty <= 1e-6:
                        continue # Skip items that are not produced in this period (i.e., those with negligible production quantity)

                    start = mu[i, t].X * Lm # De-normalize the start time for item i in period t
                    prod_time = p[i] * qty * Lm # De-normalize the production time for item i 
                    finish = start + prod_time # De-normalized finish time for item i 
                    load += p[i] * qty # the production load on the machine 
                    lines.append(
                        f"      item {i + 1}: X={qty:.3f}  "
                        f"start={start:.3f}  prod_time={prod_time:.3f}  "
                        f"finish={finish:.3f}  "
                        f"(start_norm={mu[i, t].X:.3f})"
                    ) # Print results

                lines.append(
                    f"      -> production load (norm) = {load:.3f} of 1.0  "
                    f"(= {load * Lm:.2f} of {Lm} original)"
                )
        # End of AI-generated code modified
        
        # inventory
        lines.append("")
        lines.append("INVENTORY I[i,t]")
        for i in range(nb_items):
            row = [f"{I[i, t].X:.2f}" for t in range(nb_period)]
            if any(I[i, t].X > 1e-6 for t in range(nb_period)):
                lines.append(f"  item {i + 1}: " + "  ".join(row))
    else:
        lines.append("No feasible solution found")

    print("\n".join(lines))
    result_path = os.path.join(result_dir, f"{instance_name}_result.txt")
    with open(result_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\nResult saved to", result_path)