import sys, warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score, adjusted_rand_score
d=sys.argv[1]; P=lambda f: pd.read_csv(f"{d}/{f}")
o=P("olist_orders_dataset.csv")
for c in ["order_purchase_timestamp","order_delivered_customer_date","order_estimated_delivery_date"]: o[c]=pd.to_datetime(o[c])
o=o[o.order_status=="delivered"].dropna(subset=["order_delivered_customer_date"])
o["late"]=(o.order_delivered_customer_date.dt.normalize()>o.order_estimated_delivery_date.dt.normalize()).astype(int)
rv=P("olist_order_reviews_dataset.csv").sort_values("review_creation_date").groupby("order_id").review_score.last()
it=P("olist_order_items_dataset.csv")
x=it.merge(o[["order_id","order_purchase_timestamp","late"]],on="order_id").join(rv,on="order_id")
x["low"]=(x.review_score<=2).astype(float); x.loc[x.review_score.isna(),"low"]=np.nan
x["fr"]=x.freight_value/x.price.replace(0,np.nan)
print("dòng hàng:",len(x),"seller:",x.seller_id.nunique())
def stats(df):
    g=df.groupby("seller_id")
    return pd.DataFrame({"n":g.order_id.nunique(),"rev":g.price.sum(),"late":g.late.mean(),"rev_score":g.review_score.mean(),"low":g.low.mean(),"fr":g.fr.median()})
def run(split,minn):
    print(f"\n######## Chia tại {split}, ngưỡng >= {minn} đơn ở giai đoạn 1 ########")
    a=x[x.order_purchase_timestamp<split]; b=x[x.order_purchase_timestamp>=split]
    A=stats(a); B=stats(b); A=A[A.n>=minn]
    both=A.join(B,rsuffix="_2",how="inner"); both=both[both.n_2>=10]
    print(f"seller đủ điều kiện GĐ1: {len(A)} ({A.rev.sum()/a.price.sum():.0%} doanh thu GĐ1); có ≥10 đơn ở GĐ2: {len(both)}")
    for m in ["late","rev_score","low"]:
        print(f"  tương quan hạng GĐ1→GĐ2 của {m}: Spearman {both[m].corr(both[m+'_2'],method='spearman'):.2f}")
    # curve
    A["score"]=A.late.rank(pct=True)+A.low.rank(pct=True)-A.rev_score.rank(pct=True)
    totb=b.price.sum(); rng=np.random.default_rng(0)
    bs=b.merge(A[["score","late"]].rename(columns={"late":"l1"}),left_on="seller_id",right_index=True,how="left")
    def curve(order_index):
        rows=[]; ranked=pd.Series(range(len(order_index)),index=order_index)
        rb=bs.copy(); rb["rank"]=rb.seller_id.map(ranked)
        out={}
        for share in [0.01,0.02,0.05,0.10,0.15]:
            # chọn seller theo thứ tự đến khi tổng doanh thu GĐ2 của họ >= share
            rev2=B.rev.reindex(order_index).fillna(0).cumsum(); k=(rev2<share*totb).sum()+1
            S=set(order_index[:k]); keep=b[~b.seller_id.isin(S)]
            out[share]=(len(S),1-keep.price.sum()/totb,keep.late.mean(),keep.review_score.mean())
        return out
    base_late=b.late.mean(); base_rs=b.review_score.mean()
    print(f"  GĐ2 hiện tại: trễ {base_late:.3f}, review TB {base_rs:.2f}")
    methods={"xếp hạng điểm tổng hợp GĐ1":A.sort_values("score",ascending=False).index,
             "chỉ tỷ lệ trễ GĐ1":A.sort_values("late",ascending=False).index,
             "chỉ review thấp GĐ1":A.sort_values("rev_score").index}
    res={k:curve(v) for k,v in methods.items()}
    # random baseline
    rnd={s:[] for s in [0.01,0.02,0.05,0.10,0.15]}
    for _ in range(60):
        idx=pd.Index(rng.permutation(A.index)); c=curve(idx)
        for s in rnd: rnd[s].append(c[s][2:])
    # oracle: rank seller GĐ2 (chỉ seller GĐ1) theo late GĐ2
    Bq=B.reindex(A.index).dropna(subset=["late"]); Bq=Bq[Bq.n>=10]
    oracle=curve(Bq.sort_values("late",ascending=False).index)
    print("  doanh thu GĐ2 bị mất | trễ & review còn lại (seller loại / trễ / review)")
    for s in [0.01,0.02,0.05,0.10,0.15]:
        line=f"  {s:>4.0%} | "
        for k,v in res.items(): line+=f"{k[:14]}: {v[s][0]}sl {v[s][2]:.3f}/{v[s][3]:.2f}  "
        r=np.mean(rnd[s],axis=0); line+=f"| ngẫu nhiên {r[0]:.3f}/{r[1]:.2f} | oracle {oracle[s][2]:.3f}/{oracle[s][3]:.2f}"
        print(line)
    return a,b,A,B
a,b,A,B=run("2018-01-01",30)
run("2017-10-01",20)
# K-means trên GĐ1 (split 2018-01-01)
print("\n######## K-means phân khúc seller (GĐ1, >=30 đơn) ########")
F=["late","rev_score","low","fr"]
Z=A.dropna(subset=F+["n"]).copy(); Z["lg"]=np.log1p(Z.n)
feat=F+["lg"]; sc=StandardScaler().fit(Z[feat]); X=sc.transform(Z[feat])
for k in range(2,8):
    km=KMeans(k,n_init=10,random_state=0).fit(X); print(f"k={k} silhouette {silhouette_score(X,km.labels_):.3f}")
K=4; km=KMeans(K,n_init=20,random_state=0).fit(X); Z["c"]=km.labels_
# bootstrap ổn định
rng=np.random.default_rng(1); aris=[]
for _ in range(50):
    i=rng.integers(0,len(X),len(X)); kb=KMeans(K,n_init=5,random_state=0).fit(X[i]); aris.append(adjusted_rand_score(km.labels_,kb.predict(X)))
print(f"độ ổn định bootstrap (ARI) k={K}: TB {np.mean(aris):.2f}, 5%-95% [{np.percentile(aris,5):.2f},{np.percentile(aris,95):.2f}]")
print("hồ sơ cụm trên GĐ1:")
print(Z.groupby("c").agg(sl=("n","size"),don=("n","sum"),rev=("rev","sum"),late=("late","mean"),score=("rev_score","mean"),low=("low","mean"),fr=("fr","mean")).round(3).to_string())
# GĐ2: gán cụm GĐ1 rồi xem chỉ số GĐ2 của cụm
B2=B.reindex(Z.index); B2["c"]=Z.c; B2=B2[B2.n>=10]
print("cùng các seller, chỉ số ở GĐ2 (cụm cố định từ GĐ1):")
print(B2.groupby("c").agg(sl=("n","size"),late=("late","mean"),score=("rev_score","mean"),low=("low","mean")).round(3).to_string())
# phân khúc lại độc lập ở GĐ2 và so ARI
Z2=B.reindex(Z.index).dropna(subset=F); Z2=Z2[Z2.n>=10]; Z2["lg"]=np.log1p(Z2.n)
X2=StandardScaler().fit_transform(Z2[feat]); l2=KMeans(K,n_init=20,random_state=0).fit_predict(X2)
print(f"ARI giữa phân cụm GĐ1 và phân cụm độc lập GĐ2 (cùng seller, n={len(Z2)}): {adjusted_rand_score(Z.loc[Z2.index,'c'],l2):.2f}")
