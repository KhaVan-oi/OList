# OLAP đang xử lý

Ba chủ đề, chỉ đơn `delivered`. Ba thước đo tiền đứng riêng, không cộng thành một “doanh thu”:

| Thước đo | Nguồn | Đang đọc từ kho |
|---|---|---|
| Doanh thu hàng | `sum(price)` trên `fact_sales` | 13.221.498,11 R$ |
| Cước | `sum(freight_value)` trên `fact_sales` | 2.198.275,64 R$ |
| Thanh toán | `sum(total_payment_value)` trên `fact_customer_order` | 15.422.461,77 R$ |

Giá cộng cước là 15.419.773,75 R$. Thanh toán lệch 2.688,02 R$.

**Tăng trưởng năm và quý luôn so cùng kỳ.** Dữ liệu delivered chỉ có 2016-09..2018-08 (thiếu 2016-11), nên tổng cả kỳ chia tổng cả kỳ trước sẽ trộn chênh lệch số tháng vào tăng trưởng (2018/2017 ra +21% thay vì +141% cùng kỳ). YoY chỉ cộng các tháng có ở cả hai năm; QoQ ghép tháng thứ k của quý với tháng thứ k của quý trước. Tổng của kỳ vẫn đầy đủ. Mã: `backend/app/features/sales_time/growth.py` và `sql/olap/01_sales_time.sql` phần 2 + 3. Lý do chi tiết: `docs/ra_soat_xu_ly_du_lieu.md`. Địa lý lấy trên đơn (`customer_state`, `customer_city`), không lấy từ `dim_customer`. Một đơn có thể nhiều danh mục và nhiều seller, nên không cộng cột đơn xuyên danh mục hoặc xuyên seller. Cộng đơn theo bang thì được, vì một đơn chỉ một bang. Năm 2016 và 2018 chưa đủ 12 tháng có giao dịch.

RFM, K-Means và what-if nằm ở DSS, không thuộc ba file này. Kho không có điểm review, loại thanh toán, hay số ngày giao hàng trong schema sao.

## Thao tác

Cùng một bộ thao tác, mỗi chủ đề áp vào một cây khác nhau.

| Thao tác | Việc nó làm | Cây |
|---|---|---|
| Tổng hợp | Một grain cố định, kèm tăng trưởng kỳ trước và lũy kế trong năm | Thời gian: tháng, quý, năm. Hàng hóa: một dòng tổng. Khách: KPI toàn kho |
| Cuộn (roll-up) | Nhảy lên một mức tổng, không mở cây lồng nhau. Đơn được đếm lại, không cộng từ dòng con | Thời gian: tháng → quý → năm → tổng. Hàng hóa: thành phố → bang → tổng. Khách: bậc tần suất → mua một lần / mua lại → tổng; và trạng thái × bang → trạng thái → tổng |
| Khoan (drill-down) | Đi xuống một nhánh | Thời gian sâu 4: năm → quý → tháng → ngày. Cuối tuần là lọc ở lá. Hàng hóa sâu 3: tổng → bang → thành phố |
| Lát (slice) | Giữ một giá trị của một chiều, xem các chiều còn lại | Một năm, một danh mục, hoặc nhóm VIP |
| Khối (dice) | Giao nhiều điều kiện cùng lúc | Quý và cuối tuần; seller × bang × danh mục; bang × năm × khách mua lại |
| Xoay (pivot) | Một chiều thành cột | Tháng × năm (Thời gian). Khách: bang × trạng thái; 5 bang × năm (chưa UI). Hàng hóa không dùng pivot — lát danh mục + bang đã đủ |
| Hạng | Thứ hạng trong một nhóm, không phải hạng toàn kho | Top danh mục trong từng bang; top khách chi trong từng bang |

## 1. Thời gian — `sql/olap/01_sales_time.sql`

Màn `/thoi-gian`. API `/api/sales-time/*` (alias `/api/olap/*`). Sáu chip: Khoan, Tổng, Cuộn, Lát, Khối, Xoay. Phần 1–3 dùng chung chip Tổng, đổi grain Tháng / Quý / Năm.

