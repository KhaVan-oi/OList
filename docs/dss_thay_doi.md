# DSS nhập hàng và khuyến mãi: đã thay đổi và đã làm được gì

Lý do chọn hướng này: [dss_ly_do_chuyen_huong.md](dss_ly_do_chuyen_huong.md).

## 1. Hệ thống làm gì

Màn mới **Quyết định** (`/quyet-dinh`) trả lời ba câu hỏi cho một phạm vi chọn được (toàn kho, một bang, hoặc một
danh mục):

1. **Tháng tới bán được bao nhiêu?** Dự báo trước 1 tháng, kèm sai số đo bằng backtest trượt theo thời gian.
2. **Nên nhập bao nhiêu?** Lượng nhập = dự báo × (1 + phân vị sai số tương đối của backtest ở mức phục vụ chọn).
   Kèm đường đánh đổi thiếu hàng và dư hàng đo bằng leave-one-out.
3. **Khuyến mãi có đáng không?** Bảng what-if với tham số người dùng nhập: hòa vốn, kịch bản chỉ đạt một phần mức tăng
   cầu, và bảng độ nhạy.

Đầu trang có **khung "Kết luận cho người quyết định"**: ba ý bằng câu thường (nên nhập bao nhiêu; sai số so với baseline "tháng
trước" và nhận xét mô hình hơn, ngang hay kém baseline; khuyến mãi lời hay lỗ theo giả định đang nhập). Baseline cũng được
ghi cạnh con số WAPE ở thẻ chỉ số, nhãn "baseline" ở bảng so sánh mô hình và ở tiêu đề cột bảng độ chính xác theo mức tổng hợp.
Nhận xét "hơn baseline" dùng ngưỡng cố định trên chênh lệch WAPE: trên 2 điểm phần trăm là "tốt hơn", từ 0,5 đến 2 là
"chỉ hơn", trong ±0,5 là "ngang", dưới −0,5 là "kém".

### Mô hình

| Mô hình | Công thức |
|---|---|
| Tháng trước (naive) | Lấy tháng liền trước |
| Trung bình 3 tháng | Trung bình 3 tháng gần nhất |
| Holt | Holt có suy giảm xu hướng, tham số chọn bằng lưới trên lịch sử (tự cài bằng numpy) |
| **Kết hợp (mặc định)** | Trung bình của naive và Holt |

Backtest: ở mỗi tháng từ tháng thứ 7 (2017-07) đến 2018-08, chỉ dùng dữ liệu trước tháng đó. Cửa sổ lịch sử là
2017-01 đến 2018-08. Năm 2016 quá thưa (có tháng không có đơn) và từ 2018-09 chưa có đơn delivered.

### Quyết định nhập hàng

- Hệ số đệm = 1 + phân vị `service` của (thực tế / dự báo − 1) trên các tháng backtest.
- Đường đánh đổi: với mỗi tháng, hệ số đệm chỉ học từ các tháng khác (leave-one-out), rồi đếm tỷ lệ tháng thiếu hàng và
  mức dư hàng. Vì vậy tỷ lệ thiếu hàng là số đo được, không phải cam kết lý thuyết của phân vị.
- Công tắc **"Bỏ Black Friday khỏi mẫu sai số"** (mặc định bật, vì tháng tới không phải tháng sự kiện). Khi tắt thì lượng
  đệm lớn hơn nhiều.

### What-if khuyến mãi

Với `m` là biên lợi nhuận gộp trên giá niêm yết, `d` là mức giảm giá, `u` là mức tăng cầu:

- Hòa vốn lý thuyết: `u* = d / (m − d)` (chưa tính hàng dư).
- Lợi nhuận kịch bản = hàng bán × (giá bán − giá vốn) − hàng dư × giá vốn × tổn thất hàng dư.
- Kịch bản chỉ đạt 0%, 50%, 100%, 150% mức tăng cầu giả định, với lượng nhập đã tăng theo mức giả định.
- Bảng độ nhạy: đổi lợi nhuận (%) theo (mức giảm giá × mức tăng cầu).
- Black Friday 2017 hiển thị như điểm tham chiếu quan sát (+70% số món so với trung bình 9 và 10/2017, đã lẫn xu hướng).

Bốn tham số (cầu tăng, giảm giá, biên lợi nhuận, tổn thất hàng dư) là **giả định của người dùng**, không suy ra từ
dữ liệu. Giá bán lấy từ doanh thu chia số món của 3 tháng gần nhất.

## 2. Thay đổi trong dự án

### Thêm mới

| Đường dẫn | Nội dung |
|---|---|
| `sql/dss/01_demand_mart.sql` | View `dw.v_dss_monthly_demand`: số món, doanh thu, số đơn theo tháng × bang × danh mục (đơn delivered) |
| `run_dss_01.py` | Tạo view và đối soát với `fact_sales`; in chuỗi theo tháng |
| `backend/app/features/dss/forecast.py` | Mô hình, backtest, lượng nhập, đường đánh đổi, what-if (thuần tính toán) |
| `backend/app/features/dss/routes.py` | Bốn endpoint `/api/dss/*` |
| `backend/app/features/dss/__init__.py` | Gói Python |
| `frontend/src/features/dss/components/dss-page.tsx` | Trang Quyết định, gồm khung kết luận và hiển thị baseline |
| `frontend/src/features/dss/components/whatif-panel.tsx` | Khối what-if khuyến mãi (nhận giả định đã áp dụng từ trang để khung kết luận dùng chung) |
| `frontend/src/features/dss/services/dssApi.ts` | Kiểu dữ liệu và gọi API |
| `frontend/src/features/dss/format.ts`, `index.ts` | Định dạng số, export |
| `docs/dss_ly_do_chuyen_huong.md`, `docs/dss_thay_doi.md` | Hai tài liệu này |
| `docs/dss_exploration/` | 6 script thăm dò + README (bằng chứng cho việc đổi hướng) |

### Sửa nhỏ trên file có sẵn

| File | Thay đổi |
|---|---|
| `backend/app/__init__.py` | Đăng ký blueprint DSS (2 dòng) |
| `frontend/src/App.tsx` | Thêm route `/quyet-dinh` |
| `frontend/src/components/layouts/main-layout.tsx` | Thêm mục "Quyết định" ở thanh bên |

### Đối tượng trong cơ sở dữ liệu

Một view mới `dw.v_dss_monthly_demand`. Không đổi bảng nào.

### Không thay đổi

ETL, staging, schema sao, các file OLAP SQL, các route và màn hình hiện có, `.env`, `requirements.txt` (chỉ dùng
numpy, vốn đã có sẵn cùng pandas). Frontend giữ nguyên phong cách: dùng lại `PageHeading`, `Stat`, `Card`, `Table`,
`FilterSelect`, `FilterChip`, `QueryState`, Recharts và bảng màu trong `lib/chart.ts`.

## 3. API

| Endpoint | Tham số chính | Trả về |
|---|---|---|
| `GET /api/dss/options` | none | Bang, danh mục, khoảng tháng |
| `GET /api/dss/forecast` | `scope` (total, state, category), `value`, `metric` (units, revenue), `model` (blend, naive, ma3, holt, auto), `service` (0,5 đến 0,99), `exclude_event` | Lịch sử, backtest, bảng sai số, dự báo tháng tới, lượng nhập, đường đánh đổi |
| `GET /api/dss/accuracy` | `metric` | WAPE gộp theo mức tổng hợp (tổng, 10 bang, 15 danh mục), có và không có Black Friday |
| `GET /api/dss/whatif` | như trên, thêm `uplift`, `discount`, `margin`, `loss` (phần trăm) | Hòa vốn, kịch bản, bảng độ nhạy |

Tham số sai trả mã 400 kèm thông báo. Tên cột SQL không bao giờ lấy từ query string (dùng whitelist); mọi giá trị
đi qua tham số hóa.

## 4. Cách chạy

```text
python run_dss_01.py          # tạo view (chạy lại sau mỗi lần ETL, vì ETL xóa schema dw)
python backend/run.py          # API cổng 5050
cd frontend && npm run dev     # mở /quyet-dinh
```

Lưu ý: `etl_pipeline.py` bắt đầu bằng `DROP SCHEMA dw CASCADE`, nên **view sẽ mất mỗi lần chạy lại ETL**. Chưa móc
`run_dss_01.py` vào pipeline vì không thể chạy lại ETL để kiểm chứng mà không dựng lại cả kho.

## 5. Đã kiểm tra những gì

| Việc | Kết quả |
|---|---|
| Đối soát view với `fact_sales` delivered | Khớp: 13.221.498,11 R$ và 110.197 món |
| Gọi API bằng Flask test client: tổng, bang SP và RJ, danh mục `health_beauty` và `bed_bath_table` | 200, số liệu hợp lý |
| Tham số sai (`scope`, `model`, `loss`, mã bang, danh mục không có dữ liệu) | 400 |
| Công thức hòa vốn so với bảng độ nhạy (giảm 10%, biên 35%) | Cùng điểm hòa vốn 40% |
| `npm run build` (gồm `tsc -b`) và `npm run lint` | Qua; không có cảnh báo mới ở mã DSS |
| Chụp màn hình `/quyet-dinh` bằng Edge không giao diện, với backend và dữ liệu thật | Hiển thị đủ thẻ chỉ số, biểu đồ, bảng; đã tắt hai server tạm sau đó |

### Kết quả đo được (số món, tháng dự báo 2018-09)

| Chỉ số | Giá trị |
|---|---|
| Dự báo toàn kho (mô hình kết hợp) | 7.065 món |
| Lượng nhập đề xuất ở mức phục vụ 90% (đã bỏ Black Friday khỏi mẫu sai số) | 7.942 món (đệm +12,4%) |
| Tỷ lệ tháng thiếu hàng thực nghiệm ở mức 90% | 16,7% (2 trên 12 tháng) |
| WAPE toàn kho: kết hợp, tháng trước | 11,2%, 12,2% (bỏ Black Friday: 7,4%, 7,5%) |
| WAPE 10 bang lớn: kết hợp, tháng trước | 13,0%, 15,0% |
| WAPE 15 danh mục lớn: kết hợp, tháng trước | 20,0%, 20,7% |
| What-if mặc định (cầu +50%, giảm 10%, biên 35%, hàng dư mất 20%) | Hòa vốn ở cầu +40%; lợi nhuận +5,1% nếu đạt đúng mức giả định, −51,8% nếu khuyến mãi không tăng cầu |

Giá trị mặc định của what-if (50, 10, 35, 20) là ví dụ minh họa, chưa dựa trên dữ liệu doanh nghiệp.

## 6. Chưa làm hoặc chưa kiểm tra

- **Chưa có unit test** cho `forecast.py`. Đã kiểm tra tay bằng API như bảng trên.
- **Chưa thao tác thử trên trình duyệt** các lựa chọn khác (đổi sang bang, danh mục, bấm "Tính lại"): ảnh chụp chỉ
  là trang mặc định. API của các phạm vi đó đã được gọi và trả đúng, nhưng giao diện chưa được nhìn thấy ở các trạng thái này.
  Chưa kiểm tra màn hình hẹp và trình duyệt khác.
- Dự báo chỉ trước **1 tháng**, chưa có nhiều tháng; chưa có khoảng dự báo dạng băng trên biểu đồ.
- Chưa sửa `docs/olap.md` và `sql/olap/03_customer_payment.md`: hai file này vẫn ghi RFM, K-means và what-if là việc
  của Giai đoạn 5. Nhóm nên cập nhật cho khớp với hướng mới.
- Chưa móc view DSS vào `etl_pipeline.py` (xem mục 4).
- Thư mục `frontend/dist` được build lại (đã nằm trong `.gitignore`).
- Thư mục không phải git repo nên không có commit nào được tạo.
