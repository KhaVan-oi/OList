# Bạn 2 — Sản phẩm, người bán và địa lý

File SQL sẽ là `sql/olap/02_product_seller_geo.sql`. File này chỉ đọc `dw`. Không sửa staging, không sửa schema kho.

## Mục tiêu

Phân tích doanh thu hàng đã giao theo sản phẩm, người bán và địa lý khách trên `dw`.

Phạm vi số liệu (đã chốt):

- Chỉ đơn `order_status = 'delivered'`.
- Doanh thu = `sum(price)`. Cước = `sum(freight_value)`. Không dùng `total_payment_value`.
- Ngày gắn `purchase_date_key`.
- Mọi câu đọc từ `fact_sales`, nối `fact_customer_order` (trạng thái, bang, thành phố), `dim_product`, `dim_seller`.
- Số Top: toàn kho **10**, pivot **5**, mỗi bang **3**, drill-down và slice **1**.

File SQL phải có đủ:

**Chỉ số**

- Top 10 danh mục theo `sum(price)`.
- Top 10 seller theo `sum(price)`.
- Pareto trên `product_id`: 20% số mã chiếm bao nhiêu % doanh thu `delivered` (doanh thu lũy kế, không phải lợi nhuận).
- Tỷ lệ cước `sum(freight_value) / sum(price)`.
- Số đơn (`count(DISTINCT order_id)`) và doanh thu theo bang.

**Thao tác OLAP**

1. **Roll-up** — `ROLLUP(customer_state, customer_city)`: thành phố → bang → toàn bộ.
2. **Drill-down** — 1 bang doanh thu cao nhất từ roll-up → danh mục trong bang đó.
3. **Slice** — 1 danh mục doanh thu cao nhất toàn kho (`health_beauty`).
4. **Dice** — top 10 seller toàn kho ∩ bang `SP`/`RJ`/`MG` ∩ danh mục `health_beauty`.
5. **Pivot** — top 5 danh mục × 5 bang cố định `SP, RJ, MG, RS, PR`; ô trống = 0.

**Hạng bổ sung**

- Top 3 danh mục mỗi bang bằng `ROW_NUMBER()`.

## Quy ước số Top (N)

Không ép mọi câu cùng một `N`. Chốt một bảng và giữ nguyên trong file SQL:

| Chỗ dùng | N | Ghi chú |
|---|---:|---|
| Top danh mục toàn kho | 10 | Bảng xếp hạng chính |
| Top seller toàn kho | 10 | Dice dùng lại đúng danh sách này |
| Dice | đúng top 10 seller ở trên | Không tính lại top sau khi lọc |
| Pivot, dòng | 5 | Ma trận 5×5 đọc được trên slide |
| Pivot, cột | 5 bang cố định `SP, RJ, MG, RS, PR` | Không phải top động; 5 bang nhiều khách nhất trong CSV |
| Top danh mục mỗi bang | 3 | 27 bang × 3 dòng, không nổ bảng |
| Drill-down | 1 bang | Chỉ mổ bang đứng đầu roll-up |
| Slice | 1 danh mục | Danh mục doanh thu cao nhất toàn kho |

Không đổi pivot thành 10×10. Không hạ top seller xuống 5 rồi dice vẫn nói top 10. Không nâng top mỗi bang lên 10.

## Chốt với nhóm trước khi viết

Bạn 2 viết theo các mốc dưới đây. Bạn 1 và Bạn 3 dùng cùng tập đơn và cùng nghĩa doanh thu thì tổng mới khớp.

