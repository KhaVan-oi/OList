# Đề xuất DSS: bỏ blend, sửa lượng nhập, bỏ what-if

Ba việc trên DSS đang chạy. Giữ naive, trung bình 3 tháng, Holt, WAPE và cách chia backtest. Không thêm tồn kho, lead time, chi phí thiếu hàng, kernel hay GARCH.

## 1. Bỏ blend

### Chỉnh sửa

Xóa `blend` khỏi `MODELS`, khỏi `forecast_all`, khỏi dropdown và khỏi chế độ `auto`. Mô hình ra dự báo tháng tới và lượng nhập mặc định là **Holt**. Tháng trước giữ nhãn baseline. Trung bình 3 tháng ở lại trong bảng so sánh. Không cộng ba số này lại.

Câu kết luận trên trang ghi Holt so với baseline ở cả ba mức: toàn kho, bang, danh mục. Holt hơn rõ ở bang, gần như hòa ở toàn kho, kém tháng trước ở danh mục.

| File | Việc |
|---|---|
| `backend/app/features/dss/forecast.py` | Xóa blend khỏi `forecast_all` |
| `backend/app/features/dss/routes.py` | Mặc định `model=holt`. Bỏ giá trị `blend` |
| `frontend/src/features/dss/services/dssApi.ts` | Bỏ `blend` khỏi kiểu `DssModel` |
| `frontend/src/features/dss/components/dss-page.tsx` | Dropdown còn Holt, tháng trước, trung bình 3 tháng, tự chọn. Kết luận ghi đủ ba mức |
| `docs/dss_thuat_toan.md` mục 4 | Xóa blend sau khi mã đã đổi |

### Lý do

Mặc định trang và API đang là `blend = (tháng trước + Holt) / 2`. Trọng số 1/2 được viết cố định trong `forecast_all`. Không có bước ước lượng hệ số từ dữ liệu. Tài liệu hệ thống ghi mô hình này được chốt trước khi xem backtest, theo quy ước kết hợp dự báo trên chuỗi ngắn.

Smith và Wallis (2009, *Oxford Bulletin of Economics and Statistics*) chỉ ra một việc hẹp: với mẫu ngắn, trọng số học từ sai số quá nhiễu, nên chia đều thường đỡ hại hơn trọng số ước lượng. Đó là lý do không đi tìm hệ số 0,4 hay 0,6. Chia đều không biến số trung bình thành nhu cầu tháng tới. Trung bình hai dự báo chỉ là một cách ghép hai con số.

M5 (Makridakis, Spiliotis, Assimakopoulos, *International Journal of Forecasting*, 2022) thấy kết hợp có ích khi từng mô hình nhìn một thứ mô hình kia không thấy. Người thắng dùng sáu mô hình, mỗi mô hình một cách học và một tập huấn luyện khác nhau, rồi chia đều. Á quân dùng năm cách ước lượng xu hướng khác nhau. Kết hợp trong cuộc thi đó thêm thông tin.

Tháng trước và Holt đọc cùng chuỗi số món hoặc doanh thu theo tháng. Tháng trước lấy đúng giá trị tháng cuối. Holt lấy mức đang đứng của chính chuỗi đó, cộng một độ dốc đã nhân `phi < 1`. Trung bình hai bên xấp xỉ tháng trước cộng một nửa độ dốc. Không có giá, khuyến mãi hay sự kiện nào mà chỉ một trong hai mô hình được nhìn. Blend là cách làm nhỏ độ dốc của Holt. Muốn giảm độ dốc thì sửa Holt, không phát hành thêm một số trung gian.

### Benchmark

WAPE số món, backtest 2017-07 đến 2018-08:

| Mức | Tháng trước | Holt | Blend | Trung bình 3 tháng |
|---|---:|---:|---:|---:|
| Toàn kho | 12,2% | 12,0% | 11,2% | 11,1% |
| 10 bang lớn | 15,0% | 13,6% | 12,9% | 13,7% |
| 15 danh mục lớn | 20,7% | 20,9% | 20,0% | 21,2% |

Ở toàn kho, Holt lệch cao hơn thực tế khoảng +3,9% và tháng trước lệch thấp khoảng −3,9%. Trung bình hai bên kéo bias về 0 và làm WAPE đẹp hơn. So với trung bình 3 tháng, phần đẹp thêm ở toàn kho là 11,2% so với 11,1%. Người nhập hàng không đổi quyết định vì khoảng đó.

## 2. Sửa lượng nhập

### Chỉnh sửa

Trong `backend/app/features/dss/forecast.py`, `order_plan` đang làm:

```text
e = thực tế / dự báo − 1
hệ số = 1 + phân vị(e)          làm tròn lên, numpy method="higher"
lượng nhập = dự báo tháng tới × hệ số
```

Mẫu sai số mặc định bỏ 2017-11 và 2017-12 vì `excludeEvent` trên trang đang bật. Nhãn giao diện gọi hệ số này là mức phục vụ.

Đổi thành, với mô hình đang chọn, trên các tháng backtest có dự báo dương:

```text
e = thực tế − dự báo
đệm = phân vị nội suy của các e          numpy method="linear"
lượng nhập = max(dự báo tháng tới + đệm, 0)
```

Đệm có thể âm khi mô hình dự báo cao hơn thực tế ở phân vị đang chọn. Giữ số âm. Chỉ chặn lượng nhập không xuống dưới 0.

Mức trên dropdown và trên đường đánh đổi còn bốn giá trị 85%, 90%, 95% và 99%. Mặc định giữ 90%. Bỏ 50%, 70% và 80% khỏi chỗ ra lượng nhập.

Mẫu đệm mặc định gồm mọi tháng backtest, kể cả 2017-11 và 2017-12. Công tắc bỏ hai tháng đó vẫn giữ, nhưng chỉ để xem đệm thay đổi bao nhiêu. Thẻ lượng nhập dùng mẫu đang chọn và ghi số tháng trong mẫu. Nhãn “mức phục vụ” đổi thành “phân vị sai số”. `excludeEvent` mặc định tắt.

`tradeoff` dùng cùng công thức cộng. Với từng tháng, đệm học từ các tháng còn lại, lượng của tháng đó là `dự báo tháng đó + đệm`, rồi so với thực tế.

API `order` trả thêm `buffer` là đệm đúng đơn vị (món hoặc R$). `buffer_pct` chỉ để hiển thị, bằng `đệm / dự báo`. Không dùng `buffer_pct` để tính lượng nhập.

Với khoảng 14 tháng, phân vị 99% chỉ để xem độ nhạy. Ghi trên trang là mẫu ngắn, không trình bày như một mức phục vụ đã hiệu chuẩn.

| File | Việc |
|---|---|
| `backend/app/features/dss/forecast.py` | `order_plan` và `tradeoff` cộng đệm đơn vị |
| `backend/app/features/dss/routes.py` | Trả `buffer`. Sửa `note`: đệm là phân vị sai số một tháng |
| `frontend/src/features/dss/components/dss-page.tsx` | Dropdown phân vị còn 85/90/95/99. Thẻ lượng nhập hiện đệm bằng món hoặc R$, kèm số tháng trong mẫu |
| `docs/dss_thuat_toan.md` mục 7 | Viết lại lượng nhập sau khi mã đã đổi |

### Lý do

Nguồn công thức: Juan R. Trapero, Manuel Cardós, Nikolaos Kourentzes, *Empirical safety stock estimation based on kernel and GARCH models*, Omega, 2018. https://doi.org/10.1016/j.omega.2018.05.004

Bài định nghĩa sai số trên lead time bằng số đơn vị, rồi lấy phân vị của các sai số đó làm tồn an toàn:

```text
e_L = tổng thực tế trong L kỳ − tổng dự báo trong L kỳ
tồn an toàn = phân vị của các e_L tại mức đang xét
mức đặt = dự báo trong L kỳ + tồn an toàn
```

Phân vị thực nghiệm được nội suy. Các mức họ tính là 85%, 90%, 95% và 99%. Case của bài là 229 sản phẩm, 173 tuần, lead time 4 tuần. Trên case đó GARCH cho độ phủ tốt hơn phân vị thực nghiệm. Bài cũng nói mẫu ngắn làm phân vị 99% phủ thiếu.

DSS này không có lead time và chỉ có khoảng 12–14 tháng backtest. Phần lấy sang là dạng L = 1: cộng phân vị của `(thực tế − dự báo)` một tháng, tính bằng cùng đơn vị với chỉ số đang xem. Công thức đang chạy chia sai số cho dự báo rồi nhân lại, nên một tháng bán gấp đôi dự báo kéo hệ số của mọi tháng sau. Sai số bằng món giữ tháng đó trong đơn vị của lượng nhập.

### Benchmark

Số món toàn kho, đơn `delivered`, cửa sổ 2017-01 đến 2018-08, mô hình Holt, phân vị 90%, nội suy tuyến tính. Dự báo tháng 2018-09 là 6.988,36 món.

