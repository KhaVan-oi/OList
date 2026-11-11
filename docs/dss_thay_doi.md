# DSS nhập hàng: đã thay đổi và đã làm được gì

Lý do chọn hướng này: [dss_ly_do_chuyen_huong.md](dss_ly_do_chuyen_huong.md).
Đánh giá các đề xuất chỉnh sửa và lý do bỏ what-if khuyến mãi: [dss_danh_gia_de_xuat.md](dss_danh_gia_de_xuat.md).

## 1. Hệ thống làm gì

Màn mới **Quyết định** (`/quyet-dinh`) trả lời hai câu hỏi cho một phạm vi chọn được (toàn kho, một bang, hoặc một
danh mục):

1. **Tháng tới bán được bao nhiêu?** Dự báo trước 1 tháng, kèm sai số đo bằng backtest trượt theo thời gian.
2. **Nên nhập bao nhiêu?** Lượng nhập = dự báo + phân vị sai số tuyệt đối của backtest (85, 90, 95 hoặc 99%).
   Kèm đường đánh đổi thiếu hàng và dư hàng đo bằng leave-one-out.

What-if khuyến mãi đã được bỏ: dữ liệu không có giá vốn hay đợt khuyến mãi nào để kiểm chứng, nên kết quả hoàn toàn do
giả định của người dùng. Phần kịch bản của trang là đường đánh đổi thiếu hàng và dư hàng, tính từ backtest.

