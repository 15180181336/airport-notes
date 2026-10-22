"""校验公开目录，生成 GitHub 内容，并导出明确列出的公开文件。"""

import argparse
import html
import json
import math
import re
import sys
import zipfile
from datetime import date
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
STATUS = {"pending": "待核验线索", "documented": "有来源资料", "paused": "暂停入口"}
KINDS = {"owner": "维护者提供", "screenshot": "截图记录", "official": "厂商说明", "community": "第三方公开资料"}
BILLING = {"monthly": "月付", "quarterly": "季付", "yearly": "年付", "one_time": "一次购买", "unknown": "周期待核实"}
QUOTA = {"monthly": "每月", "total": "总量", "unknown": "周期待核实"}
EXPERIENCE_TEXT = ("date", "period", "region", "isp", "access", "plan", "client", "method")
EXPERIENCE_LIST = ("observations", "pros", "cons", "limitations", "evidence")
FIXED_FILES = (
    "CONTRIBUTING.md", ".gitignore", "docs/methodology.md", "docs/disclosure.md",
    "docs/maintaining.md", "templates/experience.json", "evidence/README.md",
    "assets/cover.svg", ".github/ISSUE_TEMPLATE/experience.yml",
    ".github/ISSUE_TEMPLATE/correction.yml", ".github/ISSUE_TEMPLATE/provider.yml",
    "data/catalog.json", "tools/build.py", "tests/test_build.py", "docs/choosing.md",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def keys(value, expected, label):
    require(isinstance(value, dict) and set(value) == set(expected), f"{label} 字段不匹配")


def text(value, label):
    require(isinstance(value, str) and bool(value.strip()), f"{label} 不能为空")
    require("\n" not in value and "\r" not in value, f"{label} 请使用单行文字")


def day(value, label, optional=False):
    if value is None and optional:
        return
    require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value), f"{label} 日期格式错误")
    date.fromisoformat(value)


def url(value, label, optional=False):
    if value is None and optional:
        return
    require(isinstance(value, str), f"{label} 必须是 URL")
    parsed = urlsplit(value)
    require(parsed.scheme == "https" and parsed.hostname and not parsed.username
            and not parsed.password and not re.search(r"[\s<>\"\\]", value),
            f"{label} 必须是无账号密码的 HTTPS 地址")


def local_file(root, relative):
    require(isinstance(relative, str) and "\\" not in relative, "公开证据路径请使用正斜线")
    require(relative.startswith("evidence/") and ".." not in Path(relative).parts, "证据必须在 evidence 内")
    path = root / relative
    require(path.resolve().is_relative_to(root.resolve()) and path.is_file(), f"证据不存在或越界：{relative}")
    require(not any(p.is_symlink() for p in [path, *path.parents] if p != root.parent), "不发布符号链接证据")
    require(path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".txt", ".md", ".json"},
            f"不支持的证据格式：{relative}")
    return path


