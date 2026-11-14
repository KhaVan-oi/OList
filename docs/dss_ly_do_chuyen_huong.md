# Vì sao DSS chuyển từ phân khúc khách hàng sang nhập hàng và khuyến mãi

> **Cập nhật:** phần what-if khuyến mãi mô tả dưới đây đã được bỏ khỏi hệ thống (xem [dss_danh_gia_de_xuat.md](dss_danh_gia_de_xuat.md)). Tài liệu này giữ nguyên để ghi lại lý do chuyển hướng ban đầu.

## Tóm tắt

Kế hoạch ban đầu của nhóm cho Giai đoạn 5 là RFM, K-means, what-if và ma trận khuyến nghị theo phân khúc khách
hàng. Trước khi làm, chúng ta thử từng hướng trên dữ liệu thật. Kết quả: **mọi hướng ở cấp từng khách và từng
seller đều cho tín hiệu yếu hoặc không ổn định**, vì dữ liệu Olist không cho biết khách nào sẽ quay lại. Hướng
dự báo nhu cầu theo tháng đo được và chính xác hơn rõ rệt, nên DSS chuyển sang **hỗ trợ quyết định nhập hàng và
khuyến mãi**.

Tất cả script thăm dò nằm ở [dss_exploration/](dss_exploration/). Mọi con số dưới đây chạy lại được.

## 1. Gốc của vấn đề: 97% khách chỉ mua một lần

Trong 93.358 khách có đơn delivered, 90.557 khách (97,00%) chỉ mua đúng một đơn (số của
[sql/olap/03_customer_payment.md](../sql/olap/03_customer_payment.md)).

- Điểm F của RFM gần như là hằng số, nên RFM rút thành R × M.
- R của khách mua một lần chỉ là "đã bao lâu kể từ đơn duy nhất", không phải hành vi.
- Tỷ lệ mua lại trong 180 ngày kể từ đơn đầu (trên 55.907 khách đủ thời gian quan sát) là **3,12%**.

Đây là một đặc điểm thật của dữ liệu. Nó không làm hỏng ETL hay OLAP, nhưng nó giới hạn mọi mô hình phân khúc
hướng tới việc giữ chân khách.

## 2. Những gì đã thử và kết quả

Mỗi hướng dưới đây chạy với kiểm tra theo thời gian (huấn luyện trước, kiểm tra sau), không kiểm tra trên cùng
dữ liệu đã dùng để học.

### 2.1. Phân khúc khách hàng bằng K-means (script 05)

Đặc trưng lấy từ đơn đầu tiên: chi tiêu, số món, tỷ lệ cước trên giá, vùng, nhóm danh mục.

| Chỉ số | Kết quả |
|---|---|
| Silhouette | 0,23 đến 0,32 (cụm tách yếu) |
| Ổn định bootstrap (ARI) | 0,42 (k=4) đến 0,51 (k=6) |
| Tỷ lệ mua lại giữa các cụm | 2,3% đến 4,7%, nền 3,0% |
| AUC dùng cụm để dự đoán mua lại | 0,52 (k=4), 0,55 (k=6) |
| **Trần**: mô hình có giám sát, cùng đặc trưng | AUC 0,56 |
| AUC chỉ dùng chi tiêu đơn đầu | 0,49 (không hơn ngẫu nhiên) |

Các cụm khác nhau có ý nghĩa thống kê (chi-square p < 0,05) nhưng chênh lệch nhỏ. Ngay cả mô hình có giám sát cũng
chỉ đạt AUC 0,56, tức giới hạn nằm ở **thông tin có trong dữ liệu**, không nằm ở thuật toán K-means.

### 2.2. Trải nghiệm đơn đầu có làm khách quay lại không? (script 01)

Giả thuyết hợp lý: giao trễ và review thấp làm khách bỏ đi. Dữ liệu không ủng hộ.

| Nhóm đơn đầu | Mua lại trong 180 ngày |
|---|---|
| Review 1 / 2 / 3 / 4 / 5 sao | 3,15% / 3,03% / 3,28% / 2,75% / 3,22% |
| Giao đúng hạn (52.127 đơn) | 3,15% |
| Giao trễ (3.778 đơn) | 2,65% |

Giao trễ có liên quan mạnh đến review (4,29 sao khi đúng hạn, 2,27 sao khi trễ, tỷ lệ trễ 6,8%), nhưng review
không liên quan đến mua lại. Vì vậy một DSS kiểu "giảm giao trễ để khách quay lại" sẽ phải dựa trên giả định mà
dữ liệu không ủng hộ.

