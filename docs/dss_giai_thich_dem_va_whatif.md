# Giải thích hai phần: công thức đệm nhập hàng và việc bỏ what-if

Tài liệu ngắn để đọc nhanh. Phần 1 trả lời "công thức đệm lấy ở đâu trong paper". Phần 2 trả lời "vì sao bỏ what-if và thay bằng gì".

---

## Phần 1. Công thức đệm nhập hàng

### 1.1. Ý tưởng một câu

Dự báo nào cũng lệch. Ta nhìn xem **trong quá khứ dự báo đã lệch bao nhiêu**, rồi nhập thêm một lượng dự phòng đủ để
phần lớn các tháng quá khứ không bị thiếu hàng.

### 1.2. Công thức trong code

Hàm `order_plan` trong `backend/app/features/dss/forecast.py`:

```text
e          = thực tế − dự báo                  (mỗi tháng backtest, đơn vị món hoặc R$)
đệm        = phân vị mức `service` của các e   (nội suy tuyến tính, numpy method="linear")
lượng nhập = max(dự báo tháng tới + đệm, 0)
```

`service` là 0,85 / 0,90 / 0,95 / 0,99. Trên giao diện là ô "Mức an toàn".

### 1.3. Ví dụ tính tay

Giả sử 5 tháng backtest cho sai số (thực tế − dự báo) là: `−300, −100, +50, +200, +400`. Muốn mức 90%:

1. Sắp xếp tăng dần (đã sắp sẵn). Có n = 5 số.
2. Vị trí phân vị = (n − 1) × 0,9 = 4 × 0,9 = **3,6** (đếm từ 0). Nằm giữa số thứ 4 (= 200) và số thứ 5 (= 400).
3. Nội suy tuyến tính: 200 + 0,6 × (400 − 200) = **320**. Đây là đệm.
4. Nếu dự báo tháng tới là 7.000 thì nên nhập 7.000 + 320 = **7.320**.

Có thể kiểm tra bằng máy: `python -c "import numpy as np; print(np.quantile([-300,-100,50,200,400], 0.9, method='linear'))"` cho ra 320.

Lưu ý: trong ví dụ này, 4 trên 5 tháng quá khứ (tức 80%) có sai số không vượt 320. Mẫu càng nhỏ thì con số "90%" càng chỉ là gần
đúng. Trong hệ thống thật, ở mức 90% đo lại thì có 16,7% số tháng vẫn thiếu hàng (2 trên 12 tháng), cao hơn mức 10% mong muốn.

### 1.4. Tìm công thức này ở đâu trong paper

