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
- **bg**: `grid`, `room`, `desk`, `city`, `notebook` (trang sổ lò xo đặt nghiêng trên bàn, bàn tay vẽ lên đó), `plain`. Giữ nguyên cho cảnh sau đến khi đổi.
- **chars**: `who` (ben/piggy), `pose`, `mood`, `x` (0..1),
  `enter` (left, right, pop), `size`. Bỏ trống thì hiện linh vật mặc định; `[]` là không có nhân vật.
  - Dáng của Ben (25): idle (đứng), wave (vẫy tay), point (chỉ), hold_head (ôm đầu), cross_arms (khoanh tay),
    phone (xem điện thoại), read (cầm hóa đơn), count_money (đếm tiền), shrug (nhún vai), think (suy nghĩ),
    celebrate (ăn mừng), thumbs_up (giơ ngón cái), facepalm (che mặt), explain (giải thích), sad (buồn),
    sit_desk (ngồi bàn laptop), empty_pockets (móc túi rỗng), credit_card (quẹt thẻ), shopping_bags (xách đồ mua sắm),
    coffee (cầm cà phê), calculator (bấm máy tính), beg (chắp tay xin), throw_money (tung tiền), hug_piggy (ôm heo),
    present (cầm que chỉ biểu đồ).
  - Cảm xúc của Ben (9): smile, shock (nhảy lên), sad, worried (lo), angry (bực), smug (đắc ý), money_eyes (mắt đô la),
    tired (mệt), cry (khóc).
  - Piggy Ben: không có dáng; cảm xúc smile / shock.
- **show** (thành phần bên phải nhân vật):
  - `money_card`: `label`, `value`, `to` (đếm từ value tới to), `to_label`, `color`, `note`.
    Kiểu thẻ tự chọn: `color: red` → thẻ giá treo dây (tiền ra), `color: green` → tờ tiền (tiền vào/để dành),
    còn lại → sticker. Muốn ép kiểu: `"style": "sticker" | "tag" | "bill" | "plain"`.
  - `big_text`: `text`, `sub`, `color`
  - `invest_chart`: `monthly`, `rate`, `years`, `start_age`, `compounding` – tool tự tính đường lãi kép
  - `chart`: `title`, `labels`, `series`
  - `receipt`: `title`, `income`, `items` – tool tự tính LEFT OVER
  - `phone`: `label`, `balance`, `from`, `items` (tối đa 4) → thông báo ngân hàng trượt vào từng cái (`"style": "phone"` = màn hình điện thoại cũ)
  - `compare`: `title`, `left`, `right`
  - `list`: `title`, `items` ("+ ..." tích xanh, "- ..." gạch đỏ) → giấy note vàng, viết tay từng dòng (`"style": "card"` = kiểu cũ)
  - `coin_drop`: đồng xu rơi vào Piggy Ben (cần piggy trong `chars`)
  - `sketch`: **Ben's Notebook** – bàn tay cầm bút chì vẽ biểu đồ từng nét lên trang sổ rồi viết chữ tay.
    `kind`: `line` (đường, hoặc `invest` tự tính lãi kép), `bars` (cột), `pie` (tròn, tự tính %), `flow` (sơ đồ dòng tiền).
    Dùng với `"bg": "notebook"`; `"chars": []` để vẽ cả trang. Nên dùng khoảng 20% số cảnh, để giải thích khái niệm.
  - **Chuyển cảnh tự động**: cảnh notebook nối tiếp cảnh notebook → **lật trang**; đổi sang loại khác
    (thẻ → trang, trang → thẻ, thẻ → biểu đồ...) → **trượt vào** từ bên phải; cùng loại (thẻ → thẻ) → **bật ra**.
    `"page_flip": false` để trang trượt thay vì lật; `"enter": "slide"|"pop"` để ép kiểu cho thành phần thường.
- **lines**: `text` (tiếng Anh để đọc, số viết bằng chữ, `*từ*` để tô vàng), **`vi`** (phụ đề tiếng Việt), `pause_after`, `speaker` ("none" để nhân vật không mấp máy miệng).
- **sfx**: `{ "name": pop|coin|ding|whoosh|tick|thud|cash|page|scribble, "at_line": 0 }` (tool tự thêm tiếng lật trang, tiếng trượt "whoosh" và tiếng bút).
- **transition**: `cut` hoặc `fade`.
