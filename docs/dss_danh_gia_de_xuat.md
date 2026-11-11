# Đánh giá đề xuất `dss_de_xuat_luong_nhap.md`

Tài liệu này ghi lại việc đánh giá file đề xuất sửa DSS (bỏ blend, sửa lượng nhập, bỏ what-if), quá trình chạy thử, kết luận cuối và phần đã triển khai vào mã. Mọi số liệu được tính bằng chính `backend/app/features/dss/forecast.py` trên dữ liệu lấy **trực tiếp từ DB** (`olist_dw`, view `dw.v_dss_monthly_demand`, PostgreSQL 16). Trước đó các phép thử được chạy trên bản dựng lại từ CSV, và kết quả trùng khớp từng chữ số với DB.

## 1. Tóm tắt kết luận

| Nội dung | Kết luận | Trạng thái |
|---|---|---|
| Bỏ blend, dùng Holt | **Không áp dụng.** Giữ blend. Biện luận bằng kết quả backtest và sự đơn giản, không dựa vào bài báo. | Giữ nguyên mã |
| Đệm theo sai số tuyệt đối, nội suy tuyến tính | **Áp dụng**, với blend và `excludeEvent` bật. Kết quả không tệ hơn, ít dư hàng hơn, bám đúng công thức của bài báo nguồn. | **Đã triển khai** |
| Bỏ what-if khuyến mãi | **Bỏ**, không thay bằng what-if doanh thu hay hướng newsvendor. Trang đã có đường đánh đổi thiếu hàng và dư hàng. | **Đã triển khai** |
| Các mức phân vị 85, 90, 95, 99% | **Áp dụng** cho khớp bài báo nguồn (bỏ 70% và 80%). | **Đã triển khai** |

- Số liệu trong file đề xuất đều đúng và tái lập được chính xác.
- Kết luận về blend trong file đề xuất không vững, vì chính bảng của nó cho thấy blend tốt hơn Holt ở cả 3 mức.
- Công thức đệm tuyệt đối trong file đề xuất **có thật trong bài báo** (xem mục 5). Mã cũ dùng sai số tỷ lệ, là biến thể không trùng bài báo, nên khó giải thích khi trích dẫn nguồn.

## 2. File đề xuất nói gì

| # | Đề xuất | Nội dung |
|---|---|---|
| 1 | Bỏ blend | Xóa `blend` = (tháng trước + Holt) / 2. Mặc định dùng Holt. |
| 2 | Sửa lượng nhập | Đổi từ `dự báo × (1 + phân vị tỷ lệ sai số)` sang `dự báo + phân vị sai số tuyệt đối (món)`, nội suy tuyến tính. Mặc định tính cả tháng Black Friday. Chỉ còn mức 85/90/95/99%. |
| 3 | Bỏ what-if | Xóa khối khuyến mãi (hòa vốn, độ nhạy, kịch bản), vì dữ liệu không có giá vốn hay dữ liệu giảm giá. |

## 3. Đối chiếu mã nguồn (trước khi sửa)

Mô tả trong file khớp với mã: `blend` ở `forecast.py:63`, `order_plan` dùng `actual/forecast − 1` với `method="higher"`, mặc định `model=blend` ở `routes.py:178`, endpoint `/api/dss/whatif`.

File đề xuất **bỏ sót một chỗ**: `accuracy()` trong `routes.py:316` tính cột `wape` của mỗi chuỗi bằng `blend`. Xóa blend khỏi `MODELS` mà không sửa chỗ này sẽ gây lỗi `KeyError`. (Vì quyết định giữ blend nên chỗ này không cần sửa.)

## 4. Kiểm chứng số liệu của file đề xuất

