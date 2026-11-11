# Nguồn của các công thức và kỹ thuật trong DSS nhập hàng

Tài liệu này liệt kê từng công thức, kỹ thuật trong mã DSS, nguồn của nó, và với phần không có paper thì ghi rõ lý do nhóm
chọn. Mục đích là để người đọc báo cáo kiểm tra lại được.

**Ký hiệu trạng thái xác minh**

| Ký hiệu | Nghĩa |
|---|---|
| ✅ | Đã mở nguồn gốc (PDF hoặc trang web) và đối chiếu trực tiếp với công thức hoặc câu chữ |
| 📚 | Kỹ thuật chuẩn, trích dẫn từ kiến thức chung. **Chưa mở lại nguồn** khi viết tài liệu này, nên cần tự kiểm tra trước khi đưa vào báo cáo |
| 🛠️ | Lựa chọn của nhóm, không có paper. Lý do ghi ngay tại chỗ |

Vị trí mã: `backend/app/features/dss/forecast.py` (viết tắt `forecast.py`) và `backend/app/features/dss/routes.py`
(viết tắt `routes.py`).

---

## 1. Lượng nhập hàng: đệm bằng phân vị của sai số

### 1.1. Tồn an toàn là phân vị của sai số dự báo ✅

- **Mã:** `order_plan`, `_buffer`, `_quantile` (`forecast.py:101-122`).
- **Công thức trong mã** (với lead time L = 1 tháng):

  ```text
  e        = thực tế − dự báo                 (cùng đơn vị món hoặc R$)
  đệm      = phân vị mức `service` của các e  (nội suy tuyến tính)
  lượng nhập = max(dự báo tháng tới + đệm, 0)
  ```
