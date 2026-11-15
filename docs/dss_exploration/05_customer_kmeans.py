import sys, warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score, adjusted_rand_score, roc_auc_score
from sklearn.ensemble import HistGradientBoostingClassifier as HGC
from scipy.stats import chi2_contingency
d=sys.argv[1]; P=lambda f: pd.read_csv(f"{d}/{f}")
o=P("olist_orders_dataset.csv"); o["t"]=pd.to_datetime(o.order_purchase_timestamp)
o=o[o.order_status=="delivered"]
c=P("olist_customers_dataset.csv")[["customer_id","customer_unique_id","customer_state"]]
pay=P("olist_order_payments_dataset.csv").groupby("order_id").payment_value.sum().rename("pay")
it=P("olist_order_items_dataset.csv"); pr=P("olist_products_dataset.csv")[["product_id","product_category_name"]]
it=it.merge(pr,on="product_id",how="left")
ag=it.groupby("order_id").agg(items=("order_item_id","count"),price=("price","sum"),fr=("freight_value","sum"))
cat=it.sort_values("order_item_id").groupby("order_id").product_category_name.first()
o=o.merge(c,on="customer_id").set_index("order_id").join(pay).join(ag).join(cat).reset_index()
o=o.sort_values("t")
reg={**{s:"N" for s in "AC AM AP PA RO RR TO".split()},**{s:"NE" for s in "AL BA CE MA PB PE PI RN SE".split()},**{s:"CO" for s in "DF GO MT MS".split()},**{s:"SE" for s in "ES MG RJ SP".split()},**{s:"S" for s in "PR RS SC".split()}}
f=o.groupby("customer_unique_id").head(1).set_index("customer_unique_id")
f["second"]=o.groupby("customer_unique_id").t.apply(lambda s:s.iloc[1] if len(s)>1 else pd.NaT)
end=o.t.max(); f=f[f.t<=end-pd.Timedelta(days=180)].copy()
f["rep"]=((f.second-f.t).dt.days<=180).astype(int)
f["lpay"]=np.log1p(f.pay.fillna(f.pay.median())); f["fr_ratio"]=(f.fr/f.price.replace(0,np.nan)).clip(0,2).fillna(0.3)
f["items"]=f["items"].clip(upper=5); f["reg"]=f.customer_state.map(reg)
top=f.product_category_name.value_counts().head(8).index; f["cg"]=f.product_category_name.where(f.product_category_name.isin(top),"outros").fillna("outros")
X=pd.concat([f[["lpay","fr_ratio","items"]],pd.get_dummies(f.reg,prefix="r"),pd.get_dummies(f.cg,prefix="c")],axis=1).astype(float)
f["m"]=f.t.dt.month
print("khách đủ điều kiện:",len(f),"mua lại 180 ngày: %.4f"%f.rep.mean())
split=pd.Timestamp("2017-09-01")
tr=f[f.t<split]; te=f[f.t>=split]; Xtr=X.loc[tr.index]; Xte=X.loc[te.index]
print(f"train {len(tr)} (rep {tr.rep.mean():.4f}) | test {len(te)} (rep {te.rep.mean():.4f})")
sc=StandardScaler().fit(Xtr); A=sc.transform(Xtr); B=sc.transform(Xte)
for k in range(2,9):
    km=KMeans(k,n_init=5,random_state=0).fit(A); print(f"k={k} silhouette(train) {silhouette_score(A,km.labels_,sample_size=8000,random_state=0):.3f}")
def wilson(x,n,z=1.96):
    p=x/n; den=1+z*z/n; ctr=(p+z*z/(2*n))/den; h=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den; return ctr-h,ctr+h
for K in [4,6]:
    km=KMeans(K,n_init=10,random_state=0).fit(A); tr_c=km.labels_; te_c=km.predict(B)
    rng=np.random.default_rng(0); aris=[]
    for _ in range(20):
        i=rng.integers(0,len(A),len(A)); kb=KMeans(K,n_init=3,random_state=0).fit(A[i]); aris.append(adjusted_rand_score(tr_c,kb.predict(A)))
    print(f"\n=== K={K}: ổn định bootstrap ARI {np.mean(aris):.2f} ===")
    t=te.assign(c=te_c); tt=tr.assign(c=tr_c)
    rows=[]
    for cl in range(K):
        s=t[t.c==cl]; lo,hi=wilson(s.rep.sum(),len(s))
        rows.append((cl,len(s),f"{len(s)/len(t):.1%}",round(s.pay.mean(),0),round(s.fr_ratio.mean(),2),f"{s.rep.mean():.3f}",f"[{lo:.3f},{hi:.3f}]"))
    print(pd.DataFrame(rows,columns=["cụm","khách test","tỷ trọng","pay TB","cước/giá","mua lại 180d","CI95"]).to_string(index=False))
    ct=pd.crosstab(t.c,t.rep); print("chi-square p =",chi2_contingency(ct)[1])
    rate=tt.groupby("c").rep.mean(); sc_=t.c.map(rate)
    print("AUC: dùng tỷ lệ mua lại cụm (học từ train) làm điểm số:",round(roc_auc_score(t.rep,sc_),3))
# trần giám sát
m=HGC(max_iter=150,learning_rate=0.06,random_state=0).fit(Xtr.assign(m=tr.m),tr.rep)
print("\nTrần: GBM có giám sát trên cùng đặc trưng đơn đầu: AUC test",round(roc_auc_score(te.rep,m.predict_proba(Xte.assign(m=te.m))[:,1]),3))
for nm,col in [("chi tiêu đơn đầu (log)","lpay"),("tỷ lệ cước/giá","fr_ratio")]:
    print(f"AUC chỉ dùng {nm}:",round(roc_auc_score(te.rep,te[col]),3))
# tách một số biến đơn lẻ
for col in ["reg","cg"]:
    r=tr.groupby(col).rep.mean(); print(f"AUC chỉ dùng {col}:",round(roc_auc_score(te.rep,te[col].map(r).fillna(tr.rep.mean())),3))