Số liệu được đọc trực tiếp từ view `dw.v_dss_monthly_demand` (11.672 dòng, 2016-09 đến 2018-08, 110.197 món, cửa sổ lịch sử 2017-01 đến 2018-08 như `routes.py`), rồi chạy `forecast.py`. Chuỗi số món toàn kho theo tháng từ 2017-01 đến 2018-08 là: 913, 1.858, 2.897, 2.569, 4.004, 3.489, 4.416, 4.797, 4.737, 5.214, 8.475, 6.187, 8.037, 7.518, 8.017, 7.827, 7.810, 7.010, 6.963, 7.142.

Cách làm này được thực hiện hai lần: lần đầu trên bản dựng lại từ CSV (khi chưa có DB), lần sau trực tiếp trên DB. Hai lần cho kết quả giống hệt nhau ở mọi bảng trong tài liệu này (mục 4 đến mục 7), nên bản dựng từ CSV là tương đương với DW thật.

**WAPE số món, backtest 2017-07 đến 2018-08** (tất cả khớp với bảng của file):

| Mức | Tháng trước | Holt | Blend | TB 3 tháng | Bias Holt | Bias blend |
|---|---|---|---|---|---|---|
| Toàn kho | 12,2 | 12,0 | 11,2 | 11,1 | +3,9% | 0,0% |
| 10 bang | 15,0 | 13,6 | 12,9 | 13,7 | +4,7% | +0,3% |
| 15 danh mục | 20,7 | 20,9 | 20,0 | 21,2 | +4,3% | +0,4% |

**Lượng nhập (toàn kho, Holt, phân vị 90%, dự báo tháng 9/2018 = 6.988,36):**

| Mẫu | Đệm | Lượng nhập |
|---|---|---|
| Đủ 14 tháng backtest | +546,94 | 7.535,31 |
| Bỏ 2017-11 và 2017-12 | +39,61 | 7.027,97 |
| Số cũ của blend (tỷ lệ) | +12,4% | 7.942 |

## 5. Kiểm chứng hai bài báo được trích dẫn

Cả hai bài đều có thật và trích dẫn đúng thông tin thư mục.

### 5.1. Smith & Wallis (2009), *Oxford Bulletin of Economics and Statistics* 71(3), 331–355

- Bài giải thích "nghịch lý kết hợp dự báo": trung bình đơn giản thường thắng tổ hợp có trọng số ước lượng, vì sai số ước lượng trọng số trên mẫu hữu hạn.
- Bài **không chứng minh** trọng số 50/50 tốt hơn từng mô hình riêng lẻ, càng không chứng minh 50/50 là tối ưu.
- Vì vậy không nên viết "bài báo cho thấy 50/50 tốt". Cách biện luận đúng: **chọn blend vì kết quả backtest và vì đơn giản**. Backtest cho thấy blend có WAPE thấp nhất ở 2/3 mức (bang 12,9 và danh mục 20,0) và bias gần 0.
- Một nhận xét ở bản đánh giá trước ("bài này ủng hộ blend") nói quá. Bài chỉ ủng hộ "nếu đã kết hợp thì chia đều hơn là ước lượng trọng số".

### 5.2. Trapero, Cardós, Kourentzes (*Omega* 84, 2019, DOI 10.1016/j.omega.2018.05.004)

Đã đọc bản PDF accepted version. Các điểm khớp với file đề xuất:

| Điều file đề xuất nói | Trong bài |
|---|---|
| Sai số trên lead time là tổng thực tế trừ tổng dự báo | Có, `e_t(L) = Σ y(t+h) − Σ F(t+h)` (mục 3.2) |
| Tồn an toàn là phân vị của sai số đó | Có, **phương trình (2)**: `SS = Q_L(CSL)` |
| Phân vị nội suy tuyến tính | Có, mục 4.2.2 "Empirical percentile" |
| Các mức 85/90/95/99% | Có |
| 229 sản phẩm, 173 tuần, lead time 4 tuần | Có (mục 7) |
| Phân vị 99% phủ thiếu | Bài ghi phân vị thực nghiệm cho mức phục vụ thấp hơn mục tiêu ở 99%. Ý "do mẫu ngắn" là suy diễn của file |