def validate(data, root=ROOT):
    keys(data, ("project", "providers"), "目录")
    keys(data["project"], ("name", "updated_on", "description"), "项目")
    text(data["project"]["name"], "项目名")
    text(data["project"]["description"], "项目介绍")
    day(data["project"]["updated_on"], "整理日期")
    require(isinstance(data["providers"], list) and data["providers"], "厂商目录不能为空")
    seen = set()
    for p in data["providers"]:
        keys(p, ("id", "name", "categories", "official_url", "referral_url", "referral_confirmed",
                 "status", "summary", "facts", "unknowns", "sources", "experiences", "offers"), "厂商")
        text(p["id"], "厂商 ID")
        require(re.fullmatch(r"[a-z][a-z0-9-]*", p["id"]) and p["id"] not in seen, "厂商 ID 不合法或重复")
        seen.add(p["id"])
        for name in ("name", "summary"):
            text(p[name], name)
        require(p["status"] in STATUS, "未知收录状态")
        url(p["official_url"], "网站入口", optional=True)
        url(p["referral_url"], "邀请地址", optional=True)
        require(type(p["referral_confirmed"]) is bool, "邀请确认标记必须是布尔值")
        require(not p["referral_confirmed"] or p["referral_url"], "已确认邀请缺少地址")
        for name in ("categories", "unknowns", "sources", "facts", "experiences", "offers"):
            require(isinstance(p[name], list), f"{name} 必须是列表")
        require(p["categories"] and p["sources"], "厂商必须有资料分类和来源")
        for value in p["categories"] + p["unknowns"]:
            text(value, "分类或待核实项")
        source_ids = set()
        for source in p["sources"]:
            keys(source, ("id", "label", "kind", "observed_on", "recorded_on", "url", "note"), "来源")
            for name in ("id", "label", "note"):
                text(source[name], f"来源 {name}")
            require(source["id"] not in source_ids, "来源 ID 重复")
            source_ids.add(source["id"])
            require(source["kind"] in KINDS, "未知来源类型")
            day(source["observed_on"], "来源观察日期", optional=True)
            day(source["recorded_on"], "来源整理日期")
            url(source["url"], "来源链接", optional=True)
            require(source["kind"] not in ("official", "community") or source["url"], "公开资料必须有来源链接")
        for offer in p["offers"]:
            keys(offer, ("label", "total_cny", "billing", "quota_gb", "quota_period",
                         "source", "observed_on", "note"), "参考套餐")
            text(offer["label"], "套餐名")
            text(offer["note"], "套餐说明")
            require(offer["billing"] in BILLING and offer["quota_period"] in QUOTA, "套餐周期不合法")
            for field in ("total_cny", "quota_gb"):
                value = offer[field]
                require(value is None or (type(value) in (int, float) and math.isfinite(value) and value > 0),
                        f"套餐 {field} 应为正数或 null")
            require(offer["source"] in source_ids, "套餐引用了不存在的来源")
            day(offer["observed_on"], "套餐摘录日期")
        for fact in p["facts"]:
            keys(fact, ("text", "source"), "资料说明")
            text(fact["text"], "资料说明")
            require(fact["source"] in source_ids, "资料说明引用了不存在的来源")
        for item in p["experiences"]:
            keys(item, EXPERIENCE_TEXT + EXPERIENCE_LIST, "体验记录")
            for name in EXPERIENCE_TEXT:
                text(item[name], f"体验 {name}")
            day(item["date"], "体验日期")
            for name in EXPERIENCE_LIST:
                require(isinstance(item[name], list), f"体验 {name} 必须是列表")
                for value in item[name]:
                    text(value, f"体验 {name}")
            require(item["observations"] and item["limitations"] and item["evidence"], "正式体验需含观察、局限和证据")
            for value in item["evidence"]:
                local_file(root, value)
    return data


def md(value):
    """数据按文字输出，避免把资料中的 HTML 或 Markdown 变成页面结构。"""
    value = html.escape(str(value), quote=False)
    return re.sub(r"([\\`*_\[\]{}|])", r"\\\1", value)


def link(label, target):
    # 保留 #/register?code=...，不重新拼接邀请参数。
    safe = quote(target, safe="/:#?=&%+@~!$,;-'")
    return f"[{md(label)}]({safe})"


def bullets(items):
    return "\n".join(f"- {md(value)}" for value in items) or "暂无记录。"


def entry_link(p):
    if p["status"] == "paused":
        return "入口已暂停"
    if p["official_url"]:
        return link("网站入口", p["official_url"])
    return "官网待确认"


def invite(p):
    if p["status"] == "paused":
        return "邀请入口已暂停。"
    if p["referral_confirmed"] and p["referral_url"]:
        return link("邀请注册（购买后维护者可能获得佣金）", p["referral_url"])
    return "暂无经维护者确认的邀请链接。"


def ordered(providers):
    return sorted(providers, key=lambda p: ({"documented": 0, "pending": 1, "paused": 2}[p["status"]], p["id"]))


def offer_price(offer):
    if offer["total_cny"] is None:
        return "金额待补"
    return f"¥{offer['total_cny']:g} / {BILLING[offer['billing']]}"


def offer_quota(offer):
    if offer["quota_gb"] is None:
        return "流量额度待核实"
    return f"{offer['quota_gb']:g} GB（{QUOTA[offer['quota_period']]}）"


def source_for(p, source_id):
    return next(source for source in p["sources"] if source["id"] == source_id)


def offer_source(p, offer):
    source = source_for(p, offer["source"])
    kind = KINDS[source["kind"]]
    return f"{kind}，摘录 {offer['observed_on']}"


def freshest(p):
    return max(source["recorded_on"] for source in p["sources"])


