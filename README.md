# ExHentai 失效收藏查找器 (精简版)

该 Python 脚本扫描您的 ExHentai 收藏夹，查找失效或不可访问的画廊链接，并尝试通过 E-Hentai API 获取这些画廊的日文标题 (`title_jpn`) 和缩略图 (`thumb`)，最后将结果保存到 `result.md` 文件。

## 主要功能

*   自动抓取所有收藏夹页面。
*   识别被版权炮掉的链接 (404, 特定错误页)。
*   调用 E-Hentai API 获取失效画廊信息。
*   生成 Markdown 格式的结果报告 (`result.md`)。

## 安装

1.  **克隆仓库** (或下载脚本)。
2.  **安装依赖**:
    ```bash
    pip install requests beautifulsoup4
    ```

## 使用方法

1.  **获取 ExHentai Cookie**。
2.  **运行脚本**:
    ```bash
    python main.py
    ```
3.  **按提示操作**:
    *   输入您的 Cookie 字符串。
    *   (可选) 输入 API 批处理大小 (默认 25)。
    *   (可选) 输入 API 请求间的等待时间 (默认 5 秒)。
4.  **查看结果**: 检查生成的 `result.md` 文件。

## 输出 (`result.md`)

```markdown
# ExHentai 收藏夹处理结果

## 1. [日文标题]
![thumb 1]([缩略图 URL])
**链接:** [原始 ExHentai 链接]

...
```

## 注意

*   请求过于频繁有临时封IP的风险。

## 依赖

*   `requests`
*   `beautifulsoup4`
```
