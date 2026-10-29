# Bạn 3 — Hành vi khách hàng, thanh toán và phân khúc RFM

File SQL là `sql/olap/03_customer_payment.sql`. File này chỉ đọc `dw` (sử dụng `TEMP VIEW valid_customer_orders`). Không sửa staging, không sửa schema kho.

## Mục tiêu

Phân tích hành vi mua sắm của khách hàng, giá trị thanh toán đơn hàng (`AOV`, `Monetary`), tỷ lệ khách hàng quay lại, trạng thái vận hành đơn hàng và phân khúc khách hàng theo mô hình **RFM** trên `dw`.

Phạm vi số liệu (đã chốt với Bạn 1 và Bạn 2):

- **Đơn tính chi tiêu / doanh thu thanh toán (`Monetary`), `AOV`, `Repeat Rate` và `RFM`:** Chỉ lấy đơn `order_status = 'delivered'` (**96.478** đơn của **93.358** khách hàng duy nhất).
- **Phân biệt chỉ số tiền giữa hai bảng Fact:**
  - Bạn 1 & Bạn 2 đọc `dw.fact_sales`: Doanh thu hàng bán = `sum(price)` (**13.221.498,11 R\$**), Cước vận chuyển = `sum(freight_value)` (**2.198.266,93 R\$**).
  - Bạn 3 đọc `dw.fact_customer_order`: Giá trị thanh toán đơn đã giao (`delivered_payment_value` / `Monetary`) = `sum(total_payment_value)` (**15.422.461,77 R\$**, đã gồm tiền hàng + cước vận chuyển) và `AOV` = `avg(total_payment_value)` (**159,86 R\$**).
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
   - `4a`: `ROLLUP(customer_state, year)` trên đơn `delivered` (Năm $\to$ Bang $\to$ Toàn bộ).
   - `4b`: `ROLLUP(order_status, customer_state)` trên toàn bộ trạng thái đơn (Bang $\to$ Trạng thái $\to$ Toàn bộ, chỉ ghi nhận tiền cho `delivered`).
2. **Cube (`5`)** — `CUBE(customer_state, year)` trên 5 bang cố định `SP, RJ, MG, RS, PR` $\times$ 3 năm `2016, 2017, 2018`.
3. **Drill-down (`6a`, `6b`)**
   - `6a`: Toàn bộ khách `delivered` $\to$ Nhóm mua 1 lần (`One-time Buyer`) vs Nhóm mua nhiều lần (`Repeat Buyer`) $\to$ Bậc tần suất chi tiết (`1 đơn`, `2 đơn`, `3 đơn`, `>= 4 đơn`).
   - `6b`: Từ nhóm khách mua nhiều lần (`Repeat Buyer`) $\to$ mổ xẻ theo từng Năm (`year`) và 5 bang lớn (`SP, RJ, MG, RS, PR`).
4. **Slice (`7a`, `7b`)** — Cắt lát tập khách hàng VIP có tổng chi tiêu `delivered` trên **1.000 R\$** (`HAVING sum(payment_value) > 1000`): danh sách Top 20 khách VIP (`7a`) và thống kê theo Bang (`7b`).
5. **Dice (`8a`, `8b`)** — Giao của 4 điều kiện: Đơn `delivered` $\cap$ Bang `SP, RJ, MG` (và chi tiết `SP`) $\cap$ Năm `2017–2018` $\cap$ Khách mua lặp lại `count(order_id) >= 2`.
6. **Pivot (`9a`, `9b`)**
   - `9a`: Ma trận 27 Bang (dòng) $\times$ 8 Trạng thái đơn (cột) kèm tỷ lệ giao thành công (`%`) và `delivered_payment_value`.
   - `9b`: Ma trận 5 Bang cố định `SP, RJ, MG, RS, PR` (dòng) $\times$ 3 Năm `2016, 2017, 2018` và 3 bậc quy mô đơn hàng (`< 100 R$`, `100–500 R$`, `> 500 R$`).

**Hạng mục nâng cao (`10` – `11`)**

- `10)` Chấm điểm RFM kết hợp `NTILE(4)` (cho `R`, `M`) + `CASE WHEN` (cho `F`), xếp hạng bằng `ROW_NUMBER()` và trích xuất Top 20 khách hàng dẫn đầu.
- `11)` Báo cáo tổng hợp 6 phân khúc khách hàng RFM (`Champions / VIP`, `Loyal Customers`, `Potential VIP / Big Spenders`, `New & Promising Customers`, `At Risk`, `Hibernating / Lost`) kèm đề xuất hành động DSS.

## Quy ước ngưỡng và số dòng hiển thị (`N`)

| Chỗ dùng | Ngưỡng / N | Ghi chú |
|---|---|---|
| Ngưỡng khách hàng mua lặp lại (`Repeat`) | `count(order_id) >= 2` | Tính trên đơn `delivered` theo `customer_unique_id` (2.801 khách = 3,00%) |
| Ngưỡng Slice khách hàng VIP | `sum(payment_value) > 1000` | Có 1.149 khách VIP toàn kho; câu `7a` hiển thị Top **20** khách |
| Khối Dice (`8a`, `8b`) | `SP, RJ, MG` $\cap$ `2017–2018` $\cap$ `>= 2 đơn` | Câu `8a` tổng hợp 3 bang; câu `8b` hiển thị Top **20** khách tại `SP` |
| CUBE (`5`) & Pivot (`9b`) | 5 bang cố định `SP, RJ, MG, RS, PR` | Đồng bộ đúng 5 bang cố định với Pivot của Bạn 2 |
| Chấm điểm RFM (`10`, `11`) | Thang điểm `1..4` cho `R, F, M` | `R`, `M` dùng `NTILE(4)`; `F` dùng `CASE WHEN` (`1`, `2`, `3`, `>=4` đơn); câu `10` hiển thị Top **20** |

## Chốt với nhóm trước khi ghép báo cáo

- **Tổng số đơn `delivered`** trong `valid_customer_orders` là **96.478 đơn** — khớp với `count(DISTINCT order_id)` trên `valid_sales` của Bạn 2 (96.478 đơn).
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