Đầu trang có **khung "Kết luận cho người quyết định"**: hai ý bằng câu thường (nên nhập bao nhiêu; sai số so với baseline "tháng
trước" và nhận xét mô hình hơn, ngang hay kém baseline). Baseline cũng được
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

Backtest: ở mỗi tháng từ tháng thứ 7 (2017-07) đến 2018-08, chỉ dùng dữ liệu trước tháng đó. Đầu cửa sổ lịch sử cố
định là 2017-01 (năm 2016 quá thưa, có tháng không có đơn). **Cuối cửa sổ lấy từ dữ liệu**: là tháng gần nhất trong
view có số món ≥ 30% trung vị các tháng trong cửa sổ (`_history_end` trong `routes.py`), để một tháng cuối mới nạp
dở không bị coi là tháng thật. Với dữ liệu Olist hiện tại đó là 2018-08, nên tháng dự báo là 2018-09.

`MIN_TRAIN = 6` (số tháng lịch sử tối thiểu trước khi dự báo) **do nhóm tự đặt, không có paper quy định**. Độ nhạy
được đo bằng `docs/dss_exploration/07_min_train_sensitivity.py`: dự báo tại một tháng luôn dùng toàn bộ lịch sử trước nó,
nên `MIN_TRAIN` chỉ quyết định tháng nào được đưa vào backtest. Kết quả toàn kho (blend):

| MIN_TRAIN | Số tháng kiểm tra | WAPE | Đệm 90% | Lượng nhập | Thiếu hàng LOO |
|---|---|---|---|---|---|
| 3 | 17 | 12,6% | +12,0% | 7.912 | 13,3% |
| 4 | 16 | 12,1% | +12,8% | 7.972 | 14,3% |
| 5 | 15 | 11,5% | +5,9% | 7.485 | 15,4% |
| **6** | **14** | **11,2%** | **+6,4%** | **7.519** | **16,7%** |
| 7 | 13 | 11,2% | +2,1% | 7.214 | 9,1% |
| 8 | 12 | 11,7% | +3,2% | 7.293 | 10,0% |
| 9 | 11 | 11,9% | +4,9% | 7.413 | 11,1% |
| 10 | 10 | 12,8% | +6,6% | 7.532 | 12,5% |

Đọc kết quả: WAPE thấp nhất ở 6 và 7 (11,2%). Dưới 6, các tháng đầu (2017-04 đến 2017-06, chỉ có 3 đến 5 tháng lịch
sử) sai số 20 đến 30% nên kéo WAPE lên. Từ 8 trở lên, các tháng đầu dễ đã bị bỏ, nên tháng Black Friday (sai số 37%)
chiếm tỷ trọng lớn hơn trong ít tháng còn lại, và WAPE tăng trở lại (12,8% ở 10). Đệm cũng dao động mạnh vì mẫu sai
số chỉ còn 8 đến 15 điểm. Lượng nhập dao động 7.214 đến 7.972 (±5%) tùy `MIN_TRAIN`, và
tỷ lệ thiếu hàng thực nghiệm 9% đến 17%. Vậy 6 là giá trị hợp lý, không tối ưu rõ rệt, và kết luận nên được trình bày
là "ổn định trong khoảng ±5% quanh 7.500 món", không phải "chính xác 7.519".

### Quyết định nhập hàng

- Sai số một tháng `e = thực tế − dự báo`, cùng đơn vị với chỉ số (món hoặc R$), trên các tháng backtest có dự báo dương.
- Đệm = phân vị `service` của `e`, nội suy tuyến tính (`numpy`, `method="linear"`). Đệm có thể âm khi mô hình thường dự báo
  cao hơn thực tế.
- Lượng nhập = max(dự báo tháng tới + đệm, 0). Dạng này theo Trapero, Cardós, Kourentzes (*Omega*, 2019): tồn an toàn là
  phân vị của sai số dự báo trên lead time. Ở đây lead time L = 1 tháng và mẫu chỉ khoảng 12 đến 14 tháng, nên đây là
  ước lượng thô, không phải mức phục vụ đã hiệu chuẩn.
- API trả `buffer` (đệm đúng đơn vị) và `buffer_pct = đệm / dự báo` (chỉ để hiển thị).
- Đường đánh đổi: với mỗi tháng, đệm chỉ học từ các tháng khác (leave-one-out), lượng nhập của tháng đó là dự báo tháng
  đó cộng đệm, rồi đếm tỷ lệ tháng thiếu hàng và mức dư hàng. Vì vậy tỷ lệ thiếu hàng là số đo được, không phải cam kết
  lý thuyết của phân vị.
- Công tắc **"Bỏ Black Friday khỏi mẫu sai số"** (mặc định bật, vì tháng tới không phải tháng sự kiện). Khi tắt thì lượng
  đệm lớn hơn nhiều.

## 2. Thay đổi trong dự án

### Thêm mới

| Đường dẫn | Nội dung |
|---|---|
| `sql/dss/01_demand_mart.sql` | View `dw.v_dss_monthly_demand`: số món, doanh thu, số đơn theo tháng × bang × danh mục (đơn delivered) |
| `run_dss_01.py` | Tạo view và đối soát với `fact_sales`; in chuỗi theo tháng |
| `backend/app/features/dss/forecast.py` | Mô hình, backtest, lượng nhập, đường đánh đổi (thuần tính toán) |
| `backend/app/features/dss/routes.py` | Ba endpoint `/api/dss/*` |
| `backend/app/features/dss/__init__.py` | Gói Python |
| `frontend/src/features/dss/components/dss-page.tsx` | Trang Quyết định, gồm khung kết luận và hiển thị baseline |
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
| `GET /api/dss/forecast` | `scope` (total, state, category), `value`, `metric` (units, revenue), `model` (blend, naive, ma3, holt), `service` (0,85 đến 0,99; đường đánh đổi trả đúng 4 mức 85, 90, 95, 99%), `exclude_event` | Lịch sử, backtest, bảng sai số, dự báo tháng tới, lượng nhập, đường đánh đổi |
| `GET /api/dss/accuracy` | `metric` | WAPE gộp theo mức tổng hợp (tổng, 10 bang, 15 danh mục), có và không có Black Friday |

Tham số sai trả mã 400 kèm thông báo. Tên cột SQL không bao giờ lấy từ query string (dùng whitelist); mọi giá trị
đi qua tham số hóa.

## 4. Cách chạy

```text
python etl_pipeline.py         # nạp kho. Bước cuối tự tạo view dw.v_dss_monthly_demand
python run_dss_01.py           # (tùy chọn) tạo lại view và đối soát với fact_sales
python backend/run.py          # API cổng 5050
cd frontend && npm run dev     # mở /quyet-dinh
```

Lưu ý: `etl_pipeline.py` bắt đầu bằng `DROP SCHEMA dw CASCADE` (trong `sql/dw/dss.sql`, đây là DDL của kho theo Fix.md,
không liên quan tên "DSS"), nên view bị xóa theo. Vì vậy `run_pipeline` có thêm một bước sau phần kiểm tra để chạy
`sql/dss/01_demand_mart.sql`. Bước này **chưa được chạy thử qua một lần ETL đầy đủ**, chỉ kiểm tra bằng đọc code và
chạy view độc lập. `run_dss_01.py` vẫn giữ vai trò đối soát.

## 5. Đã kiểm tra những gì

| Việc | Kết quả |
|---|---|
| Đối soát view với `fact_sales` delivered | Khớp: 13.221.498,11 R$ và 110.197 món |
| Gọi API bằng Flask test client: tổng, bang SP và RJ, danh mục `health_beauty` và `bed_bath_table` | 200, số liệu hợp lý |
| Tham số sai (`scope`, `model`, `service`, mã bang, danh mục không có dữ liệu) | 400 |
| `npm run build` (gồm `tsc -b`) và `npm run lint` | Qua; không có cảnh báo mới ở mã DSS |
| Chụp màn hình `/quyet-dinh` bằng Edge không giao diện, với backend và dữ liệu thật | Hiển thị đủ thẻ chỉ số, biểu đồ, bảng; đã tắt hai server tạm sau đó |

### Kết quả đo được (số món, tháng dự báo 2018-09)

| Chỉ số | Giá trị |
|---|---|
| Dự báo toàn kho (mô hình kết hợp) | 7.065 món |
| Lượng nhập đề xuất ở phân vị 90% (đã bỏ Black Friday khỏi mẫu sai số) | 7.518,82 món (đệm +453,64 món, +6,4%, 12 tháng trong mẫu) |
| Tỷ lệ tháng thiếu hàng thực nghiệm (leave-one-out) ở phân vị 90% | 16,7% (2 trên 12 tháng) |
| WAPE toàn kho: kết hợp, tháng trước | 11,2%, 12,2% (bỏ Black Friday: 7,4%, 7,5%) |
| WAPE 10 bang lớn: kết hợp, tháng trước | 13,0%, 15,0% |
| WAPE 15 danh mục lớn: kết hợp, tháng trước | 20,0%, 20,7% |

## 6. Chưa làm hoặc chưa kiểm tra

- **Chưa có unit test** cho `forecast.py`. Đã kiểm tra tay bằng API như bảng trên.
- **Chưa thao tác thử trên trình duyệt** các lựa chọn khác (đổi sang bang, danh mục, bấm "Tính lại"): ảnh chụp chỉ
  là trang mặc định. API của các phạm vi đó đã được gọi và trả đúng, nhưng giao diện chưa được nhìn thấy ở các trạng thái này.
  Chưa kiểm tra màn hình hẹp và trình duyệt khác.
- Dự báo chỉ trước **1 tháng**, chưa có nhiều tháng; chưa có khoảng dự báo dạng băng trên biểu đồ.
- Chưa sửa `docs/olap.md` và `sql/olap/03_customer_payment.md`: hai file này vẫn ghi RFM, K-means và what-if là việc
  của Giai đoạn 5. Nhóm nên cập nhật cho khớp với hướng mới.
- Các số "Kết quả đo được" ở mục 5 được cập nhật theo công thức đệm tuyệt đối. Ảnh chụp màn hình cũ (nếu có) không còn
  khớp với giao diện.
- Bước tạo view trong `etl_pipeline.py` (mục 4) chưa được chạy thử qua một lần ETL đầy đủ. Comment của view đã sửa
  trong file SQL, nhưng view đang có trong DB vẫn mang comment cũ cho đến lần ETL hoặc `run_dss_01.py` kế tiếp.
- Thư mục `frontend/dist` được build lại (đã nằm trong `.gitignore`).
- Thư mục không phải git repo nên không có commit nào được tạo.