- **Nguồn:** J. R. Trapero, M. Cardós, N. Kourentzes, *Empirical safety stock estimation based on kernel and GARCH models*,
  **Omega** 84 (2019), 199–211.
  [DOI](https://doi.org/10.1016/j.omega.2018.05.004) ·
  [bản accepted (Lancaster)](https://eprints.lancs.ac.uk/id/eprint/125041/1/empirical_safety_stock.pdf)
- **Đối chiếu trong bài** (đọc từ PDF bản accepted):
  - Mục 2, **phương trình (2)**: `SS = Q_L(CSL)`, "where Q_L(CSL) is the forecast error quantile at the probability
    defined by CSL". Câu dẫn vào: "If the statistical distribution of the error is unknown, empirical non-parametric
    methods can be used instead."
  - Mục 3.2: sai số trên lead time `e_t(L) = y_L − F_L = Σ y_{t+h} − Σ F_{t+h}`. Tức là **thực tế trừ dự báo**, cùng dấu
    với `e` trong mã. Với L = 1, tổng chỉ còn một số hạng.
  - Mục 5.2: chính sách newsvendor, trong đó mức đặt hàng là phân vị của nhu cầu trên lead time ứng với CSL mục tiêu.
    Vì vậy "lượng nhập = dự báo + đệm" là cách viết tương đương: dự báo cộng phân vị của sai số.
- **Khác biệt so với bài, cần nói thẳng khi trình bày:**

  | | Bài báo | DSS này |
  |---|---|---|
  | Lead time | 1 tuần và 4 tuần | 1 tháng |
  | Mẫu sai số | 173 tuần × 229 sản phẩm | khoảng 12 đến 14 tháng, một chuỗi |
  | Dự báo điểm | SES | blend của naive và Holt |
  | Đơn vị | nhu cầu trên lead time | số món hoặc R$ theo tháng |

### 1.2. Phân vị nội suy tuyến tính ✅ (bài) và 📚 (numpy)

- **Mã:** `np.quantile(..., method="linear")` (`forecast.py:101-102`).
- **Nguồn:** Omega 84, mục **4.2.2 "Empirical percentile"**: "the requested value is typically linearly interpolated from
  the available values". Bài tính bằng hàm `prctile` của MATLAB.
- **Phía numpy:** `method="linear"` tương ứng định nghĩa type 7 trong Hyndman & Fan (1996), *Sample quantiles in
  statistical packages*, The American Statistician 50(4). [Tài liệu numpy](https://numpy.org/doc/stable/reference/generated/numpy.quantile.html) 📚

### 1.3. Các mức 85%, 90%, 95%, 99% ✅

- **Mã:** `SERVICE_LEVELS` (`forecast.py:127`); mặc định 90% (`routes.py`, hàm `forecast`).
- **Nguồn:** Omega 84, mục 5.2: "the target CSL values are set to 85%, 90%, 95% and 99% for both simulations and real
  data". Bài IJF cùng nhóm tác giả cũng dùng đúng bốn mức này ở mục 4.3:
  Trapero, Cardós, Kourentzes, *Quantile forecast optimal combination to enhance safety stock estimation*,
  International Journal of Forecasting 35(1) (2019), 239–250.
  [DOI](https://doi.org/10.1016/j.ijforecast.2018.05.009) ·
  [PDF](https://eprints.lancs.ac.uk/id/eprint/125342/1/Trapero_2018_quantile_forecast_optimal.pdf)
- Bài IJF còn nói mức doanh nghiệp thường nhắm tới "typically between 85% and 99%".
- **Mặc định 90%:** 🛠️ nằm giữa dải 85 đến 99% của bài, không có lý do định lượng nào khác. Người dùng đổi được trên giao diện.

### 1.4. Đường đánh đổi thiếu hàng và dư hàng 🛠️ (có cơ sở khái niệm trong bài ✅)

- **Mã:** `tradeoff` (`forecast.py:130-161`).
- **Cách làm (leave-one-out):** với mỗi tháng t trong backtest, đệm chỉ học từ các tháng **khác** t. Lượng nhập của tháng
  đó là dự báo tháng đó cộng đệm. Sau đó đếm tỷ lệ tháng thiếu hàng (`thực tế > lượng nhập`), mức dư (`max(nhập − thực tế, 0) / thực tế`),
  mức thiếu (`max(thực tế − nhập, 0) / thực tế`).
- **Cơ sở trong bài ✅:** mục 5.2 định nghĩa "achieved CSL" là tỷ lệ lần mà nhu cầu thực tế rơi dưới phân vị đã ước lượng, và
  dùng đường đánh đổi giữa CSL, inventory investment và backorders. Ý tưởng "đo tỷ lệ thiếu hàng thực tế thay vì tin vào mức danh nghĩa"
  là của bài.
- **Phần tự đặt 🛠️:** bài đo trên tập hold-out. DSS này chỉ có khoảng 12 đến 14 tháng, không đủ để chia hold-out, nên
  nhóm dùng leave-one-out để mỗi tháng đều được dùng mà không tự học từ chính nó. Đây là cách làm của nhóm, không có paper.
- **Kết quả không nên đọc quá mức:** ở mức 90%, tỷ lệ thiếu hàng đo được là 16,7% (2 trên 12 tháng), cao hơn mức danh nghĩa.

### 1.5. Những điều bài báo tự nói, hỗ trợ cho các giới hạn của DSS ✅

- Mục 6.1: "the percentile method is more sensitive to small sample sizes" (phân vị nhạy hơn với mẫu nhỏ).
- Mục 6.1: ở mức 99%, phân vị thực nghiệm cho CSL thấp hơn mục tiêu, kéo theo nhiều backorder hơn.
- Mục 8: nếu có đủ dữ liệu nhưng dự báo là kết hợp nhiều phương pháp, bài đề xuất cách tiếp cận thực nghiệm. Điều kiện
  "if sufficient data are available" **không thỏa** ở DSS này (12 đến 14 điểm), nên kết quả chỉ là ước lượng thô.

---

## 2. Các mô hình dự báo (`forecast_all`, `forecast.py:59-65`)

### 2.1. Naive (tháng trước) 📚

- **Mã:** `naive = y[-1]`.
- **Nguồn:** Hyndman & Athanasopoulos, *Forecasting: Principles and Practice* (3rd ed.), mục "Some simple forecasting
  methods". [Link](https://otexts.com/fpp3/simple-methods.html)
- **Lý do dùng:** làm baseline. Mọi mô hình phức tạp hơn phải hơn nó mới có giá trị. Trên giao diện, WAPE được ghi cạnh baseline này.

### 2.2. Trung bình 3 tháng (ma3) 📚

- **Mã:** `ma3 = mean(y[-3:])`.
- **Nguồn:** cùng chương trên (average method, áp dụng trên 3 quan sát gần nhất, tức moving average).
- **Lý do dùng:** baseline thứ hai, ít nhiễu hơn naive. **Không thuộc blend**, chỉ xuất hiện trong bảng so sánh mô hình
  như một lựa chọn trong ô "Cách dự báo". Kết quả cho thấy ma3 có WAPE toàn kho thấp nhất (11,1%), điều này nên được nói thẳng.
- **Số 3:** 🛠️ độ dài cửa sổ phổ biến cho chuỗi tháng, không có lý do định lượng.

### 2.3. Holt suy giảm xu hướng (damped trend) ✅

- **Mã:** `_holt_run`, `holt_forecast` (`forecast.py:30-56`):

  ```text
  dự báo 1 bước: ŷ(t+1) = ℓ_t + φ · b_t
  mức:           ℓ_t = α · y_t + (1 − α) · (ℓ_{t−1} + φ · b_{t−1})
  xu hướng:      b_t = β* · (ℓ_t − ℓ_{t−1}) + (1 − β*) · φ · b_{t−1}
  ```
- **Nguồn:** Hyndman & Athanasopoulos, *Forecasting: Principles and Practice* (3rd ed.), mục 8.2 "Damped trend methods".
  [Link](https://otexts.com/fpp3/holt.html) ✅ Ba phương trình trên trang này khớp với mã. Với h = 1, hệ số của b_t là φ.
  Gốc của phương pháp là Gardner & McKenzie (1985), *Forecasting trends in time series*, Management Science 31(10),
  1237–1246. 📚
- **Phần tự đặt 🛠️ (không có trong nguồn):**
  - Lưới tham số `α ∈ {0.2, 0.4, 0.6, 0.8, 0.95}`, `β ∈ {0.05, 0.1, 0.2, 0.4}`, `φ ∈ {0.8, 0.9, 0.98}`, chọn bộ có
    SSE dự báo 1 bước nhỏ nhất trên lịch sử. **Lý do:** tự cài bằng numpy để không thêm thư viện `statsmodels` và không phụ
    thuộc bộ tối ưu, dễ giải thích; lưới nhỏ vì chuỗi chỉ khoảng 20 điểm. Chọn tham số bằng cách cực tiểu SSE là thông
    lệ trong tài liệu dự báo, nhưng dùng lưới thay vì tối ưu liên tục là lựa chọn của nhóm.
  - Khởi tạo: `mức = y[0]`, `xu hướng = (y[k] − y[0]) / k` với `k = min(3, n − 1)`. **Lý do:** cách khởi tạo đơn giản, không
    cần tối ưu thêm; nhưng không lấy từ nguồn.
  - Nếu có dưới 3 điểm thì trả giá trị cuối cùng; kết quả bị chặn dưới ở 0 (nhu cầu không âm).
  - Script thăm dò `06_demand_forecast_backtest.py` dùng Holt của `statsmodels` nên số hơi lệch với số chính thức.

### 2.4. Blend = trung bình của naive và Holt 🛠️ (nguồn chỉ hỗ trợ một phần)

- **Mã:** `blend = (naive + holt) / 2` (`forecast.py:65`).
- **Nguồn hỗ trợ:** Smith & Wallis, *A Simple Explanation of the Forecast Combination Puzzle*, Oxford Bulletin of
  Economics and Statistics 71(3) (2009), 331–355. [DOI](https://doi.org/10.1111/j.1468-0084.2008.00541.x) ✅ thông tin
  thư mục. Bài chỉ nói: với mẫu hữu hạn, trọng số ước lượng từ dữ liệu bị nhiễu, nên chia đều thường tốt hơn trọng số ước lượng.
  **Bài không chứng minh rằng 50/50 tốt hơn từng mô hình riêng.** (Kết luận này đã được ghi trong `dss_danh_gia_de_xuat.md` mục 5.1.)
- **Lý do nhóm chọn blend (🛠️):**
  1. Chọn **trước** khi xem kết quả theo từng mức, theo quy ước "kết hợp thường bền".
  2. Kết quả backtest ủng hộ: blend có WAPE thấp nhất ở 2 trên 3 mức tổng hợp (bang 12,9% và danh mục 20,0%).
  3. Hai mô hình lệch ngược chiều (Holt lệch cao khoảng +3,9%, naive lệch thấp khoảng −3,9% ở toàn kho), nên trung bình kéo bias về 0.
  4. Đơn giản, không có hệ số phải ước lượng.
- **Hạn chế:** ở toàn kho blend (11,2%) gần như ngang ma3 (11,1%); khác biệt không đáng kể.

---

## 3. Backtest và đo sai số

### 3.1. Backtest trượt theo thời gian (rolling origin) 📚

- **Mã:** `backtest` (`forecast.py:68-73`): ở mỗi tháng t từ `MIN_TRAIN`, dự báo `values[t]` chỉ từ `values[:t]`.
- **Nguồn:** Hyndman & Athanasopoulos, FPP3, mục "Time series cross-validation". [Link](https://otexts.com/fpp3/tscv.html)
  Cùng ý tưởng được Tashman (2000), *Out-of-sample tests of forecasting accuracy*, International Journal of Forecasting 16(4), 437–450, gọi là rolling origin. 📚
- **Lý do dùng:** chuỗi thời gian không được xáo trộn hay kiểm tra trên dữ liệu đã dùng để học. Mỗi dự báo chỉ dùng thông tin
  có tại thời điểm đó, giống tình huống thật.

### 3.2. WAPE 🛠️ (định nghĩa chuẩn, không có nguồn trong repo)

- **Mã:** `model_metrics` (`forecast.py:80-90`): `WAPE = Σ|thực tế − dự báo| / Σ thực tế`.
  Kèm `MAPE = mean(|thực tế − dự báo| / max(thực tế, 1))` và `bias = (Σ dự báo − Σ thực tế) / Σ thực tế`.
- **Nguồn:** không có paper được kiểm tra cho định nghĩa này. Đây là thước đo sai số phần trăm có trọng số theo
  khối lượng, còn gọi là tỷ lệ MAD/mean (📚, cần tự tìm nguồn nếu muốn trích).
- **Lý do chọn (🛠️):**
  1. Không bị phình khi một chuỗi nhỏ có tháng gần 0 (MAPE sẽ bị; mã phải chặn mẫu số ở 1 cho MAPE).
  2. Cộng gộp được qua nhiều bang và danh mục trong một con số duy nhất.
  3. Người ra quyết định đọc được ngay: "lệch trung bình khoảng 11%".
- **Giới hạn cần biết:** Hyndman & Koehler (2006), *Another look at measures of forecast accuracy*, International Journal of
  Forecasting 22(4), 679–688 ([DOI](https://doi.org/10.1016/j.ijforecast.2006.03.001), ✅ thông tin thư mục) khuyến nghị
  sai số tỷ lệ theo thang (MASE) để so sánh qua nhiều chuỗi. Bài **không** định nghĩa WAPE, nên không dùng bài này làm
  nguồn cho công thức WAPE. Nếu bị hỏi "sao không dùng MASE", câu trả lời là: WAPE dễ giải thích hơn cho người nhập hàng
  và đủ để so sánh các mô hình trên cùng một chuỗi.

### 3.3. Không có chế độ tự chọn mô hình theo sai số thấp nhất 🛠️

- Phiên bản đầu có chế độ `auto` (hàm `pick_model`) chọn mô hình có WAPE thấp nhất trên backtest. Chế độ này **đã bị bỏ**.
- **Lý do:** (1) chọn và đo trên **cùng** các tháng nên số đo lạc quan; (2) mâu thuẫn với việc chọn `blend` làm mặc định
  trước khi xem kết quả; (3) sai số thấp nhất chưa hẳn là mô hình tốt nhất, chẳng hạn ở toàn kho ma3 (11,1%) chỉ hơn
  blend (11,2%) 0,1 điểm, nằm trong nhiễu của 14 tháng kiểm tra; (4) người dùng dễ hiểu nhầm đó là lựa chọn "tốt nhất".
  Người dùng vẫn tự chọn tay 4 mô hình và so sánh trong bảng chi tiết kỹ thuật.

---

## 4. Tham số do nhóm tự đặt

| Tham số | Giá trị | Vị trí | Lý do chọn | Kiểm tra độ nhạy |
|---|---|---|---|---|
| `MIN_TRAIN` | 6 | `forecast.py:22` | Cần đủ lịch sử để Holt khớp được, nhưng vẫn để lại khoảng 12 đến 14 tháng kiểm tra | Có. `docs/dss_exploration/07_min_train_sensitivity.py`: WAPE toàn kho 11,2% ở 6 và 7, 12,6% ở 3, 12,8% ở 10. Lượng nhập dao động khoảng ±5% |
| `MIN_ERRORS` | 3 | `forecast.py:93` | Dưới 3 sai số thì phân vị không có nghĩa, nên đệm = 0 | Không |
| `EVENT_MONTHS` | 2017-11, 2017-12 | `forecast.py:23` | Black Friday 2017 và tháng sau, là sự kiện chưa có tiền lệ trong dữ liệu, mọi mô hình hụt khoảng 31 đến 39% ở tháng này. Hệ thống báo cáo cả hai trường hợp, có và không có | Có (hai cột WAPE song song) |
| Cửa sổ lịch sử bắt đầu | 2017-01 | `routes.py:19` | 2016 quá thưa (có tháng không có đơn) | Không |
| Cửa sổ lịch sử kết thúc | tháng đầy đủ gần nhất | `routes.py:30-49` | Lấy từ dữ liệu thay vì gõ cứng | Không |
| `COMPLETE_MONTH_RATIO` | 0,3 | `routes.py:22` | Một tháng cuối chỉ được coi là đầy đủ nếu số món ≥ 30% trung vị, để tháng nạp dở không kéo dự báo xuống | Không |
| Số bang, danh mục lớn | 10 và 15 | `routes.py:26-27` | Đủ phủ phần lớn doanh thu mà vẫn đọc được trên một bảng | Không |
| Ngưỡng nhận xét "hơn baseline" | trên 2 điểm: tốt hơn; 0,5 đến 2: chỉ hơn; ±0,5: ngang; dưới −0,5: kém | `frontend/src/features/dss/format.ts:27-29` | Ngưỡng đặt tay để câu kết luận không khẳng định chênh lệch rất nhỏ là "tốt hơn". Không có cơ sở thống kê (chưa kiểm định ý nghĩa) | Không |

---

## 5. Dữ liệu và thiết kế kho

### 5.1. Nguồn dữ liệu 📚

- Olist Brazilian E-Commerce Public Dataset (Kaggle).
  [Link](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). Mô tả cột và thống kê nằm trong `docs/DATASET.md`.

### 5.2. Mô hình sao và ETL 📚

- Kho dùng mô hình sao với `dim_date`, `dim_customer`, `dim_product`, `dim_seller`, `fact_customer_order`, `fact_sales`
  (`sql/dw/dss.sql`), và tầng staging trước khi nạp.
- **Nguồn lý thuyết:** R. Kimball, M. Ross, *The Data Warehouse Toolkit* (3rd ed., Wiley, 2013), tài liệu tham khảo [2] của đề bài. Chưa
  đối chiếu số chương cụ thể, cần bổ sung khi viết báo cáo.

### 5.3. View `dw.v_dss_monthly_demand` 🛠️

- Nhu cầu được định nghĩa là **số dòng hàng trong đơn `delivered`** (mỗi dòng `fact_sales` là một món), doanh thu là
  `sum(price)` (cùng thước đo "Doanh thu hàng" của OLAP), gom theo tháng × bang khách × danh mục.
- **Lý do:** đồng nhất với OLAP để đối soát được (`run_dss_01.py` so với `fact_sales`: 13.221.498,11 R$ và 110.197 món).
  Chỉ lấy `delivered` để loại đơn hủy, vì chưa giao thì chưa phải nhu cầu thực hiện được.
- **Giới hạn:** kho không có tồn kho, nên nhu cầu bị hụt hàng không thấy được; không có giá vốn hay biên lợi nhuận.

---

## 6. Các script thăm dò (bằng chứng cho việc đổi hướng DSS)

Các script nằm trong `docs/dss_exploration/`. Chúng chỉ dùng để quyết định đề tài, không phải phần của hệ thống. Các kỹ thuật
dùng trong đó là chuẩn, nhưng **chưa được mở lại nguồn** khi viết tài liệu này (📚):

| Kỹ thuật | Dùng ở | Nguồn gợi ý |
|---|---|---|
| K-means | `05_customer_kmeans.py`, `04_seller_segments.py` | MacQueen (1967); cài đặt scikit-learn |
| Silhouette | cùng hai file trên | Rousseeuw (1987), *Silhouettes: a graphical aid to the interpretation and validation of cluster analysis*, J. Comput. Appl. Math. 20, 53–65 |
| Adjusted Rand Index (ổn định bootstrap) | cùng hai file trên | Hubert & Arabie (1985), *Comparing partitions*, Journal of Classification 2, 193–218 |
| AUC | `02`, `03`, `05` | thước đo chuẩn cho phân loại nhị phân |
| Kiểm định chi-square giữa các cụm | `05` | thống kê chuẩn |

---

## 7. Tóm tắt trạng thái xác minh

| Nội dung | Trạng thái |
|---|---|
| `SS = Q_L(CSL)`, sai số `thực tế − dự báo`, phân vị nội suy, các mức 85/90/95/99% | ✅ đã đọc bản PDF Omega 84 (2019) |
| Bốn mức 85/90/95/99% và công thức tương tự trong bài IJF | ✅ đã đọc bản PDF |
| Ba phương trình Holt suy giảm | ✅ đã đối chiếu với FPP3 mục 8.2 |
| Smith và Wallis (2009), Hyndman và Koehler (2006) | ✅ thông tin thư mục; 📚 nội dung chưa đọc toàn văn |
| FPP3 (naive, cross-validation), Hyndman và Fan (1996), Gardner và McKenzie (1985), Tashman (2000), Kimball, Rousseeuw, Hubert và Arabie, MacQueen | 📚 chưa mở lại trong phiên này |
| WAPE, leave-one-out, lưới Holt, `MIN_TRAIN`, ngưỡng giao diện, blend 50/50 | 🛠️ lựa chọn của nhóm, có lý do ở trên |
