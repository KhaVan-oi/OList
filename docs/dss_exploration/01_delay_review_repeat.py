import sys, pandas as pd, numpy as np
d = sys.argv[1]
o = pd.read_csv(d+"/olist_orders_dataset.csv", parse_dates=["order_purchase_timestamp","order_delivered_customer_date","order_estimated_delivery_date"])
c = pd.read_csv(d+"/olist_customers_dataset.csv")
r = pd.read_csv(d+"/olist_order_reviews_dataset.csv")
o = o[o.order_status=="delivered"].dropna(subset=["order_delivered_customer_date"]).merge(c[["customer_id","customer_unique_id"]], on="customer_id")
o["delay"] = (o.order_delivered_customer_date - o.order_estimated_delivery_date).dt.days
o["late"] = o.delay>0
rv = r.sort_values("review_creation_date").groupby("order_id").review_score.last()
o = o.join(rv, on="order_id")
print("delivered w/ date:", len(o), "late rate: %.3f"%o.late.mean(), "review coverage: %.3f"%o.review_score.notna().mean())
print("review dist:\n", o.review_score.value_counts(normalize=True).sort_index().round(3))
print("avg review late vs ontime:", o.groupby("late").review_score.mean().round(2).to_dict())
print("avg review by delay bucket:\n", o.groupby(pd.cut(o.delay,[-999,-1,0,3,7,14,999])).review_score.agg(["mean","count"]).round(2))
# repeat within 180d of first order, only first orders with >=180d observation
o = o.sort_values("order_purchase_timestamp")
first = o.groupby("customer_unique_id").head(1).set_index("customer_unique_id")
second = o.groupby("customer_unique_id").order_purchase_timestamp.apply(lambda s: s.iloc[1] if len(s)>1 else pd.NaT)
first["second"] = second
end = o.order_purchase_timestamp.max()
f = first[first.order_purchase_timestamp <= end - pd.Timedelta(days=180)].copy()
f["rep180"] = (f.second - f.order_purchase_timestamp).dt.days <= 180
print("eligible first orders:", len(f), "repeat180 rate: %.4f"%f.rep180.mean())
f["rs"] = f.review_score
print("repeat180 by first-order review:\n", f.groupby("rs").rep180.agg(["mean","count"]).round(4))
print("repeat180 by late:\n", f.groupby("late").rep180.agg(["mean","count"]).round(4))
