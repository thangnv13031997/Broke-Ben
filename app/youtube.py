"""youtube.txt: everything to paste into YouTube Studio, with Vietnamese labels for the owner."""

DISCLAIMER = 'This video is for educational and entertainment purposes only and is not financial advice.'


def fmt_ts(sec):
    sec = int(round(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'


def chapters_text(chapters, total):
    """YouTube needs >= 3 chapters, the first at 0:00, each >= 10 s. Returns '' if that can't be met."""
    ch = []
    for t, name in chapters:
        if ch and t - ch[-1][0] < 10:
            continue
        ch.append((0.0 if not ch else t, name))
    if len(ch) < 3 or total - ch[-1][0] < 10:
        return ''
    return '\n'.join(f'{fmt_ts(t)} {name}' for t, name in ch)


def write(script, chapters, total, path):
    yt = script.get('youtube') or {}
    titles = yt.get('title_options') or [script.get('title', '')]
    desc = (yt.get('description') or '').strip()
    chap = chapters_text(chapters, total)
    numbers = yt.get('numbers') or ''
    tags = yt.get('tags') or []
    hashtags = yt.get('hashtags') or ['personalfinance', 'moneytips', 'brokeben']
    out = []
    out.append('=== TIÊU ĐỀ (chọn 1, xếp theo đề xuất) ===')
    for i, t in enumerate(titles, 1):
        out.append(f'{i}. {t}   ({len(t)} ký tự)')
    if yt.get('title_vi'):
        out.append(f'   (nghĩa tiếng Việt: {yt["title_vi"]})')
    out.append('\n=== MÔ TẢ (dán nguyên khối) ===')
    body = [desc] if desc else []
    if chap:
        body.append('Chapters:\n' + chap)
    if numbers:
        body.append('📌 The numbers: ' + numbers)
    if DISCLAIMER.lower() not in desc.lower():
        body.append(DISCLAIMER)
    body.append(' '.join('#' + h.lstrip('#') for h in hashtags))
    out.append('\n\n'.join(body))
    if yt.get('description_vi'):
        out.append('\n(Nghĩa tiếng Việt của mô tả: ' + yt['description_vi'] + ')')
    out.append('\n=== THẺ (Tags) ===')
    out.append(', '.join(tags))
    out.append('\n=== BÌNH LUẬN GHIM ===')
    out.append(yt.get('pinned_comment', "What's YOUR biggest money leak? Tell Ben in the comments."))
    out.append('\n=== PHỤ ĐỀ ===')
    out.append('- subtitles_en.srt: tải lên YouTube Studio > Subtitles > English (bắt buộc nên có)')
    out.append('- subtitles_vi.srt: có thể tải thêm làm phụ đề tiếng Việt (tùy chọn)')
    out.append('\n=== CÀI ĐẶT KHI ĐĂNG ===')
    out.append('- Thumbnail: thumbnail_A.jpg, thử B và C bằng Test & Compare')
    out.append('- Audience: No, it\'s not made for kids')
    out.append('- Category: Education | Video language: English')
    out.append('- Altered or synthetic content: No (hoạt hình, không giả người thật)')
    out.append('- Giờ đăng: Thứ Tư / Thứ Bảy, 9:00-11:00 sáng giờ miền Đông Mỹ (khoảng 20:00-22:00 giờ Việt Nam)')
    out.append('- Thêm vào playlist đúng nhóm chủ đề; màn hình kết thúc trỏ tới video kế tiếp')
    out.append(f'\nThời lượng video: {fmt_ts(total)}')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out) + '\n')