Paper: J. R. Trapero, M. Cardós, N. Kourentzes, *Empirical safety stock estimation based on kernel and GARCH models*,
**Omega** 84 (2019), 199–211.
[DOI](https://doi.org/10.1016/j.omega.2018.05.004) ·
[bản PDF accepted](https://eprints.lancs.ac.uk/id/eprint/125041/1/empirical_safety_stock.pdf)

Công thức **không nằm gọn ở một chỗ**. Phải ghép từ các mục sau:

| Ý cần tìm | Vị trí trong paper | Nội dung |
|---|---|---|
| Đệm là phân vị của sai số | Mục 2, **phương trình (2)** | `SS = Q_L(CSL)`. Bài viết: "where Q_L(CSL) is the forecast error quantile at the probability defined by CSL" |
| Sai số tính thế nào | Mục 3.2 | `e_t(L) = y_L − F_L = Σ y_{t+h} − Σ F_{t+h}`, tức **thực tế trừ dự báo**. Với lead time L = 1 chỉ còn một số hạng |
| Phân vị nội suy tuyến tính | Mục 4.2.2 "Empirical percentile" | "the requested value is typically linearly interpolated from the available values" |
| Lượng nhập = dự báo + đệm | Mục 6.4, **phương trình (19)** | `S_t = F_L + kσ_L`. Đây là dạng cho phân phối chuẩn, trong đó `kσ_L` là đệm |
| Các mức 85/90/95/99% | Mục 5.2 | "the target CSL values are set to 85%, 90%, 95% and 99%" |

Cách ghép: phương trình (19) nói lượng nhập là dự báo cộng đệm. Phương trình (2) nói khi không giả định phân phối chuẩn thì
đệm là phân vị của sai số. Thay đệm của (19) bằng `Q_L(CSL)` của (2) thì ra công thức trong code. **Paper không viết sẵn
dòng "dự báo + phân vị sai số" thành một phương trình riêng**, và bài dùng ký hiệu `SS`, `Q_L` chứ không có chữ "đệm". Vì vậy
tìm theo từ khóa "đệm" hay "dự báo + phân vị" sẽ không thấy. Hãy tìm theo phương trình (2) và (19).

Ngoài ra, bài cùng nhóm tác giả đăng ở *International Journal of Forecasting* 35(1) (2019) cũng dùng đúng bốn mức trên (mục 4.3):
[DOI](https://doi.org/10.1016/j.ijforecast.2018.05.009). Hai bài là hai bài khác nhau.

### 1.5. Công thức cũ không có trong paper

Phiên bản code trước đó tính theo **sai số tỷ lệ**: `e = thực tế / dự báo − 1`, nhập `dự báo × (1 + phân vị)`, dùng
`method="higher"`. Đây là một biến thể của nhóm, **không có trong paper**. Nếu bạn kiểm tra công thức cũ và không thấy trong
paper thì bạn đúng. Phiên bản hiện tại (sai số tuyệt đối, nội suy tuyến tính) mới bám theo paper.

### 1.6. Khác paper ở đâu, giới hạn là gì

| | Paper | DSS này |
|---|---|---|
| Lead time | 1 tuần và 4 tuần | 1 tháng |
| Dữ liệu | 173 tuần × 229 sản phẩm | khoảng 12–14 tháng, một chuỗi |
| Dự báo điểm | SES | kết hợp "bằng tháng trước" và Holt |

Chính paper nhận xét phương pháp phân vị thực nghiệm nhạy với mẫu nhỏ (mục 6.1). Vì vậy kết quả là **ước lượng thô**, không phải
cam kết mức phục vụ.

---

## Phần 2. Vì sao bỏ what-if khuyến mãi

### 2.1. What-if đó làm gì

Người dùng gõ bốn con số: mức tăng cầu `u`, mức giảm giá `d`, biên lợi nhuận `m`, tỷ lệ hàng dư bị tổn thất. Hệ thống tính
"khuyến mãi có lời không" và mức tăng cầu cần để hòa vốn: `u* = d / (m − d)`.

### 2.2. Vì sao bỏ

Nhận xét "nó như cố nhét cho có bài toán trong DSS" **đúng một phần**. Phần này có vai trò làm thành phần "kịch bản" của DSS,
nhưng dữ liệu không đủ để làm đúng nghĩa:

- **Không có giá vốn**, nên không biết biên lợi nhuận `m`. Olist chỉ có `price` và `freight_value`. Cước vận chuyển là tiền
  cước, không phải giá vốn.
- **Không có đợt khuyến mãi nào được ghi lại.** Không có cờ giảm giá, nên không đo được cầu tăng bao nhiêu khi giảm giá.
- **Không có tồn kho**, nên không biết hàng dư tổn thất bao nhiêu.

Hệ quả: kết quả do con số người dùng gõ quyết định, không phải do dữ liệu. Ví dụ với cùng mức giảm giá 10%:

| Biên lợi nhuận gõ vào | Cầu phải tăng bao nhiêu để hòa vốn |
|---|---|
| 35% | 40% |
| 20% | 100% |
| 10% | Không bao giờ hòa vốn (giảm giá bằng đúng biên) |

Cùng một dữ liệu mà kết luận từ "khuyến mãi dễ có lời" đến "không bao giờ có lời". Quan trọng hơn, phần này **không thể
backtest**: không có tháng nào có khuyến mãi để so lợi nhuận dự tính với lợi nhuận thực.

### 2.3. Thay bằng gì

**Đường đánh đổi thiếu hàng và dư hàng** (biểu đồ "Chọn mức an toàn thế nào?" trên trang Quyết định). Với mỗi mức 85/90/95/99%:

- Hệ thống đo từ dữ liệu quá khứ xem bao nhiêu % số tháng sẽ thiếu hàng.
- Và dư hàng trung bình bao nhiêu %.

Cách đo: với mỗi tháng, đệm chỉ học từ các tháng khác (leave-one-out), nhập theo đó, rồi so với thực tế tháng đó. Đây cũng
là một dạng "nếu chọn mức X thì kết quả là Y", nhưng **Y đo từ dữ liệu thật**, không từ giả định gõ vào.

### 2.4. Nếu thầy hỏi "kịch bản đâu"

Có thể trả lời:

> "Phần kịch bản của DSS là đường đánh đổi theo mức an toàn, tính từ backtest. What-if khuyến mãi không làm vì dữ liệu
> Olist không có giá vốn hay đợt khuyến mãi để kiểm chứng. Kết quả nếu làm sẽ hoàn toàn do giả định, không phải do dữ liệu."

Giới hạn của đường đánh đổi cũng nên nói thẳng: chỉ có 12–14 tháng nên số đo nhiễu (ở mức 90% thiếu hàng 16,7%, không phải 10%).
Nếu thầy bắt buộc có phân tích kịch bản bằng giả định, có thể dựng lại what-if (mã cũ còn trong lịch sử git) và ghi rõ trên
giao diện rằng đây là giả định minh họa.

---

## Tóm tắt hai dòng

- **Công thức đệm:** `lượng nhập = dự báo + phân vị của (thực tế − dự báo)`, ghép từ phương trình (2) và (19) của paper Omega 2019.
  Phiên bản cũ dùng sai số tỷ lệ không có trong paper đã được bỏ.
- **What-if:** bỏ vì thiếu dữ liệu để kiểm chứng. Thay bằng đường đánh đổi thiếu/dư hàng đo từ backtest.
