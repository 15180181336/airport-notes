# 维护与生成

本项目使用 Python 3.11 或更新版本，只用标准库，无需安装依赖。命令在仓库根目录运行。

```powershell
python tools/build.py build
python tools/build.py check
python -m unittest discover -s tests -v
python tools/build.py export
```

`build` 从 `data/catalog.json` 生成 README 和厂商档案；不要直接编辑生成文件。`check` 检查数据规则、生成结果是否同步、受管理 Markdown 的本地链接是否存在。`export` 先检查，再将公开文件打包到仓库旁的 `artifacts/airport-notes-public.zip`。

工具不登录厂商后台，不注册账户，不购买套餐，不发送消息，不监测节点，不采集访问者信息，也不向 GitHub 上传文件。链接存在性检查不代表外部网站可访问，邀请归因必须通过真实业务记录核验。

## 目录

| 目录或文件 | 用途 |
| --- | --- |
| `data/catalog.json` | 公开内容的唯一数据源 |
| `README.md` | GitHub 首页，自动生成 |
| `reviews/` | 厂商档案，自动生成 |
| `evidence/` | 准备公开的脱敏证据 |
| `templates/experience.json` | 可选体验记录字段模板 |
| `docs/` | 方法、披露和维护说明 |
| `tools/build.py` | 校验、生成与打包 |

## 新增或更新厂商

1. 在 `providers` 中增加唯一 ASCII 小写 ID，填写名称、官方入口、简介与 `categories` 标签数组。标签仅作资料分类。
2. 在 `sources` 中记录出处；`kind` 支持 `official`、`community`、`screenshot` 和 `owner`。保留来源链接、观察日期、整理日期及必要备注，未知观察日期用 `null`。
3. 让 `facts` 的每项说明通过 `source` 引用本厂商的一条来源；把未知、冲突或过期的信息写入 `unknowns`。
4. 将维护者提供的完整邀请地址填入 referral_url，核对原文后设置 referral_confirmed 为 true。首页、套餐表和详情页的注册入口统一使用这个地址；无邀请链接时显示“邀请链接待补”，不回退到普通官网。此标记不表示订单归因或佣金到账已验证。使用体验放在可选的 `experiences` 中，没有时用空数组。
5. 更新 `project.updated_on`，执行生成与检查。该日期表示内容整理日期，不等于实测或外部信息更新日期。

按资料情况选择 `status`：`pending` 为待核验，`documented` 为有来源资料，`paused` 为暂停入口。状态不以体验记录数量为门槛；有来源资料不等于当前价格、稳定性或提现已获验证。暂停时保留历史资料，邀请链接不输出为可点击推广入口。

## 参考套餐字段

每家厂商的 offers 数组保存报价摘录：label 为套餐名，total_cny 为该周期需要支付的总金额；billing 支持 monthly、quarterly、yearly、one_time 和 unknown。年付填写整年总金额，不能用折算月费代替。

quota_gb 为流量额度，quota_period 分为 monthly（每月重置）、total（总额）与 unknown（周期未明确）。未知数字使用 null，不用 0 或无穷大表示不限量。source 必须引用该厂商已有的来源，observed_on 是报价摘录日期，note 保留使用条件和未核实事项。第三方资料的摘录日期不能当作报价生效日期。

整理日期更新不表示所有来源已重新核查；各条资料仍显示自己的观察和整理日期。

## 可选体验记录

`experiences` 的字段包括 `date`、`period`、`region`、`isp`、`access`、`plan`、`client`、`method`、`observations`、`pros`、`cons`、`limitations`、`evidence`。文本列表使用 JSON 数组，证据使用仓库内以 `evidence/` 开头的文件路径。填写真实观察，不把模板空值当作完整记录。

同一厂商的记录按观察日期倒序展示。记录存在不意味着厂商获得认证；结论应和条件、缺点、日期一起阅读。第三方评测作为 `community` 来源引用，不能改写成维护者自己的体验。

## 准备发布

项目名：`机场手记`。建议仓库名：`airport-notes`。建议描述：`机场与 VPN / 代理订阅黄页：整理厂商入口、套餐资料、公开评测和社区反馈，标注来源与更新日期。`

首批内容完成后，可在自己的 GitHub 账户创建 Public 空仓库，再从本地上传。不要把本目录之外的运营文件上传。首发不需要 GitHub Pages；未来网站沿用这里的数据，但应另行评估商业托管。

GitHub 不保证搜索引擎收录、排名或流量。描述和 Topics 只填写实际相关词。不要刷 Star、批量建同质仓库或到其他项目的 Issue 留广告。

项目以实用资料与工具为主体，相关推广需遵守 [GitHub 广告规则](https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies#10-advertising-on-github)。以促成商业交易为主要目的的网站还需考虑 [GitHub Pages 使用限制](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)。