Hệ quả:
- Công thức tuyệt đối trong file đề xuất **đúng với bài báo** (với L = 1). Mã cũ dùng sai số tỷ lệ `thực tế/dự báo − 1` và `method="higher"` là **biến thể**, không phải công thức của bài. Báo cáo không nên ghi "theo Trapero et al." cho biến thể đó.
- Bài dùng chuỗi tuần dài 173 điểm và lead time nhiều kỳ. DSS này chỉ có 12 đến 14 điểm tháng, nên mức tin cậy kém hơn nhiều.
- Phần file nói GARCH vượt phân vị thực nghiệm trên case của bài thì chưa kiểm tra.

## 6. Đánh giá file đề xuất

### 6.1. Bỏ blend: lập luận yếu

- Đúng ở chỗ blend chỉ là Holt với độ dốc giảm một nửa (hai thành phần đọc cùng một chuỗi), nên đơn giản hóa là có lý.
- Nhưng **blend tốt hơn Holt ở cả 3 mức** theo chính bảng của file (11,2 so với 12,0; 12,9 so với 13,6; 20,0 so với 20,9), và triệt tiêu bias của Holt (+3,9 đến +4,7%).
- Bài Smith–Wallis không chứng minh điều file cần (xem mục 5.1).
- Bỏ blend để dùng Holt hiện tại là đổi phương án tốt hơn lấy phương án kém hơn.

### 6.2. Sửa lượng nhập: công thức đúng, mặc định của file có vấn đề

- Chuyển sang sai số tuyệt đối là hợp lý và đúng với bài báo.
- **Mặc định tính cả Black Friday và dùng Holt** làm đệm quá lớn và bất ổn: sai số Holt (thực tế − dự báo) sắp xếp tăng dần là −2042, −1063, −861, −841, −796, −619, −451, −415, −283, −84, −37, +48, +761, +3026. Phân vị 90% nội suy rơi giữa +48 và +761 nên đệm là +547. Bỏ hai tháng sự kiện thì thứ hạng dịch chuyển và đệm thành +40.
- Khi dùng blend và bỏ sự kiện thì đệm ổn hơn nhiều (xem mục 7.2).
- Chỉ có 3 trong 14 sai số Holt dương, vì Holt dự báo cao hơn thực tế trong hầu hết 2018.

### 6.3. Bỏ what-if: lý do đúng

- Công thức hòa vốn `u* = d/(m−d)` kiểm tra đúng (35% giảm 10% cần +40%; 20% cần +100%; 10% không hòa vốn).
- `m` (biên lợi nhuận) và `loss` là giả định tự nhập, không suy ra từ dữ liệu. Backtest không chấm được phần này vì không có đợt khuyến mãi nào được ghi lại.
- Mất thành phần phân tích kịch bản là cái giá của việc bỏ (xem mục 7.4 và 8).

## 7. Quá trình chạy thử các đề xuất cải tiến

Chỉ chạy trong script riêng (không nằm trong repo). Dữ liệu lấy từ DB.

### 7.1. Damping mạnh hơn cho Holt

Thử thay lưới `_PHIS` hiện tại (0,8 / 0,9 / 0,98) bằng các giá trị nhỏ hơn.

| Mô hình | Toàn kho | 10 bang | 15 danh mục |
|---|---|---|---|
| Holt hiện tại | 12,0 (+3,9) | 13,6 (+4,7) | 20,9 (+4,3) |
| Blend hiện tại | 11,2 (0,0) | 12,9 (+0,3) | 20,0 (+0,4) |
| Holt phi 0,5 đến 0,7 | 10,4 (−2,1) | 13,8 (−1,8) | 20,0 (−1,6) |
| Holt phi 0,3 đến 0,5 | 11,2 (−3,1) | 14,0 (−3,1) | 20,3 (−2,5) |
| Blend với phi 0,5 đến 0,7 | 11,3 | 14,3 | 20,1 |

