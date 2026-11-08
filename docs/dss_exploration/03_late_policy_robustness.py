import sys, warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from sklearn.ensemble import HistGradientBoostingClassifier as HGC, HistGradientBoostingRegressor as HGR
from sklearn.metrics import roc_auc_score
d = sys.argv[1]
P = lambda f: pd.read_csv(f"{d}/{f}")
o = P("olist_orders_dataset.csv")
for c in ["order_purchase_timestamp","order_approved_at","order_delivered_customer_date","order_estimated_delivery_date"]:
    o[c] = pd.to_datetime(o[c])
o = o[(o.order_status=="delivered")].dropna(subset=["order_delivered_customer_date","order_approved_at"])
cu = P("olist_customers_dataset.csv")[["customer_id","customer_zip_code_prefix","customer_state"]]
it = P("olist_order_items_dataset.csv"); pr = P("olist_products_dataset.csv"); se = P("olist_sellers_dataset.csv"); ge = P("olist_geolocation_dataset.csv")
ge = ge[(ge.geolocation_lat.between(-34,6))&(ge.geolocation_lng.between(-74,-34))]
ge = ge.groupby("geolocation_zip_code_prefix")[["geolocation_lat","geolocation_lng"]].mean()
it = it.merge(pr[["product_id","product_category_name","product_weight_g","product_length_cm","product_height_cm","product_width_cm"]], on="product_id", how="left")
it["vol"] = it.product_length_cm*it.product_height_cm*it.product_width_cm
g = it.sort_values("order_item_id").groupby("order_id")
first = g.head(1).set_index("order_id")[["seller_id","product_category_name"]]
agg = g.agg(n_items=("order_item_id","count"), price=("price","sum"), freight=("freight_value","sum"), weight=("product_weight_g","sum"), vol=("vol","sum"), n_sellers=("seller_id","nunique"))
df = o.merge(cu,on="customer_id").set_index("order_id").join(first).join(agg).reset_index().dropna(subset=["seller_id"])
df = df.merge(se,on="seller_id",how="left")
df = df.join(ge, on="customer_zip_code_prefix").rename(columns={"geolocation_lat":"clat","geolocation_lng":"clng"})
df = df.join(ge, on="seller_zip_code_prefix").rename(columns={"geolocation_lat":"slat","geolocation_lng":"slng"})
r=np.pi/180
a = np.sin((df.clat-df.slat)*r/2)**2+np.cos(df.slat*r)*np.cos(df.clat*r)*np.sin((df.clng-df.slng)*r/2)**2
df["dist"] = 6371*2*np.arcsin(np.sqrt(a))
p0 = df.order_purchase_timestamp.dt.normalize()
df["promise"] = (df.order_estimated_delivery_date.dt.normalize()-p0).dt.days
df["actual"] = (df.order_delivered_customer_date.dt.normalize()-p0).dt.days
df["late"] = (df.actual>df.promise).astype(int)
df["month"] = df.order_purchase_timestamp.dt.month
df["appr_lag"] = (df.order_approved_at-df.order_purchase_timestamp).dt.total_seconds()/3600
df["same_state"] = (df.seller_state==df.customer_state).astype(int)
df["freight_ratio"] = df.freight/df.price.replace(0,np.nan)
df["route"] = df.seller_state+">"+df.customer_state
df["cat"] = df.product_category_name.astype("category").cat.codes
df["t"] = df.order_purchase_timestamp
print("purchase range:", df.t.min().date(), df.t.max().date())
rng = np.random.default_rng(0)
def boot(fn, n, B=300):
    idx = rng.integers(0,n,(B,n)); return np.percentile([fn(i) for i in idx],[2.5,97.5])
folds = [("2017Q4","2017-10-01","2018-01-01"),("2018Q1 (đột biến)","2018-01-01","2018-04-01"),("2018Q2","2018-04-01","2018-07-01"),("2018Q3 (đến hết dữ liệu)","2018-07-01","2019-01-01")]
FEAT = ["same_state","route_rate","dist","freight","freight_ratio","weight","vol","price","n_items","cat","month","appr_lag","n_sellers"]
out=[]
for name,ts,te_ in folds:
    ts=pd.Timestamp(ts); te_=pd.Timestamp(te_)
    tr = df[df.t < ts-pd.Timedelta(days=45)].copy(); te = df[(df.t>=ts)&(df.t<te_)].copy()
    gm=tr.late.mean(); k=20
    rt = tr.groupby("route").late.agg(["sum","count"]); rt["rate"]=(rt["sum"]+k*gm)/(rt["count"]+k)
    for x in (tr,te): x["route_rate"]=x.route.map(rt.rate).fillna(gm)
    base = te.late.mean(); n=len(te)
    # classifier
    f1=["promise","same_state","route_rate"]
    m=HGC(max_iter=200,learning_rate=0.06,random_state=0).fit(tr[f1],tr.late); pr_=m.predict_proba(te[f1])[:,1]
    auc=roc_auc_score(te.late,pr_); y=te.late.values
    def aucb(i):
        yy=y[i]; 
        return roc_auc_score(yy,pr_[i]) if 0<yy.sum()<len(yy) else np.nan
    lo,hi=boot(aucb,n,200)
    print(f"\n== {name}: train {len(tr)} (late {gm:.3f}) | test {n} (late {base:.3f}) | AUC(route) {auc:.3f} [{lo:.3f},{hi:.3f}]")
    act=te.actual.values; cur=te.promise.values; curlate=(act>cur)
    for q in [0.90,0.93,0.95]:
        mq=HGR(loss="quantile",quantile=q,max_iter=200,learning_rate=0.06,random_state=0).fit(tr[FEAT],tr.actual)
        newp=np.ceil(mq.predict(te[FEAT])); late_new=(act>newp)
        # uniform shift with equal mean promise
        s=newp.mean()-cur.mean(); late_u=(act>cur+s)
        dl=lambda i:(late_new[i].mean()-curlate[i].mean())
        dp=lambda i:(newp[i].mean()-cur[i].mean())
        du=lambda i:(late_new[i].mean()-late_u[i].mean())
        l1=boot(dl,n,300); l2=boot(dp,n,300); l3=boot(du,n,300)
        print(f" q={q:.2f}: trễ hiện tại {curlate.mean():.3f} -> mới {late_new.mean():.3f} (Δ {late_new.mean()-curlate.mean():+.3f} [{l1[0]:+.3f},{l1[1]:+.3f}]) | hứa TB {cur.mean():.1f} -> {newp.mean():.1f} (Δ {newp.mean()-cur.mean():+.1f} [{l2[0]:+.1f},{l2[1]:+.1f}]) | so với dịch đều cùng độ dài hứa: trễ {late_u.mean():.3f}, Δ {late_new.mean()-late_u.mean():+.3f} [{l3[0]:+.3f},{l3[1]:+.3f}]")
