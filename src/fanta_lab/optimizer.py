import pandas as pd
import pulp

def optimize(df: pd.DataFrame, budget=500, slots=None):
    slots=slots or {'P':3,'D':8,'C':8,'A':6}
    d=df.reset_index(drop=True).copy()
    d['price']=pd.to_numeric(d.get('price',1),errors='coerce').fillna(1).clip(lower=1)
    d['fanta_score']=pd.to_numeric(d.get('fanta_score',0),errors='coerce').fillna(0)
    prob=pulp.LpProblem('fanta',pulp.LpMaximize)
    xs=[pulp.LpVariable(f'x{i}',cat='Binary') for i in d.index]
    prob += pulp.lpSum(xs[i]*float(d.loc[i,'fanta_score']) for i in d.index)
    prob += pulp.lpSum(xs[i]*float(d.loc[i,'price']) for i in d.index) <= budget
    for r,n in slots.items():
        ids=[i for i in d.index if str(d.loc[i,'role']).upper()==r]
        prob += pulp.lpSum(xs[i] for i in ids)==n
    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    picked=d[[pulp.value(xs[i])>0.5 for i in d.index]].copy()
    return picked.sort_values(['role','fanta_score'],ascending=[True,False])