- Holt phi 0,5 đến 0,7 tốt hơn Holt hiện tại (thắng ở 17/25 chuỗi bang và danh mục).
- So với **blend hiện tại**: hòa (trung bình ba mức 14,73 so với 14,70). Damping thắng toàn kho, blend thắng bang, hòa danh mục.
- Damping quá mạnh (phi 0,3 trở xuống) lại kém đi.
- Tham số được chọn sau khi thử 4 cấu hình trên đúng cửa sổ dữ liệu này, nên kết quả hơi lạc quan.
- **Kết luận: không đổi, giữ blend.**

### 7.2. Đệm tuyệt đối, nội suy tuyến tính

Đánh giá **ngoài mẫu**: mỗi tháng chỉ học đệm từ các tháng trước. Mẫu kiểm tra là các tháng 2018-02 đến 2018-08 (cần ít nhất 5 tháng học, nên không có tháng sự kiện nào trong mẫu kiểm tra). Mức 90% nghĩa là kỳ vọng thiếu hàng khoảng 10%.

**Gộp 26 chuỗi (182 quan sát), so các phương án:**

| Phương án | Thiếu hàng thực tế ở nhãn 90% | Dư hàng ở nhãn 90% | Dư hàng khi thiếu hàng bằng 10% |
|---|---|---|---|
| A. Hiện tại (blend, tỷ lệ, `higher`, bỏ sự kiện) | 3,8% | 33,5% | 19,7% |
| B. File đề xuất (Holt, tuyệt đối, đủ 14 tháng) | 3,8% | 28,9% | 18,2% |
| C. Holt, tuyệt đối, bỏ sự kiện | 10,4% | 19,1% | 20,1% |
| **D. Blend, tuyệt đối, bỏ sự kiện** | 8,2% | 20,2% | 17,1% |
| F. Holt phi 0,5 đến 0,7, tuyệt đối, bỏ sự kiện | 8,8% | 18,4% | 17,2% |

**Theo từng mức, số món, ghi "thiếu hàng % / dư hàng %":**

| Mức | Phương án | q=0,85 | q=0,90 | q=0,95 | q=0,99 |
|---|---|---|---|---|---|
| 10 bang (70 quan sát) | Hiện tại (tỷ lệ, `higher`) | 1,4 / 24,3 | 1,4 / 30,2 | 1,4 / 32,0 | 1,4 / 32,0 |
| | **D: tuyệt đối, bỏ sự kiện** | 5,7 / 14,1 | 4,3 / 16,8 | 2,9 / 21,2 | 1,4 / 24,7 |
| | Tuyệt đối, tính cả sự kiện | 2,9 / 21,3 | 0,0 / 28,4 | 0,0 / 38,4 | 0,0 / 46,8 |
| 15 danh mục (105 quan sát) | Hiện tại | 6,7 / 41,4 | 5,7 / 47,6 | 5,7 / 49,6 | 5,7 / 49,6 |
| | **D: tuyệt đối, bỏ sự kiện** | 12,4 / 27,1 | 11,4 / 30,0 | 10,5 / 32,0 | 9,5 / 33,7 |
| | Tuyệt đối, tính cả sự kiện | 9,5 / 30,4 | 6,7 / 35,6 | 4,8 / 44,3 | 4,8 / 51,8 |

**Độ ổn định** (toàn kho, số món, q = 0,9, dự báo tháng 9/2018, bỏ lần lượt từng tháng khỏi mẫu học):

| Công thức | Lượng nhập đầy đủ | Khoảng dao động khi bỏ 1 tháng | Biên độ |
|---|---|---|---|
| Tuyệt đối + `linear` (blend, bỏ sự kiện) | 7.519 (đệm +454) | 7.214 đến 7.553 | 4,5% |
| Tỷ lệ + `higher` (hiện tại) | 7.942 | 7.291 đến 7.942 | 8,2% |

