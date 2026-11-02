# Bạn 3 — Customer / Payment & Behavioral Profiling (Hành vi thanh toán, Phân bố thuộc tính dẫn xuất R-F-M theo không gian địa lý)

File SQL là `sql/olap/03_customer_payment.sql`. File này đọc `dw` (sử dụng `TEMP VIEW valid_customer_orders`).

## Mục tiêu

Phân tích hành vi mua sắm của khách hàng, giá trị thanh toán đơn hàng (`AOV`, `Monetary`), tỷ lệ khách hàng quay lại, trạng thái vận hành đơn hàng và phân khúc khách hàng theo mô hình **RFM** trên `dw`.

Phạm vi số liệu:

- **Đơn tính chi tiêu / doanh thu thanh toán (`Monetary`), `AOV`, `Repeat Rate` và `RFM`:** Chỉ lấy đơn `order_status = 'delivered'` (**96.478** đơn của **93.358** khách hàng duy nhất).
- **Phân biệt chỉ số tiền giữa hai bảng Fact:**
  - `dw.fact_sales`: Doanh thu hàng bán = `sum(price)` (**13.221.498,11 R\$**), Cước vận chuyển = `sum(freight_value)` (**2.198.266,93 R\$**).
  - `dw.fact_customer_order`: Giá trị thanh toán đơn đã giao (`delivered_payment_value` / `Monetary`) = `sum(total_payment_value)` (**15.422.461,77 R\$**, đã gồm tiền hàng + cước vận chuyển) và `AOV` = `avg(total_payment_value)` (**159,86 R\$**).
- **Ngày:** Gắn theo `purchase_date_key` (ngày khách đặt hàng). Mốc chốt dữ liệu (`analysis_date`) để tính `recency_days` là `max(purchase_date)` của tập đơn `delivered` (`2018-08-29`).
- **Xử lý NULL thanh toán:** Có đúng 1 đơn `delivered` bị `total_payment_value IS NULL` trong nguồn; dùng `coalesce(total_payment_value, 0)` khi cộng tổng (`sum`) và giữ giá trị gốc khi tính trung bình (`avg`).

File SQL có đủ:

**Chỉ số KPI (`0` – `3`)**

- `0)` Tổng nền `valid_customer_orders`: tổng khách `delivered`, tổng số đơn `delivered`, tổng giá trị thanh toán (`delivered_payment_value`) và `delivered_aov`.
- `1)` Tỷ lệ khách hàng quay lại mua (`Repeat Customer Rate`: khách có `count(order_id) > 1`) và chi tiêu tích lũy bình quân mỗi khách (`ARPU`).
- `2)` Tỷ lệ hủy đơn / giao thành công theo 8 trạng thái `order_status` (chỉ ghi nhận `delivered_payment_value` và `delivered_aov` cho trạng thái `delivered`).
- `3)` Số khách hàng, số đơn, tổng giá trị thanh toán và `AOV` theo 27 bang (`customer_state`).

**Thao tác OLAP (`4a` – `9b`)**

1. **Roll-up (`4a`, `4b`)**
   - `4a`: `ROLLUP(buyer_group, frequency_tier)` trên Chiều Khách hàng — cuộn dọc theo Concept Hierarchy của Chiều Khách hàng từ mức chi tiết `Bậc tần suất (1, 2, 3, >= 4 đơn)` $\to$ `Nhóm khách (Mua 1 lần vs Mua lặp lại)` $\to$ `Toàn bộ khách hàng delivered (All)`.
   - `4b`: `ROLLUP(order_status, customer_state)` trên Chiều Vận hành trạng thái đơn — cuộn từ `(Trạng thái, Bang)` $\to$ `Trạng thái` $\to$ `Toàn bộ` (chỉ ghi nhận tiền cho `delivered`).
2. **Cube (`5`)** — `CUBE(customer_state, year)` trên 5 bang cố định `SP, RJ, MG, RS, PR` $\times$ 3 năm `2016, 2017, 2018`.
3. **Drill-down (`6a`, `6b`)**
   - `6a`: Drill-down trên Chiều Khách hàng (ngược hướng 100% với Roll-up `4a`): Khoan sâu từ `Toàn bộ khách hàng delivered (Cấp 0)` $\to$ `Nhóm mua 1 lần vs Nhóm mua lặp lại (Cấp 1)` $\to$ `Bậc tần suất chi tiết 1, 2, 3, >= 4 đơn (Cấp 2)`.
   - `6b`: Drill-down trên Chiều Địa lý: Khoan sâu dọc theo Concept Hierarchy Địa lý từ `Toàn quốc (27 bang - Cấp 0)` $\to$ `Bang SP (Sao Paulo - Cấp 1)` $\to$ `Top 15 thành phố tại Bang SP có thanh toán cao nhất (Cấp 2)`.
