import sys, warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from sklearn.ensemble import HistGradientBoostingRegressor as HGR
d=sys.argv[1]; P=lambda f: pd.read_csv(f"{d}/{f}")
o=P("olist_orders_dataset.csv"); o=o[o.order_status=="delivered"]; o["t"]=pd.to_datetime(o.order_purchase_timestamp)
c=P("olist_customers_dataset.csv")[["customer_id","customer_state"]]
it=P("olist_order_items_dataset.csv").merge(P("olist_products_dataset.csv")[["product_id","product_category_name"]],on="product_id",how="left")
x=it.merge(o[["order_id","customer_id","t"]],on="order_id").merge(c,on="customer_id")
x["cat"]=x.product_category_name.fillna("unknown")
x=x[(x.t>="2017-01-01")&(x.t<"2018-09-01")]
x["m"]=x.t.dt.to_period("M")
def panel(col,n):
    top=x.groupby(col).price.sum().nlargest(n).index
    p=x[x[col].isin(top)].pivot_table(index="m",columns=col,values="price",aggfunc="sum").fillna(0); return p
tot=x.groupby("m").price.sum().to_frame("total")
cats=panel("cat",15); sts=panel("customer_state",10)
print("tổng doanh thu theo tháng:"); print((tot.total/1000).round(0).astype(int).to_string())
def holt(y):
    y=np.asarray(y,float)+1
    try:
        m=ExponentialSmoothing(y,trend="add",damped_trend=True,initialization_method="estimated").fit()
        return max(m.forecast(1)[0]-1,0)
    except Exception: return y[-1]-1
def fc_single(y,i,idx):
    h=y[:i]; out={"naive":h[-1],"ma3":h[-3:].mean(),"holt":holt(h)}
    if i>=13: out["sn_ratio"]=h[-1]*(y[i-12]/max(y[i-13],1))
    out["ma3_x"]=h[-3:].mean()
    return out
def run(P_,name,test_start,seasonal=False):
    idx=list(P_.index); ts=idx.index(pd.Period(test_start)); rows=[]
    # pooled GBM (chỉ cho panel nhiều chuỗi)
    pooled = P_.shape[1]>1
    for i in range(ts,len(idx)):
        pred={}
        for j,cn in enumerate(P_.columns):
            y=P_[cn].values; pr=fc_single(y,i,idx)
            for k,v in pr.items(): pred.setdefault(k,{})[cn]=v
        if pooled:
            X=[];Y=[]
            for cn in P_.columns:
                y=P_[cn].values
                for t in range(4,i):
                    base=max(y[t-3:t].mean(),1)
                    X.append([y[t-1]/base,y[t-2]/base,y[t-3]/base,idx[t].month,np.log1p(base)]); Y.append(np.log1p(y[t])-np.log1p(base))
            m=HGR(max_iter=60,learning_rate=0.06,min_samples_leaf=5,random_state=0).fit(X,Y)
            pred["gbm"]={}
            for cn in P_.columns:
                y=P_[cn].values; base=max(y[i-3:i].mean(),1)
                f=[y[i-1]/base,y[i-2]/base,y[i-3]/base,idx[i].month,np.log1p(base)]
                pred["gbm"][cn]=max(np.expm1(m.predict([f])[0]+np.log1p(base)),0)
        for k,dct in pred.items():
            for cn,v in dct.items(): rows.append((str(idx[i]),k,cn,P_[cn].iloc[i],v))
    r=pd.DataFrame(rows,columns=["m","model","series","y","f"])
    return r
def report(r,title,drop=()):
    r=r[~r.m.isin(drop)]
    g=r.groupby("model").apply(lambda z: pd.Series({"WAPE":(z.y-z.f).abs().sum()/z.y.sum(),"MAPE":((z.y-z.f).abs()/z.y.clip(lower=1)).mean(),"thiên lệch":(z.f.sum()-z.y.sum())/z.y.sum(),"n":len(z)}))
    print(f"\n--- {title} ---"); print(g.sort_values("WAPE").round(3).to_string())
rt=run(tot,"total","2017-07"); report(rt,"TỔNG doanh thu, dự báo trước 1 tháng, test 2017-07..2018-08 (14 tháng)")
report(rt,"TỔNG, bỏ 2017-11 và 2017-12 (Black Friday và sau đó)",drop=("2017-11","2017-12"))
rt2=run(tot,"total","2018-02"); report(rt2,"TỔNG, test 2018-02..2018-08 (có thể so với seasonal ratio)")
print("\nTổng: sai số theo tháng của holt/naive/ma3 (%)")
pv=rt.assign(e=((rt.f-rt.y)/rt.y*100).round(1)).pivot(index="m",columns="model",values="e"); print(pv.to_string())
rc=run(cats,"cat","2017-07"); report(rc,"15 DANH MỤC lớn, test 2017-07..2018-08")
report(rc,"15 DANH MỤC, bỏ 2017-11/12",drop=("2017-11","2017-12"))
rs=run(sts,"state","2017-07"); report(rs,"10 BANG lớn, test 2017-07..2018-08")
report(rs,"10 BANG, bỏ 2017-11/12",drop=("2017-11","2017-12"))
# Tổng hợp từ dưới lên: tổng 15 danh mục có tốt hơn dự báo tổng không?
bu=rc[rc.model=="gbm"].groupby("m")[["y","f"]].sum(); print("\nTop-15 danh mục gộp (GBM) WAPE:",round((bu.y-bu.f).abs().sum()/bu.y.sum(),3), "| bỏ 11,12:",round((bu.drop(['2017-11','2017-12']).y-bu.drop(['2017-11','2017-12']).f).abs().sum()/bu.drop(['2017-11','2017-12']).y.sum(),3))
# Hằng tuần, tổng
w=x.set_index("t").price.resample("W-SUN").sum(); w=w["2017-01-08":"2018-08-26"]
rows=[]
for i in range(26,len(w)):
    h=w.values[:i]
    rows.append((str(w.index[i].date()),w.values[i],h[-1],h[-4:].mean(),holt(h)))
W=pd.DataFrame(rows,columns=["w","y","naive","ma4","holt"])
print("\n--- HẰNG TUẦN, tổng doanh thu, dự báo trước 1 tuần ---")
for m_ in ["naive","ma4","holt"]:
    print(m_,"WAPE",round((W.y-W[m_]).abs().sum()/W.y.sum(),3),"| bỏ tuần 2017-11 và 2017-12:",round((lambda z:(z.y-z[m_]).abs().sum()/z.y.sum())(W[~W.w.str.startswith(("2017-11","2017-12"))]),3))
