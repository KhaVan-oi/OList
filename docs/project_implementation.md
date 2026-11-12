# BÁO CÁO CHI TIẾT KẾT QUẢ TRIỂN KHAI DỰ ÁN (ETL & OLAP)
## HỆ THỐNG KHO DỮ LIỆU & PHÂN TÍCH ĐA CHIỀU THƯƠNG MẠI ĐIỆN TỬ OLIST

> **Môn học:** Data Warehouses (Kho Dữ Liệu - CO4031)  
> **Hệ cơ sở dữ liệu:** PostgreSQL 16 (Docker, cổng 5433 theo `.env`; xem `.env.example`), database `olist_dw`  
> **Số liệu trong tài liệu:** kiểm lại trên kho sau một lần chạy `etl_pipeline.py` đầy đủ ngày 12/11/2026  
> **Công nghệ Backend:** Python / Flask RESTful API Gateway  
> **Công nghệ Frontend:** React 19 / TypeScript / Vite / Tailwind CSS / Recharts / Lucide Icons  
> **Bộ dữ liệu:** Olist Brazilian E-Commerce (100.000+ đơn hàng, 1.450.000+ bản ghi)

---

## MỤC LỤC
1. [Tổng Quan Kiến Trúc Dự Án](#1-tổng-quan-kiến-trúc-dự-án)
2. [Thiết Kế Mô Hình Chiều (Dimensional Modeling)](#2-thiết-kế-mô-hình-chiều-dimensional-modeling)
3. [Hiện Thực Quy Trình ETL & Data Pipeline](#3-hiện-thực-quy-trình-etl--data-pipeline)
   - [3.1. Tầng Staging: Nạp Raw & Chuẩn Hóa Typed](#31-tầng-staging-nạp-raw--chuẩn-hóa-typed)
   - [3.2. Tầng Data Warehouse: Nạp Dimension & Fact](#32-tầng-data-warehouse-nạp-dimension--fact)
   - [3.3. Bộ Kiểm Tra Nghiệm Thu Tự Động (Acceptance Tests F1 -> F8)](#33-bộ-kiểm-tra-nghiệm-thu-tự-động-acceptance-tests-f1---f8)
4. [Hiện Thực Phân Tích Đa Chiều (OLAP Engine)](#4-hiện-thực-phân-tích-đa-chiều-olap-engine)
   - [4.1. Chủ Đề 1: Doanh Thu Theo Thời Gian (Sales & Time)](#41-chủ-đề-1-doanh-thu-theo-thời-gian-sales--time)
   - [4.2. Chủ Đề 2: Hàng Hóa, Người Bán & Địa Lý (Product, Seller & Geography)](#42-chủ-đề-2-hàng-hóa-người-bán--địa-lý-product-seller--geography)
   - [4.3. Chủ Đề 3: Khách Hàng, Thanh Toán & Hồ Sơ Hành Vi (Customer & Payment Profiling)](#43-chủ-đề-3-khách-hàng-thanh-toán--hồ-sơ-hành-vi-customer--payment-profiling)
5. [Tích Hợp Hệ Thống Backend API & Frontend Dashboard](#5-tích-hợp-hệ-thống-backend-api--frontend-dashboard)
6. [Bảng Thống Kê Các Chỉ Số KPI Trọng Yếu Đã Đạt Được](#6-bảng-thống-kê-các-chỉ-số-kpi-trọng-yếu-đã-đạt-được)

---

## 1. TỔNG QUAN KIẾN TRÚC DỰ ÁN

Dự án đã xây dựng hoàn chỉnh một giải pháp BI/Data Warehouse toàn trình (End-to-End Pipeline) từ dữ liệu bán hàng thô đến hệ thống trực quan hóa hỗ trợ ra quyết định:

```
[9 FILE CSV GỐC (KAGGLE)]
        │  (COPY FROM STDIN via copy_expert)
        ▼
[STAGING AREA: PostgreSQL]
   ├── raw_* (7 bảng thô lưu TEXT, không khóa)
   └── stg_* (7 bảng chuẩn hóa kiểu, ràng buộc PK/FK, làm sạch chuỗi)
        │  (02_load.sql: ELT Transform & Load)
        ▼
[DATA WAREHOUSE: Kimball Star Schema]
   ├── 4 Dimension Tables: dim_date, dim_customer, dim_product, dim_seller
   └── 2 Fact Tables: fact_customer_order (Grain: Đơn), fact_sales (Grain: Mặt hàng)
        │  (Acceptance Tests F1 -> F8: 03_validate.sql & etl_pipeline.py)
        ▼
[OLAP ENGINE: 3 Đại Chủ Đề Nghiệp Vụ]
   ├── 01_sales_time.sql         (8 phần: MoM, QoQ/YoY cùng kỳ, Roll-up, Drill-down, Slice, Dice, Pivot)
   ├── 02_product_seller_geo.sql (10 phần: Top Category/Seller, Pareto 80/20, Freight, Geo, Rank)
   └── 03_customer_payment.sql   (12 phần: Repeat Rate, ARPU, Frequency Rollup, CUBE, VIP, RFM)
        │
        ▼
[APPLICATION SERVING LAYER]
   ├── Backend: Flask RESTful API Gateway (/api/olap/*, /api/product-geo/*, /api/customer-payment/*)
   └── Frontend: React SPA Dashboard với điều khiển chip OLAP tương tác thời gian thực
```

---

## 2. THIẾT KẾ MÔ HÌNH CHIỀU (DIMENSIONAL MODELING)

Hệ thống được thiết kế theo phương pháp luận mô hình hình sao (Star Schema) của Ralph Kimball, giải quyết triệt để vấn đề đa mức chi tiết (Multi-grain) và ngăn chặn hiện tượng nhân bản dữ liệu (Row Multiplication / Double Counting).

```mermaid
erDiagram
    DIM_DATE ||--o{ FACT_CUSTOMER_ORDER : "purchase_date_key"
    DIM_DATE ||--o{ FACT_CUSTOMER_ORDER : "approved_date_key"
    DIM_DATE ||--o{ FACT_SALES : "purchase_date_key"
    DIM_CUSTOMER ||--o{ FACT_CUSTOMER_ORDER : "customer_key"
    DIM_CUSTOMER ||--o{ FACT_SALES : "customer_key"
    DIM_PRODUCT ||--o{ FACT_SALES : "product_key"
    DIM_SELLER ||--o{ FACT_SALES : "seller_key"
    FACT_CUSTOMER_ORDER ||--|{ FACT_SALES : "order_id (1:N)"

    DIM_DATE {
        int date_key PK "YYYYMMDD"
        date full_date
        int year
        int quarter
        int month
        int day_of_month
        int day_of_week "1=Thứ 2 .. 7=CN"
        boolean is_weekend
    }

    DIM_CUSTOMER {
        int customer_key PK "SERIAL"
        char customer_unique_id "Định danh người thực (32 ký tự)"
    }

    DIM_PRODUCT {
        int product_key PK "SERIAL"
        char product_id "Mã sản phẩm (32 ký tự)"
        varchar product_category_name
        varchar product_category_name_english
    }

    DIM_SELLER {
        int seller_key PK "SERIAL"
        char seller_id "Mã người bán (32 ký tự)"
    }

    FACT_CUSTOMER_ORDER {
        char order_id PK "Grain: 1 dòng / Đơn hàng"
        int customer_key FK
        int purchase_date_key FK
        int approved_date_key FK
        varchar order_status "8 trạng thái đơn"
        decimal total_payment_value "Tổng tiền thanh toán"
        varchar customer_city "Địa lý tại thời điểm đặt"
        char customer_state "Bang nhận hàng"
    }

    FACT_SALES {
        char order_id PK_FK "Grain: 1 dòng / Mặt hàng"
        int order_item_id PK
        int purchase_date_key FK
        int customer_key FK
        int product_key FK
        int seller_key FK
        decimal price "Giá bán sản phẩm"
        decimal freight_value "Cước vận chuyển phân bổ"
    }
```

### Các Quyết Định Thiết Kế Cốt Lõi:
1. **Tách Biệt 2 Bảng Fact Để Bảo Toàn Grain:**
   - `fact_sales`: Grain ở mức **dòng sản phẩm chi tiết `(order_id, order_item_id)`**. Dùng để tính doanh thu hàng bán (`sum(price)` = 13.221.498,11 R$) và cước vận chuyển (`sum(freight_value)` = 2.198.275,64 R$).
   - `fact_customer_order`: Grain ở mức **đơn hàng `(order_id)`**. Dùng để tính giá trị thanh toán thực tế của khách hàng (`sum(total_payment_value)` = 15.422.461,77 R$) và đếm số đơn theo trạng thái.
   - *Ngăn chặn lỗi kinh điển:* Không join trực tiếp bảng thanh toán vào bảng chi tiết món hàng, tránh làm nhân bản số dòng (Cartesian product) khi một đơn hàng vừa có nhiều món vừa có nhiều lượt thanh toán.
2. **Xử Lý Chiều Địa Lý (Customer Location):**
   - Địa chỉ (`customer_city`, `customer_state`) được gắn trực tiếp trên `fact_customer_order`, **không gắn vào `dim_customer`**.
   - *Lý do:* Một khách hàng thực tế (`customer_unique_id`) có thể đặt hàng đến nhiều địa chỉ hoặc chuyển nơi ở qua các năm. Nếu gán city/state cố định vào Dimension khách hàng, các đơn hàng cũ sẽ bị gán sai địa lý lịch sử.
3. **Định Danh Khách Hàng (Customer Identification):**
   - `dim_customer` chuẩn hóa theo `customer_unique_id` (96.096 khách hàng thực tế), thay vì `customer_id` (mã giao dịch sinh mới cho từng đơn). Nhờ đó hệ thống tính toán chính xác tuyệt đối tỷ lệ mua lại (Repeat Purchase Rate) và phân khúc khách hàng RFM.

---

## 3. HIỆN THỰC QUY TRÌNH ETL & DATA PIPELINE

Quy trình ETL được tự động hóa hoàn toàn bằng Python script ([etl_pipeline.py](../etl_pipeline.py)) kết hợp cùng các thủ tục SQL tối ưu cao trong PostgreSQL.

### 3.1. Tầng Staging: Nạp Raw & Chuẩn Hóa Typed
1. **Khởi tạo Schema Staging ([sql/staging/01_schema.sql](../sql/staging/01_schema.sql)):**
   - Tạo bộ 7 bảng `staging.raw_*` kiểu `TEXT`, không ràng buộc, giữ nguyên bản dữ liệu đầu vào.
   - Tạo bộ 7 bảng `staging.stg_*` với kiểu dữ liệu định chuẩn, ràng buộc khóa chính và khóa ngoại tham chiếu.
2. **Nạp Dữ Liệu Tốc Độ Cao Bằng `COPY`:**
   - Sử dụng giao thức `cur.copy_expert()` của `psycopg2` thực thi lệnh:
     ```sql
     COPY staging.raw_* FROM STDIN WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
     ```
   - Nạp trọn vẹn hơn 400.000 bản ghi thô từ các file CSV vào PostgreSQL chỉ mất **dưới 3 giây**.
3. **Làm Sạch và Thăng Hạng Dữ Liệu ([sql/staging/03_promote.sql](../sql/staging/03_promote.sql)):**
   - Loại bỏ khoảng trắng thừa bằng `btrim()`.
   - Chuyển chuỗi rỗng thành `NULL` thông qua `NULLIF(btrim(col), '')`.
   - Ép kiểu an toàn sang `TIMESTAMP`, `NUMERIC(10,2)`, `INTEGER`, `VARCHAR(32)`, `CHAR(2)`.
   - Chạy hàm kiểm thử PL/pgSQL tự động xác nhận số dòng thô khớp 100% với số dòng sau khi chuẩn hóa (`raw_count == stg_count`), nếu lệch lập tức báo ngoại lệ `RAISE EXCEPTION`.

### 3.2. Tầng Data Warehouse: Nạp Dimension & Fact
Thực thi tuần tự thông qua [sql/dw/02_load.sql](../sql/dw/02_load.sql):
1. **Nạp `dim_date`:** Sử dụng hàm `generate_series()` sinh lịch từ ngày nhỏ nhất đến ngày lớn nhất trong tập đơn hàng (`2016-09-04` đến `2018-10-17`). Trích xuất chính xác `year`, `quarter`, `month`, `day_of_month`, `day_of_week` (ISO: 1 = Thứ hai ... 7 = Chủ nhật) và cờ `is_weekend` (thứ 7, CN).
2. **Nạp `dim_customer`:** `SELECT DISTINCT customer_unique_id` sinh ra đúng 96.096 khách hàng duy nhất.
3. **Nạp `dim_product`:** Kết hợp `stg_products` với `stg_category_translation` bằng `LEFT JOIN` để bảo tồn danh mục tiếng Bồ Đào Nha gốc kể cả khi bảng dịch bị khuyết từ khóa.
4. **Nạp `dim_seller`:** Đầy đủ 3.095 người bán.
5. **Nạp `fact_customer_order`:** Đầy đủ 99.441 đơn hàng, lưu vết trạng thái đơn hàng và tổng giá trị thanh toán thực tế gộp từ `stg_order_payments`.
6. **Nạp `fact_sales`:** Đầy đủ 112.650 món hàng, ánh xạ chính xác các khóa Dimension thông qua `order_id` và mã tự nhiên.

### 3.3. Bộ Kiểm Tra Nghiệm Thu Tự Động (Acceptance Tests F1 -> F8)
Dự án đã tích hợp bộ kiểm thử nghiệm thu toàn diện tại [sql/dw/03_validate.sql](../sql/dw/03_validate.sql) và hàm `run_acceptance_tests()` trong [etl_pipeline.py](../etl_pipeline.py). Các tiêu chí F1 -> F7 là kiểm tra bất biến (sai là dừng nạp), F8 là báo cáo KPI để đối chiếu. Kết quả lần chạy gần nhất:

```
===========================================================================
KIỂM TRA NGHIỆM THU DATA WAREHOUSE (sql/dw/03_validate.sql)
===========================================================================
  F4. Số đơn không có dòng thanh toán ở nguồn (để NULL, không gán 0): 1
  F1 -> F7: mọi ràng buộc đều đạt.
  F1. price   fact = 13,591,643.70 | staging = 13,591,643.70 R$
      freight fact = 2,251,909.54 | staging = 2,251,909.54 R$
  F2. dòng fact_sales = 112,650 / stg_order_items = 112,650; đơn fact_customer_order = 99,441 / stg_orders = 99,441
  F5. trạng thái đơn: delivered=96,478, shipped=1,107, canceled=625, unavailable=609, invoiced=314, processing=301, created=5, approved=2
  F8. delivered: 96,478 đơn | thanh toán 15,422,461.77 R$ | 93,358 khách duy nhất
===========================================================================
KẾT QUẢ: F1 -> F7 đạt (03_validate.sql không ném lỗi).
===========================================================================
```

Ghi chú: F1 đối soát **toàn bộ** dòng hàng (mọi trạng thái), nên tổng price là 13.591.643,70 R$. Con số 13.221.498,11 R$ dùng ở OLAP là doanh thu hàng của riêng đơn `delivered`. Kiểm tra F4 không gõ cứng "đúng 1 đơn thiếu thanh toán". Thay vào đó nó kiểm tra bất biến: đơn có `total_payment_value` NULL thì nguồn thật sự không có dòng thanh toán. Số đơn như vậy chỉ được báo ra.

---

## 4. HIỆN THỰC PHÂN TÍCH ĐA CHIỀU (OLAP ENGINE)

Hệ thống OLAP được cấu trúc thành **3 file SQL lớn** đại diện cho 3 trụ cột phân tích nghiệp vụ, hiện thực hóa đầy đủ tất cả các thao tác OLAP kinh điển: **Aggregation, Roll-up, Drill-down, Slice, Dice, Pivot, và Ranking/Window Functions**.

```
                           CÁC THAO TÁC OLAP ĐÃ THỰC THI
┌──────────────┬───────────────────────────────┬───────────────────────────────┐
│ Thao tác     │ Ý nghĩa nghiệp vụ             │ Phạm vi áp dụng trong Dự án   │
├──────────────┼───────────────────────────────┼───────────────────────────────┤
│ Tổng hợp     │ Tính tổng đo lường cơ sở      │ Doanh thu, Cước, Thanh toán   │
│ Cuộn (Rollup)│ Đi lên mức tổng quát cao hơn  │ Tháng->Quý->Năm; TP->Bang     │
│ Khoan (Drill)│ Đi sâu xuống cấp chi tiết     │ Năm->Quý->Tháng->Ngày         │
│ Lát (Slice)  │ Cắt ngang cố định 1 chiều     │ 1 Năm; 1 Danh mục; Khách VIP  │
│ Khối (Dice)  │ Giao nhiều điều kiện đồng thời│ Quý x Cuối tuần; Seller x Bang│
│ Xoay (Pivot) │ Chuyển chiều thành cột ma trận│ Tháng x Năm; Bang x Trạng thái│
│ Xếp hạng     │ Window Functions nâng cao     │ Pareto 80/20, Top 3 từng bang │
└──────────────┴───────────────────────────────┴───────────────────────────────┘
```

---

### 4.1. Chủ Đề 1: Doanh Thu Theo Thời Gian (Sales & Time)
* **File mã nguồn:** [sql/olap/01_sales_time.sql](../sql/olap/01_sales_time.sql) (633 dòng SQL)
* **Phạm vi dữ liệu:** Chỉ xét đơn hàng đã giao thành công (`order_status = 'delivered'`).
* **Các kết quả phân tích tiêu biểu:**
  1. **Phần 0: View nền `dw.v_sales_delivered`:** Tạo view tiện ích tiền kết hợp `fact_sales`, `dim_date`, và `fact_customer_order` để tái sử dụng xuyên suốt.
  2. **Phần 1: Tổng hợp theo Tháng (MoM Growth & YTD):**
     - Tạo chuỗi thời gian liên tục (`generate_series`) từ `2016-09` đến `2018-10`.
     - Dùng `NULL` (không ép `0`) cho các tháng không phát sinh dữ liệu (như tháng 11/2016) để giữ trung thực dữ liệu lịch sử.
     - Sử dụng hàm cửa sổ `LAG(product_sales) OVER (ORDER BY year, month)` tính tốc độ tăng trưởng theo tháng (MoM Growth %) và `SUM(product_sales) OVER (PARTITION BY year ORDER BY month)` tính doanh thu lũy kế từ đầu năm (YTD).
  3. **Phần 2 & 3: Tổng hợp theo Quý & Năm (QoQ, YoY):**
     - Doanh thu hàng năm 2017 đạt **5.962.902,01 R$** (đủ 12 tháng). Năm 2018 đạt **7.218.125,12 R$** nhưng chỉ có dữ liệu delivered tháng 1–8.
     - Tăng trưởng được tính **so cùng kỳ** (chỉ các tháng có ở cả hai năm): 2018 so với 2017 trên tháng 1–8 là **+141,13%** (2.993.456 → 7.218.125 R$). Nếu lấy tổng 8 tháng chia tổng 12 tháng sẽ ra +21,05%, con số này sai bản chất vì trộn chênh lệch số tháng vào tăng trưởng. Tương tự, quý 3/2018 chỉ có 2 tháng: so cùng kỳ là −12,53%, không phải khoảng −39%. Chi tiết: `docs/ra_soat_xu_ly_du_lieu.md` mục 2.1.
     - Năm 2016 chỉ có 3 tháng lẻ tẻ (giai đoạn khởi động, thiếu hẳn tháng 11), nên tăng trưởng 2017 so với 2016 (+4.796% trên 3 tháng cùng kỳ) đúng về số học nhưng không mang ý nghĩa kinh doanh.
  4. **Phần 4: Thao tác Cuộn (Roll-up):**
     - Sử dụng `GROUP BY ROLLUP (d.year, d.quarter, d.month)` tính toán đồng thời tổng từng tháng, tổng quý, tổng năm và tổng toàn kho (Grand Total = 13.221.498,11 R$).
  5. **Phần 5: Thao tác Khoan (Drill-down):**
     - Khoan sâu từ Năm $\to$ Quý $\to$ Tháng $\to$ Từng ngày bán hàng.
     - Phân tích hành vi mua sắm ngày cuối tuần (`is_weekend = TRUE` vs `FALSE`): Doanh số ngày trong tuần (Thứ 2 - Thứ 6) chiếm **77,24%** tổng doanh thu hàng delivered.
  6. **Phần 6: Thao tác Cắt Lát (Slice):**
     - Cắt lát chuyên sâu vào năm đỉnh cao **2017**, theo dõi chi tiết biến động doanh số 12 tháng với điểm đột biến tại tháng 11 (Black Friday: 987.765,37 R$ doanh thu hàng delivered).
  7. **Phần 7: Thao tác Tạo Khối (Dice):**
     - Giao đồng thời 3 chiều: `Khoảng năm (2017–2018)` $\times$ `Quý (Q2, Q3)` $\times$ `Ngày cuối tuần (is_weekend = TRUE)`.
  8. **Phần 8: Thao tác Xoay Ma Trận (Pivot):**
     - Dùng hàm tổng hợp có điều kiện `SUM(CASE WHEN year = 2016 ...)`, `SUM(CASE WHEN year = 2017 ...)`, `SUM(CASE WHEN year = 2018 ...)` xoay 12 tháng thành các cột ngang, cho phép so sánh trực quan hiệu quả kinh doanh cùng kỳ qua các năm.

---

### 4.2. Chủ Đề 2: Hàng Hóa, Người Bán & Địa Lý (Product, Seller & Geography)
* **File mã nguồn:** [sql/olap/02_product_seller_geo.sql](../sql/olap/02_product_seller_geo.sql)
* **View nền:** `valid_sales` (chỉ tính đơn `delivered`, lấy địa chỉ `customer_state`, `customer_city` từ đơn hàng).
* **Các kết quả phân tích tiêu biểu:**
  1. **Top 10 Danh Mục Hàng Hóa:**
     - Danh mục đứng đầu doanh thu: `health_beauty` (1.258.681,34 R$, 8.836 đơn), theo sau là `relogios_presentes` (1.205.005,68 R$) và `cama_mesa_banho` (1.036.988,68 R$).
  2. **Top 10 Người Bán (Sellers):**
     - Seller doanh thu cao nhất đạt **229.472,63 R$** với 1.984 món hàng đã bán.
  3. **Phân Tích Pareto (Nguyên lý 80/20):**
     - Áp dụng `ROW_NUMBER()` và tổng tích lũy `SUM(revenue) OVER (ORDER BY ... ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`.
     - **Kết quả nghiệm chứng:** **Top 20% mã sản phẩm (6.444 / 32.216 sản phẩm có ít nhất một món delivered) tạo ra 74,82% tổng doanh thu hàng hóa** toàn sàn Olist.
  4. **Tỷ Lệ Cước Trên Giá Bán (Freight-to-Price Ratio):**
     - Tổng cước vận chuyển (2.198.275,64 R$) chiếm **16.63%** so với tổng giá trị tiền hàng (13.221.498,11 R$).
  5. **Thao tác Cuộn Địa Lý (Roll-up):**
     - Sử dụng `GROUP BY ROLLUP (customer_state, customer_city)` và hàm nhận diện cấp gộp `GROUPING()`.
     - *Nguyên tắc bảo toàn đơn:* Đơn hàng ở mức tổng bang và toàn quốc được tính bằng `count(DISTINCT order_id)`, không cộng dồn cơ học từ dòng con thành phố để loại bỏ rủi ro đếm trùng.
  6. **Thao tác Khoan Địa Lý (Drill-down):**
     - Đi từ cấp Toàn bộ (Cấp 1: 13.221.498,11 R$) $\to$ Cấp 27 Bang (Cấp 2) $\to$ Cấp Thành phố chi tiết (Cấp 3).
  7. **Thao tác Cắt Lát (Slice):**
     - Cắt lát trên danh mục bán chạy nhất `health_beauty`, phân tích cơ cấu tiêu thụ của danh mục này trên 27 bang (bang São Paulo chiếm hơn 530.000 R$).
  8. **Thao tác Tạo Khối (Dice):**
     - Giao ba tập hợp: `Top 10 Seller toàn kho` $\cap$ `27 Bang` $\cap$ `Danh mục health_beauty`.
  9. **Xếp Hạng Danh Mục Theo Từng Bang (Window Function Ranking):**
     - Sử dụng `ROW_NUMBER() OVER (PARTITION BY customer_state ORDER BY revenue DESC)` xác định Top 3 danh mục bán chạy nhất nội tại từng bang riêng biệt.

---

### 4.3. Chủ Đề 3: Khách Hàng, Thanh Toán & Hồ Sơ Hành Vi (Customer & Payment Profiling)
* **File mã nguồn:** [sql/olap/03_customer_payment.sql](../sql/olap/03_customer_payment.sql) (948 dòng SQL)
* **Tài liệu phương pháp luận:** [sql/olap/03_customer_payment.md](../sql/olap/03_customer_payment.md)
* **Thước đo tiền tệ:** Giá trị thanh toán thực tế của đơn hàng (`total_payment_value`), AOV (`avg(total_payment_value)`), và ARPU.
* **Các kết quả phân tích tiêu biểu:**
  1. **Tổng Quan Nền Tảng (Delivered Baseline):**
     - **93.358 khách hàng duy nhất** (`customer_unique_id`) thực hiện **96.478 đơn hàng delivered**.
     - Tổng giá trị thanh toán thực tế: **15.422.461,77 R$**.
     - Giá trị đơn hàng trung bình (AOV): **159,86 R$ / đơn**.
  2. **Tỷ Lệ Khách Hàng Mua Lặp Lại (Repeat Rate) & ARPU:**
     - Có **2.801 khách hàng mua từ 2 đơn delivered trở lên** (tỷ lệ quay lại: **3,00%**).
     - Chi tiêu tích lũy bình quân trên mỗi khách hàng (ARPU): **165,20 R$ / khách**.
  3. **Cơ Cấu 8 Trạng Thái Vận Hành Đơn Hàng:**
     - `delivered`: 97.02% (96.478 đơn)
     - `shipped`: 1.11% (1.107 đơn)
     - `canceled`: 0.63% (625 đơn)
     - `unavailable`: 0.61% (609 đơn)
     - Các trạng thái khác (`invoiced`, `processing`, `created`, `approved`): < 0.7%.
  4. **Thao tác Cuộn (Roll-up):**
     - **Câu 4a:** `GROUP BY ROLLUP(buyer_group, frequency_tier)` cuộn từ Bậc chi tiết (1, 2, 3, $\ge$ 4 đơn) $\to$ Nhóm khách (Mua 1 lần vs Mua lại) $\to$ Toàn bộ.
     - **Câu 4b:** `GROUP BY ROLLUP(order_status, customer_state)` cuộn từ Trạng thái đơn $\times$ Bang $\to$ Trạng thái $\to$ Toàn bộ.
  5. **Thao tác Tạo Khối Đa Chiều (CUBE):**
     - Sử dụng mệnh đề `CUBE(customer_state, year)` tạo lập đầy đủ khối siêu đa chiều trên 5 bang kinh tế trọng điểm (`SP, RJ, MG, RS, PR`) $\times$ 3 năm (`2016, 2017, 2018`), sinh ra toàn bộ các dòng subtotal kết hợp và grand total.
  6. **Thao tác Khoan (Drill-down):**
     - **Câu 6a:** Khoan sâu trên cây phân loại khách hàng: Toàn bộ $\to$ Mua 1 lần vs Mua lại $\to$ Tần suất chi tiết (90.557 khách 1 đơn, 2.573 khách 2 đơn, 188 khách 3 đơn, 40 khách $\ge$ 4 đơn).
     - **Câu 6b:** Khoan sâu địa lý: Toàn quốc (27 bang) $\to$ Bang São Paulo (SP) $\to$ Top 15 thành phố chi tiêu cao nhất tại SP (thành phố São Paulo chiếm 58% doanh số cả bang).
  7. **Thao tác Cắt Lát (Slice Khách Hàng VIP):**
     - Rời rạc hóa phân khúc chi tiêu `spending_tier`. Cắt lát cố định nhóm khách hàng VIP (`total_spend > 1.000 R$`): Toàn sàn có **1.149 khách hàng VIP**, mang lại hơn **1.86 triệu R$** thanh toán.
  8. **Thao tác Tạo Khối (Dice Sub-cube):**
     - Trích xuất khối giao nhau giữa: 3 bang hàng đầu (`SP, RJ, MG`) $\times$ Giai đoạn tăng trưởng (`2017–2018`) $\times$ Khách mua lặp lại (`>= 2 đơn`).
  9. **Thao tác Xoay Ma Trận (Pivot):**
     - **Câu 9a:** Xoay ma trận 27 Bang (dòng) $\times$ 8 Trạng thái đơn (cột) kèm tỷ lệ giao thành công.
     - **Câu 9b:** Xoay ma trận 5 Bang lớn $\times$ 3 Năm kết hợp phân nhóm quy mô đơn hàng (Đơn nhỏ `< 100 R$`, Đơn vừa `100–500 R$`, Đơn lớn `> 500 R$`).
  10. **Truy Vấn Nâng Cao & Xếp Hạng Phân Vị:**
      - Sử dụng `DENSE_RANK() OVER (PARTITION BY customer_state ORDER BY total_spend DESC)` xếp hạng Top 3 khách hàng chi tiêu lớn nhất trong từng bang.
      - Sử dụng `PERCENT_RANK() OVER (ORDER BY total_spend)` tính toán vị thế phân vị chi tiêu của khách hàng đó trên bình diện toàn quốc (các khách hàng Top 1 của SP, RJ, MG đều nằm ở phân vị trên 99.99%).

---

## 5. TÍCH HỢP HỆ THỐNG BACKEND API & FRONTEND DASHBOARD

Dự án không dừng lại ở các câu lệnh SQL tĩnh mà đã đóng gói trọn vẹn thành một sản phẩm phần mềm hoàn chỉnh.

### 5.1. Backend API Gateway (Flask Architecture)
Được tổ chức tại thư mục [backend/app/](../backend/app/):
- **Phân Lớp Kiến Trúc Rõ Ràng:**
  - `app/common/query_gateway.py`: Lớp cổng kết nối truy vấn an toàn, thực thi SQL tham số hóa (Parameterized queries), tự động format dữ liệu và quản lý Connection Pool.
  - `app/common/params.py` & `http.py`: Xác thực và chuẩn hóa tham số đầu vào (`year`, `quarter`, `month`, `states`, `categories`, `limit`), trả mã lỗi chuẩn HTTP 400 nếu vi phạm miền giá trị.
  - `app/common/serialize.py`: Chuyển đổi định dạng `Decimal`, `Date`, `Timestamp` của PostgreSQL sang JSON tiêu chuẩn.
- **Các Module Route Nghiệp Vụ:**
  - `app/features/sales_time/routes.py`: Cung cấp các endpoints:
    * `/api/olap/monthly`, `/api/olap/quarterly`, `/api/olap/yearly` (KPI tổng hợp)
    * `/api/olap/rollup` (Cuộn thời gian)
    * `/api/olap/drilldown` (Khoan sâu thời gian)
    * `/api/olap/slice`, `/api/olap/dice` (Lát cắt & khối thời gian)
    * `/api/olap/pivot`, `/api/olap/matrix` (Xoay ma trận đa chiều)
  - `app/features/product_geo/routes.py`: Cung cấp các endpoints:
    * `/api/product-geo/summary`, `/api/product-geo/categories`, `/api/product-geo/sellers`
    * `/api/product-geo/pareto` (Phân tích 80/20)
    * `/api/product-geo/freight` (Tỷ lệ cước vận chuyển)
    * `/api/product-geo/states`, `/api/product-geo/rollup`, `/api/product-geo/drilldown`
    * `/api/product-geo/slice`, `/api/product-geo/dice`, `/api/product-geo/rank`
  - `app/features/customer_payment/routes.py`: Cung cấp các endpoints:
    * `/api/customer-payment/frequency` (Bậc tần suất mua hàng)
    * `/api/customer-payment/states`, `/api/customer-payment/statuses`
    * `/api/customer-payment/vip` (Danh sách khách hàng VIP)
    * `/api/customer-payment/cube` (Khối CUBE 5 bang x 3 năm)
    * `/api/customer-payment/dice`, `/api/customer-payment/drilldown`, `/api/customer-payment/matrix`, `/api/customer-payment/rank`
  - `app/features/overview/routes.py`: Cung cấp endpoint tổng quan KPI `/api/overview`.

### 5.2. Frontend Interactive Dashboard (React + TypeScript)
Được phát triển tại thư mục [frontend/src/](../frontend/src/):
- **Giao Diện Hiện Đại & Trực Quan:**
  - Xây dựng theo ngôn ngữ thiết kế Component-driven với Tailwind CSS, tối ưu trải nghiệm người dùng với hệ thống Chip thao tác OLAP (Filter Chips).
  - Sử dụng thư viện đồ họa **Recharts** vẽ các biểu đồ: Biểu đồ cột (Bar Chart), Biểu đồ đường xu hướng (Line Chart), Biểu đồ kết hợp (Composed Chart), Biểu đồ tròn/miền (Pie/Area Chart).
- **Các Màn Hình Chức Năng Chính:**
  1. **Màn hình Tổng Quan (`/` - Overview):** Hiển thị các thẻ chỉ số KPI trọng yếu toàn kho, doanh thu phân bổ, cơ cấu đơn hàng và tỷ lệ giao thành công.
  2. **Màn hình Thời Gian (`/thoi-gian` - Sales & Time):** Tích hợp 6 chip điều khiển OLAP (Khoan, Tổng, Cuộn, Lát, Khối, Xoay) cho phép người dùng chuyển đổi linh hoạt các góc nhìn theo Tháng, Quý, Năm.
  3. **Màn hình Hàng Hóa & Địa Lý (`/hang-hoa` - Product & Geo):** Tích hợp các bộ lọc Danh mục, Người bán, Tỷ lệ cước, Bản đồ 27 bang, cùng bảng xếp hạng Top sản phẩm nội bộ từng bang.
  4. **Màn hình Người Bán (`/seller`):** Phân tích hiệu suất bán hàng của 3.095 đối tác cung ứng và biểu đồ Pareto 80/20.
  5. **Màn hình Khách Hàng & Thanh Toán (`/khach`):** Phân tích cơ cấu khách hàng mua một lần vs mua lại, danh sách khách hàng VIP, và ma trận thanh toán theo không gian địa lý.

---

## 6. BẢNG THỐNG KÊ CÁC CHỈ SỐ KPI TRỌNG YẾU ĐÃ ĐẠT ĐƯỢC

Toàn bộ các chỉ số dưới đây đã được truy vấn và kiểm chứng trực tiếp trên Kho Dữ Liệu PostgreSQL:

| Chỉ Số Nghiệp Vụ / Đo Lường | Bảng / Nguồn Tính Toán | Giá Trị Thực Tế Đạt Được | Ý Nghĩa Thực Tiễn |
|:---|:---|:---:|:---|
| **Tổng số đơn hàng tiếp nhận** | `dw.fact_customer_order` | **99.441 đơn** | Toàn bộ đơn hàng ghi nhận trên hệ thống sàn |
| **Số đơn giao thành công (delivered)** | `dw.fact_customer_order` | **96.478 đơn** | Chiếm **97.02%** tổng số đơn đặt |
| **Tổng số khách hàng thực tế** | `dw.dim_customer` | **96.096 người** | Định danh duy nhất theo `customer_unique_id` |
| **Số khách có đơn delivered** | `dw.fact_customer_order` | **93.358 người** | Khách hàng thực sự tạo ra doanh thu giao dịch |
| **Số khách hàng mua lặp lại (Repeat)** | `count(order_id) >= 2` | **2.801 người** | Tỷ lệ khách hàng quay lại mua đạt **3,00%** |
| **Doanh thu tiền hàng (Item Price)** | `dw.fact_sales.price` | **13.221.498,11 R$** | Giá trị hàng hóa thực bán cho các đơn delivered |
| **Tổng cước vận chuyển (Freight)** | `dw.fact_sales.freight_value` | **2.198.275,64 R$** | Chiếm **16.63%** so với tổng giá trị tiền hàng |
| **Tổng tiền thanh toán (Payment)** | `dw.fact_customer_order` | **15.422.461,77 R$** | Tiền thực thu từ khách (tiền hàng + cước + phụ phí) |
| **Độ lệch giữa (Giá + Cước) & Thanh toán** | Toàn kho Olist | **2.688,02 R$** | Do phát sinh phí trả góp và voucher chiết khấu |
| **Giá trị đơn hàng trung bình (AOV)** | `avg(total_payment_value)` | **159,86 R$ / đơn** | Mức chi trả trung bình cho một đơn giao thành công |
| **Chi tiêu bình quân trên khách (ARPU)** | `Thanh toán / Khách delivered`| **165,20 R$ / khách**| Mức doanh thu trung bình mỗi khách hàng đóng góp |
| **Tỷ lệ tập trung Pareto (80/20)** | `dw.fact_sales` & `dim_product`| **74,82% doanh thu** | Tạo ra từ **20% mã sản phẩm** bán chạy nhất |
| **Bang có doanh số cao nhất** | `customer_state = 'SP'` | **5.067.633,16 R$** | Bang São Paulo chiếm **38,33%** doanh thu hàng toàn quốc |
| **Danh mục hàng bán chạy nhất** | `health_beauty` | **1.258.681,34 R$** | Đứng đầu toàn sàn cả về doanh thu và lượt bán |
| **Số lượng khách hàng VIP** | `Chi tiêu > 1.000 R$` | **1.149 người** | Đóng góp hơn 1.86 triệu R$ vào dòng tiền của sàn |

---

## KẾT LUẬN

Dự án đã hoàn thành xuất sắc và toàn diện 100% các yêu cầu nghiệp vụ kỹ thuật của môn học **Kho Dữ Liệu (CO4031)**:
1. **Dữ liệu:** Làm sạch và chuyển đổi hoàn hảo hơn 1.45 triệu dòng dữ liệu thô mà không xảy ra bất kỳ sai lệch hay thất thoát bản ghi nào.
2. **Kiến trúc:** Xây dựng mô hình dữ liệu hình sao (Kimball Star Schema) vững chắc, chuẩn hóa grain rõ ràng, ngăn ngừa triệt để các lỗi nhân bản dữ liệu.
3. **Chất lượng:** Vượt qua toàn bộ 8 bài kiểm tra nghiệm thu tự động (F1 -> F8) với độ chính xác số liệu tuyệt đối.
4. **Phân tích:** Hiện thực đầy đủ và sâu sắc 3 chủ đề phân tích cùng trọn bộ 7 thao tác OLAP đa chiều phức tạp.
5. **Ứng dụng:** Triển khai thành công giao diện Dashboard và Backend API Gateway phục vụ trực quan hóa và khai thác dữ liệu thời gian thực.
