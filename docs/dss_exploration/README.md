# Script thăm dò để chọn đề tài DSS

Các script này đọc trực tiếp CSV gốc của Olist, không đụng vào kho. Dùng làm bằng chứng cho
[../dss_ly_do_chuyen_huong.md](../dss_ly_do_chuyen_huong.md). Đây là mã thăm dò, không phải phần của hệ thống.

```text
python -I -X utf8 <script>.py "<thư mục chứa các file olist_*.csv>"
```

Cần `pandas`, `numpy`, `scikit-learn`; script 06 cần thêm `statsmodels`. Script 06 dùng Holt của `statsmodels`, còn
hệ thống DSS tự cài Holt trong `backend/app/features/dss/forecast.py`, nên con số của hai bên lệch nhẹ. Số trong hệ
thống mới là số chính thức.

| File | Câu hỏi |
|---|---|
| `01_delay_review_repeat.py` | Giao trễ và review có liên quan đến việc khách mua lại không? |
| `02_late_delivery_model.py` | Dự đoán được đơn bị trễ không, và chính sách ngày hứa theo phân vị ra sao (một mốc chia)? |
| `03_late_policy_robustness.py` | Kết quả trên có bền khi chia nhiều giai đoạn không (kèm bootstrap)? |
| `04_seller_segments.py` | Phân khúc seller có ổn định theo thời gian không, và loại seller kém có đáng không? |
| `05_customer_kmeans.py` | K-means trên thông tin đơn đầu có dự đoán được mua lại không? |
| `06_demand_forecast_backtest.py` | Dự báo nhu cầu theo tháng chính xác đến đâu so với baseline đơn giản? |
