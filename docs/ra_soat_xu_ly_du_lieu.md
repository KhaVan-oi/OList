# Rà soát xử lý dữ liệu (12/11/2026)

Tài liệu ghi lại đợt rà soát toàn bộ luồng dữ liệu CSV → staging → kho sao → OLAP → DSS → API. Mỗi mục nêu: vấn đề,
bằng chứng (số đo trên kho), cách sửa, nguồn hoặc lý do. Ký hiệu nguồn giống `dss_nguon_tham_khao.md`:
✅ đã đối chiếu nguồn, 📚 nguồn chuẩn nhưng chưa mở lại toàn văn (cần tự kiểm trước khi đưa vào báo cáo),
🛠️ lựa chọn của nhóm, lý do ghi tại chỗ.

Mọi số dưới đây đo trên kho sau **một lần chạy `python etl_pipeline.py` đầy đủ** (PostgreSQL 16, Docker, cổng 5433).

## 1. Những gì đã đúng và giữ nguyên

| Phần | Nhận xét |
|---|---|
| Staging `raw_*` (TEXT) → `stg_*` (có kiểu, PK/FK) | Đúng thông lệ tách tầng thô và tầng chuẩn hóa; có kiểm tra số dòng raw = stg |
| Hai fact tách grain: `fact_sales` (dòng hàng), `fact_customer_order` (đơn) | Tránh nhân bản tiền khi một đơn có nhiều món và nhiều lượt thanh toán (Kimball & Ross 2013, nguyên tắc khai báo grain) 📚 |
| Địa lý trên đơn, không trên `dim_customer` | Một `customer_unique_id` có thể giao về nhiều bang (37 khách), gắn vào dim sẽ sai lịch sử |
| OLAP 02/03: đếm `DISTINCT` đúng grain, ghi rõ độ đo phi cộng gộp | Đối soát `run_olap_02.py`: nền = roll-up = drill = cộng bang = cộng thành phố (PASS) |
| Chỉ lấy đơn `delivered` cho doanh thu và DSS | Tỷ lệ delivered theo tháng mua ổn định 96–98% đến 2018-08, nên **không** có hiện tượng "đơn gần cuối chưa kịp giao" làm méo chuỗi DSS (đã đo) |
| DSS: backtest trượt, đệm = phân vị sai số (Trapero và cộng sự 2019) | Giữ nguyên; xem `dss_nguon_tham_khao.md` |

## 2. Đã sửa

### 2.1. Tăng trưởng năm / quý so sánh hai kỳ khác số tháng (lỗi số liệu)

**Vấn đề.** Dữ liệu delivered chỉ phủ 2016-09..2018-08 và thiếu hẳn 2016-11. Code cũ lấy tổng cả kỳ chia tổng cả
kỳ trước:

| Chỉ số (doanh thu hàng) | Cách cũ | So cùng kỳ |
|---|---|---|
| 2018 (T1–T8) so với 2017 | +21,05% (so với cả 12 tháng 2017) | **+141,13%** (so với T1–T8/2017: 2.993.456 → 7.218.125 R$) |
| Quý 3/2018 (chỉ T7–T8) so với quý 2/2018 | khoảng −39% | **−12,53%** (T7–T8 so với T4–T5) |
| Tài liệu cũ ghi "2018 tăng +13,04%" | sai cả con số gốc (6,10M / 6,90M) | doanh thu đúng: 5.962.902,01 / 7.218.125,12 R$ |

**Cách sửa.** Giữ tổng của kỳ, nhưng tăng trưởng chỉ tính trên các tháng có ở cả hai kỳ:

```text
YoY(Y) = Σ_{m∈M} X(Y,m) / Σ_{m∈M} X(Y−1,m) − 1      M = tháng lịch có dữ liệu ở cả Y và Y−1
QoQ(q) = tương tự, ghép tháng thứ k của quý q với tháng thứ k của quý liền trước
```

Mỗi dòng trả thêm `months_with_data`, `months_compared`, `is_partial`. Giao diện hiện hai cột số tháng và một dòng
giải thích. Mã: `backend/app/features/sales_time/growth.py` (dùng chung cho mọi route màn Thời gian, route giảm từ
1.209 xuống 711 dòng) và `sql/olap/01_sales_time.sql` phần 2 + 3.

**Nguồn.**
- INSEE (Viện Thống kê Pháp), định nghĩa *Year on year change*: với số liệu quý, đó là "the change (as a %) obtained
  between the level of the variable in Q and its level in the same quarter of the previous year (Q-4)". Tức là so với
  **cùng kỳ** năm trước, không so với tổng cả năm.
  <https://www.insee.fr/en/metadonnees/definition/c1373> 📚 (trích từ kết quả tìm kiếm, trang không mở được lúc viết)
- OECD, *Data and Metadata Reporting and Presentation Handbook* (2007), mục thuật ngữ: "Year-on-year growth rates
  (YoY) are rates of change expressed over the corresponding period (month or quarter in relation to the frequency
  of the data) of the previous year." 📚 (chưa mở bản gốc)
- **Lý do 🛠️ khi áp vào kỳ năm không đủ tháng:** hai nguồn trên định nghĩa YoY trên cùng một kỳ. Với năm thiếu tháng,
  cách nhất quán với định nghĩa là cộng đúng các tháng tương ứng. Nếu chia tổng 8 tháng cho tổng 12 tháng, tỷ lệ chứa
  hai thành phần lẫn nhau: tăng trưởng thật và hệ số 8/12.

**Lưu ý khi trình bày:** 2017 so với 2016 ra +4.796% (trên 3 tháng cùng kỳ). Đúng về số học, nhưng 2016 chỉ là giai
đoạn khởi động với vài đơn mỗi tháng, nên con số không mang ý nghĩa kinh doanh. Đây cũng là lý do DSS bắt đầu lịch
sử từ 2017-01.