### 2.3. Dự đoán đơn trễ và chính sách ngày hứa giao (script 02, 03)

| Giai đoạn kiểm tra | Tỷ lệ trễ hiện tại | AUC dự đoán trễ | Chính sách ngày hứa theo phân vị 0,93: tỷ lệ trễ mới |
|---|---|---|---|
| 2017Q4 | 8,7% | 0,56 | 4,8% (hứa dài thêm 6,5 ngày) |
| 2018Q1 (đột biến) | 12,9% | 0,62 | **16,8%** (tệ hơn) |
| 2018Q2 | 4,2% | 0,70 | 5,0% (tệ hơn, hứa ngắn hơn 4,2 ngày) |
| 2018Q3 | 4,8% | 0,57 | 2,7% (hứa dài thêm 1,4 ngày) |

AUC dao động 0,56 đến 0,70 theo giai đoạn. Chính sách ngày hứa thắng ở một giai đoạn, hòa hoặc đánh đổi ở hai
giai đoạn, và **thua rõ khi gặp đột biến** (2018Q1). Chỉ so với "cộng đều số ngày cho mọi đơn" ở cùng độ dài hứa
thì nó tốt hơn ở 3 trên 4 giai đoạn, nhưng đó là kết luận hẹp hơn nhiều so với "hơn chính sách hiện tại".

### 2.4. Phân khúc và loại bỏ seller kém (script 04)

| Chỉ số | Kết quả |
|---|---|
| Tương quan hạng giữa hai giai đoạn (trễ / review / review thấp) | 0,33 / 0,46 / 0,42 (một mốc chia); 0,24 / 0,39 / 0,31 (mốc khác) |
| Loại seller kém nhất, mất 15% doanh thu giai đoạn sau | Tỷ lệ trễ 7,5% xuống 7,2%; review 4,06 lên 4,12 |
| Giới hạn trên: biết trước tương lai (oracle), cùng mức mất 15% | Tỷ lệ trễ 6,6% |
| Phân khúc K-means seller (k=4): silhouette, ARI bootstrap | 0,26, 0,68 |
| ARI giữa phân cụm hai giai đoạn độc lập | 0,07 |

Mất 15% doanh thu chỉ giảm tỷ lệ trễ khoảng 0,3 điểm phần trăm; ngay cả biết trước tương lai cũng chỉ giảm 0,9 điểm.
Tình trạng trễ trải đều trên nhiều seller, không tập trung ở một nhóm nhỏ nên can thiệp vào seller ít hiệu quả.

### 2.5. Dự báo nhu cầu theo tháng (script 06, và hệ thống DSS)

Backtest trượt theo thời gian, dự báo trước 1 tháng, 14 tháng kiểm tra (2017-07 đến 2018-08), đo số món bán.
Con số dưới đây là của hệ thống DSS (`/api/dss/accuracy`).

| Mức tổng hợp | WAPE mô hình mặc định (kết hợp) | Baseline "tháng trước" | Bỏ Black Friday: kết hợp / tháng trước |
|---|---|---|---|
| Tổng toàn kho | 11,2% | 12,2% | 7,4% / 7,5% |
| 10 bang lớn | 12,9% | 15,0% | 9,3% / 10,6% |
| 15 danh mục lớn | 20,0% | 20,7% | 16,7% / 16,9% |

Kết quả này không loại trừ rủi ro nhưng khác hẳn các hướng trên ở ba điểm:

1. Nó **đo được bằng dữ liệu lịch sử** với một chỉ số quen thuộc (WAPE), không cần giả định về hành vi khách.
2. Mức tổng hợp càng cao càng chính xác. Ở mức tổng, độ chính xác khoảng 89% (WAPE 11%).
3. Quyết định đi kèm (lượng nhập) có chỉ số đo được từ chính backtest: tỷ lệ tháng thiếu hàng và mức dư hàng.

## 3. Vì sao chọn DSS nhập hàng và khuyến mãi

