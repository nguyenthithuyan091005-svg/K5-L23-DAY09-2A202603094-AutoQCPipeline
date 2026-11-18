"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401


def run(ds, cfg):
    c = cfg["label_format"]
    issues = []

    def add(sev, code, stem, line, msg, **extra):
        issues.append(Issue("label_format", sev, code, stem, msg, line=line, extra=extra))

    for path in ds.label_files():
        stem = path.stem
        size = ds.image_size(stem)            # (rộng, cao) px, hoặc None nếu ảnh không mở được
        seen = []                             # các box hợp lệ ở dòng trước, để phát hiện box lặp
        for line, text in ds.read_label_lines(stem) or []:
            # 1) dòng phải parse được; hỏng thì báo rồi bỏ qua dòng này
            try:
                cid, x, y, w, h = parse_yolo_line(text)
            except ValueError as e:
                add(ERROR, "BAD_FORMAT", stem, line, f"dòng nhãn sai định dạng: {e}")
                continue
            # 2) id lớp phải nằm trong danh sách lớp của dataset
            if not 0 <= cid < len(ds.classes):
                add(ERROR, "BAD_CLASS_ID", stem, line, f"id lớp {cid} ngoài khoảng 0..{len(ds.classes) - 1}")
                continue
            # 3) box phải có diện tích dương
            if w <= 0 or h <= 0:
                add(ERROR, "BOX_ZERO", stem, line, f"box rỗng (w={w}, h={h})")
                continue
            # 4) tràn ảnh: mức tràn là phần lớn nhất vượt ra ngoài [0, 1] trên 4 mép
            overflow = max(w / 2 - x, x + w / 2 - 1, h / 2 - y, y + h / 2 - 1)
            if overflow > c["overflow_tol"]:
                add(ERROR, "BOX_OUT_OF_IMAGE", stem, line, f"box tràn ảnh {overflow:.4f}", overflow=overflow)
            # 5) box lặp: cùng lớp với một dòng trước đó và IoU cao; báo ở dòng sau
            box = (x, y, w, h)
            if any(pc == cid and iou_xywh(pb, box) > c["dup_box_iou"] for pc, pb in seen):
                add(ERROR, "DUP_BOX", stem, line, "box lặp với một dòng trước đó cùng lớp")
            seen.append((cid, box))
            # 6) cảnh báo: box quá nhỏ (cạnh ngắn tính bằng px) hoặc quá lớn (chiếm gần hết ảnh)
            if size and min(w * size[0], h * size[1]) < c["min_box_px"]:
                add(WARN, "BOX_TINY", stem, line, f"cạnh ngắn {min(w * size[0], h * size[1]):.1f}px < {c['min_box_px']}px")
            if w * h > c["max_box_frac"]:
                add(WARN, "BOX_HUGE", stem, line, f"box chiếm {w * h:.2f} diện tích ảnh")
    return issues