| Mẫu | Số tháng | Đệm | Lượng nhập |
|---|---:|---:|---:|
| Cả 14 tháng backtest, gồm Black Friday | 14 | +546,94 món | 7.535,31 |
| Bỏ 2017-11 và 2017-12 | 12 | +39,61 món | 7.027,97 |

Số cũ của blend, sau khi bỏ hai tháng sự kiện và nhân tỷ lệ hụt, là 7.942 món với đệm +12,4%. Sau khi sửa, mẫu mặc định là Holt trên đủ 14 tháng và phải ra 7.535,31. Đệm Holt trên 12 tháng thường rất nhỏ vì Holt lệch cao. Đó là kết quả của mô hình.

## 3. Bỏ what-if khuyến mãi

### Chỉnh sửa

Gỡ khối Khuyến mãi what-if khỏi trang Quyết định và khỏi API. Xóa `breakeven_uplift`, `sensitivity_grid`, `promo_scenarios` và tham chiếu Black Friday nằm trong khối đó. Câu kết luận của trang chỉ còn dự báo và lượng nhập.

Giữ công tắc bỏ 2017-11 và 2017-12 ở phần đệm. Tháng sự kiện vẫn thuộc backtest dự báo. Chỉ không còn thẻ “tham chiếu quan sát” cạnh hòa vốn.

| File | Việc |
|---|---|
| `backend/app/features/dss/forecast.py` | Xóa `breakeven_uplift`, `sensitivity_grid`, `promo_scenarios` |
| `backend/app/features/dss/routes.py` | Xóa `GET /api/dss/whatif` |
| `frontend/src/features/dss/services/dssApi.ts` | Xóa `getDssWhatIf`, `DssWhatIf`, `DEFAULT_WHATIF` |
| `frontend/src/features/dss/components/whatif-panel.tsx` | Xóa file |
| `frontend/src/features/dss/components/dss-page.tsx` | Gỡ `WhatIfPanel` và đoạn hòa vốn trong `ConclusionCard` |
| `docs/dss_thuat_toan.md` mục 8 | Xóa mục Khuyến mãi what-if sau khi mã đã đổi |

### Lý do

Công thức hòa vốn `u* = d / (m − d)` cần biên đóng góp `m = (giá bán − giá vốn) / giá bán`. Tập Olist có `price` và `freight_value`. Không có giá vốn, không có lợi nhuận seller, không có cờ giảm giá, không có tồn để đặt mua trước. Phí vận chuyển là tiền cước, không đứng vai giá vốn.

`u`, `d`, `m` và `loss` là bốn ô người dùng gõ. Mặc định 50%, 10%, 35%, 20%. Mức hòa vốn trên trang tính từ `d` và `m`, không đọc một dòng doanh thu nào. Doanh thu chỉ vào giá bình quân ba tháng, rồi giá vốn một món lại bằng `giá × (1 − m)`. Cột lợi nhuận vì vậy là lợi nhuận của biên giả định.

Ba số trên cùng màn hình cũng không cùng một bài. Ô hòa vốn và bảng độ nhạy bỏ hàng dư, và cho mức tăng cầu chạy độc lập với mức giảm giá. Bảng kịch bản thì nhập `dự báo × (1 + u) × hệ số đệm` rồi mới cho cầu đạt 0%, 50%, 100%, 150%. Lượng nhập đó giả định có kho mua trước theo khuyến mãi. Đơn `delivered` của sàn không có tồn và không có lead time.

Bài toán dữ liệu trả lời được là tháng tới bán khoảng bao nhiêu món. Bài what-if còn đứng trên `price` và số món là bài doanh thu: số món thành `dự báo × (1 + u)` và giá thành `giá × (1 − d)` thì doanh thu đổi bao nhiêu. Bài đó không nói đợt giảm giá có lời. Trang hiện trả lời bài lợi nhuận, nên bỏ cả khối.

### Benchmark

Không có sai số để chấm. Kho không có đợt giảm giá đã ghi, nên không có tháng nào để so lợi nhuận dự tính với lợi nhuận thực.

Cùng mức giảm 10%, hòa vốn đổi theo biên người dùng gõ:

| Biên gõ vào | Cầu phải tăng để hòa vốn |
|---|---|
| 35% (mặc định trang) | 40% |
| 20% | 100% |
| 10% | Không có, vì giảm giá bằng biên |

Black Friday 2017 đo được trên số món: tháng 11 so với trung bình tháng 9 và 10. Đó là mức nhảy theo mùa của toàn sàn, đã lẫn đà tăng. Nó không hiệu chỉnh được `u`.