Nhận xét:
- Bản tuyệt đối có **ít dư hàng hơn rõ rệt** ở mọi mức (danh mục ở 90%: dư 30,0% so với 47,6%) và nhãn khớp thực tế hơn.
- Ở cùng tỷ lệ thiếu hàng 10%, lượng dư của các phương án gần nhau (17 đến 20%). Lợi ích chính là nhãn đúng hơn, ít dư hàng ở cùng nhãn, ổn định hơn và công thức bám bài báo.
- **Tính cả sự kiện vẫn quá dè dặt** (nhãn 90% thiếu hàng 0 đến 7%, dư 28 đến 36%), nên `excludeEvent` phải bật.
- Ở mức cao, tỷ lệ thiếu hàng không đạt mục tiêu (danh mục ở 95%: 10,5% thay vì 5%; ở 99%: 9,5% thay vì 1%), khớp với nhận xét của bài báo về phân vị 99%.
- Các số "toàn kho" chỉ có 7 quan sát, không dùng để kết luận.
- **Kết luận: áp dụng** với blend và `excludeEvent` bật. Không cần đổi sang Holt.

### 7.3. What-if doanh thu thay what-if lợi nhuận

Không có sai số để chấm. Kiểm tra tính hợp lệ của đầu vào:

- Doanh thu bằng dự báo số món nhân giá trung bình 3 tháng cho WAPE 10,7%, so với 11,6% khi dự báo trực tiếp doanh thu. Phần giá đứng vững.
- Black Friday 2017-11 so với trung bình tháng 9 và 10: số món +70,3%, giá trung bình mỗi món −7,7%, doanh thu +57,3%.
- Hòa vốn doanh thu: `u* = d/(1−d)`. Giảm giá 10% chỉ cần cầu tăng 11,1% (so với 40% theo hòa vốn lợi nhuận biên 35%). Nếu không ghi rõ đây là doanh thu, người dùng dễ kết luận khuyến mãi có lời.
- **Kết luận: không thay.**

### 7.4. Hướng A: chọn mức nhập theo tỷ lệ chi phí (newsvendor)

Người dùng nhập tỷ lệ r = chi phí một món thiếu / chi phí một món dư. Mức phân vị lý thuyết là `q* = r/(1+r)`. Chi phí = r × số món thiếu + 1 × số món dư, chia tổng cầu (ngoài mẫu, đệm tuyệt đối với blend và bỏ sự kiện).

| Mức | r | q* | Chi phí tại q* | Không đệm (q=0,5) | Cố định q=0,9 | q tốt nhất thực tế |
|---|---|---|---|---|---|---|
| 10 bang | 1 | 0,50 | 9,49 | 9,49 | 16,81 | 0,5 |
| | 3 | 0,75 | 12,54 | **11,52** | 16,93 | 0,5 |
| | 9 | 0,90 | 17,28 | 17,62 | 17,28 | **0,8** (13,98) |
| | 19 | 0,95 | 21,86 | 27,80 | **17,87** | **0,8** (15,40) |
| 15 danh mục | 3 | 0,75 | 28,63 | **27,06** | 34,46 | 0,6 |
| | 9 | 0,90 | 43,42 | 57,25 | 43,42 | 0,99 |
| | 19 | 0,95 | 53,10 | 107,57 | 58,35 | 0,99 |

- **Chấm điểm được ngoài mẫu**, khác với what-if khuyến mãi.
- **Công thức `q* = r/(1+r)` không trùng mức tốt nhất thực tế.** Với r từ 1 đến 5, nhập theo q* còn tốn hơn không đệm. Với r lớn, mức tốt nhất ở bang là 0,8 (thấp hơn q*), ở danh mục là 0,99 (cao hơn q*). Nguyên nhân là phân vị ước lượng từ 12 điểm rất nhiễu và giai đoạn kiểm tra chỉ có 7 tháng.
- Tham số r vẫn là giả định (Olist không có chi phí).
- Cùng q*, công thức tuyệt đối luôn rẻ hơn công thức tỷ lệ cũ (ví dụ bang r=9: 17,3 so với 30,3).
- **Kết luận: không thêm.** Logic không gượng ép, nhưng thực nghiệm không xác nhận công thức, và thêm một khẳng định phải bảo vệ.

