# TÀI LIỆU MÔ TẢ CHI TIẾT BỘ DỮ LIỆU THƯƠNG MẠI ĐIỆN TỬ OLIST (BRAZILIAN E-COMMERCE PUBLIC DATASET)

> **Dự án:** Kho Dữ Liệu (Data Warehouse) & DSS / OLAP  
> **Nguồn dữ liệu:** Olist Store Public Dataset (Kaggle)  
> **Phạm vi thời gian:** Tháng 09/2016 – Tháng 10/2018 (Chủ yếu tập trung 2017 – 2018)  
> **Đơn vị tiền tệ:** Đồng Real Brasil (BRL / R$)  
> **Hệ tọa độ:** WGS84 (Kinh độ/Vĩ độ tại Brazil)

---

## MỤC LỤC
1. [Tổng Quan Về Dataset](#1-tổng-quan-về-dataset)
2. [Sơ Đồ Quan Hệ Thực Thể (ERD)](#2-sơ-đồ-quan-hệ-thực-thể-erd)
3. [Mô Tả Chi Tiết Từng Bảng Dữ Liệu (9 Bảng)](#3-mô-tả-chi-tiết-từng-bảng-dữ-liệu-9-bảng)
   - [3.1. olist_orders_dataset.csv](#31-olist_orders_datasetcsv)
   - [3.2. olist_order_items_dataset.csv](#32-olist_order_items_datasetcsv)
   - [3.3. olist_order_payments_dataset.csv](#33-olist_order_payments_datasetcsv)
   - [3.4. olist_order_reviews_dataset.csv](#34-olist_order_reviews_datasetcsv)
   - [3.5. olist_customers_dataset.csv](#35-olist_customers_datasetcsv)
   - [3.6. olist_products_dataset.csv](#36-olist_products_datasetcsv)
   - [3.7. olist_sellers_dataset.csv](#37-olist_sellers_datasetcsv)
   - [3.8. olist_geolocation_dataset.csv](#38-olist_geolocation_datasetcsv)
   - [3.9. product_category_name_translation.csv](#39-product_category_name_translationcsv)
4. [Phân Tích Dữ Liệu Đặc Biệt & Tính Toàn Vẹn Liên Bảng (Cross-Table Integrity)](#4-phân-tích-dữ-liệu-đặc-biệt--tính-toàn-vẹn-liên-bảng)
5. [Khuyến Nghị Cho Quy Trình Xử Lý Dữ Liệu (ETL & Staging)](#5-khuyến-nghị-cho-quy-trình-xử-lý-dữ-liệu-etl--staging)

---

## 1. TỔNG QUAN VỀ DATASET

Bộ dữ liệu gồm **9 file CSV** phản ánh toàn bộ quy trình mua hàng trên sàn thương mại điện tử Olist tại Brazil: từ việc đặt đơn, thanh toán, chọn người bán, vận chuyển, giao nhận đến đánh giá của khách hàng.

### Bảng Thống Kê Quy Mô 9 File Dữ Liệu

| STT | Tên File CSV | Kích Thước | Số Dòng (Records) | Số Cột | Dòng Trùng Lặp 100% | Vai Trò Nghiệp Vụ Trong DW |
|:---:|:---|:---:|:---:|:---:|:---:|:---|
| 1 | `olist_orders_dataset.csv` | 16.84 MB | 99.441 | 8 | 0 | Trung tâm quản lý vòng đời và trạng thái đơn hàng |
| 2 | `olist_order_items_dataset.csv` | 14.72 MB | 112.650 | 7 | 0 | Chi tiết từng mặt hàng, giá bán, phí cước vận chuyển |
| 3 | `olist_order_payments_dataset.csv` | 5.51 MB | 103.886 | 5 | 0 | Giao dịch thanh toán, phương thức trả, số kỳ trả góp |
| 4 | `olist_order_reviews_dataset.csv` | 13.78 MB | 99.224 | 7 | 0 | Điểm đánh giá (1-5 sao) và nhận xét của khách |
| 5 | `olist_customers_dataset.csv` | 8.62 MB | 99.441 | 5 | 0 | Thông tin định danh khách hàng và vị trí nhận hàng |
| 6 | `olist_products_dataset.csv` | 2.27 MB | 32.951 | 9 | 0 | Danh mục, thông số vật lý (trọng lượng, kích thước) sản phẩm |
| 7 | `olist_sellers_dataset.csv` | 170.61 KB | 3.095 | 4 | 0 | Danh sách đối tác người bán (seller) và địa bàn hoạt động |
| 8 | `olist_geolocation_dataset.csv` | 58.44 MB | 1.000.163 | 5 | **261.831** | Bản đồ mã bưu chính (CEP), tọa độ Lat/Lng tại Brazil |
| 9 | `product_category_name_translation.csv` | 2.55 KB | 71 | 2 | 0 | Bảng dịch danh mục sản phẩm từ tiếng Bồ Đào Nha sang Anh |
| **TỔNG** | **9 files** | **~120.35 MB** | **1.451.922** | **52 cột** | **261.831** | **Toàn bộ hệ thống giao dịch Olist** |

---

## 2. SƠ ĐỒ QUAN HỆ THỰC THỂ (ERD)

```mermaid
erDiagram
    CUSTOMERS ||--o{ ORDERS : "places (1:1 token)"
    ORDERS ||--|{ ORDER_ITEMS : "contains (1:N)"
    ORDERS ||--|{ ORDER_PAYMENTS : "paid_by (1:N)"
    ORDERS ||--o{ ORDER_VIEWS : "reviewed_by (1:N)"
    PRODUCTS ||--o{ ORDER_ITEMS : "ordered_in (1:N)"
    SELLERS ||--o{ ORDER_ITEMS : "fulfilled_by (1:N)"
    PRODUCTS }o--|| CATEGORY_TRANSLATION : "translates (N:1)"
    CUSTOMERS }o--o{ GEOLOCATION : "located_at (N:M zip)"
    SELLERS }o--o{ GEOLOCATION : "located_at (N:M zip)"

    CUSTOMERS {
        string customer_id PK
        string customer_unique_id
        string customer_zip_code_prefix
        string customer_city
        string customer_state
    }

    ORDERS {
        string order_id PK
        string customer_id FK
        string order_status
        timestamp order_purchase_timestamp
        timestamp order_approved_at
        timestamp order_delivered_carrier_date
        timestamp order_delivered_customer_date
        timestamp order_estimated_delivery_date
    }

    ORDER_ITEMS {
        string order_id PK_FK
        int order_item_id PK
        string product_id FK
        string seller_id FK
        timestamp shipping_limit_date
        decimal price
        decimal freight_value
    }

    ORDER_PAYMENTS {
        string order_id PK_FK
        int payment_sequential PK
        string payment_type
        int payment_installments
        decimal payment_value
    }

    ORDER_VIEWS {
        string review_id
        string order_id FK
        int review_score
        string review_comment_title
        string review_comment_message
        timestamp review_creation_date
        timestamp review_answer_timestamp
    }

    PRODUCTS {
        string product_id PK
        string product_category_name FK
        int product_name_lenght
        int product_description_lenght
        int product_photos_qty
        decimal product_weight_g
        decimal product_length_cm
        decimal product_height_cm
        decimal product_width_cm
    }

    SELLERS {
        string seller_id PK
        string seller_zip_code_prefix
        string seller_city
        string seller_state
    }

    CATEGORY_TRANSLATION {
        string product_category_name PK
        string product_category_name_english
    }

    GEOLOCATION {
        string geolocation_zip_code_prefix
        decimal geolocation_lat
        decimal geolocation_lng
        string geolocation_city
        string geolocation_state
    }
```

---

## 3. MÔ TẢ CHI TIẾT TỪNG BẢNG DỮ LIỆU (9 BẢNG)

---

### 3.1. `olist_orders_dataset.csv`
* **Mô tả nghiệp vụ:** Bảng lõi quản lý thông tin tổng thể của đơn hàng và tiến trình xử lý theo thời gian.
* **Số dòng:** 99.441 | **Số cột:** 8 | **Dung lượng:** 16.84 MB
* **Khóa chính (Primary Key):** `order_id` (Duy nhất 100%, không trùng lặp).
* **Khóa ngoại (Foreign Key):** `customer_id` -> `olist_customers_dataset.csv(customer_id)`.

#### Chi tiết các cột:

| Tên Cột | Ý Nghĩa Nghiệp Vụ | Kiểu CSV | Kiểu DW Đề Xuất | Số Null | % Null | Số Giá Trị Khác Biệt | Miền Giá Trị / Ví Dụ |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---|
| `order_id` | Mã định danh đơn hàng (GUID 32 ký tự) | string | `VARCHAR(32)` | 0 | 0.00% | 99.441 | `e481f51cbdc54678b7cc49136f2d6af7` |
| `customer_id` | Mã token khách hàng theo từng đơn | string | `VARCHAR(32)` | 0 | 0.00% | 99.441 | Khớp 1:1 với `customers.customer_id` |
| `order_status` | Trạng thái hiện tại của đơn hàng | string | `VARCHAR(20)` | 0 | 0.00% | 8 | 8 trạng thái: `delivered` (96.478), `shipped` (1.107), `canceled` (625), `unavailable` (609), `invoiced` (314), `processing` (301), `created` (5), `approved` (2) |
| `order_purchase_timestamp` | Thời điểm khách nhấn đặt mua | string | `TIMESTAMP` | 0 | 0.00% | 98.875 | Từ `2016-09-04 21:15:19` đến `2018-10-17 17:30:18` |
| `order_approved_at` | Thời điểm đơn được xác nhận thanh toán | string | `TIMESTAMP` | 160 | 0.16% | 90.733 | Null ở đơn hủy hoặc lỗi đối soát (14 đơn `delivered` vẫn bị Null) |
| `order_delivered_carrier_date` | Thời điểm bàn giao cho đối tác vận chuyển | string | `TIMESTAMP` | 1.783 | 1.79% | 81.018 | Null ở đơn chưa gửi kho (có 2 đơn `delivered` bị Null) |
| `order_delivered_customer_date` | Thời điểm khách thực tế nhận được hàng | string | `TIMESTAMP` | 2.965 | 2.98% | 95.664 | Null ở đơn chưa giao xong (có 8 đơn `delivered` bị Null) |
| `order_estimated_delivery_date` | Ngày giao hàng dự kiến thông báo lúc mua | string | `TIMESTAMP` | 0 | 0.00% | 459 | Mặc định định dạng giờ `00:00:00`. Từ `2016-09-30` đến `2018-11-12` |

#### Dữ liệu đặc biệt & Bất thường (Anomalies):
1. **Dữ liệu Null hợp logic và bất hợp logic:**
   - 2.965 đơn thiếu `order_delivered_customer_date` phần lớn là do đơn đang vận chuyển (`shipped`: 1.107), bị hủy (`canceled`: 619), hoặc hết hàng (`unavailable`: 609).
   - Tuy nhiên, có **8 đơn có `order_status = 'delivered'` nhưng `order_delivered_customer_date` lại là NULL**.
   - Có **14 đơn đã `delivered` nhưng `order_approved_at` là NULL**.
2. **Nghịch lý dòng thời gian (Chronological Inversion):**
   - **23 đơn hàng** có ngày nhận hàng trước ngày bàn giao cho bên vận chuyển (`order_delivered_customer_date < order_delivered_carrier_date`).
   - **165 đơn hàng** có ngày bàn giao vận chuyển ghi nhận trước cả ngày khách đặt hàng (`order_delivered_carrier_date < order_purchase_timestamp`).
   - **7.826 đơn hàng** giao trễ hạn so với ngày dự kiến (`order_delivered_customer_date > order_estimated_delivery_date`), chiếm 8.11% số đơn đã giao.
3. **Độ bao phủ thời gian:**
   - Năm 2016 chỉ có 329 đơn (tháng 9, 10, 12; tháng 11 khuyết hoàn toàn).
   - Năm 2017 có đủ 12 tháng (đỉnh điểm Black Friday tháng 11/2017 với 7.544 đơn).
   - Năm 2018 kết thúc vào tháng 8 (tháng 9 có 16 đơn, tháng 10 chỉ có 4 đơn).

---

### 3.2. `olist_order_items_dataset.csv`
* **Mô tả nghiệp vụ:** Lưu từng dòng sản phẩm chi tiết trong đơn hàng. Một đơn hàng có thể có nhiều mặt hàng (multi-item order).
* **Số dòng:** 112.650 | **Số cột:** 7 | **Dung lượng:** 14.72 MB
* **Khóa chính kết hợp (Composite PK):** `(order_id, order_item_id)` (100% duy nhất, 0 bản ghi trùng).
* **Khóa ngoại (FK):**
  - `order_id` -> `olist_orders_dataset.csv(order_id)`
  - `product_id` -> `olist_products_dataset.csv(product_id)`
  - `seller_id` -> `olist_sellers_dataset.csv(seller_id)`

#### Chi tiết các cột:

| Tên Cột | Ý Nghĩa Nghiệp Vụ | Kiểu CSV | Kiểu DW Đề Xuất | Số Null | % Null | Số Giá Trị Khác Biệt | Miền Giá Trị / Thống Kê |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---|
| `order_id` | Mã đơn hàng | string | `VARCHAR(32)` | 0 | 0.00% | 98.666 | Gồm 98.666 đơn (775 đơn trong `orders` không có item) |
| `order_item_id` | Số thứ tự mặt hàng trong đơn (1, 2, 3...) | int64 | `INTEGER` | 0 | 0.00% | 21 | Min: 1, Max: 21 (đơn nhiều món nhất có 21 items) |
| `product_id` | Mã sản phẩm được mua | string | `VARCHAR(32)` | 0 | 0.00% | 32.951 | 100% khớp với bảng `products` |
| `seller_id` | Mã người bán cung ứng món hàng | string | `VARCHAR(32)` | 0 | 0.00% | 3.095 | 100% khớp với bảng `sellers` |
| `shipping_limit_date` | Hạn chót người bán phải giao hàng cho đơn vị vận chuyển | string | `TIMESTAMP` | 0 | 0.00% | 93.318 | Từ `2016-09-19 00:15:34` đến `2020-04-09 22:35:08` |
| `price` | Giá bán lẻ của 1 sản phẩm (R$) | float64 | `NUMERIC(10,2)` | 0 | 0.00% | 5.968 | Min: 0.85 R$, Max: 6.735.00 R$, Trung bình: 120.65 R$, Trung vị: 74.99 R$ |
| `freight_value` | Phí vận chuyển phân bổ cho mặt hàng (R$) | float64 | `NUMERIC(10,2)` | 0 | 0.00% | 6.999 | Min: 0.00 R$, Max: 409.68 R$, Trung bình: 19.99 R$, Trung vị: 16.26 R$ |

#### Dữ liệu đặc biệt & Bất thường (Anomalies):
1. **Phí cước bằng 0 (Free shipping):** Có **383 dòng có `freight_value = 0.00`**. Đây là các đơn hàng được người bán hoặc sàn trợ giá miễn phí vận chuyển.
2. **Không có sản phẩm giá 0:** Giá bán tối thiểu là 0.85 R$, không có bản ghi quà tặng 0 đồng.
3. **Đơn hàng đa người bán (Multi-seller Orders):** Có nhiều đơn hàng chứa các `order_item_id` đến từ các `seller_id` khác nhau. Khi cuộn (roll-up) theo Seller, **không được cộng gộp số lượng đơn hàng** một cách đơn thuần vì sẽ bị đếm trùng đơn (double-counting).

---

### 3.3. `olist_order_payments_dataset.csv`
* **Mô tả nghiệp vụ:** Lưu các phương thức thanh toán khách áp dụng cho từng đơn hàng. Khách có thể thanh toán kết hợp nhiều hình thức (ví dụ: Voucher + Thẻ tín dụng).
* **Số dòng:** 103.886 | **Số cột:** 5 | **Dung lượng:** 5.51 MB
* **Khóa chính kết hợp (Composite PK):** `(order_id, payment_sequential)` (100% duy nhất).
* **Khóa ngoại (FK):** `order_id` -> `olist_orders_dataset.csv(order_id)`.

#### Chi tiết các cột:

| Tên Cột | Ý Nghĩa Nghiệp Vụ | Kiểu CSV | Kiểu DW Đề Xuất | Số Null | % Null | Số Giá Trị Khác Biệt | Miền Giá Trị / Thống Kê |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---|
| `order_id` | Mã đơn hàng | string | `VARCHAR(32)` | 0 | 0.00% | 99.440 | Bao phủ 99.440 đơn (chỉ thiếu đúng 1 đơn so với `orders`) |
| `payment_sequential` | Thứ tự lượt thanh toán trong đơn | int64 | `INTEGER` | 0 | 0.00% | 29 | Min: 1, Max: 29 (một đơn áp dụng tối đa tới 29 voucher) |
| `payment_type` | Loại hình thanh toán | string | `VARCHAR(20)` | 0 | 0.00% | 5 | `credit_card` (76.795 ~ 73.9%), `boleto` (19.784 ~ 19.0%), `voucher` (5.775 ~ 5.6%), `debit_card` (1.529 ~ 1.5%), `not_defined` (3) |
| `payment_installments` | Số kỳ trả góp (chỉ áp dụng thẻ tín dụng) | int64 | `INTEGER` | 0 | 0.00% | 24 | Min: 0, Max: 24. Đa số trả 1 lần (52.556 dòng) |
| `payment_value` | Số tiền thanh toán ở lượt này (R$) | float64 | `NUMERIC(10,2)` | 0 | 0.00% | 29.077 | Min: 0.00 R$, Max: 13.664.08 R$, Trung bình: 154.10 R$ |

#### Dữ liệu đặc biệt & Bất thường (Anomalies):
1. **Giá trị thanh toán bằng 0 đồng:** Có **9 dòng có `payment_value = 0.00`**:
   - 6 dòng thuộc loại `voucher` (phiếu giảm giá 0 đồng hoặc hủy đổi).
   - 3 dòng thuộc loại `not_defined` (lỗi hệ thống ghi nhận lúc khởi tạo).
2. **Số kỳ trả góp bằng 0:** Có **2 dòng có `payment_installments = 0`** dù số tiền thanh toán dương (`58.69 R$` và `129.94 R$`). Theo quy định ngân hàng, trả ngay phải là 1 kỳ.
3. **Đơn hàng mồ côi (1 đơn không có bất kỳ thanh toán nào):**
   - Đơn hàng `order_id = 'bfbd0f9bdef84302105ad712db648a6c'` (đặt ngày 15/09/2016, trạng thái `delivered`, có 3 món hàng trị giá 143.46 R$) **hoàn toàn không có dòng nào trong bảng payments**.
4. **Lệch tiền giữa Payment và (Price + Freight):**
   - Trong 98.665 đơn hàng có cả dữ liệu ở items và payments, có **576 đơn có tổng tiền thanh toán lệch so với tổng tiền hàng + cước**.
   - 367 đơn khách trả dư (do phát sinh phụ phí trả góp qua thẻ tín dụng, chênh lệch tối đa +182.81 R$).
   - 209 đơn khách trả thiếu (do áp dụng mã chiết khấu trực tiếp ở cổng thanh toán, lệch tối đa -51.62 R$).

---

### 3.4. `olist_order_reviews_dataset.csv`
* **Mô tả nghiệp vụ:** Khảo sát mức độ hài lòng của khách hàng sau khi đặt mua/nhận hàng.
* **Số dòng:** 99.224 | **Số cột:** 7 | **Dung lượng:** 13.78 MB
* **Khóa ứng viên:** Cặp `(order_id, review_id)` là duy nhất 100%. `review_id` đơn lẻ **KHÔNG PHẢI KHÓA CHÍNH** vì bị trùng lặp.
* **Khóa ngoại (FK):** `order_id` -> `olist_orders_dataset.csv(order_id)`.

#### Chi tiết các cột:

| Tên Cột | Ý Nghĩa Nghiệp Vụ | Kiểu CSV | Kiểu DW Đề Xuất | Số Null | % Null | Số Giá Trị Khác Biệt | Miền Giá Trị / Thống Kê |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---|
| `review_id` | Mã định danh bản đánh giá | string | `VARCHAR(32)` | 0 | 0.00% | 98.410 | Bị trùng lặp: có 814 mã review_id xuất hiện từ 2 lần trở lên |
| `order_id` | Mã đơn hàng được đánh giá | string | `VARCHAR(32)` | 0 | 0.00% | 98.673 | Khớp với `orders.order_id` (768 đơn không có review) |
| `review_score` | Điểm số đánh giá (sao) từ 1 đến 5 | int64 | `INTEGER` | 0 | 0.00% | 5 | 1 sao: 11.424 (11.5%), 2 sao: 3.151 (3.2%), 3 sao: 8.179 (8.2%), 4 sao: 19.142 (19.3%), 5 sao: 57.328 (57.8%) |
| `review_comment_title` | Tiêu đề phản hồi ngắn gọn | string | `VARCHAR(255)` | **87.656** | **88.34%** | 4.527 | Phần lớn để trống. Ví dụ: `recomendo`, `Super recomendo`, `Muito bom` |
| `review_comment_message` | Nội dung nhận xét chi tiết | string | `TEXT` | **58.247** | **58.70%** | 36.159 | Hơn một nửa khách chỉ chấm sao mà không viết nội dung nhận xét |
| `review_creation_date` | Ngày hệ thống gửi bảng khảo sát cho khách | string | `TIMESTAMP` | 0 | 0.00% | 636 | Giờ mặc định `00:00:00`. Từ `2016-10-02` đến `2018-08-31` |
| `review_answer_timestamp` | Thời điểm khách gửi phản hồi | string | `TIMESTAMP` | 0 | 0.00% | 98.248 | Từ `2016-10-07 18:32:28` đến `2018-10-29 12:27:35` |

#### Dữ liệu đặc biệt & Bất thường (Anomalies):
1. **Trùng lặp Review ID (`review_id` duplication):**
   - Có **814 mã `review_id` bị lặp lại**, liên quan đến **1.603 dòng**.
   - Nguyên nhân: Khi một khách hàng đặt cùng lúc nhiều đơn hàng con (split orders), hệ thống gửi 1 email khảo sát duy nhất mang cùng một `review_id` gán cho tất cả các đơn hàng con đó.
2. **Một đơn hàng có nhiều lượt đánh giá:**
   - Có **547 đơn hàng có từ 2 đánh giá trở lên** (tổng cộng 1.098 dòng).
   - Ví dụ đơn `0035246a40f520710769010f752e7507` được đánh giá vào ngày 25/08/2017 và đánh giá lại vào ngày 29/08/2017.
3. **Tỷ lệ thiếu hụt văn bản cực cao:**
   - 88.34% thiếu tiêu đề và 58.70% thiếu nội dung bình luận.
   - Các dòng văn bản còn lại chứa nhiều ký tự xuống dòng (`\r\n`), emoji, và ký tự đặc biệt tiếng Bồ Đào Nha (`ã`, `ç`, `é`).

---

### 3.5. `olist_customers_dataset.csv`
* **Mô tả nghiệp vụ:** Lưu trữ thông tin khách hàng và địa chỉ giao hàng của từng đơn.
* **Số dòng:** 99.441 | **Số cột:** 5 | **Dung lượng:** 8.62 MB
* **Khóa chính (PK):** `customer_id` (Duy nhất 100%, 0 bản ghi trùng).
* **Khóa định danh người dùng thực tế:** `customer_unique_id`.

#### Chi tiết các cột:

| Tên Cột | Ý Nghĩa Nghiệp Vụ | Kiểu CSV | Kiểu DW Đề Xuất | Số Null | % Null | Số Giá Trị Khác Biệt | Miền Giá Trị / Thống Kê |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---|
| `customer_id` | Mã định danh phiên khách hàng theo đơn | string | `VARCHAR(32)` | 0 | 0.00% | 99.441 | Khóa chính đại diện cho 1 lần đặt hàng |
| `customer_unique_id` | Mã định danh khách hàng thực tế (duy nhất) | string | `VARCHAR(32)` | 0 | 0.00% | 96.096 | Dùng để phân tích khách hàng thân thiết, RFM, tần suất mua lại |
| `customer_zip_code_prefix` | 5 chữ số đầu của mã bưu điện (CEP) | int64 | `VARCHAR(5)` | 0 | 0.00% | 14.994 | Min: `01003`, Max: `99990`. Có **23.995 dòng bắt đầu bằng chữ số 0** |
| `customer_city` | Tên thành phố | string | `VARCHAR(100)` | 0 | 0.00% | 4.119 | Top đầu: `sao paulo` (15.540), `rio de janeiro` (6.882), `belo horizonte` (2.773) |
| `customer_state` | Mã viết tắt của bang (2 chữ cái) | string | `CHAR(2)` | 0 | 0.00% | 27 | Đầy đủ 26 bang + 1 đặc khu liên bang Brasil (DF). Top: SP (41.746 ~ 42%) |

#### Dữ liệu đặc biệt & Bất thường (Anomalies):
1. **Phân biệt then chốt giữa `customer_id` và `customer_unique_id`:**
   - Olist sinh ra một `customer_id` mới cho mỗi đơn hàng để bảo vệ quyền riêng tư. Vì vậy `customer_id` có quan hệ 1:1 với `order_id`.
   - Để nhận diện hành vi khách hàng mua lại (repeat customer), **phải dùng `customer_unique_id`**. Trong 96.096 khách hàng thực tế, có **2.997 khách đã mua hàng từ 2 lần trở lên** (khách mua nhiều nhất đạt 17 đơn hàng).
2. **Nguy cơ rụng số 0 ở mã bưu chính (CEP Leading Zero):**
   - Mã bưu điện Brazil chuẩn gồm 5 chữ số đầu. Tại bang São Paulo (SP), các mã CEP bắt đầu bằng số `0` (ví dụ: `01003`).
   - Nếu đọc tự động vào kiểu số nguyên (`INT`), **23.995 bản ghi (24.1%) sẽ bị rụng mất số 0** biến thành 4 chữ số (`1003`), gây lỗi khi JOIN với bảng địa lý `geolocation`.
3. **Sạch sẽ hoàn hảo:** Toàn bộ bảng **không có bất kỳ giá trị NULL nào (0%)**.

---

### 3.6. `olist_products_dataset.csv`
* **Mô tả nghiệp vụ:** Danh mục và thuộc tính kích thước, cân nặng của các sản phẩm bán trên sàn.
* **Số dòng:** 32.951 | **Số cột:** 9 | **Dung lượng:** 2.27 MB
* **Khóa chính (PK):** `product_id` (Duy nhất 100%, 0 trùng lặp).
* **Khóa ngoại (FK):** `product_category_name` -> `product_category_name_translation.csv`.

#### Chi tiết các cột:

| Tên Cột | Ý Nghĩa Nghiệp Vụ | Kiểu CSV | Kiểu DW Đề Xuất | Số Null | % Null | Số Giá Trị Khác Biệt | Miền Giá Trị / Thống Kê |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---|
| `product_id` | Mã định danh sản phẩm | string | `VARCHAR(32)` | 0 | 0.00% | 32.951 | Duy nhất 100% |
| `product_category_name` | Tên danh mục bằng tiếng Bồ Đào Nha | string | `VARCHAR(100)` | **610** | **1.85%** | 73 | 73 danh mục khác nhau. Phổ biến nhất: `cama_mesa_banho` (3.029) |
| `product_name_lenght` *(sic)* | Độ dài tên sản phẩm (ký tự) | float64 | `INTEGER` | 610 | 1.85% | 66 | Min: 5, Max: 76 ký tự. Lỗi chính tả tên cột gốc Kaggle: `lenght` |
| `product_description_lenght` *(sic)* | Độ dài phần mô tả sản phẩm | float64 | `INTEGER` | 610 | 1.85% | 2.960 | Min: 4, Max: 3.992 ký tự. Lỗi chính tả tên cột gốc Kaggle: `lenght` |
| `product_photos_qty` | Số lượng hình ảnh chụp sản phẩm | float64 | `INTEGER` | 610 | 1.85% | 19 | Min: 1, Max: 20 ảnh |
| `product_weight_g` | Khối lượng sản phẩm (gram) | float64 | `NUMERIC(10,2)` | 2 | 0.01% | 2.204 | Min: 0.0 g, Max: 40.425.0 g (~40.4 kg). Có 4 dòng có cân nặng = 0 |
| `product_length_cm` | Chiều dài sản phẩm (cm) | float64 | `NUMERIC(10,2)` | 2 | 0.01% | 99 | Min: 7 cm, Max: 105 cm |
| `product_height_cm` | Chiều cao sản phẩm (cm) | float64 | `NUMERIC(10,2)` | 2 | 0.01% | 102 | Min: 2 cm, Max: 105 cm |
| `product_width_cm` | Chiều rộng sản phẩm (cm) | float64 | `NUMERIC(10,2)` | 2 | 0.01% | 95 | Min: 6 cm, Max: 118 cm |

#### Dữ liệu đặc biệt & Bất thường (Anomalies):
1. **Lỗi chính tả tên cột (Typo in Schema):**
   - Hai cột `product_name_lenght` và `product_description_lenght` bị nhà cung cấp dữ liệu viết sai chính tả chữ `length` thành `lenght`. Khi thiết kế Staging / DDL cần giữ nguyên hoặc alias phù hợp.
2. **Cụm 610 sản phẩm thiếu toàn bộ metadata:**
   - Đúng **610 sản phẩm bị thiếu đồng thời**: danh mục, độ dài tên, độ dài mô tả và số lượng ảnh.
3. **Cụm 2 sản phẩm thiếu kích thước vật lý:**
   - Hai sản phẩm (`09ff539a621711667c43eba6a3bd8466` và `5eb564652db742ff8f28759cd8d2652a`) bị NULL cả 4 trường: `weight`, `length`, `height`, `width`.
4. **Trọng lượng bằng 0:**
   - Có **4 sản phẩm có `product_weight_g = 0.0`** dù thuộc danh mục `cama_mesa_banho` (chăn ga gối đệm).

---

### 3.7. `olist_sellers_dataset.csv`
* **Mô tả nghiệp vụ:** Thông tin định danh và địa bàn đặt kho của các nhà bán hàng (sellers).
* **Số dòng:** 3.095 | **Số cột:** 4 | **Dung lượng:** 170.61 KB
* **Khóa chính (PK):** `seller_id` (Duy nhất 100%, 0 trùng lặp).
* **Khóa ngoại tham chiếu:** `seller_zip_code_prefix` -> `olist_geolocation_dataset.csv`.

#### Chi tiết các cột:

| Tên Cột | Ý Nghĩa Nghiệp Vụ | Kiểu CSV | Kiểu DW Đề Xuất | Số Null | % Null | Số Giá Trị Khác Biệt | Miền Giá Trị / Thống Kê |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---|
| `seller_id` | Mã định danh người bán | string | `VARCHAR(32)` | 0 | 0.00% | 3.095 | Duy nhất 100% |
| `seller_zip_code_prefix` | 5 số đầu mã bưu điện người bán | int64 | `VARCHAR(5)` | 0 | 0.00% | 2.246 | Min: `01001`, Max: `99730`. Có **1.027 dòng bắt đầu bằng chữ số 0** |
| `seller_city` | Thành phố nơi đặt kho/trụ sở seller | string | `VARCHAR(100)` | 0 | 0.00% | 611 | Top đầu: `sao paulo` (694), `curitiba` (127), `rio de janeiro` (96) |
| `seller_state` | Bang nơi seller đăng ký kinh doanh | string | `CHAR(2)` | 0 | 0.00% | 23 | Chỉ có sellers ở 23/27 bang. SP chiếm áp đảo với 1.849 sellers (59.74%) |

#### Dữ liệu đặc biệt & Bất thường (Anomalies):
1. **Độ tập trung địa lý cực lớn:**
   - Riêng bang São Paulo (SP) chiếm gần **60% người bán**, theo sau là Paraná (PR - 349) và Minas Gerais (MG - 244).
   - Có **4 bang không có người bán nào**: Acre (AC), Amapá (AP), Roraima (RR), và Tocantins (TO).
2. **Bảo toàn số 0 ở đầu mã CEP:**
   - 1.027 seller (33.18%) có mã CEP bắt đầu bằng chữ số 0.
3. **Sạch sẽ:** Không có bản ghi NULL (0%).

---

### 3.8. `olist_geolocation_dataset.csv`
* **Mô tả nghiệp vụ:** Ánh xạ từ tiền tố mã bưu chính (CEP 5 chữ số) ra tọa độ địa lý (Vĩ độ Lat, Kinh độ Lng), Thành phố và Bang tại Brazil.
* **Số dòng:** 1.000.163 | **Số cột:** 5 | **Dung lượng:** 58.44 MB
* **Khóa chính:** Không có khóa chính tự nhiên. `geolocation_zip_code_prefix` là quan hệ 1-Nhiều (1 mã bưu chính chứa nhiều tọa độ).

#### Chi tiết các cột:

| Tên Cột | Ý Nghĩa Nghiệp Vụ | Kiểu CSV | Kiểu DW Đề Xuất | Số Null | % Null | Số Giá Trị Khác Biệt | Miền Giá Trị / Thống Kê |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---|
| `geolocation_zip_code_prefix` | 5 chữ số đầu của mã bưu chính | int64 | `VARCHAR(5)` | 0 | 0.00% | 19.015 | Min: `01001`, Max: `99990`. Có **245.733 dòng bắt đầu bằng số 0** |
| `geolocation_lat` | Vĩ độ địa lý (Latitude) | float64 | `DOUBLE PRECISION` | 0 | 0.00% | 717.372 | Min: `-36.605374`, Max: `+45.065933` (chứa dữ liệu ngoại lai) |
| `geolocation_lng` | Kinh độ địa lý (Longitude) | float64 | `DOUBLE PRECISION` | 0 | 0.00% | 717.615 | Min: `-101.466766`, Max: `+121.105394` (chứa dữ liệu ngoại lai) |
| `geolocation_city` | Tên thành phố ứng với mã bưu chính | string | `VARCHAR(100)` | 0 | 0.00% | 8.011 | Chứa nhiều biến thể dấu và cách viết (ví dụ: `sao paulo` vs `são paulo`) |
| `geolocation_state` | Mã bang | string | `CHAR(2)` | 0 | 0.00% | 27 | Đủ 27 bang của Brazil |

#### Dữ liệu đặc biệt & Bất thường (Anomalies):
1. **Hiện tượng trùng lặp dòng khổng lồ (Exact Duplicates):**
   - Có tới **261.831 dòng trùng lặp 100%** trên toàn bộ 5 cột (chiếm **26.18%** toàn bộ file).
   - Nếu tính cả dòng gốc và dòng lặp thì có tới 390.005 dòng liên quan đến trùng lặp.
2. **Quan hệ 1 Mã CEP - Nhiều Tọa độ (1:N):**
   - Có 1.000.163 dòng nhưng chỉ có 19.015 mã `zip_code_prefix`. Trung bình một mã CEP có hơn 50 dòng tọa độ khác nhau đại diện cho các khúc đường phố. Khi đưa vào chiều địa lý `dim_geolocation`, **bắt buộc phải gom cụm (GROUP BY / AVG) lấy tọa độ trung tâm**.
3. **Ngoại lai tọa độ nằm ngoài lãnh thổ Brazil (Severe Spatial Outliers):**
   - Lãnh thổ Brazil hợp lệ nằm trong phạm vi xấp xỉ: Vĩ độ `[-33.75, +5.27]`, Kinh độ `[-73.98, -34.79]`.
   - **31 dòng có vĩ độ vượt ra ngoài Brazil**: Điển hình dòng 387565 có `lat = 28.008978, lng = -15.536867` (nằm tại quần đảo Canary, Tây Ban Nha) dù ghi thành phố là `bom retiro da esperanca, SP`.
   - **37 dòng có kinh độ vượt ra ngoài Brazil**: Điển hình dòng 965687 có `lat = 14.585073, lng = +121.105394` (kinh độ dương nằm tận thủ đô Manila, Philippines) dù nhãn ghi bang Rio Grande do Sul (RS).
4. **Không nhất quán dấu thanh tiếng Bồ Đào Nha:** Cùng một thành phố có nhiều cách viết hoa thường và có dấu / không dấu.

---

### 3.9. `product_category_name_translation.csv`
* **Mô tả nghiệp vụ:** Bảng đối chiếu từ điển dịch tên danh mục sản phẩm từ tiếng Bồ Đào Nha sang tiếng Anh.
* **Số dòng:** 71 | **Số cột:** 2 | **Dung lượng:** 2.55 KB
* **Khóa chính (PK):** `product_category_name` (Duy nhất 100%).

#### Chi tiết các cột:

| Tên Cột | Ý Nghĩa Nghiệp Vụ | Kiểu CSV | Kiểu DW Đề Xuất | Số Null | % Null | Số Giá Trị Khác Biệt | Miền Giá Trị / Thống Kê |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---|
| `product_category_name` | Tên danh mục tiếng Bồ Đào Nha | string | `VARCHAR(100)` | 0 | 0.00% | 71 | 71 danh mục |
| `product_category_name_english` | Tên danh mục dịch sang tiếng Anh | string | `VARCHAR(100)` | 0 | 0.00% | 71 | 71 bản dịch tiếng Anh tương ứng |

#### Dữ liệu đặc biệt & Bất thường (Anomalies):
1. **Thiếu sót danh mục so với bảng sản phẩm (Missing Categories):**
   - Trong bảng `olist_products_dataset.csv` có **73 danh mục khác nhau**, nhưng bảng dịch chỉ có **71 danh mục**.
   - **2 danh mục bị bỏ quên hoàn toàn trong bảng dịch:**
     1. `portateis_cozinha_e_preparadores_de_alimentos` (Thiết bị nhà bếp mini & chế biến thực phẩm): gồm 10 sản phẩm, phát sinh **15 món hàng đã bán**.
     2. `pc_gamer` (Máy tính chơi game): gồm 3 sản phẩm, phát sinh **9 món hàng đã bán**.
2. **Cảnh báo mất mát dữ liệu (Data Loss Risk):**
   - Nếu trong quá trình ETL hoặc viết câu lệnh SQL phân tích sử dụng `INNER JOIN` vào bảng dịch này, **24 lượt bán hàng sẽ bị loại bỏ âm thầm**, làm sai lệch doanh thu của toàn bộ kho dữ liệu. Bắt buộc phải dùng `LEFT JOIN` và bổ sung giá trị mặc định (`COALESCE`).

---

## 4. PHÂN TÍCH DỮ LIỆU ĐẶC BIỆT & TÍNH TOÀN VẸN LIÊN BẢNG

Dưới đây là bảng tổng hợp các bất thường toàn vẹn tham chiếu (Referential Integrity Check) giữa các bảng:

```
[ORDERS] (99.441 đơn)
   ├── 98.666 đơn có mặt hàng (order_items) ──── 775 đơn KHÔNG CÓ MẶT HÀNG
   ├── 99.440 đơn có thanh toán (order_payments) ── 1 đơn KHÔNG CÓ THANH TOÁN
   └── 98.673 đơn có đánh giá (order_reviews) ── 768 đơn KHÔNG CÓ ĐÁNH GIÁ
```

### 4.1. Đơn hàng không có mặt hàng (775 đơn)
- Bảng `orders` có 99.441 đơn, nhưng bảng `order_items` chỉ chứa 98.666 đơn -> Có **775 đơn hàng không có bất kỳ dòng nào trong `order_items`**.
- **Phân bố trạng thái của 775 đơn này:**
  * `unavailable` (Hết hàng/Nhà cung cấp không giao được): **603 đơn**
  * `canceled` (Đơn bị hủy trước khi xuất kho): **164 đơn**
  * `created` (Vừa tạo đơn, chưa xử lý): **5 đơn**
  * `invoiced` (Đã xuất hóa đơn nhưng chưa đóng gói): **2 đơn**
  * `shipped` (Đang giao): **1 đơn**
  * `delivered` (Đã giao thành công): **0 đơn** (100% đơn giao thành công đều có dữ liệu mặt hàng).

### 4.2. Đơn hàng không có dữ liệu thanh toán (1 đơn duy nhất)
- Mã đơn hàng: `bfbd0f9bdef84302105ad712db648a6c`.
- Ngày mua: `2016-09-15 12:16:38`.
- Trạng thái: `delivered` (đã giao thành công).
- Có 3 mặt hàng trong `order_items` với tổng giá trị tiền hàng: `134.97 R$` + tiền cước: `8.49 R$` = `143.46 R$`.
- **Hoàn toàn không tồn tại bản ghi thanh toán nào trong `order_payments`**. Trong DW, đơn này nếu tính doanh thu theo `fact_sales` thì có số liệu, nhưng tính theo `fact_customer_order (payment_value)` sẽ bị khuyết.

### 4.3. Đơn hàng không có đánh giá (768 đơn)
- Có 768 đơn hàng khách hàng không điền form khảo sát review, gồm 646 đơn `delivered`, 75 đơn `shipped`, 20 đơn `canceled`, v.v.

### 4.4. Trùng lặp Review ID (814 mã review gán cho nhiều đơn)
- 814 `review_id` xuất hiện trên 1.603 dòng trong `olist_order_reviews_dataset.csv`.
- Do đó, khóa chính của bảng đánh giá bắt buộc phải là cặp **`(order_id, review_id)`** hoặc sinh khóa nhân tạo (`Surrogate Key`).

### 4.5. Lệch số tiền giữa Hóa đơn hàng và Thanh toán
- **98.089 đơn hàng** có `payment_value == price + freight_value` (Khớp tuyệt đối).
- **576 đơn hàng bị lệch tiền**:
  * 367 đơn có tiền thanh toán lớn hơn tiền hàng (do phí trả góp qua thẻ tín dụng).
  * 209 đơn có tiền thanh toán nhỏ hơn tiền hàng (do mã giảm giá/voucher áp dụng tại bước thanh toán ngoài).
- Tổng chênh lệch toàn kho giữa thanh toán và giá+cước là khoảng **2.688,02 R$**.

### 4.6. Mã bưu điện khách hàng và người bán không tìm thấy trong Geolocation
- **278 khách hàng** (thuộc 157 mã CEP khác nhau) có mã `customer_zip_code_prefix` không tồn tại trong `olist_geolocation_dataset`.
- **7 người bán** (thuộc 7 mã CEP khác nhau) có mã `seller_zip_code_prefix` không tồn tại trong `olist_geolocation_dataset`.
- Khi xây dựng Dimension Địa lý, cần sử dụng kỹ thuật `OUTER JOIN` hoặc bổ sung bản ghi giả lập `Unknown / Unmapped Location` để tránh làm rơi rụng đơn hàng của các khách hàng này.

---

## 5. KHUYẾN NGHỊ CHO QUY TRÌNH XỬ LÝ DỮ LIỆU (ETL & STAGING)

Dựa trên các đặc thù và bất thường đã phân tích ở trên, đây là các quy tắc vàng cho quy trình ETL vào Kho Dữ Liệu:

### 1. Xử lý Kiểu dữ liệu & Số 0 ở đầu (Leading Zeros)
> [!IMPORTANT]
> Tuyệt đối không lưu các cột mã bưu điện (`customer_zip_code_prefix`, `seller_zip_code_prefix`, `geolocation_zip_code_prefix`) ở dạng số nguyên (`INTEGER`). Bắt buộc lưu dạng chuỗi ký tự cố định `CHAR(5)` hoặc `VARCHAR(5)` kèm hàm `LPAD(col::text, 5, '0')` để bảo toàn chữ số 0 ở đầu.

### 2. Khử trùng lặp Geolocation
> [!TIP]
> Bảng `olist_geolocation_dataset.csv` có 26.18% dòng trùng lặp hoàn toàn. Trước khi tải vào DW:
> 1. Chạy `SELECT DISTINCT` để loại bỏ 261.831 dòng rác.
> 2. Gom cụm theo `geolocation_zip_code_prefix` bằng các hàm tổng hợp: `AVG(lat)`, `AVG(lng)`, lấy mode (hoặc MAX) của `city` và `state` để tạo ra bảng chiều địa lý duy nhất theo mã CEP (1 dòng / 1 CEP).

### 3. Quy tắc JOIN Danh mục sản phẩm (Category Translation)
> [!WARNING]
> Luôn sử dụng `LEFT JOIN` từ `products` sang `product_category_name_translation` và dùng hàm `COALESCE(trans.product_category_name_english, prod.product_category_name, 'unknown')` để đảm bảo không làm mất 24 lượt mua hàng của `pc_gamer` và `portateis_cozinha_e_preparadores_de_alimentos`.

### 4. Định nghĩa Thước đo Doanh thu trong OLAP
- Tách bạch rõ ràng 3 chỉ số tài chính, không cộng gộp lẫn lộn:
  1. **Doanh thu tiền hàng (Item Price):** `SUM(price)` từ bảng `order_items` cho các đơn `delivered`.
  2. **Tiền cước vận chuyển (Freight):** `SUM(freight_value)` từ bảng `order_items`.
  3. **Tiền thanh toán thực thu (Payment):** `SUM(payment_value)` từ bảng `order_payments`.
- Khi phân tích doanh thu theo Người bán (Seller) hoặc Danh mục (Product Category), **phải dùng `SUM(price)`**, không dùng `payment_value` (vì `payment_value` nằm ở mức đơn hàng, không thể phân bổ chính xác cho từng seller nếu đơn đó có nhiều seller).

### 5. Khóa chính cho Bảng Đánh giá (Reviews)
- Không dùng `review_id` làm khóa chính đơn nhất.
- Đặt khóa chính tổng hợp là `PRIMARY KEY (order_id, review_id)` hoặc tạo cột tự tăng `review_surrogate_key SERIAL PRIMARY KEY`.

---

*Tài liệu được phân tích tự động và xác thực từ toàn bộ 1.451.922 dòng dữ liệu thực tế của dự án.*