| Tiêu chí | Phân khúc khách (K-means, RFM) | Giao hàng, seller | **Dự báo nhu cầu, nhập hàng** |
|---|---|---|---|
| Dữ liệu cho phép dự báo tốt | Không (AUC trần 0,56) | Yếu, không ổn định theo thời gian | Có (WAPE 11% ở mức tổng) |
| Đo được hiệu quả bằng dữ liệu lịch sử | Không | Một phần, kết quả đổi chiều tùy giai đoạn | Có (backtest) |
| Cần sửa ETL | Không | Có (mốc giao hàng, review, geo) | **Không** |
| Giả định cần có | Uplift hành vi khách | Uplift hành vi khách | Chỉ ở phần what-if khuyến mãi, được tách rõ |
| Khớp gợi ý của đề bài | Có | Một phần | Có ("hỗ trợ quyết định nhập hàng, khuyến mãi", "dự báo nhu cầu") |

Đề bài (CO4031_Assignment_HK261.md) yêu cầu "một DSS đơn giản" với bước mô hình hóa rõ ràng và phần "đánh giá kết quả,
phân tích hạn chế". DSS mới đáp ứng cả ba, và các kết quả âm ở mục 2 chính là chất liệu cho phần hạn chế.

## 4. Giới hạn cần nói thẳng khi trình bày

- **Mô hình kết hợp chỉ hơn baseline "tháng trước" một chút** (11,2% so với 12,2% ở mức tổng, gần như hòa khi bỏ
  Black Friday). Mô hình trung bình 3 tháng còn có WAPE thấp nhất ở mức tổng (11,1%). Giá trị của DSS không nằm ở
  một thuật toán thông minh mà ở việc đo sai số thật, biến nó thành lượng đệm nhập hàng, và hiển thị rõ đánh đổi.
- **Chỉ có 14 tháng kiểm tra** và một sự kiện không có tiền lệ (Black Friday 2017). Mọi mô hình hụt khoảng 31 đến 39%
  ở tháng đó. Hệ thống báo cáo song song số liệu có và không có tháng này, và có công tắc để bỏ nó khỏi mẫu sai số.
- **Phần khuyến mãi là what-if với giả định của người dùng** (mức tăng cầu, mức giảm giá, biên lợi nhuận, tổn thất
  hàng dư). Kho không có thí nghiệm khuyến mãi nên không đo được hiệu quả thật. Black Friday 2017 chỉ là điểm tham
  chiếu quan sát (lẫn xu hướng tăng), không phải ước lượng nhân quả.
- **"Nhu cầu" ở đây là số món đã bán** trong đơn delivered. Kho không có tồn kho nên nhu cầu bị hụt hàng không thấy
  được, và dữ liệu cũng không có chi phí hay biên lợi nhuận thực.
- Dự báo chỉ trước **1 tháng**. Thời gian đặt hàng của nhà cung cấp dài hơn thì cần mở rộng.
- Mô hình mặc định được chọn **trước** khi nhìn kết quả theo từng mức (kết hợp naive và Holt, vì ensemble thường
  bền). Chế độ "tự chọn theo WAPE" chọn và đo trên cùng các tháng nên hơi lạc quan, và được ghi rõ ở giao diện.

## 5. Câu hỏi có thể gặp và cách trả lời

**Vì sao không làm RFM như kế hoạch ban đầu?**
97% khách chỉ mua một lần nên F là hằng số. K-means nhiều đặc trưng hơn cũng chỉ đạt AUC 0,52 đến 0,55 trong việc
dự đoán mua lại, sát trần 0,56 của mô hình có giám sát. Dữ liệu không đủ thông tin để phân khúc hướng giữ chân.

**Sao không dùng review và giao hàng, vì Olist có các cột đó?**
Chúng ta đã thử trên CSV gốc. Giao trễ làm review tụt mạnh, nhưng review và giao trễ gần như không liên quan đến
mua lại. Mô hình dự đoán đơn trễ chỉ đạt AUC 0,56 đến 0,70 và không bền theo thời gian.

**Độ chính xác bao nhiêu?**
WAPE 11% ở mức tổng, 13% ở 10 bang lớn, 20% ở 15 danh mục lớn, đo bằng backtest trượt trên 14 tháng. Mức chi tiết
càng cao thì càng kém, và hệ thống hiển thị điều đó thay vì chỉ báo con số đẹp nhất.

**Phần khuyến mãi có đáng tin không?**
Không nên coi là dự đoán. Đó là bảng "nếu thì" với giả định do người dùng nhập, kèm hòa vốn, kịch bản chỉ đạt một
phần mức tăng cầu, và bảng độ nhạy. Giá trị của nó là chỉ ra khi nào khuyến mãi lỗ, nhất là khi giảm giá gần bằng
biên lợi nhuận.
