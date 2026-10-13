# Định dạng kịch bản Money Studio (JSON) – tóm tắt tiếng Việt

Hướng dẫn đầy đủ (tiếng Anh, để Claude đọc): `docs/PROMPT_FOR_CLAUDE.md`. Tập mẫu: `scripts/ep00_trailer.json`.

## Khung chung
| Trường | Ý nghĩa |
|---|---|
| `title` | Tên tập (tiếng Anh) |
| `mascot` | Linh vật mặc định: `ben` hoặc `piggy` |
| `narrator` | Giọng đọc `voice` (mặc định `am_michael`) và `speed` |
| `music` | `light` (vui nhẹ), `thoughtful` (trầm), `none` |
| `youtube` | `title_options`, `title_vi`, `description`, `description_vi`, `numbers` (giả định số liệu), `tags`, `hashtags`, `pinned_comment` |
| `thumbnail.variants` | 3 bố cục: `face_number`, `object`, `split` |
| `shorts` | `scenes: [từ, đến]` (đánh số từ 1), `hook_text`, `end_text` |
| `scenes` | Danh sách cảnh |

## Mỗi cảnh (3-7 giây lời đọc)
- **purpose**: hook, promise, setup, open_loop, beat, rehook, payoff, action, outro.
- **chapter**: tên chương YouTube (cần ≥ 3 chương).
- **bg**: `grid`, `room`, `desk`, `city`, `notebook` (bút chì vẽ dần), `plain`. Giữ nguyên cho cảnh sau đến khi đổi.
- **chars**: `who` (ben/piggy), `pose`, `mood`, `x` (0..1),
  `enter` (left, right, pop), `size`. Bỏ trống thì hiện linh vật mặc định; `[]` là không có nhân vật.
  - Dáng của Ben (15): idle (đứng), wave (vẫy tay), point (chỉ), hold_head (ôm đầu), cross_arms (khoanh tay),
    phone (xem điện thoại), read (cầm hóa đơn), count_money (đếm tiền), shrug (nhún vai), think (suy nghĩ),
    celebrate (ăn mừng – nhảy lên), thumbs_up (giơ ngón cái), facepalm (lấy tay che mặt), explain (giải thích), sad (buồn).
  - Cảm xúc của Ben (6): smile, shock (sốc – nhảy lên), sad, worried (lo), angry (bực), smug (đắc ý).
  - Piggy Ben: không có dáng; cảm xúc smile / shock.
- **show** (thành phần bên phải nhân vật):
  - `money_card`: `label`, `value`, `to` (đếm từ value tới to), `to_label`, `color`, `note`
  - `big_text`: `text`, `sub`, `color`
  - `invest_chart`: `monthly`, `rate`, `years`, `start_age`, `compounding` – tool tự tính đường lãi kép
  - `chart`: `title`, `labels`, `series`
  - `receipt`: `title`, `income`, `items` – tool tự tính LEFT OVER
  - `phone`: `label`, `balance`, `from`, `items`
  - `compare`: `title`, `left`, `right`
  - `list`: `title`, `items` ("+ ..." tích xanh, "- ..." gạch đỏ)
  - `coin_drop`: đồng xu rơi vào Piggy Ben (cần piggy trong `chars`)
  - thêm `"enter": "slide"` để trượt vào thay vì bật ra.
- **lines**: `text` (tiếng Anh để đọc, số viết bằng chữ, `*từ*` để tô vàng), **`vi`** (phụ đề tiếng Việt), `pause_after`, `speaker` ("none" để nhân vật không mấp máy miệng).
- **sfx**: `{ "name": pop|coin|ding|whoosh|tick|thud|cash, "at_line": 0 }`.
- **transition**: `cut` hoặc `fade`.