## 8. Kết luận cuối cùng

| Đề xuất | Quyết định | Lý do chính |
|---|---|---|
| Bỏ blend, dùng Holt | Không áp dụng | Blend tốt hơn Holt ở cả 3 mức. Damping ngang blend, không hơn. |
| Đệm tuyệt đối + `linear` + blend + `excludeEvent` bật | **Áp dụng (đã triển khai)** | Ít dư hàng hơn, ổn định hơn, nhãn đúng hơn, bám đúng bài báo nên dễ giải thích |
| What-if doanh thu | Không áp dụng | Dễ hiểu nhầm doanh thu là lợi nhuận |
| What-if newsvendor | Không áp dụng | Thực nghiệm không xác nhận `q* = r/(1+r)` |
| Bỏ what-if khuyến mãi | **Bỏ (đã triển khai)** | Hai giả định không có dữ liệu, không kiểm chứng được |
| Mức phân vị 85, 90, 95, 99% | **Áp dụng (đã triển khai)** | Khớp các mức của bài báo nguồn. Mức 70 và 80% không có trong bài |

Về what-if khuyến mãi: trang có **đường đánh đổi thiếu hàng và dư hàng**, tính từ dữ liệu thật và cho người dùng chọn mức phân vị. Đó là phần kịch bản có cơ sở của DSS. Khi trình bày có thể nói: "Phần kịch bản của DSS là đường đánh đổi theo phân vị, tính từ backtest. What-if khuyến mãi không làm vì dữ liệu không có giá vốn hay đợt khuyến mãi để kiểm chứng." Nếu sau này thầy yêu cầu bắt buộc có phân tích kịch bản, cần dựng lại (mã cũ còn trong lịch sử git) và ghi rõ trên giao diện rằng đây là giả định minh họa.

Việc nhỏ nên làm thêm: ghi rõ trên trang rằng kết quả dựa trên mẫu 12 đến 14 tháng (đã thêm vào `note` của API và mô tả đường đánh đổi).

## 9. Đã triển khai vào mã

Ba thay đổi: (1) đệm theo sai số tuyệt đối, (2) bỏ what-if khuyến mãi, (3) các mức phân vị còn 85, 90, 95, 99%. Giữ nguyên blend và mặc định bật bỏ Black Friday.

| File | Thay đổi |
|---|---|
| `backend/app/features/dss/forecast.py` | Thay `relative_errors` bằng `forecast_errors` (thực tế − dự báo). `_quantile` dùng `method="linear"`. `order_plan` trả `buffer` (đúng đơn vị), `buffer_pct` (chỉ hiển thị), `n_errors`. `tradeoff` học đệm kiểu leave-one-out theo công thức cộng. `SERVICE_LEVELS = (0.85, 0.9, 0.95, 0.99)`. Thêm `MIN_ERRORS = 3`. **Xóa** `breakeven_uplift`, `sensitivity_grid`, `promo_scenarios`, `event_uplift` và các hằng số lưới của what-if |
| `backend/app/features/dss/routes.py` | `_forecast_bundle` dùng `forecast_errors`. Sửa `note`. **Xóa** `GET /api/dss/whatif` và trường `event_uplift` trong `/api/dss/forecast`. Tham số `service` giờ chỉ nhận 0,85 đến 0,99 |
| `frontend/src/features/dss/services/dssApi.ts` | Kiểu `order` có `buffer`, `n_errors`. **Xóa** `WhatIfInputs`, `DEFAULT_WHATIF`, `WhatIfScenario`, `DssWhatIf`, `getDssWhatIf`, `event_uplift` |
| `frontend/src/features/dss/format.ts` | Thêm `signedMetric`. Xóa `signedPct` và `units` (chỉ what-if dùng) |
| `frontend/src/features/dss/components/whatif-panel.tsx` | **Xóa file** |
| `frontend/src/features/dss/components/dss-page.tsx` | Thẻ "Lượng nhập đề xuất" hiện đệm bằng món hoặc R$ kèm số tháng trong mẫu. Nhãn "Mức phục vụ" đổi thành "Phân vị sai số", chỉ còn 4 mức. Gỡ `WhatIfPanel`, truy vấn what-if và ý "Khuyến mãi" trong khung kết luận. Cập nhật mô tả trang |
| `docs/dss_thay_doi.md` | Viết lại mục "Quyết định nhập hàng", xóa mục what-if, cập nhật API và số đo |
| `docs/dss_ly_do_chuyen_huong.md` | Thêm ghi chú đầu file: what-if đã bỏ |