| Phần | Thao tác | Câu hỏi | Chip |
|---|---|---|---|
| 0 | Nền delivered | Tập nào được tính? | Không có chip. Mỗi câu tự lọc delivered |
| 1 | Tổng theo tháng, MoM, YTD | Tháng này bán được bao nhiêu so với tháng trước, và từ đầu năm đến nay? | Tổng → Tháng |
| 2 | Tổng theo quý, QoQ **cùng kỳ** | Quý này hơn hay kém quý trước? | Tổng → Quý. Cột số tháng có dữ liệu / số tháng so |
| 3 | Tổng theo năm, YoY **cùng kỳ** | Năm nay hơn năm trước bao nhiêu phần trăm, trên cùng các tháng? | Tổng → Năm. 2018 (T1–T8) so với T1–T8/2017: +141,13% |
| 4 | Cuộn tháng → quý → năm → tổng | Tổng một quý hoặc một năm là bao nhiêu khi không cộng tay từ dòng con? | Cuộn |
| 5 | Khoan năm → quý → tháng → ngày | Ngày nào trong tháng đang xem tạo ra doanh thu? Cuối tuần có khác ngày thường không? | Khoan. Cuối tuần chỉ ở mức ngày |
| 6 | Lát một năm, 12 tháng, MoM | Trong đúng một năm, tháng nào kéo doanh thu? | Lát |
| 7 | Khối quý, cuối tuần, khoảng năm | Các ngày cuối tuần của một quý, trong một khoảng năm, bán thế nào? | Khối |
| 8 | Xoay tháng × năm | Cùng một tháng lịch, ba năm đứng cạnh nhau ra sao? MoM của tháng đó trong từng năm là bao nhiêu? | Xoay. Có thêm cước và số món; SQL gốc chỉ xoay doanh thu hàng |

## 2. Hàng hóa, seller, địa lý — `sql/olap/02_product_seller_geo.sql`

Màn `/hang-hoa`. API `/api/product-geo/*` (alias `/api/olap/product/*`). Không có pivot riêng: lát danh mục đã chiếu ra chart Bang.

| Phần | Thao tác | Câu hỏi | Chip |
|---|---|---|---|
| 0 | Tổng doanh thu hàng, cước, món, đơn | Toàn kho delivered bán được bao nhiêu, ship bao nhiêu, bao nhiêu món, bao nhiêu đơn? | Tổng |
| 1 | Top danh mục | Danh mục nào mang doanh thu hàng? | Danh mục |
| 2 | Top seller | Seller nào mang doanh thu hàng? | Seller |
| 3 | Pareto 20% mã sản phẩm | Một nhóm nhỏ sản phẩm có đang chiếm phần lớn doanh thu không? | Pareto. Một dòng tóm tắt, không có đường cong |
| 4 | Cước / giá | Cước đang nặng bao nhiêu so với giá bán? | Cước |
| 5 | Doanh thu và đơn theo bang | Bang nào là thị trường của đơn? | Bang |
| 6 | Cuộn thành phố → bang → tổng | Tổng một bang có khớp khi đếm lại đơn, không cộng đơn của từng thành phố? | Cuộn |
| 7 | Khoan tổng → bang → thành phố | Trong một bang, thành phố nào đang mua? | Khoan |
| 8 | Lát một hoặc vài danh mục × bang | Danh mục này bán chạy ở bang nào? | Lát. Mặc định `health_beauty` |
| 9 | Khối top seller toàn kho ∩ bang ∩ danh mục | Những seller lớn của toàn kho có thực sự bán danh mục này ở các bang khách (đủ bang delivered) không? | Khối. Không xếp hạng lại trong khối. UI/SQL cho chọn đủ 27 bang; mặc định khối mở SP, RJ, MG |
| 10 | Hạng top danh mục trong từng bang | Trong bang này khách mua danh mục gì, kể cả khi danh mục đó không phải top toàn kho? | Hạng. UI mặc định top 5 trong bang; «Xem thêm danh mục» mới tải đủ (tối đa 200) |

## 3. Khách và thanh toán — `sql/olap/03_customer_payment.sql`

Tiền ở đây là thanh toán của đơn, không phải doanh thu hàng. Màn `/khach` hiện chỉ có một bảng bậc tần suất. API có thêm vài route, chưa đủ các phần SQL, và chưa có chip.

