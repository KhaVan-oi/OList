import sys, warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from sklearn.ensemble import HistGradientBoostingClassifier as HGC, HistGradientBoostingRegressor as HGR
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score
d = sys.argv[1]
P = lambda f: pd.read_csv(f"{d}/{f}")
o = P("olist_orders_dataset.csv")
for c in ["order_purchase_timestamp","order_approved_at","order_delivered_customer_date","order_estimated_delivery_date"]:
    o[c] = pd.to_datetime(o[c])
o = o[(o.order_status=="delivered")].dropna(subset=["order_delivered_customer_date","order_approved_at"])
cu = P("olist_customers_dataset.csv")[["customer_id","customer_zip_code_prefix","customer_state"]]
it = P("olist_order_items_dataset.csv")
pr = P("olist_products_dataset.csv")
se = P("olist_sellers_dataset.csv")
ge = P("olist_geolocation_dataset.csv")
ge = ge[(ge.geolocation_lat.between(-34,6))&(ge.geolocation_lng.between(-74,-34))]
ge = ge.groupby("geolocation_zip_code_prefix")[["geolocation_lat","geolocation_lng"]].mean()
it = it.merge(pr[["product_id","product_category_name","product_weight_g","product_length_cm","product_height_cm","product_width_cm"]], on="product_id", how="left")
it["vol"] = it.product_length_cm*it.product_height_cm*it.product_width_cm
g = it.sort_values("order_item_id").groupby("order_id")
first = g.head(1).set_index("order_id")[["seller_id","product_category_name"]]
agg = g.agg(n_items=("order_item_id","count"), price=("price","sum"), freight=("freight_value","sum"),
            weight=("product_weight_g","sum"), vol=("vol","sum"), n_sellers=("seller_id","nunique"))
df = o.merge(cu,on="customer_id").set_index("order_id").join(first).join(agg).reset_index().dropna(subset=["seller_id"])
df = df.merge(se,on="seller_id",how="left")
df = df.join(ge, on="customer_zip_code_prefix").rename(columns={"geolocation_lat":"clat","geolocation_lng":"clng"})
df = df.join(ge, on="seller_zip_code_prefix").rename(columns={"geolocation_lat":"slat","geolocation_lng":"slng"})
r=np.pi/180
a = np.sin((df.clat-df.slat)*r/2)**2+np.cos(df.slat*r)*np.cos(df.clat*r)*np.sin((df.clng-df.slng)*r/2)**2
df["dist"] = 6371*2*np.arcsin(np.sqrt(a))
pd_ = df.order_purchase_timestamp.dt.normalize()
df["promise"] = (df.order_estimated_delivery_date.dt.normalize()-pd_).dt.days
df["actual"] = (df.order_delivered_customer_date.dt.normalize()-pd_).dt.days
df["late"] = (df.actual>df.promise).astype(int)
df["month"] = df.order_purchase_timestamp.dt.month
df["dow"] = df.order_purchase_timestamp.dt.dayofweek
df["appr_lag"] = (df.order_approved_at-df.order_purchase_timestamp).dt.total_seconds()/3600
df["same_state"] = (df.seller_state==df.customer_state).astype(int)
df["freight_ratio"] = df.freight/df.price.replace(0,np.nan)
df["route"] = df.seller_state+">"+df.customer_state
print("orders:",len(df)," late rate %.3f"%df.late.mean())
print(df.groupby(df.order_purchase_timestamp.dt.to_period("Q")).late.agg(["mean","count"]).round(3).T.to_string())
tr = df[df.order_purchase_timestamp<"2018-03-01"].copy()
te = df[df.order_purchase_timestamp>="2018-04-01"].copy()
print(f"train {len(tr)} late {tr.late.mean():.3f} | test {len(te)} late {te.late.mean():.3f}")
# seller smoothed late rate from train only
gm = tr.late.mean(); k=20
s = tr.groupby("seller_id").late.agg(["sum","count"])
s["rate"]=(s["sum"]+k*gm)/(s["count"]+k)
for x in (tr,te): x["seller_rate"]=x.seller_id.map(s.rate).fillna(gm); x["seller_n"]=x.seller_id.map(s["count"]).fillna(0)
rt = tr.groupby("route").late.agg(["sum","count"]); rt["rate"]=(rt["sum"]+k*gm)/(rt["count"]+k)
for x in (tr,te): x["route_rate"]=x.route.map(rt.rate).fillna(gm)
cats = pd.concat([tr,te]).product_category_name.astype("category").cat.categories
for x in (tr,te): x["cat"]=pd.Categorical(x.product_category_name,categories=cats).codes
sets = {
 "promise only":["promise"],
 "+ route/state":["promise","same_state","route_rate"],
 "+ distance/freight/weight":["promise","same_state","route_rate","dist","freight","freight_ratio","weight","vol","price","n_items","cat"],
 "+ seller history":["promise","same_state","route_rate","dist","freight","freight_ratio","weight","vol","price","n_items","cat","seller_rate","seller_n"],
 "+ time/approval":["promise","same_state","route_rate","dist","freight","freight_ratio","weight","vol","price","n_items","cat","seller_rate","seller_n","month","dow","appr_lag","n_sellers"],
}
print("\nAUC theo tập đặc trưng (test theo thời gian):")
best=None
for n,f in sets.items():
    m = HGC(max_iter=200,learning_rate=0.06,random_state=0).fit(tr[f],tr.late)
    p = m.predict_proba(te[f])[:,1]
    top = te.assign(p=p).nlargest(len(te)//10,"p").late.mean()
    print(f"{n:28s} AUC {roc_auc_score(te.late,p):.3f}  PR-AUC {average_precision_score(te.late,p):.3f}  late-rate top10% {top:.3f} (lift {top/te.late.mean():.1f}x)")
    best=(m,f,p)
te["risk"]=best[2]
print("\nBaseline AUC chỉ dùng seller_rate:", round(roc_auc_score(te.late,te.seller_rate),3))
# Policy replay
print("\nChính sách ngày hứa (test). Hiện tại: late %.3f, hứa trung bình %.1f ngày"%(te.late.mean(),te.promise.mean()))
f=[c for c in sets["+ time/approval"] if c!="promise"]
rows=[]
for q in [0.80,0.85,0.90,0.93,0.95,0.97]:
    m=HGR(loss="quantile",quantile=q,max_iter=200,learning_rate=0.06,random_state=0).fit(tr[f],tr.actual)
    newp=np.ceil(m.predict(te[f]))
    rows.append((f"dự báo q={q:.2f}",(te.actual>newp).mean(),newp.mean()))
for k_ in [0,1,2,3,5,7,10]:
    rows.append((f"cộng đều +{k_} ngày",(te.actual>te.promise+k_).mean(),(te.promise+k_).mean()))
for thr in [0.5,0.3,0.2,0.1]:
    for k_ in [3,7,10]:
        flag=te.risk>thr; newp=te.promise+np.where(flag,k_,0)
        rows.append((f"cộng +{k_}d cho đơn risk>{thr} ({flag.mean():.0%} đơn)",(te.actual>newp).mean(),newp.mean()))
print(pd.DataFrame(rows,columns=["chính sách","tỷ lệ trễ","hứa TB (ngày)"]).round(3).to_string(index=False))