**Kiểm tra sau khi sửa** (trên DB, qua API thật `GET /api/dss/forecast`, toàn kho, số món, blend, bỏ Black Friday):

| Phân vị | Đệm | Lượng nhập | Số tháng trong mẫu |
|---|---|---|---|
| 85% | +267,20 (+3,8%) | 7.332,38 | 12 |
| **90%** | **+453,64 (+6,4%)** | **7.518,82** | 12 |
| 95% | +855,56 (+12,1%) | 7.920,75 | 12 |
| 99% | +1.215,41 (+17,2%) | 8.280,59 | 12 |
| 90%, tính cả Black Friday | +1.060,02 (+15,0%) | 8.125,20 | 14 |
| 90% trước khi sửa (blend, tỷ lệ) | +12,4% | 7.942 | 12 |

- Số 7.518,82 khớp với kết quả phép thử (7.519). Đường đánh đổi trả đúng 4 mức (0,85, 0,9, 0,95, 0,99).
- `service=0.7` trả 400 ("service là số từ 0.85 đến 0.99"). `GET /api/dss/whatif` trả 404. `/api/dss/options` và `/api/dss/accuracy` vẫn trả 200. API theo danh mục (`bed_bath_table`) vẫn trả 200.
- Kiểm tra kiểu của frontend (`tsc`) và `oxlint` không báo lỗi. Chưa mở giao diện trên trình duyệt.
- Chưa sửa `sql/dss/01_demand_mart.sql` (comment đầu file và `COMMENT ON VIEW` vẫn nhắc what-if khuyến mãi), vì sửa `COMMENT ON VIEW` cần chạy lại `run_dss_01.py`.

## 10. Hạn chế của các phép thử

- Phép thử đệm ngoài mẫu chỉ có 7 tháng kiểm tra (2018-02 đến 2018-08), không có tháng sự kiện nào. Chưa kiểm tra trường hợp tháng cần nhập là tháng sự kiện. Khi đó phương án bỏ sự kiện sẽ nhập thiếu.
- 26 chuỗi được gộp chung nhưng cùng chung các tháng nên không độc lập.
- Tham số damping được chọn sau khi thử 4 cấu hình trên đúng dữ liệu này.
- Đường đánh đổi trên trang dùng leave-one-out (có dùng cả tháng sau để học), nên tỷ lệ thiếu hàng hiển thị có thể khác phép thử ngoài mẫu. Ví dụ toàn kho ở 90%: leave-one-out cho 16,7% thiếu hàng (12 tháng), còn phép thử ngoài mẫu gộp cho 8,2%.
- Các số về what-if chỉ là quan sát, không có đợt khuyến mãi nào được ghi lại để so sánh.
- Các script chạy thử nằm trong thư mục tạm của phiên làm việc, chưa đưa vào repo.