- **Đơn tính doanh thu** chỉ có `order_status = 'delivered'`. `shipped`, `canceled`, `unavailable`, `created`, `approved`, `invoiced`, `processing` không tính.
- **Doanh thu** là `sum(price)` trên `fact_sales`. Cước là `sum(freight_value)`. Không cộng hai cột. Không lấy `total_payment_value` làm doanh thu.
- **Ngày** là `purchase_date_key`, ngày khách đặt. `approved_date_key` không dùng làm mốc doanh thu. `recency_days` và frequency của Bạn 3 cũng chỉ trên đơn `delivered`.
- **Địa lý** là `customer_state` và `customer_city` trên `fact_customer_order`. `dim_seller` không có thành phố hay bang. Kho không có phường. CSV khách có 27 bang.
- **Danh mục** là `COALESCE(product_category_name_english, product_category_name, 'Unknown')`. Sản phẩm thiếu tên tiếng Anh vẫn nằm trong doanh thu.
- **Số món** là `count(*)` trên dòng `fact_sales`. **Số đơn** là `count(DISTINCT order_id)`. Đơn không có dòng hàng không có trong fact bán.
- **Phá hòa** khi xếp hạng: `sum(price)` giảm dần, rồi số món giảm dần, rồi tên danh mục hoặc `seller_id` tăng dần.
- **Pareto** đếm 20% số `product_id` có ít nhất một dòng `delivered`, không đếm 20% dòng `dim_product` và không đếm danh mục. Doanh thu lũy kế chia cho tổng `price` của các dòng `delivered`. Ghi đúng tỷ lệ đo được. Kho không có giá vốn nên đây là doanh thu lũy kế, không phải lợi nhuận.
- **Dice** lấy top 10 seller trên mọi đơn `delivered` trước, rồi mới lọc bang `SP`/`RJ`/`MG` và danh mục `health_beauty`. Không tính lại top sau khi lọc. Ba bang là top doanh thu trên `valid_sales`; `health_beauty` là danh mục doanh thu cao nhất (trùng slice).
- **Top 3 mỗi bang** dùng `ROW_NUMBER()`, mỗi bang tối đa 3 dòng. Bang ít hơn 3 danh mục thì ít hơn 3 dòng.
- **Slice** lấy danh mục doanh thu cao nhất (`health_beauty`), không dùng `bed_bath_table` vì tên đó đứng thứ ba về `sum(price)`.

## Dữ liệu lấy từ đâu

`fact_sales` không có trạng thái và không có địa lý. Mọi câu đi từ dòng bán, nối fact đơn để lọc `delivered` và lấy thành phố, bang.

```text
dw.fact_sales
    JOIN dw.fact_customer_order   ON order_id
    JOIN dw.dim_product           ON product_key
    JOIN dw.dim_seller            ON seller_key
```

`WHERE fact_customer_order.order_status = 'delivered'`.

## Các bước làm

1. Nhóm xác nhận các chốt ở trên, nhất là chỉ `delivered`, doanh thu là `price`, và bảng `N` (10 / 5 / 3 / 1).
2. Chạy `etl_pipeline.py` nếu kho chưa có dữ liệu. Schema `dw` phải đã nạp xong.
3. Viết một CTE `valid_sales` ở đầu file: dòng `fact_sales` của đơn `delivered`, kèm danh mục, `seller_id`, bang, thành phố, `price`, `freight_value`, `order_id`. Mọi câu phía dưới đọc CTE này.
4. Viết các chỉ số: top 10 danh mục, top 10 seller, Pareto, tỷ lệ cước, số đơn và doanh thu theo bang.
5. Viết roll-up. Dùng `GROUPING(customer_state)` và `GROUPING(customer_city)` để tách dòng tổng khỏi thành phố thật đang NULL.
6. Drill-down lấy 1 bang đứng đầu theo `sum(price)` từ roll-up, rồi nhóm theo danh mục trong bang đó.
7. Viết slice 1 danh mục (`health_beauty`); dice = top 10 seller toàn kho ∩ `SP`/`RJ`/`MG` ∩ `health_beauty`; pivot top 5 danh mục × 5 bang cố định.
8. Viết top 3 danh mục mỗi bang bằng `ROW_NUMBER()`.
9. Chạy file trên database `olist_dw`. Cộng doanh thu các danh mục phải bằng tổng `price` trong `valid_sales`. Tổng đó là số Bạn 1 phải ra khi cộng doanh thu đơn `delivered`.