| Phần | Thao tác | Câu hỏi | Đang có ở đâu |
|---|---|---|---|
| 0 | Nền | Bao nhiêu khách, bao nhiêu đơn delivered, thanh toán và AOV là bao nhiêu? | Tổng quan đọc các số này. API khách chưa có route riêng |
| 1 | Repeat rate và ARPU | Bao nhiêu khách mua lại, mỗi khách đóng góp bao nhiêu thanh toán? | Tổng quan có tỷ lệ mua lại. Màn Khách chỉ hiện bậc tần suất |
| 2 | Tỷ lệ theo trạng thái đơn | Đơn chết ở trạng thái nào, và tiền chỉ ghi nhận khi delivered? | API `/statuses`. Chưa lên màn |
| 3 | Khách, đơn, thanh toán, AOV theo bang | Bang nào mang thanh toán, giá trị đơn trung bình ra sao? | API `/states`. Chưa lên màn |
| 4a | Cuộn bậc tần suất → mua một lần / mua lại → tổng | Khách mua một lần và khách mua lại đóng góp khác nhau thế nào? | API `/frequency` là chi tiết bậc 1, 2, 3, ≥ 4. Màn Khách đang hiện bảng này. Chưa có mức cuộn |
| 4b | Cuộn trạng thái × bang → trạng thái → tổng | Một trạng thái đơn phân bố ở bang nào? | Chưa có |
| 5 | Khối bang lớn × năm | SP, RJ, MG, RS, PR theo từng năm thanh toán bao nhiêu? | API `/cube` là `GROUP BY` có lọc, chưa phải `GROUP BY CUBE` của file SQL |
| 6a | Khoan tổng → nhóm khách → bậc tần suất | Trong nhóm mua lại, khách mua 2 đơn, 3 đơn hay từ 4 đơn? | Chưa có cây. Bảng tần suất là lá của cây này |
| 6b | Khoan tổng → bang → thành phố trên thanh toán | Thành phố nào mang thanh toán? | Chưa có |
| 7a | Lát VIP, chi trên 1.000 R$ | Những khách chi nhiều là ai? | API `/vip`. Chưa lên màn. Kho có 1.149 khách |
| 7b | Lát VIP theo bang | VIP tập trung ở bang nào? | Chưa có |
| 8 | Khối bang × năm × khách có ít nhất 2 đơn | Khách mua lại ở vài bang, vài năm, đang chi bao nhiêu? | API `/dice` gom theo bang × năm. File SQL còn một câu liệt kê top khách trong khối |
| 9a | Xoay 27 bang × trạng thái đơn | Trạng thái đơn có khác nhau giữa các bang không? | Chưa có |
| 9b | Xoay 5 bang × 3 năm, kèm cỡ đơn | Thanh toán của năm bang lớn đổi thế nào qua các năm, và đơn nhỏ hay đơn lớn? | Chưa có |
| 10 | Hạng top khách trong từng bang, và phân vị chi tiêu | Trong một bang, ai chi nhiều nhất, và khách này nằm ở phân vị nào của cả nước? | Chưa có |

## Chip hiện tại so với câu hỏi

Thời gian đã gộp đúng: ba câu tổng hợp tháng / quý / năm là một chip, grain đổi bên trong. Hàng hóa không còn pivot.

| Câu người dùng muốn biết | Chip đang tách |
|---|---|
| Khoảng thời gian nào bán chạy, và so với kỳ trước? | Khoan, Tổng, Cuộn, Lát, Khối, Xoay của màn Thời gian |
| Cái gì và ai đang mang doanh thu hàng? | Danh mục, Seller, Pareto, Hạng |
| Cước có đang nặng hơn giá không? | Tổng, Cước |
| Hàng đang bán ở đâu? | Khoan, Cuộn, Bang |
| Một lát đã chọn bán ở đâu, và seller lớn có nằm trong lát đó không? | Lát, Khối |
| Khách có quay lại, và thanh toán nằm ở đâu? | Màn Khách mới có bậc tần suất. Các phần 2–10 của file khách chưa thành chip |