def readme(data):
    project, providers = data["project"], data["providers"]
    entries = ordered(providers)
    lines = [
        "<!-- 自动生成：python tools/build.py build -->",
        "![机场手记：厂商目录、来源索引、使用反馈](assets/cover.svg)",
        f"# {md(project['name'])} · 机场黄页",
        "查机场、对照套餐、找到原始资料。整理 VPN 与代理订阅服务的官网、公开报价、产品说明和使用反馈。",
        f"**整理日期：{project['updated_on']}** · {len(providers)} 家厂商 · "
        f"{sum(bool(p['offers']) for p in providers)} 家有参考套餐",
        "[厂商速查](#厂商速查) · [参考套餐](#参考套餐) · [按需求找](#按需求找) · "
        "[怎么选](docs/choosing.md) · [补充收录](CONTRIBUTING.md)",
        "部分链接为维护者的邀请链接，符合条件的购买可能产生佣金。"
        "[推广关系与来源说明](docs/disclosure.md)。收录不等于质量推荐，官网宣传和第三方评价均注明出处。",
        "## 厂商速查",
        "点击厂商名查看资料、入口、问题线索和原文。按资料状态及 ID 排列，顺序与佣金无关。",
        "| 厂商 | 信息要点 | 可追溯资料 | 入口 |\n| --- | --- | --- | --- |",
    ]
    for p in entries:
        categories = " / ".join(p["categories"])
        lines.append(f"| {link(p['name'], 'reviews/' + p['id'] + '.md')} | {md(categories)} | "
                     f"{STATUS[p['status']]} · {freshest(p)} | {entry_link(p)} |")
    lines += [
        "## 参考套餐",
        "以下是公开来源的报价摘录。**年付显示一次付款总额，流量重置周期另列。第三方报价尚未由本项目核对当前售价。**"
        "没有价格的厂商仍保留在黄页，付款前以结算页为准。",
        "| 厂商 / 套餐 | 付款总额 / 周期 | 流量 | 出处与摘录日期 |\n| --- | --- | --- | --- |",
    ]
    for p in entries:
        for offer in p["offers"]:
            source = source_for(p, offer["source"])
            origin = KINDS[source["kind"]]
            if source["url"]:
                origin = link(origin, source["url"])
            lines.append(f"| {link(p['name'], 'reviews/' + p['id'] + '.md')} · {md(offer['label'])} | "
                         f"{md(offer_price(offer))} | {md(offer_quota(offer))} | "
                         f"{origin} · {offer['observed_on']} |")
    lines += [
        "## 按需求找",
        "标签是产品信息的检索入口；家宽、专线等为相应来源的描述，实际表现请结合原文和自己的网络判断。",
    ]
    for category in sorted({c for p in providers for c in p["categories"]}):
        names = " · ".join(link(p["name"], f"reviews/{p['id']}.md") for p in entries if category in p["categories"])
        lines.append(f"**{md(category)}**：{names}")
    lines += [
        "## 最近补充",
        "- 边界云：补入官网年付、季付及按量套餐，区分一次付款额和每月流量。\n"
        "- 雪山：补入品牌公告中的直连定位与历史波动说明。\n"
        "- 苏菲：补入住宅代理定位和备用入口公示；套餐页价格仍待补。\n"
        "- 第三方线索：保留来源报价和链接核查结果，方便继续了解。",
        "## 参与维护",
        "可以提交官网入口、价格变动、公开评测或亲身体验，无需先逐家购买。"
        "资料说明谁说的、何时看到、原文在哪；不知道的内容留空。",
        "[如何选套餐](docs/choosing.md) · [资料整理方法](docs/methodology.md) · "
        "[提交资料](CONTRIBUTING.md) · [维护命令](docs/maintaining.md)",
        "可直接复用 [公开目录数据](data/catalog.json)，或运行工具生成同样的首页与厂商档案。"
        "项目不提供节点或订阅配置。",
    ]
    return "\n\n".join(lines).replace(" |\n\n| ", " |\n| ") + "\n"