**Sửa kèm:**
- Khi lọc theo năm, QoQ của quý 1 và MoM của tháng 1 từng bị NULL vì LAG chạy sau bộ lọc. Nay LAG tính trên toàn
  chuỗi rồi mới lọc.
- Pivot 8b trong SQL dùng `COALESCE(…, 0)` nên sinh MoM −100% giả ở tháng dữ liệu kết thúc (2018-09). Nay giữ NULL,
  nhất quán với phần 1.
- Comment phần 1 ghi "tháng thiếu → 0" nhưng code giữ NULL: đã sửa comment.

### 2.2. DSS: WAPE thiếu nguồn, kết luận "hơn baseline" không có thước đo chuẩn

- **WAPE** = Σ|e| / Σ thực tế chính là tỷ số MAD/Mean của Kolassa & Schütz (2007), *Foresight* 6, 40–43. 📚
  Công thức không đổi, chỉ bổ sung nguồn.
- **Thêm MASE** (Hyndman & Koehler 2006, *IJF* 22(4), 679–688): sai số chia MAE của naive một bước trong mẫu. Trong
  backtest trượt, mẫu số ở tháng t chỉ dùng `values[:t]`, nên không rò rỉ thông tin tương lai (có unit test).
- Kết quả (số món, blend so với naive): toàn kho 0,88 so với 0,97; 10 bang 1,01 so với 1,12; 15 danh mục 1,23 so
  với 1,27. Ở mức bang và danh mục, chính naive cũng có MASE > 1, vì giai đoạn kiểm tra biến động mạnh hơn lịch sử.
  Vì vậy **so MASE giữa các mô hình**, không so với mốc 1.
- WAPE, lượng nhập (7.518,82 món) và đường đánh đổi không đổi. Thay đổi chỉ thêm thông tin.
- Không thêm kiểm định Diebold–Mariano: chỉ có 12–14 tháng kiểm tra, kiểm định gần như luôn ra "chưa đủ bằng chứng",
  và cần thêm thư viện `scipy`.

### 2.3. Nghiệm thu kho: logic kiểm tra nằm hai nơi, có điều kiện gõ cứng

| Trước | Sau |
|---|---|
| `03_validate.sql` và `run_acceptance_tests()` trong Python mỗi bên tự viết lại các kiểm tra; bản Python in "F1 → F8" nhưng **không có F1** | `03_validate.sql` là nguồn kiểm tra duy nhất (sai là RAISE EXCEPTION, ETL rollback). Python chỉ chạy file đó và in số đối soát, có F1 |
| F4 bắt buộc "đúng 1 đơn thiếu thanh toán", tức gõ cứng một đặc điểm của bộ dữ liệu | Kiểm tra bất biến: đơn có thanh toán NULL thì nguồn thật sự không có dòng thanh toán. Số đơn như vậy (hiện là 1) chỉ được báo bằng NOTICE |
| `check_acceptia.py` (sai chính tả) bắt lỗi rồi vẫn thoát mã 0 | `check_acceptance.py` thoát mã 1 khi nghiệm thu sai |
| Câu chữ "ĐẠT CHUẨN XUẤT SẮC" | Câu chữ trung tính |

🛠️ Nguyên tắc: kiểm thử dữ liệu kiểm tra bất biến (khóa, đối soát tổng, miền giá trị), không kiểm tra số đếm cụ thể.
Nếu nạp phiên bản Olist khác, kiểm thử vẫn đúng.

### 2.4. Tài liệu sai lệch với kho

Đo lại trên kho rồi sửa trong `docs/project_implementation.md`:

| Chỉ số | Tài liệu cũ | Kho hiện tại |
|---|---|---|
| Doanh thu hàng 2017 / 2018 | 6.103.955,67 / 6.899.967,73 | 5.962.902,01 / 7.218.125,12 |
| Tháng 11/2017 (Black Friday) | 1.010.271,31 | 987.765,37 |
| Bang SP | 5.000.564,30 (37,82%) | 5.067.633,16 (38,33%) |
| Pareto top 20% sản phẩm | 6.591 / 32.951, 74,07% | 6.444 / 32.216 sản phẩm có bán, 74,82% |
| Ngày thường, cước/giá, khách mua lại | 77%, 16,63%, 2.801 (3,00%) | khớp |

Ở bảng Pareto, mẫu số cũ (32.951) đếm cả sản phẩm chưa từng có món delivered. Câu SQL thì chỉ đếm sản phẩm có bán.
Cũng sửa trong tài liệu: các link `file:///…/archive/…` trỏ sang thư mục khác, header "PostgreSQL 17 cổng 5435",
mô tả ngưỡng giao diện DSS đã bị bỏ, và câu "không phải git repo".

## 3. Đã kiểm chứng

| Việc | Kết quả |
|---|---|
| `python etl_pipeline.py` đầy đủ (gồm bước tạo view DSS, trước đây chưa từng chạy qua) | Hoàn tất; F1–F7 đạt |
| `python run_dss_01.py` | PASS: view = fact delivered (13.221.498,11 R$; 110.197 món) |
| `python run_olap_02.py` | 4/4 PASS |
| `sql/olap/01_sales_time.sql` chạy toàn file | 15 câu lệnh chạy được, số khớp API |
| Flask test client: 15 URL màn Thời gian, 3 URL DSS | 200; tham số sai trả 400 |
| `python -m unittest discover -s backend/tests -t backend` | 16/16 đạt |
| `npm run build` và `npm run lint` | Qua; 2 cảnh báo lint đã có từ trước, không thuộc file đã sửa |