4. **Slice (`7a`, `7b`)** — Ứng dụng kỹ thuật rời rạc hóa (*Discretization* — Chapter 2-continue) tạo chiều phân hạng chi tiêu `spending_tier`, sau đó cố định lát cắt 1 chiều `WHERE spending_tier = 'VIP (> 1,000 R$)'`: danh sách Top 20 khách VIP (`7a`) và thống kê theo Bang (`7b`).
5. **Dice (`8a`, `8b`)** — Trích xuất khối Sub-cube đa chiều từ giao của các chiều: Địa lý (`SP, RJ, MG`) $\times$ Thời gian (`2017–2018`) $\times$ Phân loại khách (`Repeat Buyer >= 2 đơn`), giữ nguyên các trục `(customer_state, purchase_year)` ở câu `8a` và chi tiết Top 20 khách tại `SP` ở câu `8b`.
6. **Pivot (`9a`, `9b`)**
   - `9a`: Ma trận 27 Bang (dòng) $\times$ 8 Trạng thái đơn (cột) kèm tỷ lệ giao thành công (`%`) và `delivered_payment_value`.
   - `9b`: Ma trận 5 Bang cố định `SP, RJ, MG, RS, PR` (dòng) $\times$ 3 Năm `2016, 2017, 2018` (cả giá trị thanh toán và số đơn) kèm 3 bậc quy mô đơn hàng đã rời rạc hóa (`< 100 R$`, `100–500 R$`, `> 500 R$`).

**Hạng mục nâng cao (Window Functions — `10`)**

- `10)` Xếp hạng Top 3 khách hàng chi tiêu lớn nhất trong từng Bang lớn (`DENSE_RANK() OVER (PARTITION BY customer_state ORDER BY total_spend DESC)`) và phân vị chi tiêu toàn quốc (`PERCENT_RANK()`).
  - Phục vụ phân tích hồ sơ chi tiêu khách hàng theo không gian địa lý bằng ROLAP.
  - Đồng bộ cấu trúc bài làm với Bạn 1 (`LAG` MoM Growth) và Bạn 2 (`DENSE_RANK` Top sản phẩm theo bang).
  - *Lưu ý quan trọng:* Toàn bộ mô hình phân khúc RFM, thuật toán học máy K-Means Clustering, kịch bản mô phỏng What-if và ma trận khuyến nghị chiến lược được hiện thực trọn vẹn trong **Giai đoạn 5 (DSS)** theo đúng đề xuất phân công nhóm.

## Quy ước ngưỡng và số dòng hiển thị (`N`)

| Chỗ dùng | Ngưỡng / N | Ghi chú |
|---|---|---|
| Ngưỡng khách hàng mua lặp lại (`Repeat`) | `count(order_id) >= 2` | Tính trên đơn `delivered` theo `customer_unique_id` (2.801 khách = 3,00%) |
| Ngưỡng Slice khách hàng VIP | `spending_tier = 'VIP (> 1,000 R$)'` | Có 1.149 khách VIP toàn kho; câu `7a` hiển thị Top **20** khách |
| Khối Dice (`8a`, `8b`) | `SP, RJ, MG` $\times$ `2017–2018` $\times$ `>= 2 đơn` | Câu `8a` hiển thị Sub-cube 3 bang $\times$ 2 năm (6 ô); câu `8b` hiển thị Top **20** khách tại `SP` |
| CUBE (`5`) & Pivot (`9b`) | 5 bang cố định `SP, RJ, MG, RS, PR` |  |
| Xếp hạng Window Function (`10`) | Top 3 khách mỗi bang | 5 bang lớn `SP, RJ, MG, RS, PR` (15 dòng kết quả) |

## Chốt với nhóm trước khi ghép báo cáo

- **Tổng số đơn `delivered`** trong `valid_customer_orders` là **96.478 đơn** — khớp với `count(DISTINCT order_id)` trên `valid_sales` (96.478 đơn).
- **Định danh khách hàng** luôn dùng `customer_unique_id` trên `dw.dim_customer` (không đếm `customer_id`). Tổng khách có đơn `delivered` là **93.358 người**.
- **Vì sao điểm `F` (Frequency) dùng `CASE WHEN` thay vì `NTILE(4)`:** Trong 93.358 khách `delivered`, có **90.557 khách (97,00%) chỉ mua đúng 1 đơn**. Nếu áp `NTILE(4)` trực tiếp lên `frequency`, 97% khách mua 1 đơn sẽ bị chia ngẫu nhiên vào cả 4 nhóm điểm `1, 2, 3, 4`. Dùng `CASE WHEN` (`1 đơn -> 1`, `2 đơn -> 2`, `3 đơn -> 3`, `>= 4 đơn -> 4`) giữ đúng ý nghĩa hành vi mua lặp lại.
- **Phá hòa (Tie-breaking):** Mọi hàm cửa sổ (`NTILE(4)`, `ROW_NUMBER()`) và mệnh đề `ORDER BY ... LIMIT` đều có `customer_unique_id ASC` hoặc `customer_state ASC` ở cuối để kết quả cố định tuyệt đối giữa mọi lần chạy.

## Dữ liệu lấy từ đâu

```text
dw.fact_customer_order
    JOIN dw.dim_customer   ON customer_key
    JOIN dw.dim_date       ON purchase_date_key = date_key
```

`WHERE fact_customer_order.order_status = 'delivered'` (trừ câu `2`, `4b`, `9a` khi cần đếm tỷ lệ 8 trạng thái đơn).