def provider_page(p):
    lines = [
        "<!-- 自动生成：请编辑 data/catalog.json -->",
        link("返回机场黄页", "../README.md"),
        f"# {md(p['name'])}",
        md(p["summary"]),
        f"**{STATUS[p['status']]}** · 最近整理：{freshest(p)} · {md(' / '.join(p['categories']))}",
        "## 网站与资料",
        entry_link(p),
        invite(p),
        "## 参考套餐",
    ]
    if p["offers"]:
        lines.append("| 套餐 | 付款总额 / 周期 | 流量 | 出处 |\n| --- | --- | --- | --- |")
        for offer in p["offers"]:
            lines.append(f"| {md(offer['label'])} | {md(offer_price(offer))} | {md(offer_quota(offer))} | "
                         f"{md(offer_source(p, offer))} |")
        for offer in p["offers"]:
            lines.append(f"- **{md(offer['label'])}**：{md(offer['note'])}")
        lines.append("报价是来源记录，付款前请核对结算页。按量总额和周期流量不可直接按同一单价比较。")
    else:
        lines.append("本次没有获得足够明确的公开价格，保留空缺。")
    lines.append("## 产品资料与问题线索")
    labels = {s["id"]: s["label"] for s in p["sources"]}
    lines += [f"- {md(f['text'])}（{md(labels[f['source']])}）" for f in p["facts"]]
    if not p["facts"]:
        lines.append("暂只有公开目录中的厂商线索。")
    lines += ["## 还需要核对", bullets(p["unknowns"]), "## 使用反馈"]
    if not p["experiences"]:
        lines.append("尚未收录使用记录。你可以先从原始资料了解产品，也可以提交自己的体验。")
    for item in sorted(p["experiences"], key=lambda e: e["date"], reverse=True):
        lines += [
            f"### {item['date']} · {md(item['period'])}",
            f"环境：{md(item['region'])} / {md(item['isp'])} / {md(item['access'])}。"
            f"套餐：{md(item['plan'])}。客户端：{md(item['client'])}。",
            f"方法：{md(item['method'])}",
            "**观察**\n\n" + bullets(item["observations"]),
            "**优点**\n\n" + bullets(item["pros"]),
            "**问题**\n\n" + bullets(item["cons"]),
            "**局限**\n\n" + bullets(item["limitations"]),
            "证据：" + " · ".join(link(Path(path).name, "../" + path) for path in item["evidence"]),
        ]
    lines.append("## 原始来源")
    for s in p["sources"]:
        enabled = not (s["url"] == p["referral_url"] and (p["status"] == "paused" or not p["referral_confirmed"]))
        title = link(s["label"], s["url"]) if s["url"] and enabled else md(s["label"])
        lines.append(f"- {title}。{KINDS[s['kind']]}；观察：{s['observed_on'] or '未知'}；"
                     f"整理：{s['recorded_on']}。{md(s['note'])}")
    lines.append("[补充与更正](../CONTRIBUTING.md) · [来源方法](../docs/methodology.md) · [推广披露](../docs/disclosure.md)")
    return "\n\n".join(lines).replace(" |\n\n| ", " |\n| ") + "\n"


def outputs(data):
    return {"README.md": readme(data), **{f"reviews/{p['id']}.md": provider_page(p) for p in data["providers"]}}


def package_files(data):
    evidence = {path for p in data["providers"] for e in p["experiences"] for path in e["evidence"]}
    return sorted(set(FIXED_FILES) | set(outputs(data)) | evidence)


def check_links(root, files):
    for relative in files:
        path = root / relative
        require(path.is_file(), f"缺少公开文件：{relative}")
        require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()), f"文件路径异常：{relative}")
        if path.suffix != ".md":
            continue
        for target in re.findall(r"!?\[[^\]]*\]\(([^)\s]+)\)", path.read_text(encoding="utf-8")):
            if urlsplit(target).scheme or target.startswith("#"):
                continue
            dest = (path.parent / unquote(target.split("#", 1)[0])).resolve()
            require(dest.is_relative_to(root.resolve()) and dest.is_file(), f"{relative} 本地链接无效：{target}")


def run(command, root=ROOT):
    data = validate(json.loads((root / "data/catalog.json").read_text(encoding="utf-8")), root)
    generated = outputs(data)
    if command == "build":
        for relative, body in generated.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8", newline="\n")
    else:
        for relative, body in generated.items():
            path = root / relative
            require(path.is_file() and path.read_text(encoding="utf-8") == body, f"请先重新生成：{relative}")
    files = package_files(data)
    check_links(root, files)
    if command == "export":
        destination = root.parent / "artifacts" / "airport-notes-public.zip"
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for relative in files:
                archive.write(root / relative, relative)
        print(f"已导出 {len(files)} 个公开文件：{destination}")
    else:
        print(f"{command} 完成：{len(data['providers'])} 家厂商，{len(generated)} 个生成文件，公开链接检查通过。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "check", "export"))
    args = parser.parse_args()
    try:
        run(args.command)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"失败：{error}", file=sys.stderr)
        sys.exit(1)
